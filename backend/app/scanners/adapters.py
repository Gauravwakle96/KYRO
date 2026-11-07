import json
from pathlib import Path
from uuid import uuid4

from app.core.config import settings
from app.sandbox.runner import container_command, installed_image, managed_mount, process
from app.scanners.normalization import parse_osv, parse_semgrep, parse_trivy

RULES = Path(__file__).resolve().parents[2] / "rules" / "security.yml"


class ScannerAdapter:
    name: str
    image: str
    args: list[str]

    def __init__(self, name: str):
        self.name = name
        self.image = {"semgrep": settings.semgrep_image, "osv": settings.osv_image, "trivy": settings.trivy_image}[name]
        self.args = {
            "semgrep": ["semgrep", "scan", "--config", "/rules/security.yml", "--json", "--metrics", "off", "--disable-version-check", "--no-git-ignore", "/workspace"],
            "osv": ["scan", "source", "--recursive", "--format", "json", "/workspace"],
            "trivy": ["fs", "--scanners", "vuln", "--format", "json", "--exit-code", "0", "--cache-dir", "/cache", "/workspace"],
        }[name]

    def health(self) -> dict:
        if not installed_image(self.image):
            return {"scanner": self.name, "available": False, "image": self.image, "error": "Scanner image is not installed"}
        try:
            args = ["semgrep", "--version", "--disable-version-check", "--metrics", "off"] if self.name == "semgrep" else ["--version"]
            name = "kyro-health-" + uuid4().hex
            result = process(["docker", "run", "--rm", "--name", name, "--network", "none", "--read-only", "--cpus=1", "--memory=512m", "--pids-limit=128", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "--env", "HOME=/tmp", "--env", "SEMGREP_ENABLE_VERSION_CHECK=0", "--env", "SEMGREP_SEND_METRICS=off", "--env", "OTEL_SDK_DISABLED=true", "--cap-drop=ALL", "--security-opt=no-new-privileges", self.image, *args], 60, container=name)
            available = result["status"] == "COMPLETED" and result["exit_code"] == 0
            return {"scanner": self.name, "available": available, "image": self.image, "version": result["stdout"].strip()[:500], "error": (result["stderr"][:500] or result["status"]) if not available else None, "retryable": result["status"] == "TIMED_OUT"}
        except OSError as error:
            return {"scanner": self.name, "available": False, "image": self.image, "error": str(error)}

    def execute(self, root: Path, job_id: str | None = None) -> dict:
        health = self.health()
        if not health["available"]:
            return {"scanner": self.name, "status": "FAILED", "metadata": health, "findings": [], "retryable": health.get("retryable", False)}
        rule_mount = managed_mount(settings.data_dir / "rules", "/rules") if settings.workspace_volume else f"type=bind,src={RULES.parent},dst=/rules,readonly"
        mounts = [rule_mount] if self.name == "semgrep" else ["type=volume,src=kyro-trivy-cache,dst=/cache"] if self.name == "trivy" else []
        network = "none" if self.name == "semgrep" else settings.scanner_network
        argv, name = container_command(root, self.image, self.args, network=network, extra_mounts=mounts, extra_env={"TMPDIR": "/cache"} if self.name == "trivy" else {}, memory=1536 if self.name == "semgrep" else 1024)
        result = process(argv, settings.scanner_timeout, job_id, name)
        metadata = {**result, "version": health.get("version"), "image": self.image, "network": network}
        if self.name == "osv" and result["status"] == "COMPLETED" and result["exit_code"] == 128 and "No package sources found, --help for usage information." in result["stderr"]:
            return {"scanner": self.name, "status": "NOT_APPLICABLE", "metadata": {**metadata, "coverage": "NO_SUPPORTED_INPUTS", "error": "No supported dependency sources found; dependency coverage is unavailable"}, "findings": []}
        try:
            if result["status"] != "COMPLETED" or result["exit_code"] not in ({0, 1} if self.name == "osv" else {0}):
                raise ValueError(f"{self.name} execution failed: {result['status']} / exit {result['exit_code']}")
            data = json.loads(result["stdout"])
            findings = {"semgrep": parse_semgrep, "osv": parse_osv, "trivy": parse_trivy}[self.name](data)
            if self.name == "trivy" and not data.get("Results"):
                return {"scanner": self.name, "status": "NOT_APPLICABLE", "metadata": {**metadata, "coverage": "NO_SUPPORTED_INPUTS", "error": "No supported package files detected; dependency coverage is unavailable"}, "findings": findings}
            # Semgrep partial analysis errors mean incomplete coverage even if JSON is present.
            status = "PARTIAL" if self.name == "semgrep" and data.get("errors") else "SUCCEEDED"
            if status == "PARTIAL":
                metadata["error"] = f"Semgrep reported {len(data['errors'])} parsing/analysis errors; inspect raw scanner evidence for affected files"
            return {"scanner": self.name, "status": status, "metadata": metadata, "findings": findings}
        except (ValueError, KeyError, TypeError) as error:
            return {"scanner": self.name, "status": "FAILED", "metadata": {**metadata, "error": str(error)}, "findings": [], "retryable": result["status"] == "TIMED_OUT"}


ADAPTERS = [ScannerAdapter(name) for name in ["semgrep", "osv", "trivy"]]
