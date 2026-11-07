import io
import tarfile

import pytest

from app.agents.engine import TRANSITIONS, plan_digest, validate_patch
from app.agents.models import validate_local_endpoint
from app.agents.schemas import Patch
from app.core.security import digest, redact, safe_path
from app.database import Project, Remediation, Repository, User
from app.integrations.github import extract_archive
from app.sandbox.runner import container_command, validate_command


def test_unauthenticated_access(client):
    assert client.get("/api/projects").status_code == 401
    assert client.post("/api/projects", json={"name": "hidden"}).status_code == 401


def test_bootstrap_and_csrf(client, owner):
    assert client.post("/api/auth/register", json={"email": "attacker@example.test", "password": "long attack password"}).status_code == 403
    csrf = client.headers.pop("X-CSRF-Token")
    assert client.post("/api/projects", json={"name": "Denied"}).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert client.post("/api/projects", json={"name": "Owned"}).status_code == 201


def test_cross_origin_and_headers(client, owner):
    assert client.post("/api/projects", headers={"Origin": "https://malicious.example"}, json={"name": "Attack"}).status_code == 403
    response = client.get("/api/health")
    assert response.headers["x-frame-options"] == "DENY"
    assert "unsafe-inline" not in response.headers["content-security-policy"]


def test_ownership(client, owner):
    from app.database import SessionLocal
    with SessionLocal() as db:
        other = User(email="other@example.test", password_hash="unusable")
        db.add(other)
        db.flush()
        project = Project(user_id=other.id, name="Private")
        db.add(project)
        db.commit()
        identifier = project.id
    assert client.delete("/api/projects/" + identifier).status_code == 404
    assert not client.get("/api/projects").json()


@pytest.mark.parametrize("path", ["../outside", "/etc/passwd", "C:/Windows/system.ini", "a\\b", ".git/config", ".env", ".env.local", "a/../../file", "file\x00name"])
def test_path_traversal(tmp_path, path):
    with pytest.raises(ValueError):
        safe_path(tmp_path, path)


def test_archive_link_blocked(tmp_path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        member = tarfile.TarInfo("root/link")
        member.type, member.linkname = tarfile.SYMTYPE, "../../outside"
        archive.addfile(member)
    with pytest.raises(ValueError):
        extract_archive(stream.getvalue(), tmp_path)


@pytest.mark.parametrize("argv", [["bash", "-c", "id"], ["python", "-c", "import os"], ["docker", "run", "--privileged"], ["curl", "https://example.com"], ["python", "-m", "pytest", "-p", "malicious"]])
def test_unsafe_commands_blocked(argv):
    with pytest.raises(ValueError):
        validate_command(argv)


def test_allowed_command():
    validate_command(["python", "-m", "unittest", "discover", "-s", "tests"])


def test_local_only():
    validate_local_endpoint("http://127.0.0.1:8080/v1")
    with pytest.raises(ValueError):
        validate_local_endpoint("https://8.8.8.8/v1")
    with pytest.raises(ValueError):
        validate_local_endpoint("http://user:secret@127.0.0.1/v1")


def test_prompt_injection_cannot_expand_scope(tmp_path):
    (tmp_path / "app.py").write_text("safe = True\n", encoding="utf-8")
    patch = Patch.model_validate({"summary": "Repository comment instructed deleting policy", "changes": [{"path": "../credentials", "before_hash": digest("x"), "content": "leak"}]})
    with pytest.raises(ValueError):
        validate_patch(tmp_path, {"files": ["app.py"]}, patch)


def test_approval_changes_when_plan_changes():
    repo = Repository(sha="a", full_name="owner/repo", branch="main", project_id="p")
    task = Remediation(finding_id="f", plan={"files": ["app.py"]})
    old = plan_digest(task, repo)
    task.plan = {"files": ["secrets.py"]}
    assert plan_digest(task, repo) != old


def test_state_machine_never_skips_approval():
    assert "EXECUTING" not in TRANSITIONS["PLANNING"]
    assert "SUCCEEDED" not in TRANSITIONS["EXECUTING"]


def test_redacts_secret_patterns():
    assert "ghp_" not in redact("ghp_" + "x" * 36)


def test_payload_limits(client):
    assert client.post("/api/auth/login", content="a" * 1_000_001, headers={"Content-Type": "application/json"}).status_code == 413


def test_host_mount_boundary(tmp_path):
    with pytest.raises(ValueError):
        container_command(tmp_path / "outside", "image", ["python", "--version"])
