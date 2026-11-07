import difflib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.engine import transition, workspace
from app.core.config import settings
from app.core.security import digest, safe_path
from app.database import Finding, Remediation, Repository, ScannerExecution, now
from app.jobs.worker import progress
from app.sandbox.runner import execute_command
from app.scanners.normalization import deduplicate
from app.scanners.service import scan_repository


def compare_findings(before: list[dict], after: list[dict]) -> dict:
    old = {item["fingerprint"] for item in before}
    new = {item["fingerprint"] for item in after}
    return {"resolved": sorted(old - new), "remaining": sorted(old & new), "introduced": sorted(new - old), "before_count": len(old), "after_count": len(new)}


def verification_status(*, original_resolved: bool, new_findings: int, scanner_status: str, commands: list[dict], has_tests: bool, within_scope: bool, baseline_status: str) -> tuple[str, list[str]]:
    limitations = []
    if not within_scope or any(command["status"] == "FAILED" for command in commands) or new_findings:
        return "FAILED", ["Patch scope, test failure or new security findings failed the quality gate."]
    if scanner_status == "FAILED" or baseline_status != "SUCCEEDED":
        return "INCONCLUSIVE", ["A complete baseline and independent scanner run are required."]
    if not original_resolved:
        return "FAILED", ["The original finding remains in independent scanner results."]
    kinds = {command["kind"] for command in commands if command["status"] == "PASSED"}
    if not has_tests or not kinds.intersection({"test", "regression"}):
        limitations.append("No existing test suite ran successfully; missing tests are not a pass.")
    if "build" not in kinds:
        limitations.append("No build command ran successfully.")
    if scanner_status != "SUCCEEDED":
        limitations.append("At least one scanner has incomplete coverage.")
    if limitations:
        return "PARTIALLY_VERIFIED", limitations
    return "VERIFIED", ["Passing scans and tests do not prove absence of all security defects.", "Runtime exploitability and deployments were not tested."]


def tree_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Workspace contains a symlink")
        if path.is_file() and not any(p in {"__pycache__", ".pytest_cache", "node_modules", ".git"} for p in path.parts):
            hashes[path.relative_to(root).as_posix()] = digest(path.read_bytes())
    return hashes


def verify(db: Session, task: Remediation, repo: Repository, finding: Finding, job_id: str) -> dict:
    if not task.evidence.get("changes"):
        raise ValueError("No executed patch available")
    if task.state != "VERIFYING":
        transition(db, task, "VERIFYING", job_id)
    source = workspace(task)
    base = tree_hashes(settings.data_dir / "repositories" / repo.id)
    commands = []
    for command in task.plan["commands"]:
        progress(job_id, "Independent " + command["kind"], {"command": command["argv"]})
        commands.append(execute_command(source, command, job_id))
    updated = tree_hashes(source)
    changed = {path for path in set(base) | set(updated) if base.get(path) != updated.get(path)}
    approved = set(task.plan["files"])
    within_scope = changed <= approved
    executed_hashes = {change["path"]: digest(change["content"]) for change in task.evidence["changes"]}
    patch_unchanged_by_tests = all(updated.get(path) == hash_value for path, hash_value in executed_hashes.items())
    within_scope = within_scope and patch_unchanged_by_tests
    rescan = scan_repository(db, repo, source, job_id, purpose="verification")
    baseline_executions = list(db.scalars(select(ScannerExecution).where(ScannerExecution.scan_id == finding.scan_id)))
    baseline = deduplicate([item for execution in baseline_executions for item in execution.normalized])
    baseline_status = "SUCCEEDED" if len(baseline_executions) == 3 and all(ex.status == "SUCCEEDED" for ex in baseline_executions) else "PARTIAL"
    comparison = compare_findings(baseline, rescan["findings"])
    # Rule/location shifts must not count as remediation; compare semantic identities for the target too.
    target = finding.data
    remains = any((item.get("cve") or item.get("rule_id")) == (target.get("cve") or target.get("rule_id")) and item.get("file_path") == target.get("file_path") and item.get("package_name") == target.get("package_name") for item in rescan["findings"])
    status, limitations = verification_status(original_resolved=not remains, new_findings=len(comparison["introduced"]), scanner_status=rescan["status"], commands=commands, has_tests=bool(repo.analysis.get("tests")), within_scope=within_scope, baseline_status=baseline_status)
    # Re-read changes from disk after commands; never deliver stale agent claims.
    actual_changes = [{"path": path, "content": safe_path(source, path, allow_new=False).read_text(encoding="utf-8"), "verified_hash": updated[path]} for path in sorted(changed & approved) if path in updated]
    actual_diff = "\n".join("".join(difflib.unified_diff(safe_path(settings.data_dir / "repositories" / repo.id, item["path"]).read_text(encoding="utf-8").splitlines(keepends=True), item["content"].splitlines(keepends=True), fromfile="a/" + item["path"], tofile="b/" + item["path"])) for item in actual_changes)
    report = {"status": status, "created_at": now(), "original_finding": {"id": finding.id, "title": finding.title, "data": finding.data}, "root_cause": task.plan["root_cause"], "changed_files": sorted(changed), "diff": actual_diff, "commands": commands, "baseline_status": baseline_status, "security_scan": {"scan_id": rescan["scan_id"], "status": rescan["status"], "scanners": rescan["scanners"]}, "comparison": comparison, "new_findings": [item for item in rescan["findings"] if item["fingerprint"] in comparison["introduced"]], "original_resolved": not remains, "patch_quality": {"within_scope": within_scope, "patch_unchanged_by_tests": patch_unchanged_by_tests, "modified_files": len(changed), "dependency_compatibility": "Tested only by recorded commands", "root_cause_review": "Plan and diff available for human review"}, "limitations": limitations, "verified_changes": actual_changes}
    task.verification = report
    transition(db, task, "SUCCEEDED" if status == "VERIFIED" else "FAILED" if status == "FAILED" else "INCONCLUSIVE", job_id)
    return {"remediation_id": task.id, "status": status}
