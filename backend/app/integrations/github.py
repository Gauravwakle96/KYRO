import base64
import io
import re
import tarfile
import time
from pathlib import Path
from urllib.parse import quote

import httpx
import jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ServiceError
from app.core.security import cipher, safe_path
from app.database import Credential, Repository


def validate_repository(name: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}/[A-Za-z0-9_.-]{1,100}", name) or ".." in name:
        raise ValueError("Use a GitHub owner/repository name")
    return name


class GitHub:
    def __init__(self, db: Session, user_id: str):
        self.installation = False
        credential = db.get(Credential, user_id)
        token = cipher().decrypt(credential.ciphertext.encode()).decode() if credential else settings.github_token
        if not token and settings.github_app_id and settings.github_installation_id:
            key = Path(settings.github_app_private_key_path).read_text()
            app_jwt = jwt.encode({"iat": int(time.time()) - 60, "exp": int(time.time()) + 540, "iss": settings.github_app_id}, key, algorithm="RS256")
            with httpx.Client(timeout=20, trust_env=False) as client:
                response = client.post(f"https://api.github.com/app/installations/{settings.github_installation_id}/access_tokens", headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"})
                if response.status_code != 201:
                    raise RuntimeError(f"GitHub App authentication failed ({response.status_code})")
                token = response.json()["token"]
                self.installation = True
        if not token:
            raise RuntimeError("GitHub is not connected. Configure a GitHub App, OAuth client or backend token.")
        self.client = httpx.Client(base_url="https://api.github.com", headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}, timeout=30, trust_env=False)

    def close(self):
        self.client.close()

    def request(self, method: str, path: str, **kwargs):
        response = self.client.request(method, path, **kwargs)
        if response.status_code >= 400:
            if response.status_code == 409 and "/commits/" in path:
                raise ServiceError("GitHub repository has no commits yet; push source code before importing it (409)")
            rate_limited = response.status_code == 429 or (response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0")
            retryable = response.status_code in {408, 500, 502, 503, 504} or rate_limited
            delay = response.headers.get("Retry-After", "")
            retry_after = min(int(delay), 60) if delay.isdigit() else None
            message = "GitHub is temporarily unavailable" if retryable else "GitHub access was rejected; check repository selection and permissions"
            raise ServiceError(f"{message} ({response.status_code})", retryable=retryable, retry_after=retry_after)
        return response.json() if response.content else {}

    def repositories(self) -> list:
        result: list[dict] = []
        for page in range(1, 11):
            response = self.request("GET", f"/installation/repositories?per_page=100&page={page}" if self.installation else f"/user/repos?per_page=100&page={page}&sort=updated")
            data = response.get("repositories", []) if self.installation else response
            result.extend({"full_name": item["full_name"], "private": item["private"], "default_branch": item["default_branch"], "language": item["language"], "permissions": item.get("permissions", {})} for item in data)
            if len(data) < 100:
                break
        return result

    def ingest(self, repo: Repository, root: Path):
        name = validate_repository(repo.full_name)
        commit = self.request("GET", f"/repos/{name}/commits/{quote(repo.branch, safe='')}")
        sha = commit["sha"]
        response = self.client.get(f"/repos/{name}/tarball/{sha}", follow_redirects=False)
        if response.status_code != 302:
            raise ServiceError(f"GitHub archive retrieval failed ({response.status_code})", retryable=response.status_code in {408, 429, 500, 502, 503, 504})
        url = httpx.URL(response.headers["location"])
        if url.host != "codeload.github.com" or url.scheme != "https":
            raise RuntimeError("Untrusted GitHub archive redirect")
        payload = bytearray()
        with httpx.Client(timeout=60, trust_env=False) as client, client.stream("GET", str(url)) as archive:
            archive.raise_for_status()
            for chunk in archive.iter_bytes():
                payload.extend(chunk)
                if len(payload) > 100_000_000:
                    raise ValueError("Archive exceeds the 100 MB download limit")
        extract_archive(bytes(payload), root)
        repo.sha = sha


def extract_archive(payload: bytes, root: Path):
    root.mkdir(parents=True, exist_ok=True)
    total, count = 0, 0
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz") as archive:
        for member in archive:
            parts = member.name.split("/")[1:]
            relative = "/".join(parts)
            if not relative or member.isdir():
                continue
            count += 1
            total += member.size
            if count > 10000 or total > 200_000_000 or member.size > 10_000_000:
                raise ValueError("Archive exceeds extraction limits")
            if not member.isfile():
                raise ValueError("Archive contains forbidden links or special files")
            if any(p in {".git", ".env", ".ssh", ".aws"} or p.startswith(".env.") for p in parts):
                continue
            path = safe_path(root, relative)
            file = archive.extractfile(member)
            if file is None:
                raise ValueError("Invalid archive file")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(file.read(member.size + 1))


def create_pull_request(github: GitHub, repo: Repository, task_id: str, changes: list[dict], report: dict, plan: dict) -> dict:
    name = validate_repository(repo.full_name)
    current = github.request("GET", f"/repos/{name}/git/ref/heads/{quote(repo.branch, safe='')}")
    if current["object"]["sha"] != repo.sha:
        raise RuntimeError("Base branch changed. Re-ingest and re-verify before delivery.")
    base = github.request("GET", f"/repos/{name}/git/commits/{repo.sha}")
    tree_items = []
    for change in changes:
        blob = github.request("POST", f"/repos/{name}/git/blobs", json={"content": base64.b64encode(change["content"].encode()).decode(), "encoding": "base64"})
        tree_items.append({"path": change["path"], "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = github.request("POST", f"/repos/{name}/git/trees", json={"base_tree": base["tree"]["sha"], "tree": tree_items})
    commit = github.request("POST", f"/repos/{name}/git/commits", json={"message": f"fix: {plan['title'][:100]} (KYRO)", "tree": tree["sha"], "parents": [repo.sha]})
    branch = f"kyro/remediation-{task_id}"
    github.request("POST", f"/repos/{name}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": commit["sha"]})
    body = f"{plan['root_cause']}\n\n{plan['strategy']}\n\nChanged files:\n" + "\n".join(f"- `{c['path']}`" for c in changes)
    body += f"\n\nVerification: **{report['status']}**\n\n" + "\n".join(f"- {test['kind']}: {test['status']} (exit {test.get('exit_code')})" for test in report.get("commands", []))
    body += "\n\nLimitations:\n" + "\n".join(f"- {limit}" for limit in report.get("limitations", []))
    body += f"\n\nOriginal finding: {report.get('original_finding', {}).get('title', '')}\n\nSecurity comparison:\n```json\n{__import__('json').dumps(report.get('comparison', {}), indent=2)}\n```\n\nHuman review and merge approval are required."
    pr = github.request("POST", f"/repos/{name}/pulls", json={"title": f"KYRO: {plan['title'][:150]}", "head": branch, "base": repo.branch, "body": body, "draft": True})
    return {"number": pr["number"], "url": pr["html_url"], "state": pr["state"], "branch": branch, "commit": commit["sha"], "draft": pr["draft"]}
