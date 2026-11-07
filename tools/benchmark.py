"""Summarize captured measurements with explicit, narrow denominators."""
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "evidence"


def read(name):
    path = EVIDENCE / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


baseline = read("live-baseline-scan.json")
task = read("live-agent-execution.json")
final_task = read("live-agent-final.json")
verification = read("live-verification.json")
rejected = read("live-verification-rejected-eval.json")
security = read("live-security-checks.json")
model = read("model-readiness.json")
if not all([baseline, task, verification]):
    raise SystemExit("Run the real acceptance suite first; missing measurements cannot be synthesized")
raw = [finding for execution in baseline["executions"] for finding in execution["normalized"]]
positive = any("dynamic-eval" in finding.get("rule_id", "") for finding in raw)
usage = [record for record in (model or {}).get("usage", []) if record.get("remediation_id") == task["id"]]
commands = verification["commands"]
report = {
    "created_at": datetime.now(UTC).isoformat(),
    "corpus": {"repositories": 1, "label": "Explicit controlled KYRO arithmetic fixture", "snapshot_sha": baseline["snapshot_sha"], "selected_remediation_id": task["id"]},
    "detection": {"labelled_source_positives": 1, "detected_labelled_source_positives": int(positive), "selected_source_recall": int(positive), "precision": None, "false_positive_rate": None, "reason": "Dependency advisories lack independent corpus labels; no general precision/recall claim", "raw_findings": len(raw), "normalized_before": verification["comparison"]["before_count"], "scanner_executions": [{"scanner": execution["scanner"], "status": execution["status"], "duration_seconds": execution["metadata_json"].get("duration_seconds"), "version": execution["metadata_json"].get("version")} for execution in baseline["executions"]]},
    "engineering": {"selected_task_completed": final_task["state"] == "SUCCEEDED" if final_task and final_task["id"] == task["id"] else None, "patch_files": len(task["evidence"].get("changes", [])), "attempts": task["evidence"].get("attempts", []), "commands": [{key: command.get(key) for key in ["kind", "status", "duration_seconds", "tests_executed"]} for command in commands]},
    "verification": {"status": verification["status"], "original_resolved": verification["original_resolved"], "introduced_findings": len(verification["comparison"]["introduced"]), "normalized_after": verification["comparison"]["after_count"], "known_insecure_eval_patch_result": rejected["status"] if rejected else None, "false_verified_eval_cases": int(rejected["status"] == "VERIFIED") if rejected else None, "insecure_eval_case_denominator": 1 if rejected else 0, "independent_security_regression": (security or {}).get("independent_security_regression", {}).get("status")},
    "cost": {"provider_requests_for_selected_task": len(usage), "reported_input_tokens": sum(record.get("input_tokens") or 0 for record in usage), "reported_output_tokens": sum(record.get("output_tokens") or 0 for record in usage), "missing_usage_records": sum(record.get("input_tokens") is None or record.get("output_tokens") is None for record in usage), "local_request_seconds": sum(record["duration_seconds"] for record in usage if record["provider"] == "local"), "cloud_requests": sum(record["provider"] != "local" for record in usage), "estimated_api_cost": sum(record["estimated_cost"] or 0 for record in usage), "local_compute_cost": None},
    "limitations": ["A single selected task cannot establish general remediation reliability", "One known insecure patch cannot establish a general false-verification rate", "No competitor comparison performed", "Local energy/hardware cost was not measured", "Missing usage stays excluded rather than estimated"]
}
(EVIDENCE / "benchmark-results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"verification": report["verification"], "cost": report["cost"]}, indent=2))
