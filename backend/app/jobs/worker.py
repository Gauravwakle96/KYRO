import threading
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import settings
from app.core.security import redact
from app.database import Audit, Job, Remediation, Repository, ScanRun, SessionLocal, now
from app.jobs import recovery

HANDLERS: dict[str, Callable] = {}
STOP = threading.Event()
WORKER: threading.Thread | None = None


class Cancelled(Exception):
    pass


def cancelled(job_id: str) -> bool:
    if STOP.is_set():
        return True
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or job.cancel_requested:
            return True
        if job.started_at and (datetime.now(UTC) - datetime.fromisoformat(job.started_at)).total_seconds() > settings.job_timeout:
            return True
        return False


def progress(job_id: str, message: str, detail: dict | None = None):
    if cancelled(job_id):
        raise Cancelled("Job cancelled")
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job:
            job.events = [*job.events, {"at": now(), "message": redact(message), "detail": detail or {}}][-500:]
            db.commit()


def run_job(job_id: str):
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None or job.status != "PENDING":
            return
        job.status, job.started_at = "RUNNING", job.started_at or now()
        db.commit()
        try:
            recovery.begin_attempt(job)
            db.commit()
            progress(job.id, f"Started {job.kind}")
            result = HANDLERS[job.kind](job)
            db.refresh(job)
            if cancelled(job.id):
                raise Cancelled("Job cancelled")
            job.status, job.error, job.result = "SUCCEEDED", None, result
            outcome = result.get("state") or result.get("status") if isinstance(result, dict) else None
            if outcome == "FAILED":
                job.status, job.error = "FAILED", "Operation failed its quality gates; inspect recorded execution or verification evidence"
            elif outcome in {"INCONCLUSIVE", "PARTIALLY_VERIFIED"}:
                job.status, job.error = "INCONCLUSIVE", "Operation has incomplete evidence; inspect its report before retrying"
        except Cancelled:
            db.refresh(job)
            if STOP.is_set() and not job.cancel_requested and recovery.schedule(job, RuntimeError("Worker shutdown interrupted a read operation"), interrupted=True):
                db.add(Audit(user_id=job.user_id, action="job.recovery_scheduled", resource_id=job.id, detail=job.payload["automatic_recovery"]))
            else:
                job.status, job.error = "CANCELLED", "Cancelled by user, execution deadline or application shutdown"
        except Exception as error:
            db.refresh(job)
            job.status, job.error = "FAILED", redact(str(error))[:2000]
            job.events = [*job.events, {"at": now(), "message": "Operation failed", "detail": {"error_type": type(error).__name__, "reason": job.error}}][-500:]
            if recovery.schedule(job, error):
                db.add(Audit(user_id=job.user_id, action="job.recovery_scheduled", resource_id=job.id, detail=job.payload["automatic_recovery"]))
        if job.kind in {"plan", "execute", "verify"} and job.status in {"FAILED", "CANCELLED"}:
            task = db.get(Remediation, job.resource_id)
            if task:
                task.state = "CANCELLED" if job.status == "CANCELLED" else "FAILED"
        if job.kind in {"ingest", "fixture", "analyze"} and job.status in {"FAILED", "CANCELLED"}:
            repo = db.get(Repository, job.resource_id)
            if repo:
                repo.status = job.status
        job.ended_at = None if job.status == "PENDING" else now()
        db.commit()


def recover_interrupted_jobs():
    # Resume only bounded read operations. Edits, tests, verification and writes retain review.
    with SessionLocal() as db:
        for job in db.scalars(select(Job).where(Job.status == "RUNNING")):
            if recovery.schedule(job, RuntimeError("Worker interrupted during a read operation"), interrupted=True):
                db.add(Audit(user_id=job.user_id, action="job.recovery_scheduled", resource_id=job.id, detail=job.payload["automatic_recovery"]))
            else:
                job.status, job.error, job.ended_at = "FAILED", "Worker interrupted; inspect checkpoint and explicitly retry", now()
                if job.kind in {"ingest", "fixture", "analyze"}:
                    repo = db.get(Repository, job.resource_id)
                    if repo:
                        repo.status = "FAILED"
            if job.kind == "scan":
                for run in db.scalars(select(ScanRun).where(ScanRun.repository_id == job.resource_id, ScanRun.status == "RUNNING")):
                    run.status, run.completed_at = "FAILED", now()
            if job.kind in {"plan", "execute", "verify"}:
                task = db.get(Remediation, job.resource_id)
                if task:
                    task.state = "INCONCLUSIVE"
        db.commit()


def next_pending_job() -> str | None:
    with SessionLocal() as db:
        for job in db.scalars(select(Job).where(Job.status == "PENDING").order_by(Job.created_at).limit(1000)):
            if recovery.due(job):
                return job.id
    return None


def loop():
    recover_interrupted_jobs()
    while not STOP.wait(0.5):
        job_id = next_pending_job()
        if job_id:
            run_job(job_id)


def start():
    global WORKER
    STOP.clear()
    WORKER = threading.Thread(target=loop, daemon=True, name="kyro-worker")
    WORKER.start()


def stop():
    STOP.set()
    if WORKER:
        WORKER.join(timeout=5)
