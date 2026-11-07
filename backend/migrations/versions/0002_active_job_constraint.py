"""Prevent duplicate active operations atomically on SQLite and PostgreSQL."""
from alembic import op
from sqlalchemy import text

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("uq_jobs_active_resource", "jobs", ["user_id", "resource_id"], unique=True, sqlite_where=text("status IN ('PENDING', 'RUNNING')"), postgresql_where=text("status IN ('PENDING', 'RUNNING')"))


def downgrade():
    op.drop_index("uq_jobs_active_resource", table_name="jobs")
