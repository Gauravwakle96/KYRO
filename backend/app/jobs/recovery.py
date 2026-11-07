from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import settings
from app.core.errors import ServiceError
from app.core.security import redact
from app.database import Job, now

SAFE_KINDS = frozenset({"ingest", "fixture", "analyze", "scan", "enrich"})
TRANSIENT_ERRORS = (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.RemoteProtocolError)


def transient(error: Exception) -> bool:
    if isinstance(error, ServiceError):
        return error.retryable
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {408, 429, 500, 502, 503, 504}
    return isinstance(error, TRANSIENT_ERRORS)


def state(job: Job) -> dict:
    info = job.payload.get("automatic_recovery", {})
    if not isinstance(info, dict):
        return {"attempt": settings.job_max_attempts}
    attempt = info.get("attempt", 0)
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 0:
        return {"attempt": settings.job_max_attempts}
    return {**info, "attempt": attempt}


def due(job: Job) -> bool:
    stamp = state(job).get("not_before")
    if not stamp:
        return True
    try:
        return datetime.fromisoformat(stamp) <= datetime.now(UTC)
    except (TypeError, ValueError):
        # Invalid internal scheduling data must produce an explicit error, not a stuck queue.
        return True


def begin_attempt(job: Job):
    info = state(job)
    if info["attempt"] >= settings.job_max_attempts:
        raise ValueError("Automatic recovery attempt limit reached; inspect the original failure")
    info = {**info, "attempt": info["attempt"] + 1, "max_attempts": settings.job_max_attempts}
    info.pop("not_before", None)
    job.payload = {**job.payload, "automatic_recovery": info}


def schedule(job: Job, error: Exception, *, interrupted=False) -> bool:
    if not settings.automatic_recovery or job.kind not in SAFE_KINDS or job.cancel_requested:
        return False
    info = state(job)
    attempt = max(info["attempt"], 1)
    if attempt >= settings.job_max_attempts or not (interrupted or transient(error)):
        return False
    if job.started_at and (datetime.now(UTC) - datetime.fromisoformat(job.started_at)).total_seconds() >= settings.job_timeout:
        return False
    delay = min(settings.job_retry_delay * 2 ** (attempt - 1), 60)
    if isinstance(error, ServiceError) and error.retry_after is not None:
        delay = min(max(delay, error.retry_after), 60)
    stamp = now()
    history = info.get("history", [])
    if not isinstance(history, list):
        return False
    reason = redact(str(error))[:1000]
    action = {"at": stamp, "attempt": attempt, "reason": reason, "recovery": "resume_read_operation" if interrupted else "retry_transient_failure", "delay_seconds": delay}
    not_before = (datetime.now(UTC) + timedelta(seconds=delay)).isoformat()
    job.payload = {**job.payload, "automatic_recovery": {**info, "attempt": attempt, "max_attempts": settings.job_max_attempts, "not_before": not_before, "history": [*history, action]}}
    job.events = [*job.events, {"at": stamp, "message": f"Automatic recovery scheduled: attempt {attempt + 1}/{settings.job_max_attempts} in {delay}s", "detail": action}][-500:]
    job.status, job.error, job.ended_at = "PENDING", None, None
    return True
