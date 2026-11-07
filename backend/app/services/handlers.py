import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.engine import create_plan, execute_fix, snapshot, workspace
from app.core.errors import ServiceError
from app.core.security import digest, safe_path
from app.database import Finding, Job, Remediation, Repository, SessionLocal
from app.integrations.github import GitHub, create_pull_request
from app.intelligence.assessment import risk_assessment
from app.intelligence.enrichment import enrich
from app.jobs.worker import HANDLERS, progress
from app.repository.intelligence import index_repository
from app.scanners.service import scan_repository
from app.verification.engine import verify


def get_repo(db: Session, identifier: str) -> Repository:
    repo = db.get(Repository, identifier)
    if repo is None:
        raise ValueError("Repository no longer exists")
    return repo


def repository_job(job: Job) -> dict:
    with SessionLocal() as db:
        repo = get_repo(db, job.resource_id)
        root = snapshot(repo)
        if job.kind in {"ingest", "fixture"}:
            if root.exists():
                if root.is_symlink() or not root.is_dir() or not repo.sha:
                    raise ValueError("Incomplete repository snapshot retained; connect a new snapshot for review")
                progress(job.id, f"Resuming analysis of downloaded commit {repo.sha[:12]}")
            elif job.kind == "fixture":
                fixture = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "vulnerable-python"
                shutil.copytree(fixture, root)
                repo.sha = digest("KYRO controlled vulnerable-python fixture v1")
                progress(job.id, "Imported explicitly labelled controlled test fixture")
            else:
                github = GitHub(db, job.user_id)
                try:
                    progress(job.id, "Retrieving authorized GitHub commit archive")
                    github.ingest(repo, root)
                finally:
                    github.close()
            db.commit()
            progress(job.id, f"Source snapshot retrieved at {repo.sha[:12]}; starting repository analysis")
        if job.kind == "scan":
            result = scan_repository(db, repo, root, job.id)
            if any(scanner.get("retryable") for scanner in result["scanners"]):
                raise ServiceError("Scanner coverage is incomplete after a temporary execution failure; recorded results are retained", retryable=True)
            if result["status"] == "FAILED":
                raise RuntimeError("All security scanners failed; see scanner execution evidence")
            return {"scan_id": result["scan_id"], "scan_status": result["status"], "findings": len(result["findings"]), "state": "SUCCEEDED" if result["status"] == "SUCCEEDED" else "INCONCLUSIVE"}
        analysis = index_repository(db, repo, root, lambda msg: progress(job.id, msg))
        return {"repository_id": repo.id, "files": len(analysis["files"]), "languages": analysis["languages"]}


def enrichment_job(job: Job) -> dict:
    with SessionLocal() as db:
        finding = db.get(Finding, job.resource_id)
        if finding is None:
            raise ValueError("Finding no longer exists")
        progress(job.id, "Retrieving OSV, NVD, EPSS and KEV information where identifiers exist")
        finding.intelligence = enrich(finding.data)
        finding.risk = risk_assessment(finding.data, finding.reachability, finding.intelligence)
        db.commit()
        if any(error.get("retryable") for error in finding.intelligence["errors"]):
            raise ServiceError("Vulnerability intelligence is incomplete after a temporary provider failure; available evidence is retained", retryable=True)
        return {"finding_id": finding.id, "sources": len(finding.intelligence["sources"]), "errors": finding.intelligence["errors"], "state": "SUCCEEDED" if finding.intelligence["sources"] and not finding.intelligence["errors"] else "INCONCLUSIVE"}


def agent_job(job: Job) -> dict:
    with SessionLocal() as db:
        task = db.get(Remediation, job.resource_id)
        if task is None:
            raise ValueError("Remediation no longer exists")
        repo = get_repo(db, task.repository_id)
        finding = db.get(Finding, task.finding_id)
        if finding is None:
            raise ValueError("Finding no longer exists")
        if job.kind == "plan":
            return create_plan(db, task, repo, finding, job.user_id, job.id)
        if job.kind == "execute":
            return execute_fix(db, task, repo, job.user_id, job.id)
        if job.kind == "verify":
            return verify(db, task, repo, finding, job.id)
        if job.kind == "deliver":
            if task.verification.get("status") != "VERIFIED" or repo.source != "github":
                raise ValueError("A verified GitHub remediation is required")
            changes = task.verification.get("verified_changes", [])
            for change in changes:
                if digest(safe_path(workspace(task), change["path"], allow_new=False).read_bytes()) != change["verified_hash"]:
                    raise ValueError("Workspace changed after independent verification")
            progress(job.id, "Creating approved GitHub branch, commit and draft pull request")
            github = GitHub(db, job.user_id)
            try:
                result = create_pull_request(github, repo, task.id, changes, task.verification, task.plan)
            finally:
                github.close()
            task.pull_request = result
            db.commit()
            return result
    raise ValueError("Unknown agent job")


def register():
    for kind in ["ingest", "fixture", "analyze", "scan"]:
        HANDLERS[kind] = repository_job
    HANDLERS["enrich"] = enrichment_job
    for kind in ["plan", "execute", "verify", "deliver"]:
        HANDLERS[kind] = agent_job
