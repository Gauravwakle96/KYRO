import ipaddress
import json
import socket
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import digest, redact
from app.database import ModelUsage


def validate_local_endpoint(url: str):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Use an HTTP model endpoint without credentials, query or fragment")
    if parsed.hostname == "host.docker.internal":
        # Docker's explicit host gateway is local to the deployed server.
        return
    try:
        addresses = {entry[4][0] for entry in socket.getaddrinfo(parsed.hostname, parsed.port or 80)}
    except OSError as error:
        raise ValueError("Local endpoint cannot be resolved") from error
    if not addresses or not all(ipaddress.ip_address(address).is_loopback for address in addresses):
        raise ValueError("LOCAL_ONLY blocks external model endpoints; use loopback or Docker host gateway")


def model_health() -> dict:
    try:
        validate_local_endpoint(settings.local_model_url)
        with httpx.Client(timeout=8, trust_env=False, follow_redirects=False) as client:
            response = client.get(settings.local_model_url.rstrip("/") + "/models")
            response.raise_for_status()
            available = [m["id"] for m in response.json().get("data", [])]
        return {"available": True, "models": available, "selected": settings.local_model, "selected_available": settings.local_model in available, "local_only": settings.local_only, "endpoint": settings.local_model_url, "cloud_authorized": settings.cloud_authorized}
    except Exception as error:
        return {"available": False, "error": str(error)[:300], "local_only": settings.local_only, "endpoint": settings.local_model_url, "selected": settings.local_model, "cloud_authorized": settings.cloud_authorized}


def select_provider(finding: dict) -> str:
    if settings.model_routing == "local" or settings.local_only:
        return "local"
    if settings.model_routing == "cloud":
        if not settings.cloud_authorized:
            raise ValueError("Cloud remediation requires operator authorization")
        return "cloud"
    complex_task = not finding.get("package_name") or finding.get("severity") in {"HIGH", "CRITICAL"}
    return "cloud" if settings.cloud_authorized and complex_task else "local"


def complete(db: Session, user_id: str, messages: list[dict], remediation_id: str | None = None, *, provider="local", max_tokens: int | None = None, cache=False, schema: dict | None = None) -> dict:
    if provider != "local":
        if settings.local_only or not settings.cloud_authorized:
            raise ValueError("Cloud inference is blocked by LOCAL_ONLY or missing cost authorization")
        url, model = settings.cloud_model_url, settings.cloud_model
        key = settings.cloud_api_key or (Path(settings.cloud_api_key_path).read_text(encoding="utf-8").strip() if settings.cloud_api_key_path else "")
        if not key:
            raise ValueError("Cloud provider is not configured on the backend")
        requests = list(db.scalars(select(ModelUsage).where(ModelUsage.provider == "cloud")))
        if len(requests) >= settings.cloud_request_limit:
            raise ValueError("Authorized cloud request limit reached; local-only remains available")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Cloud model endpoint must use HTTPS")
    else:
        url, model, key = settings.local_model_url, settings.local_model, ""
        validate_local_endpoint(url)
    if len(json.dumps(messages)) > 48000:
        raise ValueError("Model context exceeds 48,000 character budget")
    output_limit = min(max_tokens or settings.max_model_tokens, settings.max_model_tokens)
    if remediation_id:
        records = list(db.scalars(select(ModelUsage).where(ModelUsage.remediation_id == remediation_id)))
        # Use actual provider tokens when available, and reserve a conservative byte upper bound before sending.
        consumed = sum((r.input_tokens or 0) + (r.output_tokens or 0) for r in records)
        if any(r.input_tokens is None or r.output_tokens is None for r in records):
            consumed += sum(settings.max_model_tokens for r in records if r.input_tokens is None or r.output_tokens is None)
        reserved = len(json.dumps(messages).encode()) + output_limit
        if consumed + reserved > settings.agent_token_budget:
            raise ValueError("Remediation token budget exceeded; narrow context or raise the server budget")
    identity = digest(json.dumps([user_id, remediation_id, provider, url, settings.cloud_protocol if provider != "local" else "chat", model, messages, output_limit, schema], sort_keys=True))
    cache_dir = settings.data_dir / "model-cache"
    cache_dir.mkdir(exist_ok=True)
    cache_path = cache_dir / (identity + ".json")
    if cache and cache_path.exists():
        return json.loads(cache_path.read_text(encoding="utf-8"))
    start = time.monotonic()
    usage = ModelUsage(user_id=user_id, remediation_id=remediation_id, provider=provider, model=model, input_tokens=None, output_tokens=None, duration_seconds=0, estimated_cost=0.0 if provider == "local" else None, status="FAILED")
    try:
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        with httpx.Client(timeout=settings.model_timeout, trust_env=False, follow_redirects=False) as client:
            response_format = {"type": "json_schema", "json_schema": {"name": "kyro_response", "schema": schema}} if schema else {"type": "json_object"}
            if provider != "local" and settings.cloud_protocol == "responses":
                payload = {"model": model, "input": messages, "max_output_tokens": output_limit, "stream": False, "text": {"format": {"type": "json_schema", "name": "kyro_response", "schema": schema} if schema else {"type": "json_object"}}}
                response = client.post(url.rstrip("/") + "/responses", headers={**headers, "User-Agent": "KYRO/0.1"}, json=payload)
            else:
                response = client.post(url.rstrip("/") + "/chat/completions", headers=headers, json={"model": model, "messages": messages, "max_tokens": output_limit, "temperature": 0.1, "stream": False, "response_format": response_format})
            if response.status_code >= 400:
                try:
                    error = response.json().get("error", "")
                    detail = error.get("message", "") if isinstance(error, dict) else str(error)
                except ValueError:
                    detail = ""
                raise RuntimeError(f"Model provider returned HTTP {response.status_code}: {redact(detail.replace(key, '[REDACTED]') if key else detail)[:300]}")
            if len(response.content) > 500000:
                raise ValueError("Model output exceeds response limit")
            data = response.json()
        tokens = data.get("usage", {})
        usage.input_tokens, usage.output_tokens = tokens.get("prompt_tokens", tokens.get("input_tokens")), tokens.get("completion_tokens", tokens.get("output_tokens"))
        if provider != "local" and usage.input_tokens is not None and usage.output_tokens is not None and settings.cloud_input_price_per_million is not None and settings.cloud_output_price_per_million is not None:
            usage.estimated_cost = (usage.input_tokens * settings.cloud_input_price_per_million + usage.output_tokens * settings.cloud_output_price_per_million) / 1_000_000
        if provider != "local" and settings.cloud_protocol == "responses":
            if data.get("status") != "completed":
                raise ValueError("Cloud response is incomplete; it cannot be used as a patch")
            raw = "".join(content["text"] for output in data.get("output", []) if output.get("type") == "message" for content in output.get("content", []) if content.get("type") == "output_text")
        else:
            raw = data["choices"][0]["message"]["content"]
        raw = raw.split("</think>")[-1].strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0]
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError("Model response must be a JSON object")
        usage.status = "SUCCEEDED"
        if cache:
            cache_path.write_text(json.dumps(parsed), encoding="utf-8")
        return parsed
    finally:
        usage.duration_seconds = round(time.monotonic() - start, 3)
        db.add(usage)
        db.commit()
