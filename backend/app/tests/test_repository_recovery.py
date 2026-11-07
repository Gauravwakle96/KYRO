import json
import os
import subprocess
import sys
import textwrap

import pytest

from app.core.config import settings
from app.database import Job, Project, Repository, SessionLocal, User


@pytest.fixture
def failed_import(owner, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    with SessionLocal() as db:
        project = Project(user_id=owner["id"], name="Recovery test fixture")
        db.add(project)
        db.flush()
        repo = Repository(project_id=project.id, full_name="controlled/recovery", branch="main", sha="a" * 40)
        db.add(repo)
        db.flush()
        job = Job(user_id=owner["id"], kind="ingest", resource_id=repo.id, status="FAILED", error="Worker interrupted", events=[{"message": "Original retrieval evidence"}])
        db.add(job)
        db.commit()
        identifiers = {"job": job.id, "repo": repo.id, "project": project.id}
    root = tmp_path / "repositories" / identifiers["repo"]
    root.mkdir(parents=True)
    (root / "app.ts").write_text("export function main() { return 1 }", encoding="utf-8")
    return identifiers, root


def test_retry_resumes_completed_snapshot_and_preserves_failure(client, failed_import):
    identifiers, root = failed_import
    response = client.post("/api/jobs/" + identifiers["job"] + "/retry")
    assert response.status_code == 202
    retried = response.json()
    assert retried["id"] != identifiers["job"]
    assert retried["kind"] == "analyze" and retried["status"] == "PENDING"
    assert retried["payload"] == {"retry_of": identifiers["job"]}
    assert (root / "app.ts").is_file()
    original = client.get("/api/jobs/" + identifiers["job"]).json()
    assert original["status"] == "FAILED" and original["error"] == "Worker interrupted"
    assert original["events"] == [{"message": "Original retrieval evidence"}]
    assert client.post("/api/jobs/" + identifiers["job"] + "/retry").status_code == 409


def test_retry_preserves_incomplete_archive(client, failed_import):
    identifiers, root = failed_import
    with SessionLocal() as db:
        repo = db.get(Repository, identifiers["repo"])
        assert repo is not None
        repo.sha = ""
        db.commit()
    response = client.post("/api/jobs/" + identifiers["job"] + "/retry")
    assert response.status_code == 409
    assert "incomplete" in response.json()["detail"]
    assert (root / "app.ts").read_text(encoding="utf-8").startswith("export")
    assert client.post("/api/repositories/" + identifiers["repo"] + "/analyze").status_code == 409


def test_retry_download_when_no_snapshot_exists(client, failed_import):
    identifiers, root = failed_import
    (root / "app.ts").unlink()
    root.rmdir()
    with SessionLocal() as db:
        repo = db.get(Repository, identifiers["repo"])
        assert repo is not None
        repo.sha = ""
        db.commit()
    response = client.post("/api/jobs/" + identifiers["job"] + "/retry")
    assert response.status_code == 202 and response.json()["kind"] == "ingest"


@pytest.mark.parametrize("kind", ["execute", "deliver", "plan", "verify"])
def test_retry_does_not_replay_agent_actions(client, failed_import, kind):
    identifiers, _ = failed_import
    with SessionLocal() as db:
        job = db.get(Job, identifiers["job"])
        assert job is not None
        job.kind = kind
        db.commit()
    response = client.post("/api/jobs/" + identifiers["job"] + "/retry")
    assert response.status_code == 409
    assert "approval" in response.json()["detail"]


@pytest.mark.parametrize("status", ["SUCCEEDED", "RUNNING", "PENDING"])
def test_retry_rejects_active_or_successful_job(client, failed_import, status):
    identifiers, _ = failed_import
    with SessionLocal() as db:
        job = db.get(Job, identifiers["job"])
        assert job is not None
        job.status = status
        db.commit()
    assert client.post("/api/jobs/" + identifiers["job"] + "/retry").status_code == 409


def test_retry_requires_job_and_repository_ownership(client, failed_import):
    identifiers, _ = failed_import
    with SessionLocal() as db:
        other = User(email="other@recovery.test", password_hash="unusable")
        db.add(other)
        db.flush()
        job = db.get(Job, identifiers["job"])
        project = db.get(Project, identifiers["project"])
        assert job is not None and project is not None
        original_owner = job.user_id
        job.user_id = other.id
        db.commit()
        assert client.post("/api/jobs/" + identifiers["job"] + "/retry").status_code == 404
        job.user_id = original_owner
        project.user_id = other.id
        db.commit()
    assert client.post("/api/jobs/" + identifiers["job"] + "/retry").status_code == 404


def test_retry_requires_session_and_csrf(client, failed_import):
    identifiers, _ = failed_import
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/jobs/" + identifiers["job"] + "/retry").status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    client.cookies.clear()
    assert client.post("/api/jobs/" + identifiers["job"] + "/retry").status_code == 401


def test_retry_scan_requires_completed_analysis(client, failed_import):
    identifiers, _ = failed_import
    with SessionLocal() as db:
        job = db.get(Job, identifiers["job"])
        assert job is not None
        job.kind = "scan"
        db.commit()
    assert client.post("/api/jobs/" + identifiers["job"] + "/retry").status_code == 409
    with SessionLocal() as db:
        repo = db.get(Repository, identifiers["repo"])
        assert repo is not None
        repo.status = "READY"
        db.commit()
    response = client.post("/api/jobs/" + identifiers["job"] + "/retry")
    assert response.status_code == 202 and response.json()["kind"] == "scan"


def test_retry_cancelled_job_has_fresh_cancellation_state(client, failed_import):
    identifiers, _ = failed_import
    with SessionLocal() as db:
        job = db.get(Job, identifiers["job"])
        assert job is not None
        job.status, job.cancel_requested = "CANCELLED", True
        db.commit()
    response = client.post("/api/jobs/" + identifiers["job"] + "/retry")
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING" and response.json()["cancel_requested"] is False


def test_retry_blocks_snapshot_symlink(client, failed_import, tmp_path):
    identifiers, root = failed_import
    (root / "app.ts").unlink()
    root.rmdir()
    other = tmp_path / "outside"
    other.mkdir()
    try:
        root.symlink_to(other, target_is_directory=True)
    except OSError:
        pytest.skip("Creating test symlinks is unavailable on this platform")
    try:
        response = client.post("/api/jobs/" + identifiers["job"] + "/retry")
        assert response.status_code == 409
        assert "boundary" in response.json()["detail"]
    finally:
        root.unlink()


def test_large_typescript_index_survives_background_thread_and_json_persistence(tmp_path):
    """Synthetic source; isolate native parser faults so a regression cannot crash pytest."""
    script = textwrap.dedent('''
        import json, threading
        from pathlib import Path
        from app.core.config import settings
        from app.database import Base, FileRecord, Project, Repository, SessionLocal, User, engine
        from app.repository.intelligence import index_repository
        from sqlalchemy import select

        Base.metadata.create_all(engine)
        root = settings.data_dir / "source"
        root.mkdir(parents=True)
        code = "\\n" * 300 + "import React from 'react';\\n"
        for index in range(600):
            code += f"export function component{index}() {{\\n const value = require('dependency');\\n return <div>{{value()}}</div>;\\n}}\\n"
        (root / "large.tsx").write_text(code, encoding="utf-8")
        outcome = {}
        def work():
            try:
                with SessionLocal() as db:
                    user = User(email="synthetic@parser.test", password_hash="unusable")
                    db.add(user)
                    db.flush()
                    project = Project(user_id=user.id, name="Synthetic parser regression")
                    db.add(project)
                    db.flush()
                    repo = Repository(project_id=project.id, full_name="controlled/parser", branch="main")
                    db.add(repo)
                    db.commit()
                    index_repository(db, repo, root)
                    db.expire_all()
                    record = db.scalar(select(FileRecord))
                    facts = record.facts
                    outcome.update(status=repo.status, symbols=len(facts["symbols"]), imports=len(facts["imports"]), calls=len(facts["calls"]), last_line=facts["symbols"][-1]["line"], errors=facts["errors"])
            except Exception as error:
                outcome["error"] = type(error).__name__
        thread = threading.Thread(target=work)
        thread.start()
        thread.join()
        print(json.dumps(outcome))
    ''')
    environment = {**os.environ, "KYRO_DATABASE_URL": "sqlite:///" + (tmp_path / "index.db").as_posix(), "KYRO_DATA_DIR": str(tmp_path), "KYRO_GITHUB_TOKEN": ""}
    result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", script], env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"status": "READY", "symbols": 600, "imports": 601, "calls": 1200, "last_line": 2698, "errors": []}
