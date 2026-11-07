"""Check an empty deployment volume using actual HTTP and scanner containers."""
import json
import pathlib
import secrets
import urllib.request
from datetime import UTC, datetime

import live_acceptance

ROOT = pathlib.Path(__file__).resolve().parents[1]
live_acceptance.DATA = ROOT / "data" / "deployment-acceptance"
api = live_acceptance.API("http://127.0.0.1:8789")
api.login()
health = api.request("/health")
with urllib.request.urlopen("http://127.0.0.1:8789", timeout=20) as response:
    html = response.read().decode()
assert '<div id="root">' in html and '/assets/' in html
name = "Clean deployment fixture " + secrets.token_hex(4)
project = api.request("/projects", "POST", {"name": name, "description": "Explicit deployment test fixture"})
imported = api.request("/repositories/fixture?project_id=" + project["id"], "POST")
api.wait(imported["job"])
repo = api.request("/repositories/" + imported["repository"]["id"])
assert repo["status"] == "READY" and repo["source"] == "fixture" and repo["analysis"]["files"]
scanned = api.wait(api.request("/repositories/" + repo["id"] + "/scans", "POST"))
scan = api.request("/scans/" + scanned["result"]["scan_id"])
assert scan["status"] == "SUCCEEDED" and len(scan["executions"]) == 3
assert all(execution["status"] == "SUCCEEDED" for execution in scan["executions"])
report = {"created_at": datetime.now(UTC).isoformat(), "target": "Clean named volume kyro-clean-acceptance; local Compose overlay", "health": health, "frontend_served": True, "repository": repo, "scan": scan, "limitations": ["Authorized GitHub acceptance still requires credentials and an owned repository", "No public deployment performed", "Local model host gateway inference is checked separately from native loopback inference"]}
(ROOT / "docs" / "evidence" / "clean-deployment-acceptance.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print("Clean deployment: frontend, authentication, persistence, ingestion, indexing and three actual scanner containers passed")
