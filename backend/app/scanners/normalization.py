import re

from app.core.security import digest

LEVELS = {"ERROR": "HIGH", "WARNING": "MEDIUM", "INFO": "LOW", "CRITICAL": "CRITICAL", "HIGH": "HIGH", "MODERATE": "MEDIUM", "MEDIUM": "MEDIUM", "LOW": "LOW"}


def severity(value) -> str:
    if isinstance(value, (int, float)) or isinstance(value, str) and re.fullmatch(r"\d+(\.\d+)?", value):
        score = float(value)
        return "CRITICAL" if score >= 9 else "HIGH" if score >= 7 else "MEDIUM" if score >= 4 else "LOW"
    return LEVELS.get(str(value).upper(), "UNKNOWN")


def relative_path(value: str) -> str:
    value = value.replace("\\", "/")
    for prefix in ["/workspace/", "workspace/", "./"]:
        if value.startswith(prefix):
            value = value[len(prefix):]
    if value.startswith("/") or ".." in value.split("/"):
        return ""
    return value


def fingerprint(item: dict) -> str:
    identity = item.get("cve") or item.get("rule_id") or item["title"]
    # SCA aliases collapse only at the same manifest/package/version. SAST rules retain locations.
    fields = [identity, item.get("file_path", ""), item.get("package_name", ""), item.get("installed_version", "")]
    if not item.get("package_name"):
        fields.append(str(item.get("line_number", "")))
    return digest("|".join(str(v or "") for v in fields))


def parse_semgrep(data: dict) -> list[dict]:
    if "results" not in data or not isinstance(data["results"], list):
        raise ValueError("Semgrep output has no results array")
    result = []
    for match in data["results"]:
        extra = match.get("extra", {})
        meta = extra.get("metadata", {})
        result.append({"scanner": "semgrep", "rule_id": match["check_id"], "title": extra.get("message") or match["check_id"], "description": extra.get("message", ""), "severity": severity(extra.get("severity")), "file_path": relative_path(match.get("path", "")), "line_number": match.get("start", {}).get("line"), "cwe": meta.get("cwe", []), "confidence": meta.get("confidence", "MEDIUM"), "references": meta.get("references", []), "evidence": match, "cve": None, "cvss_score": None, "cvss_vector": None})
    return result


def parse_osv(data: dict) -> list[dict]:
    if "results" not in data or not isinstance(data["results"], (list, type(None))):
        raise ValueError("OSV output has no results array")
    result = []
    for source in data["results"] or []:
        for package in source.get("packages", []):
            info = package.get("package", {})
            for vuln in package.get("vulnerabilities", []):
                cve = next((alias for alias in [vuln["id"], *vuln.get("aliases", [])] if alias.startswith("CVE-")), None)
                fixes: list[str] = []
                for affected in vuln.get("affected", []):
                    if affected.get("package", {}).get("name") == info.get("name"):
                        fixes.extend(event["fixed"] for item in affected.get("ranges", []) for event in item.get("events", []) if "fixed" in event)
                group: dict = next((g for g in package.get("groups", []) if vuln["id"] in g.get("ids", [])), {})
                raw_severity = vuln.get("database_specific", {}).get("severity") or group.get("max_severity", "UNKNOWN")
                vector = next((s["score"] for s in vuln.get("severity", []) if s.get("type") in {"CVSS_V3", "CVSS_V4"}), None)
                result.append({"scanner": "osv", "rule_id": vuln["id"], "cve": cve, "aliases": vuln.get("aliases", []), "title": vuln.get("summary") or vuln["id"], "description": vuln.get("details", ""), "severity": severity(raw_severity), "cvss_vector": vector, "cvss_score": None, "file_path": relative_path(source.get("source", {}).get("path", "")), "package_name": info.get("name"), "installed_version": info.get("version"), "ecosystem": info.get("ecosystem"), "fixed_versions": list(dict.fromkeys(fixes)), "fixed_version": fixes[0] if len(fixes) == 1 else None, "affected": vuln.get("affected", []), "references": [r["url"] for r in vuln.get("references", [])], "cwe": vuln.get("database_specific", {}).get("cwe_ids", []), "confidence": "HIGH", "evidence": {"vulnerability": vuln, "package": info, "group": group}})
    return result


def parse_trivy(data: dict) -> list[dict]:
    # Trivy omits Results when it detects no supported package files. Validate
    # its report envelope so malformed/empty output never becomes a clean scan.
    if "Results" not in data:
        if data.get("SchemaVersion") != 2 or data.get("ArtifactType") != "filesystem" or not isinstance(data.get("ArtifactName"), str) or not data["ArtifactName"]:
            raise ValueError("Trivy output has no valid report envelope or Results array")
    elif not isinstance(data["Results"], (list, type(None))):
        raise ValueError("Trivy output has an invalid Results array")
    result = []
    for target in data.get("Results") or []:
        for vuln in target.get("Vulnerabilities") or []:
            cvss: dict = next(iter(vuln.get("CVSS", {}).values()), {})
            result.append({"scanner": "trivy", "rule_id": vuln["VulnerabilityID"], "cve": vuln["VulnerabilityID"] if vuln["VulnerabilityID"].startswith("CVE-") else None, "title": vuln.get("Title") or vuln["VulnerabilityID"], "description": vuln.get("Description", ""), "severity": severity(vuln.get("Severity")), "file_path": relative_path(target.get("Target", "")), "package_name": vuln.get("PkgName"), "installed_version": vuln.get("InstalledVersion"), "fixed_version": vuln.get("FixedVersion"), "cvss_score": cvss.get("V3Score"), "cvss_vector": cvss.get("V3Vector"), "cwe": vuln.get("CweIDs", []), "references": vuln.get("References", []), "confidence": "HIGH", "evidence": vuln})
    return result


def deduplicate(items: list[dict]) -> list[dict]:
    result: dict[str, dict] = {}
    rank = {"UNKNOWN": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    for item in items:
        key = fingerprint(item)
        provenance = {"scanner": item["scanner"], "rule_id": item["rule_id"], "evidence": item["evidence"]}
        if key not in result:
            result[key] = {**item, "fingerprint": key, "provenance": [provenance]}
        else:
            existing = result[key]
            existing["provenance"].append(provenance)
            if rank[item["severity"]] > rank[existing["severity"]]:
                existing["severity"] = item["severity"]
            existing["references"] = list(dict.fromkeys([*existing.get("references", []), *item.get("references", [])]))
            for field in ["cvss_score", "cvss_vector", "fixed_version"]:
                if not existing.get(field) and item.get(field):
                    existing[field] = item[field]
    return list(result.values())
