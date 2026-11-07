import json
import pathlib
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parents[1] / "docs" / "research"
URLS = {
    "fastapi-security": "https://fastapi.tiangolo.com/tutorial/security/",
    "sqlalchemy-sessions": "https://docs.sqlalchemy.org/en/20/orm/session_basics.html",
    "tree-sitter-python-api": "https://raw.githubusercontent.com/tree-sitter/py-tree-sitter/master/README.md",
    "osv-json-contract": "https://raw.githubusercontent.com/google/osv-scanner/main/pkg/models/results.go",
    "osv-output-docs": "https://google.github.io/osv-scanner/usage/output/",
    "semgrep-cli": "https://semgrep.dev/docs/cli-reference",
    "trivy-json": "https://trivy.dev/latest/docs/configuration/reporting/",
    "github-device-flow": "https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps",
    "github-git-database": "https://docs.github.com/en/rest/git/trees",
    "llama-server": "https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md",
    "docker-resource-constraints": "https://docs.docker.com/engine/containers/resource_constraints/",
    "owasp-threat-model": "https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html",
    "osv-api": "https://google.github.io/osv.dev/api/",
    "epss-api": "https://www.first.org/epss/api",
    "snyk-workflow": "https://docs.snyk.io/scan-with-snyk/snyk-open-source",
    "github-advanced-security": "https://docs.github.com/en/get-started/learning-about-github/about-github-advanced-security",
}

def fetch(item):
    name, url = item
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "KYRO-primary-docs"})
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read(500000).decode("utf-8", errors="replace")
        (ROOT / (name + ".txt")).write_text(text, encoding="utf-8")
        return {"name": name, "source": url, "status": "retrieved", "bytes": len(text)}
    except Exception as error:
        return {"name": name, "source": url, "status": "failed", "error": str(error)}

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(fetch, URLS.items()))
    for repo in ["semgrep/semgrep", "aquasecurity/trivy", "google/osv-scanner"]:
        try:
            with urllib.request.urlopen("https://api.github.com/repos/" + repo + "/releases/latest", timeout=15) as response:
                data = json.load(response)
            print(repo, data["tag_name"])
            results.append({"name": repo, "release": data["tag_name"], "source": data["html_url"]})
        except Exception as error:
            print(repo, str(error))
    (ROOT / "primary-docs.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    for result in results:
        print(result["name"], result.get("status", "release"))
