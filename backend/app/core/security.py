import hashlib
import os
import re
import secrets
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import LoginSession, User, get_db

password_hasher = PasswordHasher(memory_cost=32768, time_cost=3, parallelism=2)


def digest(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def redact(value: str) -> str:
    for secret in [settings.github_token, settings.cloud_api_key]:
        if secret:
            value = value.replace(secret, "[REDACTED]")
    value = re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{16,})", "[REDACTED]", value)
    value = re.sub(r"(?i)(authorization[\"\s:=]+(?:bearer|token)\s+)[^\s\"']+", r"\1[REDACTED]", value)
    return value


def cipher() -> Fernet:
    path = settings.data_dir / "credential.key"
    if not path.exists():
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "wb") as file:
                file.write(Fernet.generate_key())
        except FileExistsError:
            pass
    return Fernet(path.read_bytes())


def safe_path(root: Path, relative: str, *, allow_new: bool = True) -> Path:
    if not relative or "\\" in relative or "\x00" in relative or ":" in relative:
        raise ValueError("Invalid repository path")
    posix = PurePosixPath(relative)
    if posix.is_absolute() or any(p in {"..", ".git", ".env", ".aws", ".ssh"} or p.startswith(".env.") for p in posix.parts):
        raise ValueError("Path is outside the allowed repository boundary")
    path = root.joinpath(*posix.parts)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes the workspace")
    cursor = path
    while cursor != root and cursor.is_relative_to(root):
        if cursor.is_symlink():
            raise ValueError("Symlinks are forbidden")
        cursor = cursor.parent
    if not allow_new and not path.is_file():
        raise ValueError("File not found")
    return path


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get("kyro_session", "")
    session = db.get(LoginSession, digest(token)) if token else None
    if session is None or datetime.fromisoformat(session.expires_at) <= datetime.now(UTC):
        raise HTTPException(401, "Sign in to continue")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if not secrets.compare_digest(request.headers.get("X-CSRF-Token", ""), session.csrf):
            raise HTTPException(403, "Invalid CSRF token")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Session expired")
    request.state.login_session = session
    return user
