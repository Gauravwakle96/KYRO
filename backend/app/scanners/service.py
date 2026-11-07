from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Finding, Repository, ScannerExecution, ScanRun, now
from app.intelligence.assessment import reachability, risk_assessment
from app.jobs.worker import progress
from app.scanners.adapters import ADAPTERS
from app.scanners.normalization import deduplicate


def scan_repository(db: Session, repo: Repository, root: Path, job_id: str | None = None, *, purpose="baseline") -> dict:
    run = ScanRun(repository_id=repo.id, snapshot_sha=repo.sha, purpose=purpose)
    db.add(run)
    db.commit()
    executions = []
    for adapter in ADAPTERS:
        if job_id:
            progress(job_id, f"Running {adapter.name}")
        try:
            result = adapter.execute(root, job_id)
        except Exception as error:
            from app.jobs.worker import Cancelled
            if isinstance(error, Cancelled):
                run.status, run.completed_at = "CANCELLED", now()
                db.commit()
                raise
            result = {"scanner": adapter.name, "status": "FAILED", "metadata": {"error": str(error)}, "findings": []}
        db.add(ScannerExecution(scan_id=run.id, scanner=adapter.name, status=result["status"], metadata_json=result["metadata"], normalized=result["findings"]))
        db.commit()
        executions.append(result)
        if job_id:
            progress(job_id, f"{adapter.name}: {result['status']}; {len(result['findings'])} findings")
    statuses = [item["status"] for item in executions]
    run.status = "SUCCEEDED" if all(s == "SUCCEEDED" for s in statuses) else "FAILED" if all(s == "FAILED" for s in statuses) else "PARTIAL"
    run.completed_at = now()
    normalized = deduplicate([finding for result in executions for finding in result["findings"]])
    if purpose == "baseline":
        for item in normalized:
            record = db.scalar(select(Finding).where(Finding.repository_id == repo.id, Finding.fingerprint == item["fingerprint"]))
            reach = reachability(db, repo, item)
            if record is None:
                record = Finding(repository_id=repo.id, scan_id=run.id, fingerprint=item["fingerprint"], title=item["title"], severity=item["severity"], data=item, reachability=reach, risk=risk_assessment(item, reach))
                db.add(record)
            else:
                record.data, record.scan_id, record.last_detected = item, run.id, now()
                record.title, record.severity, record.status = item["title"], item["severity"], "OPEN"
                record.reachability, record.risk = reach, risk_assessment(item, reach, record.intelligence)
        # A complete scan can mark absence, not proof of a secure fix.
        if run.status == "SUCCEEDED":
            keys = {item["fingerprint"] for item in normalized}
            for record in db.scalars(select(Finding).where(Finding.repository_id == repo.id)):
                if record.fingerprint not in keys:
                    record.status = "NOT_DETECTED"
    db.commit()
    return {"scan_id": run.id, "status": run.status, "findings": normalized, "scanners": [{"scanner": r["scanner"], "status": r["status"], "error": r["metadata"].get("error"), "retryable": r.get("retryable", False)} for r in executions]}
