"""Initial KYRO schema."""
from alembic import op
from sqlalchemy import JSON, Boolean, Column, Float, Integer, String, UniqueConstraint

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    def table(name, columns, constraints=()):
        op.create_table(name, *[Column(n, t, primary_key=p, nullable=nullable) for n, t, p, nullable in columns], *constraints)

    s = String
    ident = ("id", s, True, False)
    created = ("created_at", s, False, False)
    table("users", [ident, ("email", s(254), False, False), ("password_hash", s, False, False), created], [UniqueConstraint("email")])
    table("sessions", [("token_hash", s, True, False), ("user_id", s, False, False), ("csrf", s, False, False), ("expires_at", s, False, False)])
    table("credentials", [("user_id", s, True, False), ("ciphertext", s, False, False), ("github_login", s, False, False)])
    table("projects", [ident, ("user_id", s, False, False), ("name", s(120), False, False), ("description", s, False, False), created])
    table("repositories", [ident, ("project_id", s, False, False), ("full_name", s, False, False), ("branch", s, False, False), ("sha", s, False, False), ("source", s, False, False), ("status", s, False, False), ("analysis", JSON, False, False), created])
    table("repository_files", [ident, ("repository_id", s, False, False), ("path", s, False, False), ("digest", s, False, False), ("language", s, False, False), ("facts", JSON, False, False)], [UniqueConstraint("repository_id", "path")])
    table("scan_runs", [ident, ("repository_id", s, False, False), ("status", s, False, False), created, ("completed_at", s, False, True), ("snapshot_sha", s, False, False), ("purpose", s, False, False)])
    table("scanner_executions", [ident, ("scan_id", s, False, False), ("scanner", s, False, False), ("status", s, False, False), ("metadata_json", JSON, False, False), ("normalized", JSON, False, False)])
    table("findings", [ident, ("repository_id", s, False, False), ("scan_id", s, False, False), ("fingerprint", s, False, False), ("title", s, False, False), ("severity", s, False, False), ("status", s, False, False), ("data", JSON, False, False), ("risk", JSON, False, False), ("reachability", JSON, False, False), ("intelligence", JSON, False, False), ("first_detected", s, False, False), ("last_detected", s, False, False)], [UniqueConstraint("repository_id", "fingerprint")])
    table("jobs", [ident, ("user_id", s, False, False), ("kind", s, False, False), ("resource_id", s, False, False), ("payload", JSON, False, False), ("status", s, False, False), ("events", JSON, False, False), ("result", JSON, False, False), ("error", s, False, True), ("cancel_requested", Boolean, False, False), created, ("started_at", s, False, True), ("ended_at", s, False, True)])
    table("remediation_tasks", [ident, ("finding_id", s, False, False), ("repository_id", s, False, False), ("state", s, False, False), ("plan", JSON, False, False), ("approval_digest", s, False, True), ("approved_by", s, False, True), ("evidence", JSON, False, False), ("verification", JSON, False, False), ("pull_request", JSON, False, False), created])
    table("model_usage", [ident, ("user_id", s, False, False), ("remediation_id", s, False, True), ("provider", s, False, False), ("model", s, False, False), ("input_tokens", Integer, False, True), ("output_tokens", Integer, False, True), ("duration_seconds", Float, False, False), ("retries", Integer, False, False), ("estimated_cost", Float, False, True), ("status", s, False, False), created])
    table("audit_logs", [ident, ("user_id", s, False, False), ("action", s, False, False), ("resource_id", s, False, False), ("detail", JSON, False, False), created])
    # SQLite cannot ALTER foreign keys: recreate constraints through batch operations.
    foreign_keys = {"sessions": [("user_id", "users")], "credentials": [("user_id", "users")], "projects": [("user_id", "users")], "repositories": [("project_id", "projects")], "repository_files": [("repository_id", "repositories")], "scan_runs": [("repository_id", "repositories")], "scanner_executions": [("scan_id", "scan_runs")], "findings": [("repository_id", "repositories"), ("scan_id", "scan_runs")], "jobs": [("user_id", "users")], "remediation_tasks": [("finding_id", "findings"), ("repository_id", "repositories")], "model_usage": [("user_id", "users")]}
    for name, keys in foreign_keys.items():
        with op.batch_alter_table(name) as batch:
            for column, target in keys:
                batch.create_foreign_key(f"fk_{name}_{column}", target, [column], ["id"], ondelete="CASCADE")
                if column != "user_id" or name != "credentials":
                    batch.create_index(f"ix_{name}_{column}", [column])
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])


def downgrade():
    for name in ["audit_logs", "model_usage", "remediation_tasks", "jobs", "findings", "scanner_executions", "scan_runs", "repository_files", "repositories", "projects", "credentials", "sessions", "users"]:
        op.drop_table(name)
