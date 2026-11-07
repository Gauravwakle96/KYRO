import json

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.agents.engine import validate_patch
from app.agents.schemas import Change, Patch
from app.core.security import digest
from app.database import Finding, Job, ModelUsage, Project, Remediation, Repository, User


@pytest.mark.parametrize("code", ["eval('1')", "builtins.eval('1')", "x = eval", "compile('1', '', 'eval')", "__import__('os')", "exec('pass')"])
def test_dynamic_execution_patch_rejected_before_writing(tmp_path, code):
    path = tmp_path / "app.py"
    path.write_text("original = 1")
    patch = Patch(summary="Controlled adversarial patch", changes=[Change(path="app.py", before_hash=digest(path.read_bytes()), content=code)])
    with pytest.raises(ValueError, match="retains dynamic execution"):
        validate_patch(tmp_path, {"files": ["app.py"]}, patch, {"rule_id": "kyro.python.dynamic-eval"})
    assert path.read_text() == "original = 1"


def test_parser_and_explicit_operator_patch_allowed(tmp_path):
    path = tmp_path / "app.py"
    path.write_text("original = 1")
    patch = Patch(summary="Controlled parser patch", changes=[Change(path="app.py", before_hash=digest(path.read_bytes()), content="import ast\nnode = ast.parse('1 + 2', mode='eval')")])
    validate_patch(tmp_path, {"files": ["app.py"]}, patch, {"rule_id": "kyro.python.dynamic-eval"})


def test_active_jobs_have_database_uniqueness(db):
    user = User(email="jobs@local.test", password_hash="unusable")
    db.add(user)
    db.commit()
    job = Job(user_id=user.id, resource_id="controlled", kind="scan")
    db.add(job)
    db.commit()
    db.add(Job(user_id=user.id, resource_id="controlled", kind="analyze"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    job.status = "SUCCEEDED"
    db.commit()
    db.add(Job(user_id=user.id, resource_id="controlled", kind="analyze"))
    db.commit()


def test_model_cache_preserves_schema_and_does_not_invent_usage(db, tmp_path, monkeypatch):
    import httpx

    from app.agents import models
    from app.core.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    user = User(email="cache@local.test", password_hash="unusable")
    db.add(user)
    db.commit()
    original = httpx.Client
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"result": "fixture"})}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    monkeypatch.setattr(models.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    messages = [{"role": "user", "content": "controlled cache fixture"}]
    assert models.complete(db, user.id, messages, cache=True) == models.complete(db, user.id, messages, cache=True)
    assert len(calls) == 1 and len(list(db.scalars(select(ModelUsage)))) == 1


def test_agent_recovers_after_rejecting_unapproved_file(db, tmp_path, monkeypatch):
    """Unit harness: model and container IO are explicitly replaced; not live evidence."""
    from app.agents import engine
    from app.core.config import settings

    monkeypatch.setattr(settings, "data_dir", tmp_path)
    user = User(email="retry@local.test", password_hash="unusable")
    db.add(user)
    db.flush()
    project = Project(user_id=user.id, name="Controlled unit fixture")
    db.add(project)
    db.flush()
    repo = Repository(project_id=project.id, full_name="unit/fixture", branch="main", sha="unit-sha")
    db.add(repo)
    db.flush()
    finding = Finding(repository_id=repo.id, scan_id="unit-only", fingerprint="unit", title="eval", severity="HIGH", data={"rule_id": "kyro.python.dynamic-eval"})
    # DB fixture uses metadata tables; this harness creates the referenced scan.
    from app.database import ScanRun
    scan = ScanRun(repository_id=repo.id, snapshot_sha="unit-sha")
    db.add(scan)
    db.flush()
    finding.scan_id = scan.id
    db.add(finding)
    db.flush()
    source = tmp_path / "repositories" / repo.id
    source.mkdir(parents=True)
    original = "value = 1\n"
    (source / "app.py").write_text(original, newline="")
    task = Remediation(repository_id=repo.id, finding_id=finding.id, state="AWAITING_APPROVAL", plan={"files": ["app.py"], "context_paths": ["app.py"], "file_hashes": {"app.py": digest(original)}, "commands": [{"kind": "test", "argv": ["python", "-m", "unittest"]}]}, approved_by=user.id)
    db.add(task)
    db.flush()
    task.approval_digest = engine.plan_digest(task, repo)
    db.commit()
    prompts = []
    def model(_db, _user, messages, *_args, **_kwargs):
        prompt = json.loads(messages[1]["content"])
        prompts.append(prompt)
        return {"summary": "Controlled test replacement", "changes": [{"path": "tests.py" if len(prompts) == 1 else "app.py", "before_hash": prompt["context"][0]["hash"], "content": "value = 2\n"}]}
    def apply(root, changes, *_args):
        for change in changes:
            (root / change["path"]).write_text(change["content"], newline="")
        return {"status": "PASSED"}
    monkeypatch.setattr(engine, "complete", model)
    monkeypatch.setattr(engine, "apply_patch", apply)
    monkeypatch.setattr(engine, "execute_command", lambda *_: {"status": "PASSED", "tests_executed": 1})
    monkeypatch.setattr(engine, "progress", lambda *_: None)
    outcome = engine.execute_fix(db, task, repo, user.id, "controlled-unit-job")
    assert outcome["state"] == "VERIFYING"
    assert task.evidence["attempts"][0]["status"] == "REJECTED"
    assert "approved file scope" in prompts[1]["previous_validation_errors"][0]
    assert not (engine.workspace(task) / "tests.py").exists()
    assert (source / "app.py").read_text() == original
