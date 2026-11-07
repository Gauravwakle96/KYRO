"""Actual restart recovery in the dedicated local acceptance deployment.

Generates labelled source fixtures, interrupts their real indexing job, and
checks automatic recovery without issuing a retry or modifying user projects.
"""
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

import live_acceptance

ROOT = Path(__file__).resolve().parents[1]
CONTAINER = "kyro-clean-acceptance-kyro-1"


def main():
    identity = subprocess.check_output(["docker", "inspect", CONTAINER, "--format", '{{index .Config.Labels "com.docker.compose.project"}}'], text=True).strip()
    if identity != "kyro-clean-acceptance":
        raise RuntimeError("Recovery test is restricted to the dedicated acceptance deployment")
    live_acceptance.DATA = ROOT / "data/deployment-acceptance"
    api = live_acceptance.API("http://127.0.0.1:8789")
    api.login()
    policy = api.request("/settings")["automatic_recovery"]
    assert policy["enabled"] and policy["max_attempts"] == 3
    project = api.request("/projects", "POST", {"name": "Automatic recovery acceptance", "description": "Labelled synthetic fixture; real restart and indexing recovery"})
    connected = api.request("/repositories/fixture?project_id=" + project["id"], "POST")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        imported = api.request("/jobs/" + connected["job"]["id"])
        if imported["status"] == "SUCCEEDED":
            break
        if imported["status"] in {"FAILED", "CANCELLED", "INCONCLUSIVE"}:
            raise RuntimeError("Controlled fixture import failed")
        time.sleep(0.2)
    else:
        raise TimeoutError("Controlled fixture import timed out")
    repo_id = connected["repository"]["id"]
    script = r'''
import sys
from app.database import SessionLocal, Repository
from app.agents.engine import snapshot
from app.core.security import digest
with SessionLocal() as db:
    repo = db.get(Repository, sys.argv[1])
    if repo is None or repo.source != 'fixture':
        raise ValueError('Fault injection is restricted to labelled fixtures')
    root = snapshot(repo)
    directory = root / 'recovery_fixture'
    directory.mkdir()
    for index in range(1500):
        (directory / f'function_{index:04d}.py').write_text(f'def function_{index}():\n    return {index}\n'.replace('\\n','\n'), encoding='utf-8')
    code = '\n' * 300 + "import React from 'react';\n"
    for index in range(600):
        code += f'export function component{index}() {{\n return <div>{{helper()}}</div>;\n}}\n'
    (directory / 'large.tsx').write_text(code.replace('\\n','\n'), encoding='utf-8')
    repo.sha = digest('Controlled recovery stress fixture: 1500 Python functions and 600 TSX symbols')
    db.commit()
'''
    completed = subprocess.run(["docker", "exec", CONTAINER, "python", "-c", script, repo_id], capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError("Preparing labelled recovery source failed; inspect private diagnostics")
    queued = api.request("/repositories/" + repo_id + "/analyze", "POST")
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        before = api.request("/jobs/" + queued["id"])
        if before["status"] == "RUNNING" and len(before["events"]) >= 5:
            break
        if before["status"] not in {"PENDING", "RUNNING"}:
            raise RuntimeError("Indexing finished before fault injection; no restart recovery is claimed")
        time.sleep(0.02)
    else:
        raise TimeoutError("Indexing did not begin for recovery test")
    print("Interrupting the actual acceptance indexing job; user deployment is untouched", flush=True)
    subprocess.run(["docker", "restart", "--time", "0", CONTAINER], check=True, capture_output=True, text=True)
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        try:
            api.request("/health")
            break
        except Exception:
            time.sleep(0.5)
    else:
        raise TimeoutError("Acceptance deployment did not restart")
    while time.monotonic() < deadline:
        after = api.request("/jobs/" + queued["id"])
        if after["status"] == "SUCCEEDED":
            break
        if after["status"] not in {"PENDING", "RUNNING"}:
            raise RuntimeError("Recovery did not succeed: " + str(after["error"]))
        time.sleep(0.2)
    else:
        raise TimeoutError("Automatic indexing recovery timed out")
    recovered = api.request("/repositories/" + repo_id)
    metadata = after["payload"]["automatic_recovery"]
    assert recovered["status"] == "READY"
    assert metadata["attempt"] == 2
    assert metadata["history"][0]["recovery"] == "resume_read_operation"
    assert after["started_at"] == before["started_at"]
    assert len(recovered["analysis"]["files"]) == 1504
    assert recovered["analysis"]["errors"] == []
    symbols = api.request("/repository-intelligence/" + repo_id)
    large = next(record for record in symbols if record["path"] == "recovery_fixture/large.tsx")
    assert len(large["symbols"]) == 600 and large["symbols"][-1]["line"] > 256
    ids = {"repository_id": repo_id, "analysis_job_id": queued["id"], "indexed_files": 1504}
    (live_acceptance.DATA / "recovery-ids.json").write_text(json.dumps(ids, indent=2), encoding="utf-8")
    evidence = {"checked_at": datetime.now(UTC).isoformat(), "target": "Dedicated local acceptance instance at 8789", "fixture": "1500 generated Python files, 600 TSX symbols and original vulnerable arithmetic fixture", "fault": "Actual abrupt container restart while a persistent indexing job was RUNNING", "manual_retry_issued": False, "user_repositories_modified": False, "cloud_requests_issued": False, "policy": policy, "before": before, "after": after, "repository_id": repo_id, "indexed_files": len(recovered["analysis"]["files"]), "status": "PASSED"}
    (ROOT / "docs/evidence/live-automatic-recovery.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Automatic restart recovery PASSED: same job, attempt 2, 1504 real indexed files, no manual retry", flush=True)


if __name__ == "__main__":
    main()
