import json
import logging
import shutil
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agents.models import validate_local_endpoint
from app.api.routes import router
from app.core.config import settings
from app.jobs import worker
from app.services.handlers import register

logger = logging.getLogger("kyro")
RATE_LOCK = threading.Lock()
REQUESTS: dict[str, deque] = defaultdict(deque)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "migrations"))
    command.upgrade(config, "head")
    if settings.workspace_volume:
        target = settings.data_dir / "rules"
        target.mkdir(exist_ok=True)
        shutil.copyfile(Path(__file__).resolve().parents[1] / "rules" / "security.yml", target / "security.yml")
    saved = settings.data_dir / "model-settings.json"
    if saved.exists():
        data = json.loads(saved.read_text(encoding="utf-8"))
        validate_local_endpoint(data["endpoint"])
        settings.local_model_url, settings.local_model = data["endpoint"], data["model"]
        if settings.cloud_authorized:
            settings.local_only = data["local_only"]
        settings.model_routing = data.get("routing", "local")
    register()
    if settings.enable_worker:
        worker.start()
    yield
    if settings.enable_worker:
        worker.stop()


app = FastAPI(title="KYRO", description="Think. Build. Secure. Evidence-backed software remediation.", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Content-Type", "X-CSRF-Token", "Last-Event-ID"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[x.strip() for x in settings.allowed_hosts.split(",")])


@app.middleware("http")
async def security_boundary(request: Request, call_next):
    origin = request.headers.get("origin")
    if origin and origin not in settings.origins:
        return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
    identity = request.client.host if request.client else "unknown"
    bucket = "auth" if request.url.path in {"/api/auth/login", "/api/auth/register"} else "api" if request.url.path.startswith("/api/") else "static"
    limit = {"auth": 15, "api": 300, "static": 3000}[bucket]
    key = identity + ":" + bucket
    instant = time.monotonic()
    with RATE_LOCK:
        if len(REQUESTS) > 10000:
            for old in list(REQUESTS):
                if not REQUESTS[old] or REQUESTS[old][-1] < instant - 60:
                    del REQUESTS[old]
        history = REQUESTS[key]
        while history and history[0] < instant - 60:
            history.popleft()
        if len(history) >= limit:
            return JSONResponse({"detail": "Request limit reached; retry in a minute"}, status_code=429, headers={"Retry-After": "60"})
        history.append(instant)
    if request.method in {"POST", "PUT", "PATCH"}:
        payload = bytearray()
        async for chunk in request.stream():
            payload.extend(chunk)
            if len(payload) > 1_000_000:
                return JSONResponse({"detail": "Request exceeds 1 MB limit"}, status_code=413)
        request._body = bytes(payload)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"
    if request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(ValueError)
async def invalid_input(request: Request, error: ValueError):
    return JSONResponse({"detail": str(error)[:300]}, status_code=400)


@app.exception_handler(RuntimeError)
async def integration_error(request: Request, error: RuntimeError):
    from app.core.security import redact
    return JSONResponse({"detail": redact(str(error))[:500]}, status_code=409)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, error: Exception):
    logger.error("Unexpected request error: %s", type(error).__name__)
    return JSONResponse({"detail": "Unexpected error; inspect server diagnostics"}, status_code=500)


app.include_router(router)
DOCS_ASSETS = Path(__file__).resolve().parents[1] / "static" / "api-docs"
app.mount("/api/docs-static", StaticFiles(directory=DOCS_ASSETS), name="api-docs-static")


@app.get("/docs", include_in_schema=False)
def api_documentation():
    return HTMLResponse('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>KYRO API reference</title><link rel="stylesheet" href="/api/docs-static/swagger-ui.css"></head><body><p>KYRO API reference. Sign in to the workspace before trying protected operations.</p><div id="swagger-ui"></div><script src="/api/docs-static/swagger-ui-bundle.js"></script><script src="/api/docs-static/initialize.js"></script></body></html>')


FRONTEND = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if FRONTEND.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND / "assets"), name="assets")
    if (FRONTEND / "licenses").exists():
        app.mount("/licenses", StaticFiles(directory=FRONTEND / "licenses"), name="font-licenses")
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"detail": "API endpoint not found"}, status_code=404)
        return FileResponse(FRONTEND / "index.html")
