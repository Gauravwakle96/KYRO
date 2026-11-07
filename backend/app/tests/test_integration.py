import pytest

from app.core.config import settings
from app.core.security import digest
from app.database import Job, Project, Repository, User
from app.jobs import worker
from app.repository.intelligence import index_repository


def test_index_incremental(db, tmp_path):
    user = User(email="owner@local.test", password_hash="hash")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="Tests")
    db.add(project)
    db.flush()
    repo = Repository(project_id=project.id, full_name="controlled/repo", branch="main")
    db.add(repo)
    db.commit()
    (tmp_path / "app.py").write_text("def first(): return 1\n")
    first = index_repository(db, repo, tmp_path)
    assert first["files"][0]["hash"] == digest("def first(): return 1\n")
    (tmp_path / "app.py").write_text("def second(): return 2\n")
    second = index_repository(db, repo, tmp_path)
    assert first["files"][0]["hash"] != second["files"][0]["hash"]


def test_job_failure_is_persisted(db):
    user = User(email="owner@local.test", password_hash="hash")
    db.add(user)
    db.flush()
    job = Job(user_id=user.id, kind="unknown", resource_id="x")
    db.add(job)
    db.commit()
    worker.STOP.clear()
    worker.run_job(job.id)
    db.refresh(job)
    assert job.status == "FAILED"
    assert job.error and job.ended_at


def test_database_job_result_persisted(db):
    user = User(email="owner@local.test", password_hash="hash")
    db.add(user)
    db.flush()
    job = Job(user_id=user.id, kind="controlled", resource_id="x")
    db.add(job)
    db.commit()
    worker.HANDLERS["controlled"] = lambda _: {"real_result": 4}
    worker.STOP.clear()
    worker.run_job(job.id)
    db.refresh(job)
    assert job.result == {"real_result": 4}
    assert job.status == "SUCCEEDED"


def test_business_failure_does_not_become_successful_job(db):
    user = User(email="failure@local.test", password_hash="hash")
    db.add(user)
    db.flush()
    job = Job(user_id=user.id, kind="controlled-failure", resource_id="x")
    db.add(job)
    db.commit()
    worker.HANDLERS["controlled-failure"] = lambda _: {"state": "FAILED", "evidence": "Controlled test failure"}
    worker.STOP.clear()
    worker.run_job(job.id)
    db.refresh(job)
    assert job.status == "FAILED" and job.result["state"] == "FAILED" and job.error


def test_cloud_block_precedes_network(db):
    from app.agents.models import complete
    settings.local_only = True
    with pytest.raises(ValueError, match="Cloud inference is blocked"):
        complete(db, "unused", [], provider="cloud")


def test_project_persistence_and_deletion(client, owner):
    project = client.post("/api/projects", json={"name": "Platform"}).json()
    assert client.get("/api/projects").json()[0]["name"] == "Platform"
    assert client.delete("/api/projects/" + project["id"]).status_code == 200
    assert client.get("/api/projects").json() == []


def test_approval_required(client, owner):
    assert client.post("/api/remediation/nonexistent/execute").status_code == 404


def test_bad_password(client, owner):
    assert client.post("/api/auth/login", json={"email": "owner@example.test", "password": "incorrect password"}).status_code == 401


def test_session_cookie_security(client, owner):
    client.post("/api/auth/logout")
    assert client.get("/api/projects").status_code == 401
    response = client.post("/api/auth/login", json={"email": "owner@example.test", "password": "correct horse local fixture"})
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie
