"""Real fixture acceptance through the running HTTP API. Never publishes external changes."""
import argparse
import json
import pathlib
import secrets
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "acceptance"
EVIDENCE = ROOT / "docs" / "evidence"


class API:
    def __init__(self, base):
        self.base = base
        self.csrf = ""
        self.client = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))

    def request(self, path, method="GET", body=None):
        payload = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json", "X-CSRF-Token": self.csrf}
        request = urllib.request.Request(self.base + "/api" + path, data=payload, headers=headers, method=method)
        try:
            with self.client.open(request, timeout=90) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            raise RuntimeError(f"{path} HTTP {error.code}: {error.read().decode()[:1500]}") from error

    def login(self):
        DATA.mkdir(parents=True, exist_ok=True)
        login_file = DATA / "test-login.json"
        if not login_file.exists():
            credentials = {"email": "acceptance@kyro.local", "password": secrets.token_urlsafe(32)}
            login_file.write_text(json.dumps(credentials), encoding="utf-8")
        credentials = json.loads(login_file.read_text(encoding="utf-8"))
        setup = self.request("/auth/setup")
        result = self.request("/auth/register" if setup["setup_required"] else "/auth/login", "POST", credentials)
        self.csrf = result["csrf_token"]

    def wait(self, job):
        job_id = job["id"]
        seen = 0
        started = time.monotonic()
        while time.monotonic() - started < 1800:
            record = self.request("/jobs/" + job_id)
            for event in record["events"][seen:]:
                print(event["message"], flush=True)
            seen = len(record["events"])
            if record["status"] not in {"PENDING", "RUNNING"}:
                (EVIDENCE / f"job-{job_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
                if record["status"] != "SUCCEEDED":
                    raise RuntimeError(record["error"])
                return record
            time.sleep(2)
        raise TimeoutError("Acceptance job exceeded 1800 seconds")


def main():
    global DATA, EVIDENCE
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["scan", "plan", "execute", "verify", "all"], default="all")
    parser.add_argument("--url", default="http://127.0.0.1:8788")
    parser.add_argument("--data-dir", type=pathlib.Path, default=DATA,
                        help="Isolated credentials and workflow state for the selected test server")
    parser.add_argument("--evidence-dir", type=pathlib.Path, default=EVIDENCE,
                        help="Directory for actual execution reports; use a separate directory per acceptance target")
    args = parser.parse_args()
    DATA, EVIDENCE = args.data_dir.resolve(), args.evidence_dir.resolve()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    api = API(args.url)
    api.login()
    state_path = DATA / "workflow.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    def save():
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    if args.phase in {"scan", "all"}:
        health = api.request("/scanners")
        (EVIDENCE / "scanner-readiness.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
        print("Scanner readiness:", [(s["scanner"], s["available"]) for s in health["scanners"]], flush=True)
        if "repository_id" not in state:
            project = api.request("/projects", "POST", {"name": "Controlled acceptance benchmark", "description": "Explicit test fixture; actual scans and local inference"})
            result = api.request("/repositories/fixture?project_id=" + project["id"], "POST")
            api.wait(result["job"])
            state.update(project_id=project["id"], repository_id=result["repository"]["id"])
            save()
        repo = api.request("/repositories/" + state["repository_id"])
        if repo["source"] != "fixture":
            raise RuntimeError("Automatic acceptance approvals are restricted to controlled fixtures")
        job = api.request("/repositories/" + repo["id"] + "/scans", "POST")
        result = api.wait(job)
        state["scan_id"] = result["result"]["scan_id"]
        scan = api.request("/scans/" + state["scan_id"])
        (EVIDENCE / "live-baseline-scan.json").write_text(json.dumps(scan, indent=2), encoding="utf-8")
        findings = api.request("/findings?repository_id=" + repo["id"])
        selected = next((f for f in findings if f["data"]["scanner"] == "semgrep" and "dynamic-eval" in f["data"]["rule_id"]), None)
        if selected is None:
            raise RuntimeError("Real Semgrep did not report the expected controlled eval finding")
        state["finding_id"] = selected["id"]
        save()
        print("Live baseline:", scan["status"], "findings:", len(findings), flush=True)
    if args.phase in {"plan", "all"}:
        health = api.request("/models")
        (EVIDENCE / "model-readiness.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
        print("Local model:", health["selected"], "available:", health["available"], flush=True)
        result = api.request("/findings/" + state["finding_id"] + "/remediation", "POST")
        state["remediation_id"] = result["remediation"]["id"]
        save()
        api.wait(result["job"])
        task = api.request("/remediation/" + state["remediation_id"])
        (EVIDENCE / "live-remediation-plan.json").write_text(json.dumps(task, indent=2), encoding="utf-8")
        print("Actual plan:", task["plan"]["title"], flush=True)
    if args.phase in {"execute", "all"}:
        task = api.request("/remediation/" + state["remediation_id"])
        repo = api.request("/repositories/" + task["repository_id"])
        if repo["source"] != "fixture":
            raise RuntimeError("Automatic acceptance approval is limited to labelled fixtures")
        if not task.get("approved_by"):
            api.request("/remediation/" + task["id"] + "/approve", "POST", {"approved": True, "plan_digest": task["plan_digest"]})
        try:
            api.wait(api.request("/remediation/" + task["id"] + "/execute", "POST"))
        finally:
            task = api.request("/remediation/" + task["id"])
            (EVIDENCE / "live-agent-execution.json").write_text(json.dumps(task, indent=2), encoding="utf-8")
        print("Agent outcome:", task["state"], flush=True)
        if task["state"] != "VERIFYING":
            raise RuntimeError("Agent tests did not pass; inspect captured execution evidence")
    if args.phase in {"verify", "all"}:
        api.wait(api.request("/remediation/" + state["remediation_id"] + "/verify", "POST"))
        report = api.request("/remediation/" + state["remediation_id"] + "/report")
        (EVIDENCE / "live-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("Independent verification:", report["status"], report["comparison"], flush=True)
        (EVIDENCE / "model-readiness.json").write_text(json.dumps(api.request("/models"), indent=2), encoding="utf-8")
        (EVIDENCE / "live-agent-final.json").write_text(json.dumps(api.request("/remediation/" + state["remediation_id"]), indent=2), encoding="utf-8")
        if report["status"] != "VERIFIED":
            raise RuntimeError(f"Independent verification did not pass; inspect {EVIDENCE / 'live-verification.json'}")
    print("Acceptance phase completed:", args.phase, flush=True)


if __name__ == "__main__":
    main()
