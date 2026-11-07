import io
import json
import tarfile

import httpx
import pytest

from app.core.config import settings
from app.database import ModelUsage, Repository, User
from app.integrations.github import GitHub, create_pull_request, extract_archive, validate_repository
from app.sandbox.runner import executed_tests, process
from app.scanners.adapters import ScannerAdapter


@pytest.fixture
def local_user(db):
    user = User(email="contracts@local.test", password_hash="unusable")
    db.add(user)
    db.commit()
    return user


def test_archive_content_and_secret_exclusion(tmp_path):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for name in ["root/app.py", "root/.env"]:
            info = tarfile.TarInfo(name)
            info.size = 4
            archive.addfile(info, io.BytesIO(b"safe"))
    extract_archive(stream.getvalue(), tmp_path)
    assert (tmp_path / "app.py").read_bytes() == b"safe"
    assert not (tmp_path / ".env").exists()


@pytest.mark.parametrize("name", ["owner/repo/extra", "../repo", "https://github.com/repo", "repo", "a/.."])
def test_repository_name_boundary(name):
    with pytest.raises(ValueError):
        validate_repository(name)


def github_fixture(handler):
    github = GitHub.__new__(GitHub)
    github.installation = False
    github.client = httpx.Client(base_url="https://api.github.com", transport=httpx.MockTransport(handler))
    return github


def test_github_api_error_reports_no_success():
    github = github_fixture(lambda request: httpx.Response(403, json={"message": "denied"}))
    with pytest.raises(RuntimeError, match="403"):
        github.request("POST", "/repos/controlled/test/pulls", json={})
    github.close()


def test_app_repository_listing_contract():
    github = github_fixture(lambda request: httpx.Response(200, json={"repositories": [{"full_name": "controlled/test", "private": True, "default_branch": "main", "language": "Python"}]}))
    github.installation = True
    assert github.repositories()[0]["full_name"] == "controlled/test"
    github.close()


def test_pr_parent_conflict_blocks_writes():
    calls = []
    def handler(request):
        calls.append(request.method)
        return httpx.Response(200, json={"object": {"sha": "changed"}})
    github = github_fixture(handler)
    repo = Repository(full_name="controlled/test", branch="main", sha="original")
    with pytest.raises(RuntimeError, match="Base branch changed"):
        create_pull_request(github, repo, "fixture", [], {}, {})
    assert calls == ["GET"]
    github.close()


def test_pr_requires_api_confirmed_result():
    paths = []
    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "original"}})
        if request.url.path.endswith("commits/original"):
            return httpx.Response(200, json={"tree": {"sha": "tree"}})
        if request.url.path.endswith("pulls"):
            assert json.loads(request.content)["draft"] is True
            return httpx.Response(201, json={"number": 1, "html_url": "https://github.com/controlled/test/pull/1", "state": "open", "draft": True})
        return httpx.Response(201, json={"sha": "created"})
    github = github_fixture(handler)
    repo = Repository(full_name="controlled/test", branch="main", sha="original")
    pr = create_pull_request(github, repo, "fixture", [{"path": "app.py", "content": "safe"}], {"status": "VERIFIED"}, {"title": "fixture", "root_cause": "controlled unit fixture", "strategy": "test API contract"})
    assert pr["number"] == 1 and pr["draft"]
    assert paths[-1].endswith("pulls")
    github.close()


def test_model_reports_real_contract_usage(db, local_user, monkeypatch):
    from app.agents import models
    original = httpx.Client
    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == settings.local_model
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"fixture":"structured"}'}}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    monkeypatch.setattr(models.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    value = models.complete(db, local_user.id, [{"role": "user", "content": "controlled unit fixture"}])
    assert value == {"fixture": "structured"}
    from sqlalchemy import select
    usage = db.scalar(select(ModelUsage))
    assert usage.input_tokens == 10 and usage.output_tokens == 5
    assert usage.estimated_cost == 0 and usage.provider == "local"


def test_model_bad_json_logs_failure(db, local_user, monkeypatch):
    from app.agents import models
    original = httpx.Client
    monkeypatch.setattr(models.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"choices": [{"message": {"content": "invalid"}}]})), **kwargs))
    with pytest.raises(ValueError):
        models.complete(db, local_user.id, [{"role": "user", "content": "unit fixture"}])
    from sqlalchemy import select
    usage = db.scalar(select(ModelUsage))
    assert usage.status == "FAILED" and usage.input_tokens is None


def test_token_budget_blocks_before_request(db, local_user, monkeypatch):
    from app.agents import models
    monkeypatch.setattr(settings, "agent_token_budget", 2)
    with pytest.raises(ValueError, match="token budget"):
        models.complete(db, local_user.id, [{"role": "user", "content": "too much context"}], "task")


def test_scanner_timeout_does_not_become_success(monkeypatch, tmp_path):
    import app.scanners.adapters as adapters
    adapter = ScannerAdapter("osv")
    monkeypatch.setattr(adapter, "health", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr(adapters, "container_command", lambda *args, **kwargs: (["controlled-fixture"], "fixture"))
    monkeypatch.setattr(adapters, "process", lambda *args, **kwargs: {"status": "TIMED_OUT", "exit_code": -9, "stdout": '{"results":[]}', "stderr": "timeout"})
    assert adapter.execute(tmp_path)["status"] == "FAILED"


def test_semgrep_partial_errors_stay_partial(monkeypatch, tmp_path):
    import app.scanners.adapters as adapters
    adapter = ScannerAdapter("semgrep")
    monkeypatch.setattr(adapter, "health", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr(adapters, "container_command", lambda *args, **kwargs: (["controlled-fixture"], "fixture"))
    monkeypatch.setattr(adapters, "process", lambda *args, **kwargs: {"status": "COMPLETED", "exit_code": 0, "stdout": '{"results":[],"errors":[{"message":"partial"}]}', "stderr": ""})
    assert adapter.execute(tmp_path)["status"] == "PARTIAL"


def test_trivy_valid_no_input_report_is_not_a_parser_failure(monkeypatch, tmp_path):
    import app.scanners.adapters as adapters
    adapter = ScannerAdapter("trivy")
    monkeypatch.setattr(adapter, "health", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr(adapters, "container_command", lambda *args, **kwargs: (["controlled-fixture"], "fixture"))
    envelope = {"SchemaVersion": 2, "ArtifactName": "/workspace", "ArtifactType": "filesystem"}
    monkeypatch.setattr(adapters, "process", lambda *args, **kwargs: {"status": "COMPLETED", "exit_code": 0, "stdout": json.dumps(envelope), "stderr": ""})
    result = adapter.execute(tmp_path)
    assert result["status"] == "NOT_APPLICABLE" and result["findings"] == []
    assert result["metadata"]["coverage"] == "NO_SUPPORTED_INPUTS"


@pytest.mark.parametrize("output", [{}, {"SchemaVersion": 2}, {"Results": "invalid"}])
def test_trivy_malformed_output_remains_an_error(output):
    from app.scanners.normalization import parse_trivy
    with pytest.raises(ValueError):
        parse_trivy(output)


def test_osv_no_supported_sources_keeps_coverage_unavailable(monkeypatch, tmp_path):
    import app.scanners.adapters as adapters
    adapter = ScannerAdapter("osv")
    monkeypatch.setattr(adapter, "health", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr(adapters, "container_command", lambda *args, **kwargs: (["controlled-fixture"], "fixture"))
    monkeypatch.setattr(adapters, "process", lambda *args, **kwargs: {"status": "COMPLETED", "exit_code": 128, "stdout": "", "stderr": "No package sources found, --help for usage information."})
    result = adapter.execute(tmp_path)
    assert result["status"] == "NOT_APPLICABLE" and result["metadata"]["exit_code"] == 128


def test_osv_other_exit_128_does_not_hide_a_failure(monkeypatch, tmp_path):
    import app.scanners.adapters as adapters
    adapter = ScannerAdapter("osv")
    monkeypatch.setattr(adapter, "health", lambda: {"available": True, "version": "fixture"})
    monkeypatch.setattr(adapters, "container_command", lambda *args, **kwargs: (["controlled-fixture"], "fixture"))
    monkeypatch.setattr(adapters, "process", lambda *args, **kwargs: {"status": "COMPLETED", "exit_code": 128, "stdout": "", "stderr": "Unsupported argument"})
    assert adapter.execute(tmp_path)["status"] == "FAILED"


@pytest.mark.parametrize("output,count", [("Ran 0 tests in 0s", 0), ("Ran 4 tests in .1s", 4), ("7 passed in 1s", 7), ("running 3 tests\nrunning 0 tests", 3), ("no tests ran", 0), ("success", None)])
def test_no_test_execution_is_not_a_pass(output, count):
    assert executed_tests(output) == count


def test_process_timeout_actual():
    import sys
    result = process([sys.executable, "-c", "import time; time.sleep(5)"], 1)
    assert result["status"] == "TIMED_OUT" and result["exit_code"] != 0
