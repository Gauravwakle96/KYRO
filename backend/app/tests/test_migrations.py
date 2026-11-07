import os
import subprocess


def test_clean_migration(tmp_path):
    env = {**os.environ, "KYRO_DATABASE_URL": "sqlite:///" + (tmp_path / "migration.db").as_posix(), "KYRO_DATA_DIR": str(tmp_path)}
    result = subprocess.run(["uv", "run", "alembic", "upgrade", "head"], env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    import sqlite3
    connection = sqlite3.connect(tmp_path / "migration.db")
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    assert connection.execute("select version_num from alembic_version").fetchone()[0] == ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    assert "uq_jobs_active_resource" in {row[1] for row in connection.execute("pragma index_list(jobs)")}
    assert connection.execute("pragma foreign_key_list(findings)").fetchall()
    connection.close()
