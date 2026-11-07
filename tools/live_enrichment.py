"""Exercise public advisory enrichment through KYRO's actual background job API."""
import json

from live_acceptance import API, DATA, EVIDENCE

api = API("http://127.0.0.1:8788")
api.login()
state = json.loads((DATA / "workflow.json").read_text())
findings = api.request("/findings?repository_id=" + state["repository_id"])
finding = next(finding for finding in findings if finding["data"].get("cve"))
api.wait(api.request("/findings/" + finding["id"] + "/enrich", "POST"))
result = api.request("/findings/" + finding["id"])
(EVIDENCE / "live-intelligence-enrichment.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps({"cve": result["data"]["cve"], "sources": result["intelligence"]["sources"], "errors": result["intelligence"]["errors"]}, indent=2))
