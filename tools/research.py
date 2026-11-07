"""Retrieve primary project documentation and license/maintenance metadata. No credentials."""
import concurrent.futures
import json
import pathlib
import urllib.request
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPOS = ["OpenHands/vulnerability-fixer", "OpenHands/OpenHands", "OpenHands/software-agent-sdk", "Aider-AI/aider", "SWE-agent/SWE-agent", "SWE-agent/mini-swe-agent", "DefectDojo/django-DefectDojo", "DependencyTrack/dependency-track", "infobyte/faraday", "semgrep/semgrep", "aquasecurity/trivy", "google/osv-scanner", "anchore/syft", "anchore/grype", "gitleaks/gitleaks", "zaproxy/zaproxy", "projectdiscovery/nuclei", "tree-sitter/tree-sitter", "moby/moby", "google/gvisor", "langchain-ai/langgraph"]

def fetch(repo):
    result = {"repository": repo, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    try:
        req = urllib.request.Request("https://api.github.com/repos/" + repo, headers={"User-Agent": "KYRO-research"})
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.load(response)
        result.update({key: data.get(key) for key in ["html_url", "description", "pushed_at", "archived", "default_branch", "license"]})
        for filename in ["README.md", "README.rst", "README"]:
            try:
                url = f"https://raw.githubusercontent.com/{repo}/{data['default_branch']}/{filename}"
                with urllib.request.urlopen(url, timeout=15) as response:
                    content = response.read(120000).decode("utf-8", errors="replace")
                target = ROOT / "docs" / "research" / (repo.replace("/", "__") + ".md")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                result.update(readme_source=url, local_reference=str(target.relative_to(ROOT)))
                break
            except Exception:
                continue
    except Exception as error:
        result["error"] = str(error)
    return result

if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(fetch, REPOS))
    (ROOT / "docs" / "research").mkdir(parents=True, exist_ok=True)
    (ROOT / "docs" / "research" / "sources.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    for result in results:
        print(result["repository"], result.get("license", {}).get("spdx_id") if result.get("license") else "unknown", result.get("pushed_at"), result.get("error", "retrieved"))
