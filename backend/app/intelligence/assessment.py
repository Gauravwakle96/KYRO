from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import FileRecord, Repository


def reachability(db: Session, repo: Repository, finding: dict) -> dict:
    evidence = []
    package = finding.get("package_name")
    if not package:
        if finding.get("file_path") and finding.get("line_number"):
            evidence.append({"file": finding["file_path"], "line": finding["line_number"], "kind": "scanner_reference", "source": finding["scanner"]})
            category = "CONFIRMED_REFERENCE"
        else:
            category = "UNKNOWN"
    else:
        aliases = {package.lower().replace("-", "_"), package.lower()}
        category = "NO_REFERENCE_FOUND"
        for record in db.scalars(select(FileRecord).where(FileRecord.repository_id == repo.id)):
            for imp in record.facts.get("imports", []):
                module = imp["name"].lower()
                if module.split(".")[0] not in aliases and module not in aliases and not any(module.startswith(alias + "/") for alias in aliases):
                    continue
                evidence.append({"file": record.path, "line": imp["line"], "kind": "dependency_import", "name": imp["name"]})
                imported_alias = imp.get("alias", module.split(".")[0])
                calls = [call for call in record.facts.get("calls", []) if call["name"] == imported_alias or call["name"].startswith(imported_alias + ".")]
                evidence.extend({"file": record.path, "line": call["line"], "kind": "dependency_call", "name": call["name"]} for call in calls)
                if calls:
                    category = "POTENTIAL_REACHABILITY"
                elif category != "POTENTIAL_REACHABILITY":
                    category = "INFERRED_REACHABILITY"
    installed = [dep for dep in repo.analysis.get("dependencies", []) if dep["name"].lower().replace("-", "_") == str(package).lower().replace("-", "_")]
    return {"category": category, "evidence": evidence, "dependency_presence": installed, "confidence": "HIGH" if category == "CONFIRMED_REFERENCE" else "MEDIUM" if evidence else "LOW", "limitations": ["Static evidence does not prove runtime exploitability or absence of risk.", "Package imports and calls do not identify a vulnerable function without advisory-level function metadata.", "Transitive imports, reflection, aliases and injected dependencies can be missed."]}


def risk_assessment(finding: dict, reach: dict, intelligence: dict | None = None) -> dict:
    intelligence = intelligence or {}
    base = {"CRITICAL": 80, "HIGH": 65, "MEDIUM": 40, "LOW": 20, "UNKNOWN": 30}.get(finding["severity"], 30)
    factors = [{"factor": "Scanner severity", "points": base, "evidence": finding["severity"]}]
    score = base
    bonus = {"CONFIRMED_REFERENCE": 10, "POTENTIAL_REACHABILITY": 6, "INFERRED_REACHABILITY": 3}.get(reach["category"], 0)
    if bonus:
        factors.append({"factor": "Static reference evidence", "points": bonus, "evidence": reach["category"]})
        score += bonus
    if reach.get("dependency_presence"):
        factors.append({"factor": "Dependency declared in repository", "points": 5, "evidence": reach["dependency_presence"]})
        score += 5
    if intelligence.get("kev") is True:
        factors.append({"factor": "CISA known exploited catalog", "points": 10, "evidence": intelligence.get("kev_source")})
        score += 10
    epss = intelligence.get("epss")
    if epss is not None and epss >= 0.5:
        factors.append({"factor": "EPSS >= 0.5", "points": 8, "evidence": epss})
        score += 8
    return {"score": min(score, 100), "model_version": "kyro-risk-1", "priority": "URGENT" if score >= 80 else "HIGH" if score >= 60 else "NORMAL" if score >= 35 else "LOW", "factors": factors, "raw_cvss": finding.get("cvss_score"), "confidence": reach["confidence"], "limitations": ["KYRO priority is separate from CVSS.", "Exposure and mitigations are unknown unless verified by a reviewer.", "No reference found does not lower severity or certify safety.", "EPSS and KEV do not establish application-specific exploitability."]}


def attack_graph(db: Session, repo: Repository, findings: list) -> dict:
    nodes = [{"id": repo.id, "type": "repository", "label": repo.full_name}]
    edges = []
    node_ids = {repo.id}
    for finding in findings:
        nodes.append({"id": finding.id, "type": "finding", "label": finding.title, "severity": finding.severity})
        edges.append({"source": repo.id, "target": finding.id, "type": "AFFECTED_BY", "evidence": {"scan_id": finding.scan_id}})
        for evidence in finding.reachability.get("evidence", []):
            file_id = "file:" + evidence["file"]
            if file_id not in node_ids:
                node_ids.add(file_id)
                nodes.append({"id": file_id, "type": "file", "label": evidence["file"]})
                edges.append({"source": repo.id, "target": file_id, "type": "CONTAINS", "evidence": {"index": "repository_files"}})
            edges.append({"source": file_id, "target": finding.id, "type": "REFERENCES", "evidence": evidence})
    return {"nodes": nodes, "edges": edges, "limitations": ["Edges represent recorded references, not a proven exploit chain."]}
