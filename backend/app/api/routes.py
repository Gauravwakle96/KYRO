import json
import secrets
import shutil
import threading
from datetime import UTC, datetime, timedelta

import httpx
from argon2.exceptions import VerificationError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.agents.engine import plan_digest, snapshot
from app.agents.models import model_health, validate_local_endpoint
from app.api.schemas import (
    Approval,
    DeliveryApproval,
    Login,
    ModelSettings,
    OAuthPoll,
    ProjectInput,
    RepositoryInput,
)
from app.core.config import settings
from app.core.security import cipher, current_user, digest, password_hasher, safe_path
from app.database import (
    Audit,
    Credential,
    FileRecord,
    Finding,
    Job,
    LoginSession,
    ModelUsage,
    Project,
    Remediation,
    Repository,
    ScannerExecution,
    ScanRun,
    SessionLocal,
    User,
    audit,
    get_db,
    now,
)
from app.integrations.github import GitHub
from app.intelligence.assessment import attack_graph
from app.jobs.recovery import SAFE_KINDS
from app.sandbox.runner import docker_health, installed_image
from app.scanners.adapters import ADAPTERS

router = APIRouter(prefix="/api")
BOOTSTRAP_LOCK = threading.Lock()
DEVICE_CODES: dict[str, tuple[str, float, int]] = {}


def entity(row) -> dict:
    excluded = {"password_hash", "token_hash", "csrf", "ciphertext"}
    return {column.key: getattr(row, column.key) for column in inspect(row).mapper.column_attrs if column.key not in excluded}


def owned_project(db: Session, user: User, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(404, "Project not found")
    return project


def owned_repo(db: Session, user: User, repository_id: str) -> Repository:
    repo = db.get(Repository, repository_id)
    if repo is None:
        raise HTTPException(404, "Repository not found")
    owned_project(db, user, repo.project_id)
    return repo


def owned_finding(db: Session, user: User, finding_id: str) -> Finding:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise HTTPException(404, "Finding not found")
    owned_repo(db, user, finding.repository_id)
    return finding


def owned_task(db: Session, user: User, task_id: str) -> Remediation:
    task = db.get(Remediation, task_id)
    if task is None:
        raise HTTPException(404, "Remediation not found")
    owned_repo(db, user, task.repository_id)
    return task


def owned_repo_ids(db: Session, user: User):
    return select(Repository.id).join(Project, Repository.project_id == Project.id).where(Project.user_id == user.id)


def enqueue(db: Session, user: User, kind: str, resource_id: str, payload: dict | None = None):
    active = db.scalar(select(Job).where(Job.user_id == user.id, Job.status.in_(["PENDING", "RUNNING"]), Job.resource_id == resource_id))
    if active:
        raise HTTPException(409, "An operation on this resource is already active")
    count = db.scalar(select(func.count()).select_from(Job).where(Job.user_id == user.id, Job.status.in_(["PENDING", "RUNNING"])))
    if count and count >= 10:
        raise HTTPException(429, "Background job queue is full")
    job = Job(user_id=user.id, kind=kind, resource_id=resource_id, payload=payload or {})
    db.add(job)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "An operation on this resource is already active") from error
    audit(db, user.id, f"job.{kind}.queued", resource_id, {"job_id": job.id})
    return entity(job)


def signin(db: Session, user: User, response: Response) -> dict:
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    session = LoginSession(token_hash=digest(token), user_id=user.id, csrf=csrf, expires_at=(datetime.now(UTC) + timedelta(hours=settings.session_hours)).isoformat())
    db.add(session)
    db.commit()
    response.set_cookie("kyro_session", token, httponly=True, secure=settings.cookie_secure, samesite="strict", max_age=settings.session_hours * 3600, path="/")
    return {"user": entity(user), "csrf_token": csrf}


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ok", "version": "0.1.0"}


@router.get("/auth/setup")
def setup(db: Session = Depends(get_db)):
    return {"setup_required": db.scalar(select(func.count()).select_from(User)) == 0}


@router.post("/auth/register", status_code=201)
def register(body: Login, response: Response, db: Session = Depends(get_db)):
    with BOOTSTRAP_LOCK:
        if db.scalar(select(func.count()).select_from(User)):
            raise HTTPException(403, "Initial owner already exists; public signup is disabled")
        user = User(email=body.email, password_hash=password_hasher.hash(body.password))
        db.add(user)
        db.commit()
    audit(db, user.id, "auth.owner_created", user.id)
    return signin(db, user, response)


@router.post("/auth/login")
def login(body: Login, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    try:
        valid = user is not None and password_hasher.verify(user.password_hash, body.password)
    except VerificationError:
        valid = False
    if not valid or user is None:
        # Password hashing also applies to unknown accounts to limit enumeration timing.
        if user is None:
            password_hasher.hash(body.password)
        raise HTTPException(401, "Email or password is incorrect")
    return signin(db, user, response)


@router.get("/auth/me")
def me(request: Request, user: User = Depends(current_user)):
    return {"user": entity(user), "csrf_token": request.state.login_session.csrf}


@router.post("/auth/logout")
def logout(request: Request, response: Response, user: User = Depends(current_user), db: Session = Depends(get_db)):
    db.delete(request.state.login_session)
    db.commit()
    response.delete_cookie("kyro_session", path="/")
    return {"status": "signed_out"}


@router.get("/projects")
def projects(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [entity(p) for p in db.scalars(select(Project).where(Project.user_id == user.id).order_by(Project.created_at.desc()))]


@router.post("/projects", status_code=201)
def create_project(body: ProjectInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = Project(user_id=user.id, **body.model_dump())
    db.add(project)
    db.commit()
    audit(db, user.id, "project.created", project.id)
    return entity(project)


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: ProjectInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = owned_project(db, user, project_id)
    project.name, project.description = body.name, body.description
    db.commit()
    audit(db, user.id, "project.updated", project.id)
    return entity(project)


@router.delete("/projects/{project_id}")
def delete_project(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    project = owned_project(db, user, project_id)
    repo_ids = list(db.scalars(select(Repository.id).where(Repository.project_id == project.id)))
    tasks = list(db.scalars(select(Remediation).where(Remediation.repository_id.in_(repo_ids))))
    resource_ids = [*repo_ids, *(task.id for task in tasks)]
    if db.scalar(select(Job.id).where(Job.resource_id.in_(resource_ids), Job.status.in_(["PENDING", "RUNNING"]))):
        raise HTTPException(409, "Cancel active jobs before deleting this project")
    for folder, identifiers in [("repositories", repo_ids), ("workspaces", [t.id for t in tasks]), ("checkpoints", [t.id for t in tasks])]:
        base = (settings.data_dir / folder).resolve()
        for identifier in identifiers:
            target = (base / identifier).resolve()
            if not target.is_relative_to(base):
                raise HTTPException(400, "Invalid cleanup boundary")
            if target.exists():
                shutil.rmtree(target)
    for job in db.scalars(select(Job).where(Job.user_id == user.id, Job.resource_id.in_(resource_ids))):
        db.delete(job)
    db.delete(project)
    db.commit()
    audit(db, user.id, "project.deleted", project_id)
    return {"status": "deleted"}


@router.get("/github/status")
def github_status(user: User = Depends(current_user), db: Session = Depends(get_db)):
    credential = db.get(Credential, user.id)
    return {"configured": bool(credential or settings.github_token or settings.github_app_id), "oauth_available": bool(settings.github_client_id), "account": credential.github_login if credential else None, "method": "oauth" if credential else "app" if settings.github_app_id else "backend_token" if settings.github_token else None}


@router.post("/github/device")
def github_device(user: User = Depends(current_user)):
    if not settings.github_client_id:
        raise HTTPException(409, "Set KYRO_GITHUB_CLIENT_ID for GitHub OAuth device authorization")
    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.post("https://github.com/login/device/code", data={"client_id": settings.github_client_id, "scope": "repo"}, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
    if "device_code" not in data:
        raise HTTPException(502, "GitHub device authorization failed")
    DEVICE_CODES[data["device_code"]] = (user.id, datetime.now(UTC).timestamp() + data["expires_in"], data.get("interval", 5))
    return data


@router.post("/github/device/poll")
def github_poll(body: OAuthPoll, user: User = Depends(current_user), db: Session = Depends(get_db)):
    info = DEVICE_CODES.get(body.device_code)
    if info is None or info[0] != user.id or datetime.now(UTC).timestamp() > info[1]:
        raise HTTPException(400, "Device authorization expired or not owned by this user")
    with httpx.Client(timeout=20, trust_env=False) as client:
        response = client.post("https://github.com/login/oauth/access_token", data={"client_id": settings.github_client_id, "device_code": body.device_code, "grant_type": "urn:ietf:params:oauth:grant-type:device_code"}, headers={"Accept": "application/json"})
        response.raise_for_status()
        data = response.json()
        if "access_token" not in data:
            return {"status": data.get("error", "authorization_pending"), "interval": data.get("interval", info[2])}
        account = client.get("https://api.github.com/user", headers={"Authorization": f"Bearer {data['access_token']}"})
        account.raise_for_status()
    credential = db.get(Credential, user.id) or Credential(user_id=user.id, ciphertext="", github_login="")
    credential.ciphertext = cipher().encrypt(data["access_token"].encode()).decode()
    credential.github_login = account.json()["login"]
    db.add(credential)
    db.commit()
    del DEVICE_CODES[body.device_code]
    audit(db, user.id, "github.connected", user.id)
    return {"status": "connected", "account": credential.github_login}


@router.delete("/github/connection")
def github_disconnect(user: User = Depends(current_user), db: Session = Depends(get_db)):
    credential = db.get(Credential, user.id)
    if credential:
        db.delete(credential)
        db.commit()
    audit(db, user.id, "github.disconnected", user.id)
    return {"status": "disconnected", "backend_configuration_present": bool(settings.github_token or settings.github_app_id)}


@router.get("/github/repositories")
def github_repos(user: User = Depends(current_user), db: Session = Depends(get_db)):
    github = GitHub(db, user.id)
    try:
        return github.repositories()
    finally:
        github.close()


@router.get("/github/branches")
def github_branches(full_name: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    from app.integrations.github import validate_repository
    name = validate_repository(full_name)
    github = GitHub(db, user.id)
    try:
        return github.request("GET", f"/repos/{name}/branches?per_page=100")
    finally:
        github.close()


@router.get("/repositories")
def repositories(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [entity(repo) for repo in db.scalars(select(Repository).where(Repository.id.in_(owned_repo_ids(db, user))).order_by(Repository.created_at.desc()))]


@router.post("/repositories", status_code=202)
def connect_repository(body: RepositoryInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_project(db, user, body.project_id)
    repo = Repository(**body.model_dump())
    db.add(repo)
    db.commit()
    return {"repository": entity(repo), "job": enqueue(db, user, "ingest", repo.id)}


@router.post("/repositories/fixture", status_code=202)
def fixture(project_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_project(db, user, project_id)
    repo = Repository(project_id=project_id, full_name="KYRO/controlled-test-fixture", branch="fixture", source="fixture")
    db.add(repo)
    db.commit()
    return {"repository": entity(repo), "job": enqueue(db, user, "fixture", repo.id)}


@router.get("/repositories/{repository_id}")
def repository(repository_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return entity(owned_repo(db, user, repository_id))


@router.post("/repositories/{repository_id}/analyze", status_code=202)
def analyze(repository_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    repo = owned_repo(db, user, repository_id)
    if not repo.sha or not snapshot(repo).is_dir():
        raise HTTPException(409, "Repository ingestion has not completed")
    return enqueue(db, user, "analyze", repo.id)


@router.get("/repositories/{repository_id}/files")
def source_file(repository_id: str, path: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    repo = owned_repo(db, user, repository_id)
    file = safe_path(snapshot(repo), path, allow_new=False)
    if file.stat().st_size > 200000:
        raise HTTPException(413, "File too large for browser preview")
    return {"path": path, "content": file.read_text(encoding="utf-8")}


@router.get("/repository-intelligence/{repository_id}")
def repository_symbols(repository_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    owned_repo(db, user, repository_id)
    return [{"path": record.path, "hash": record.digest, **record.facts} for record in db.scalars(select(FileRecord).where(FileRecord.repository_id == repository_id))]


@router.post("/repositories/{repository_id}/scans", status_code=202)
def scan(repository_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    repo = owned_repo(db, user, repository_id)
    if repo.status != "READY":
        raise HTTPException(409, "Analyze the repository before scanning")
    return enqueue(db, user, "scan", repo.id)


@router.get("/scanners")
def scanners(user: User = Depends(current_user)):
    return {"docker": docker_health(), "scanners": [adapter.health() for adapter in ADAPTERS], "sandbox_image": settings.sandbox_image, "sandbox_available": installed_image(settings.sandbox_image)}


@router.get("/scans")
def scans(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [entity(scan) for scan in db.scalars(select(ScanRun).where(ScanRun.repository_id.in_(owned_repo_ids(db, user))).order_by(ScanRun.created_at.desc()).limit(100))]


@router.get("/scans/{scan_id}")
def scan_details(scan_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    scan = db.get(ScanRun, scan_id)
    if scan is None:
        raise HTTPException(404, "Scan not found")
    owned_repo(db, user, scan.repository_id)
    return {**entity(scan), "executions": [entity(ex) for ex in db.scalars(select(ScannerExecution).where(ScannerExecution.scan_id == scan.id))]}


@router.get("/findings")
def findings(repository_id: str | None = None, severity: str | None = None, search: str | None = None, user: User = Depends(current_user), db: Session = Depends(get_db)):
    query = select(Finding).where(Finding.repository_id.in_(owned_repo_ids(db, user)))
    if repository_id:
        owned_repo(db, user, repository_id)
        query = query.where(Finding.repository_id == repository_id)
    if severity:
        query = query.where(Finding.severity == severity)
    if search:
        query = query.where(Finding.title.contains(search, autoescape=True))
    return sorted([entity(f) for f in db.scalars(query.limit(1000))], key=lambda f: f["risk"].get("score", 0), reverse=True)


@router.get("/findings/{finding_id}")
def finding_details(finding_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return entity(owned_finding(db, user, finding_id))


@router.post("/findings/{finding_id}/enrich", status_code=202)
def enrich_finding(finding_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    finding = owned_finding(db, user, finding_id)
    return enqueue(db, user, "enrich", finding.id)


@router.get("/dependencies")
def dependency_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{**dependency, "repository_id": repo.id, "repository": repo.full_name} for repo in db.scalars(select(Repository).where(Repository.id.in_(owned_repo_ids(db, user)))) for dependency in repo.analysis.get("dependencies", [])]


@router.get("/attack-paths/{repository_id}")
def graph(repository_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    repo = owned_repo(db, user, repository_id)
    return attack_graph(db, repo, list(db.scalars(select(Finding).where(Finding.repository_id == repo.id))))


@router.post("/findings/{finding_id}/remediation", status_code=202)
def remediation_plan(finding_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    finding = owned_finding(db, user, finding_id)
    task = Remediation(finding_id=finding.id, repository_id=finding.repository_id)
    db.add(task)
    db.commit()
    return {"remediation": entity(task), "job": enqueue(db, user, "plan", task.id)}


@router.get("/remediation")
def remediation_list(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [entity(task) for task in db.scalars(select(Remediation).where(Remediation.repository_id.in_(owned_repo_ids(db, user))).order_by(Remediation.created_at.desc()))]


@router.get("/remediation/{task_id}")
def remediation_details(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    return {**entity(task), "plan_digest": plan_digest(task, owned_repo(db, user, task.repository_id))}


@router.post("/remediation/{task_id}/approve")
def approve(task_id: str, body: Approval, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    repo = owned_repo(db, user, task.repository_id)
    if task.state != "AWAITING_APPROVAL" or not body.approved or body.plan_digest != plan_digest(task, repo):
        raise HTTPException(409, "Approval requires the current validated plan")
    task.approval_digest, task.approved_by = body.plan_digest, user.id
    db.commit()
    audit(db, user.id, "remediation.approved", task.id, {"digest": body.plan_digest})
    return {"status": "approved"}


@router.post("/remediation/{task_id}/execute", status_code=202)
def execute(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    if task.state not in {"AWAITING_APPROVAL", "FAILED", "INCONCLUSIVE"} or task.approved_by != user.id or task.approval_digest != plan_digest(task, owned_repo(db, user, task.repository_id)):
        raise HTTPException(409, "Approve this exact plan before executing")
    if not installed_image(settings.sandbox_image):
        raise HTTPException(409, "Sandbox image is unavailable")
    return enqueue(db, user, "execute", task.id)


@router.post("/remediation/{task_id}/verify", status_code=202)
def verification(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    if not task.evidence.get("changes"):
        raise HTTPException(409, "Execute an approved patch first")
    return enqueue(db, user, "verify", task.id)


@router.get("/remediation/{task_id}/report")
def report(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    if not task.verification:
        raise HTTPException(409, "Independent verification has not run")
    return task.verification


@router.post("/remediation/{task_id}/pull-request", status_code=202)
def deliver(task_id: str, body: DeliveryApproval, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    repo = owned_repo(db, user, task.repository_id)
    if repo.source != "github":
        raise HTTPException(409, "Test fixtures cannot create real GitHub pull requests")
    if not body.approved or task.verification.get("status") != "VERIFIED" or task.pull_request:
        raise HTTPException(409, "Delivery requires approval, VERIFIED evidence and no existing pull request")
    audit(db, user.id, "pull_request.approved", task.id)
    return enqueue(db, user, "deliver", task.id)


@router.get("/pull-requests")
def pull_requests(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [{**task.pull_request, "remediation_id": task.id, "verification_status": task.verification.get("status")} for task in db.scalars(select(Remediation).where(Remediation.repository_id.in_(owned_repo_ids(db, user)))) if task.pull_request]


@router.post("/remediation/{task_id}/pull-request/refresh")
def refresh_pr(task_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    repo = owned_repo(db, user, task.repository_id)
    if not task.pull_request:
        raise HTTPException(409, "No pull request exists")
    github = GitHub(db, user.id)
    try:
        pr = github.request("GET", f"/repos/{repo.full_name}/pulls/{task.pull_request['number']}")
    finally:
        github.close()
    task.pull_request = {**task.pull_request, "state": pr["state"], "merged": pr["merged"], "draft": pr["draft"]}
    db.commit()
    return task.pull_request


@router.get("/models")
def models(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {**model_health(), "routing": settings.model_routing, "cloud_model": settings.cloud_model, "cloud_protocol": settings.cloud_protocol, "cloud_request_limit": settings.cloud_request_limit, "cloud_requests_used": db.scalar(select(func.count()).select_from(ModelUsage).where(ModelUsage.provider == "cloud")), "usage": [entity(usage) for usage in db.scalars(select(ModelUsage).where(ModelUsage.user_id == user.id).order_by(ModelUsage.created_at.desc()).limit(100))]}


@router.put("/models/settings")
def model_settings(body: ModelSettings, user: User = Depends(current_user), db: Session = Depends(get_db)):
    validate_local_endpoint(body.endpoint)
    if not body.local_only and not settings.cloud_authorized:
        raise HTTPException(403, "Cloud cost authorization must be enabled by the server operator")
    settings.local_model_url, settings.local_model, settings.local_only = body.endpoint, body.model, body.local_only
    settings.model_routing = body.routing
    (settings.data_dir / "model-settings.json").write_text(json.dumps(body.model_dump()), encoding="utf-8")
    audit(db, user.id, "model.settings_updated", user.id, {"model": body.model, "local_only": body.local_only})
    return {"status": "saved"}


@router.get("/jobs")
def jobs(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [entity(job) for job in db.scalars(select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).limit(100))]


@router.get("/jobs/{job_id}")
def job_details(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "Job not found")
    return entity(job)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "Job not found")
    if job.status not in {"PENDING", "RUNNING"}:
        raise HTTPException(409, "Job is already finished")
    job.cancel_requested = True
    if job.status == "PENDING":
        job.status, job.ended_at = "CANCELLED", now()
    db.commit()
    audit(db, user.id, "job.cancel_requested", job.id)
    return {"status": "cancellation_requested"}


@router.post("/jobs/{job_id}/retry", status_code=202)
def retry_job(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if job is None or job.user_id != user.id:
        raise HTTPException(404, "Job not found")
    if job.status not in {"FAILED", "CANCELLED", "INCONCLUSIVE"}:
        raise HTTPException(409, "Only failed or cancelled operations can be retried")
    if job.kind not in {"ingest", "fixture", "analyze", "scan", "enrich"}:
        raise HTTPException(409, "Use the remediation review and approval controls to retry this operation")
    kind = job.kind
    if kind == "enrich":
        owned_finding(db, user, job.resource_id)
    else:
        repo = owned_repo(db, user, job.resource_id)
        root = snapshot(repo)
        if root.is_symlink():
            raise HTTPException(409, "Repository snapshot is outside the allowed boundary")
        if kind in {"ingest", "fixture"}:
            if root.exists():
                if not repo.sha or not root.is_dir():
                    raise HTTPException(409, "Source retrieval is incomplete; connect a new snapshot to preserve the original evidence")
                kind = "analyze"
        elif not repo.sha or not root.is_dir():
            raise HTTPException(409, "Repository ingestion has not completed")
        if kind == "scan" and repo.status != "READY":
            raise HTTPException(409, "Analyze the repository before retrying its scan")
    return enqueue(db, user, kind, job.resource_id, {"retry_of": job.id})


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)):
    import asyncio
    job_details(job_id, user, db)
    async def stream():
        last = request.headers.get("Last-Event-ID", "")
        for _ in range(600):
            if await request.is_disconnected():
                break
            with SessionLocal() as session:
                job = session.get(Job, job_id)
                if job is None or job.user_id != user.id:
                    break
                latest_event = job.events[-1].get("at", "") if job.events else ""
                stamp = f"{len(job.events)}:{latest_event}:{job.status}"
                if stamp != last:
                    yield f"id: {stamp}\ndata: {json.dumps(entity(job))}\n\n"
                    last = stamp
                else:
                    yield ": heartbeat\n\n"
                if job.status not in {"PENDING", "RUNNING"}:
                    break
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/analytics")
def analytics(user: User = Depends(current_user), db: Session = Depends(get_db)):
    repos = list(db.scalars(select(Repository).where(Repository.id.in_(owned_repo_ids(db, user)))))
    findings = list(db.scalars(select(Finding).where(Finding.repository_id.in_(owned_repo_ids(db, user)))))
    tasks = list(db.scalars(select(Remediation).where(Remediation.repository_id.in_(owned_repo_ids(db, user)))))
    scans = list(db.scalars(select(ScanRun).where(ScanRun.repository_id.in_(owned_repo_ids(db, user)))))
    usage = list(db.scalars(select(ModelUsage).where(ModelUsage.user_id == user.id)))
    severity_counts = {level: sum(f.severity == level and f.status == "OPEN" for f in findings) for level in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN"]}
    verified = [task for task in tasks if task.verification.get("status") == "VERIFIED"]
    return {"repositories": len(repos), "findings": sum(f.status == "OPEN" for f in findings), "severity": severity_counts, "remediations": len(tasks), "verified_fixes": len({task.finding_id for task in verified}), "verified_runs": len(verified), "scans": len(scans), "scan_history": [entity(s) for s in scans[-30:]], "model_requests": len(usage), "input_tokens": sum(u.input_tokens or 0 for u in usage), "output_tokens": sum(u.output_tokens or 0 for u in usage), "missing_token_records": sum(u.input_tokens is None or u.output_tokens is None for u in usage), "estimated_cloud_cost": sum(u.estimated_cost or 0 for u in usage if u.provider != "local"), "missing_cloud_cost_records": sum(u.provider != "local" and u.estimated_cost is None for u in usage), "local_inference_seconds": sum(u.duration_seconds for u in usage if u.provider == "local"), "cost_per_verified_remediation": sum(u.estimated_cost or 0 for u in usage) / len(verified) if verified and not any(u.provider != "local" and u.estimated_cost is None for u in usage) else None, "verification_outcomes": {s: sum(t.verification.get("status") == s for t in tasks) for s in ["VERIFIED", "PARTIALLY_VERIFIED", "FAILED", "INCONCLUSIVE"]}}


@router.get("/settings")
def configuration(user: User = Depends(current_user)):
    return {"local_only": settings.local_only, "sandbox": {"image": settings.sandbox_image, "network": "none", "cpu": 1, "memory_mb": 1024, "pids": 128, "command_timeout_seconds": settings.command_timeout}, "scanner_network": settings.scanner_network, "max_agent_steps": settings.max_agent_steps, "retention": "Data persists until explicitly deleted by its owner", "github_app_configured": bool(settings.github_app_id), "cloud_authorized": settings.cloud_authorized, "automatic_recovery": {"enabled": settings.automatic_recovery, "max_attempts": settings.job_max_attempts, "base_delay_seconds": settings.job_retry_delay, "operations": sorted(SAFE_KINDS), "approval_required": ["execute", "verify", "deliver"], "scope": "Temporary provider failures and interrupted read operations; failures and evidence remain visible"}}


@router.get("/audit")
def audit_history(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [entity(record) for record in db.scalars(select(Audit).where(Audit.user_id == user.id).order_by(Audit.created_at.desc()).limit(200))]
