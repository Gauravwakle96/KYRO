"""Sequential live audit of explicitly authorized repositories through deployed KYRO.

This trusted operator harness queues real backend jobs. It never runs repository
scripts, generates approvals, modifies remote code, or handles GitHub credentials.
"""
import argparse
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BACKEND = r'''
import json, sys
from sqlalchemy import select
from app.api.routes import connect_repository, create_project, enqueue, graph, owned_repo, scan
from app.api.schemas import ProjectInput, RepositoryInput
from app.core.security import redact
from app.database import SessionLocal, User, Project, Repository, Job, Finding, ScanRun, ScannerExecution, FileRecord
from app.integrations.github import GitHub
from app.agents.engine import snapshot
from app.repository.intelligence import relevant_context

operation = sys.argv[1]
try:
    with SessionLocal() as db:
        users = list(db.scalars(select(User)))
        if len(users) != 1:
            raise ValueError('This local operator audit requires exactly one owner')
        user = users[0]
        if operation == 'list':
            github = GitHub(db, user.id)
            try:
                result = github.repositories()
            finally:
                github.close()
        elif operation == 'ensure':
            name, branch = sys.argv[2:4]
            repo = db.scalar(select(Repository).join(Project).where(Project.user_id == user.id, Repository.full_name == name, Repository.branch == branch).order_by(Repository.created_at))
            if repo is None:
                project = db.scalar(select(Project).where(Project.user_id == user.id, Project.name == 'Repository validation'))
                if project is None:
                    project_data = create_project(ProjectInput(name='Repository validation', description='User-authorized sequential live repository checks'), user, db)
                    project = db.get(Project, project_data['id'])
                connected = connect_repository(RepositoryInput(project_id=project.id, full_name=name, branch=branch), user, db)
                repo = db.get(Repository, connected['repository']['id'])
            active = db.scalar(select(Job).where(Job.user_id == user.id, Job.resource_id == repo.id, Job.status.in_(['PENDING', 'RUNNING'])))
            if repo.status != 'READY' and active is None:
                root = snapshot(repo)
                if root.is_dir() and repo.sha:
                    queued = enqueue(db, user, 'analyze', repo.id, {'operator_audit': True})
                elif not root.exists():
                    queued = enqueue(db, user, 'ingest', repo.id, {'operator_audit': True})
                else:
                    raise ValueError('Incomplete source snapshot retained; retrieval must be reviewed')
                active = db.get(Job, queued['id'])
            result = {'repository_id': repo.id, 'status': repo.status, 'job_id': active.id if active else None}
        elif operation == 'job':
            job = db.get(Job, sys.argv[2])
            if job is None or job.user_id != user.id:
                raise ValueError('Job not found')
            result = {'id': job.id, 'kind': job.kind, 'status': job.status, 'error': redact(job.error or ''), 'result': job.result, 'started_at': job.started_at, 'ended_at': job.ended_at, 'payload': job.payload}
        elif operation == 'scan':
            repo = owned_repo(db, user, sys.argv[2])
            active = db.scalar(select(Job).where(Job.user_id == user.id, Job.resource_id == repo.id, Job.status.in_(['PENDING', 'RUNNING'])))
            if active:
                result = {'job_id': active.id, 'kind': active.kind}
            else:
                queued = scan(repo.id, user, db)
                result = {'job_id': queued['id'], 'kind': 'scan'}
        elif operation == 'summary':
            repo = owned_repo(db, user, sys.argv[2])
            finding_rows = list(db.scalars(select(Finding).where(Finding.repository_id == repo.id, Finding.status == 'OPEN')))
            run = db.scalar(select(ScanRun).where(ScanRun.repository_id == repo.id, ScanRun.purpose == 'baseline').order_by(ScanRun.created_at.desc()))
            executions = list(db.scalars(select(ScannerExecution).where(ScannerExecution.scan_id == run.id))) if run else []
            records = list(db.scalars(select(FileRecord).where(FileRecord.repository_id == repo.id)))
            evidence_graph = graph(repo.id, user, db)
            context = relevant_context(db, repo, snapshot(repo), finding_rows[0].data) if finding_rows else []
            result = {
                'repository_id': repo.id, 'commit': repo.sha, 'index_status': repo.status,
                'indexed_files': len(repo.analysis.get('files', [])), 'languages': repo.analysis.get('languages', {}),
                'frameworks': repo.analysis.get('frameworks', []), 'dependencies': len(repo.analysis.get('dependencies', [])),
                'test_files': len(repo.analysis.get('tests', [])), 'symbols': sum(len(x.facts.get('symbols', [])) for x in records),
                'parse_errors': repo.analysis.get('errors', []), 'findings': len(finding_rows),
                'severity': {level: sum(x.severity == level for x in finding_rows) for level in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']},
                'risk_assessments_with_factors': sum(bool(x.risk.get('factors')) for x in finding_rows),
                'reachability': {category: sum(x.reachability.get('category') == category for x in finding_rows) for category in ['CONFIRMED_REFERENCE', 'POTENTIAL_REACHABILITY', 'INFERRED_REACHABILITY', 'NO_REFERENCE_FOUND', 'UNKNOWN']},
                'context_selection': {'files': len(context), 'characters': sum(len(x['content']) for x in context), 'evaluated': bool(finding_rows)},
                'graph': {'nodes': len(evidence_graph['nodes']), 'edges': len(evidence_graph['edges'])},
                'scan_id': run.id if run else None, 'scan_status': run.status if run else 'NOT_RUN',
                'scanners': [{'scanner': x.scanner, 'status': x.status, 'findings': len(x.normalized), 'version': x.metadata_json.get('version'), 'exit_code': x.metadata_json.get('exit_code'), 'duration_seconds': x.metadata_json.get('duration_seconds'), 'error': redact(str(x.metadata_json.get('error', '')))} for x in executions],
                'limitations': repo.analysis.get('limitations', [])
            }
        else:
            raise ValueError('Unknown audit operation')
        print(json.dumps({'result': result}))
except Exception as error:
    message = getattr(error, 'detail', None) or str(error)
    print(json.dumps({'error': redact(str(message))[:1000], 'error_type': type(error).__name__}))
    sys.exit(1)
'''


def invoke(operation: str, *arguments: str):
    result = subprocess.run(["docker", "compose", "exec", "-T", "kyro", "python", "-c", BACKEND, operation, *arguments], cwd=ROOT, capture_output=True, text=True, timeout=120)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise RuntimeError("Deployed backend did not return a structured audit result") from error
    if result.returncode or "error" in payload:
        raise RuntimeError(payload.get("error", "Deployed backend operation failed"))
    return payload["result"]


def wait(job_id: str):
    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        job = invoke("job", job_id)
        if job["status"] not in {"PENDING", "RUNNING"}:
            return job
        time.sleep(2)
    raise TimeoutError("Repository stage exceeded the 30-minute audit limit")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", action="append", help="Limit to listed owner/repository names")
    parser.add_argument("--output", default="docs/evidence/live-repository-audit.json")
    args = parser.parse_args()
    target = (ROOT / args.output).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError("Audit evidence must remain within the project")
    repositories = invoke("list")
    if args.repository:
        requested = set(args.repository)
        repositories = [x for x in repositories if x["full_name"] in requested]
        if {x["full_name"] for x in repositories} != requested:
            raise ValueError("Requested repository is absent from the authorized listing")
    report = {"started_at": datetime.now(UTC).isoformat(), "status": "RUNNING", "scope": "Sequential indexing, actual scanner execution and evidence/data boundaries on authorized default branches", "transport": "Deployed backend services and persistent jobs; not a browser login test", "repository_count": len(repositories), "repositories": [], "remote_writes_performed": False, "limitations": ["Build/test execution, remediation approval and PR creation are not established by this read-and-scan audit.", "Zero findings does not establish that a repository is safe."]}

    def save():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    save()
    for index, item in enumerate(repositories, 1):
        name, branch = item["full_name"], item["default_branch"]
        entry = {"name": name, "branch": branch, "private": item["private"], "status": "RUNNING", "started_at": datetime.now(UTC).isoformat()}
        report["repositories"].append(entry)
        save()
        print(f"[{index}/{len(repositories)}] {name} ({branch}): indexing", flush=True)
        try:
            connected = invoke("ensure", name, branch)
            identifier = connected["repository_id"]
            entry["repository_id"] = identifier
            if connected["job_id"]:
                entry["ingestion_job"] = wait(connected["job_id"])
                if entry["ingestion_job"]["status"] != "SUCCEEDED":
                    raise RuntimeError(entry["ingestion_job"]["error"] or "Repository ingestion did not succeed")
            save()
            print(f"[{index}/{len(repositories)}] {name}: running Semgrep, OSV-Scanner and Trivy", flush=True)
            queued = invoke("scan", identifier)
            entry["scan_job"] = wait(queued["job_id"])
            if queued["kind"] != "scan" and entry["scan_job"]["status"] == "SUCCEEDED":
                entry["scan_job"] = wait(invoke("scan", identifier)["job_id"])
            entry.update(invoke("summary", identifier))
            entry["status"] = "SUCCEEDED" if entry["index_status"] == "READY" and entry["scan_status"] == "SUCCEEDED" else "INCONCLUSIVE"
            print(f"[{index}/{len(repositories)}] {name}: {entry['status']} — {entry['indexed_files']} files, {entry['findings']} findings", flush=True)
        except Exception as error:
            entry["status"], entry["error"] = "FAILED", str(error)[:1000]
            print(f"[{index}/{len(repositories)}] {name}: FAILED — {entry['error']}", flush=True)
        entry["completed_at"] = datetime.now(UTC).isoformat()
        save()
    report["completed_at"] = datetime.now(UTC).isoformat()
    report["outcomes"] = {state: sum(x["status"] == state for x in report["repositories"]) for state in ["SUCCEEDED", "INCONCLUSIVE", "FAILED"]}
    report["status"] = "COMPLETED" if report["outcomes"]["SUCCEEDED"] == len(repositories) else "COMPLETED_WITH_FAILURES"
    save()
    print(json.dumps(report["outcomes"]), flush=True)


if __name__ == "__main__":
    main()
