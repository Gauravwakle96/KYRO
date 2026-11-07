from collections.abc import Generator
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings


def uid() -> str:
    return str(uuid4())


def now() -> str:
    return datetime.now(UTC).isoformat()


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class LoginSession(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf: Mapped[str]
    expires_at: Mapped[str]


class Credential(Base):
    __tablename__ = "credentials"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    ciphertext: Mapped[str]
    github_login: Mapped[str]


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(default="")
    created_at: Mapped[str] = mapped_column(default=now)


class Repository(Base):
    __tablename__ = "repositories"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str]
    branch: Mapped[str]
    sha: Mapped[str] = mapped_column(default="")
    source: Mapped[str] = mapped_column(default="github")
    status: Mapped[str] = mapped_column(default="PENDING")
    analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)


class FileRecord(Base):
    __tablename__ = "repository_files"
    __table_args__ = (UniqueConstraint("repository_id", "path"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    path: Mapped[str]
    digest: Mapped[str]
    language: Mapped[str]
    facts: Mapped[dict] = mapped_column(JSON, default=dict)


class ScanRun(Base):
    __tablename__ = "scan_runs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(default="RUNNING")
    created_at: Mapped[str] = mapped_column(default=now)
    completed_at: Mapped[str | None]
    snapshot_sha: Mapped[str]
    purpose: Mapped[str] = mapped_column(default="baseline")


class ScannerExecution(Base):
    __tablename__ = "scanner_executions"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scan_runs.id", ondelete="CASCADE"), index=True)
    scanner: Mapped[str]
    status: Mapped[str]
    metadata_json: Mapped[dict] = mapped_column(JSON)
    normalized: Mapped[list] = mapped_column(JSON, default=list)


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (UniqueConstraint("repository_id", "fingerprint"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    scan_id: Mapped[str] = mapped_column(ForeignKey("scan_runs.id", ondelete="CASCADE"))
    fingerprint: Mapped[str]
    title: Mapped[str]
    severity: Mapped[str]
    status: Mapped[str] = mapped_column(default="OPEN")
    data: Mapped[dict] = mapped_column(JSON)
    risk: Mapped[dict] = mapped_column(JSON, default=dict)
    reachability: Mapped[dict] = mapped_column(JSON, default=dict)
    intelligence: Mapped[dict] = mapped_column(JSON, default=dict)
    first_detected: Mapped[str] = mapped_column(default=now)
    last_detected: Mapped[str] = mapped_column(default=now)


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("uq_jobs_active_resource", "user_id", "resource_id", unique=True, sqlite_where=text("status IN ('PENDING', 'RUNNING')"), postgresql_where=text("status IN ('PENDING', 'RUNNING')")),)
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str]
    resource_id: Mapped[str]
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(default="PENDING", index=True)
    events: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None]
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[str] = mapped_column(default=now)
    started_at: Mapped[str | None]
    ended_at: Mapped[str | None]


class Remediation(Base):
    __tablename__ = "remediation_tasks"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    repository_id: Mapped[str] = mapped_column(ForeignKey("repositories.id", ondelete="CASCADE"), index=True)
    state: Mapped[str] = mapped_column(default="PENDING")
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    approval_digest: Mapped[str | None]
    approved_by: Mapped[str | None]
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    verification: Mapped[dict] = mapped_column(JSON, default=dict)
    pull_request: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)


class ModelUsage(Base):
    __tablename__ = "model_usage"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    remediation_id: Mapped[str | None]
    provider: Mapped[str]
    model: Mapped[str]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    duration_seconds: Mapped[float]
    retries: Mapped[int] = mapped_column(default=0)
    estimated_cost: Mapped[float | None]
    status: Mapped[str]
    created_at: Mapped[str] = mapped_column(default=now)


class Audit(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(index=True)
    action: Mapped[str]
    resource_id: Mapped[str]
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(default=now)


settings.data_dir.mkdir(parents=True, exist_ok=True)
engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}, pool_pre_ping=True)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_pragmas(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=10000")

SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Generator[Session]:
    with SessionLocal() as session:
        yield session


def audit(db: Session, user_id: str, action: str, resource_id: str, detail: dict | None = None):
    db.add(Audit(user_id=user_id, action=action, resource_id=resource_id, detail=detail or {}))
    db.commit()
