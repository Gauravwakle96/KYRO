from app.intelligence.assessment import risk_assessment
from app.repository.intelligence import dependencies, python_facts, tree_facts
from app.scanners.normalization import deduplicate, parse_osv, parse_semgrep, parse_trivy
from app.verification.engine import compare_findings, verification_status


def test_dependency_parsing():
    deps = dependencies("requirements.txt", "requests==2.19.1\nflask>=3\n-r other.txt\n#comment")
    assert deps[0]["version"] == "2.19.1"
    assert deps[1]["version"] is None
    assert len(deps) == 2


def test_python_call_relationships():
    facts = python_facts("import requests as r\nclass Service:\n def fetch(self):\n  return r.get('url')\n")
    assert facts["imports"][0]["alias"] == "r"
    assert facts["calls"][0]["name"] == "r.get"
    assert len(facts["symbols"]) == 2


def test_treesitter_typescript():
    facts = tree_facts("import axios from 'axios'; function load() { return axios.get('/'); }", ".ts")
    assert facts["symbols"][0]["name"] == "load"
    assert facts["imports"][0]["name"] == "axios"
    assert facts["calls"][0]["name"] == "axios.get"


def test_semgrep_contract():
    findings = parse_semgrep({"results": [{"check_id": "rule", "path": "/workspace/app.py", "start": {"line": 4}, "extra": {"message": "Unsafe eval", "severity": "ERROR"}}]})
    assert findings[0]["severity"] == "HIGH"
    assert findings[0]["file_path"] == "app.py"


def test_osv_contract():
    findings = parse_osv({"results": [{"source": {"path": "/workspace/requirements.txt"}, "packages": [{"package": {"name": "requests", "version": "2.19.1", "ecosystem": "PyPI"}, "groups": [{"ids": ["GHSA-test"], "max_severity": "7.5"}], "vulnerabilities": [{"id": "GHSA-test", "aliases": ["CVE-2024-12345"], "affected": [{"package": {"name": "requests"}, "ranges": [{"events": [{"fixed": "2.32.0"}]}]}]}]}]}]})
    assert findings[0]["cve"] == "CVE-2024-12345"
    assert findings[0]["fixed_version"] == "2.32.0"
    assert findings[0]["severity"] == "HIGH"


def test_dedup_preserves_provenance():
    a = {"scanner": "osv", "rule_id": "GHSA-test", "cve": "CVE-2024-1234", "title": "Vulnerability", "severity": "HIGH", "file_path": "requirements.txt", "package_name": "requests", "installed_version": "2.19.1", "evidence": {"source": "original"}}
    b = {**a, "scanner": "trivy", "rule_id": "CVE-2024-1234", "evidence": {"different": "original"}}
    result = deduplicate([a, b])
    assert len(result) == 1
    assert len(result[0]["provenance"]) == 2
    assert len(deduplicate([a, {**b, "installed_version": "2.20.0"}])) == 2


def test_risk_does_not_certify_no_reference():
    finding = {"severity": "HIGH", "cvss_score": 7.5}
    reach = {"category": "NO_REFERENCE_FOUND", "confidence": "LOW", "dependency_presence": []}
    risk = risk_assessment(finding, reach)
    assert risk["score"] == 65
    assert risk["raw_cvss"] == 7.5
    assert risk["confidence"] == "LOW"


def test_scan_output_errors_fail():
    import pytest
    for parser in [parse_semgrep, parse_osv, parse_trivy]:
        with pytest.raises(ValueError):
            parser({"invalid": []})


def test_verification_missing_tests_is_not_verified():
    state, _ = verification_status(original_resolved=True, new_findings=0, scanner_status="SUCCEEDED", baseline_status="SUCCEEDED", commands=[{"kind": "build", "status": "PASSED"}], has_tests=False, within_scope=True)
    assert state == "PARTIALLY_VERIFIED"


def test_verification_scanner_failure_is_inconclusive():
    state, _ = verification_status(original_resolved=True, new_findings=0, scanner_status="FAILED", baseline_status="SUCCEEDED", commands=[], has_tests=True, within_scope=True)
    assert state == "INCONCLUSIVE"


def test_verification_new_findings_fail():
    state, _ = verification_status(original_resolved=True, new_findings=1, scanner_status="SUCCEEDED", baseline_status="SUCCEEDED", commands=[], has_tests=True, within_scope=True)
    assert state == "FAILED"


def test_before_after_comparison():
    assert compare_findings([{"fingerprint": "a"}, {"fingerprint": "b"}], [{"fingerprint": "b"}, {"fingerprint": "c"}]) == {"resolved": ["a"], "remaining": ["b"], "introduced": ["c"], "before_count": 2, "after_count": 2}
