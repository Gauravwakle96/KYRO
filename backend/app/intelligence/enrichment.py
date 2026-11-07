import json
import re
import time
from urllib.parse import quote

import httpx

from app.core.config import settings
from app.core.security import digest
from app.database import now
from app.jobs.recovery import transient


def cached_fetch(url: str, ttl=86400) -> dict:
    cache = settings.data_dir / "intelligence-cache"
    cache.mkdir(exist_ok=True)
    path = cache / (digest(url) + ".json")
    if path.exists() and time.time() - path.stat().st_mtime < ttl:
        return json.loads(path.read_text(encoding="utf-8"))
    with httpx.Client(timeout=20, trust_env=False) as client:
        for attempt in range(2):
            response = client.get(url)
            if response.status_code in {429, 502, 503} and attempt == 0:
                time.sleep(1)
                continue
            response.raise_for_status()
            if len(response.content) > 15_000_000:
                raise ValueError("Intelligence response exceeded size limit")
            data = {"source": url, "retrieved_at": now(), "data": response.json()}
            path.write_text(json.dumps(data), encoding="utf-8")
            return data
    raise RuntimeError("Intelligence service unavailable")


def enrich(finding: dict) -> dict:
    result: dict = {"sources": [], "errors": [], "epss": None, "kev": None, "cvss": None}
    advisory = finding.get("rule_id", "")
    if re.fullmatch(r"(?:GHSA|PYSEC|CVE|RUSTSEC|GO)-[A-Za-z0-9-]+", advisory):
        try:
            source = cached_fetch("https://api.osv.dev/v1/vulns/" + quote(advisory, safe=""))
            result["osv"] = source["data"]
            result["sources"].append({k: v for k, v in source.items() if k != "data"})
        except Exception as error:
            result["errors"].append({"provider": "OSV", "error": type(error).__name__, "retryable": transient(error)})
    cve = finding.get("cve")
    if cve and re.fullmatch(r"CVE-\d{4}-\d{4,}", cve):
        urls = {
            "NVD": f"https://services.nvd.nist.gov/rest/json/cves/2.0?cveId={cve}",
            "EPSS": f"https://api.first.org/data/v1/epss?cve={cve}",
            "KEV": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        }
        for provider, url in urls.items():
            try:
                source = cached_fetch(url)
                data = source["data"]
                if provider == "NVD":
                    result["nvd"] = data
                    entries = data.get("vulnerabilities", [])
                    if entries:
                        metrics = entries[0]["cve"].get("metrics", {})
                        metric: dict = next(iter(metrics.get("cvssMetricV31", []) or metrics.get("cvssMetricV30", []) or metrics.get("cvssMetricV40", [])), {})
                        result["cvss"] = metric.get("cvssData")
                elif provider == "EPSS" and data.get("data"):
                    result["epss"] = float(data["data"][0]["epss"])
                    result["epss_date"] = data["data"][0].get("date")
                elif provider == "KEV":
                    result["kev"] = any(item["cveID"] == cve for item in data.get("vulnerabilities", []))
                    result["kev_source"] = source["source"]
                result["sources"].append({"provider": provider, "source": source["source"], "retrieved_at": source["retrieved_at"]})
            except Exception as error:
                result["errors"].append({"provider": provider, "error": type(error).__name__, "retryable": transient(error)})
    return result
