"""Live migrations and transactions against a disposable local PostgreSQL container."""
import json
import os
import pathlib
import secrets
import subprocess
import time
from datetime import UTC, datetime

from sqlalchemy import create_engine, inspect, text

ROOT = pathlib.Path(__file__).resolve().parents[1]
name = "kyro-postgres-acceptance-" + secrets.token_hex(4)
password = secrets.token_urlsafe(24)
environment = {**os.environ, "POSTGRES_PASSWORD": password}


def docker(args):
    result = subprocess.run(["docker", *args], env=environment, capture_output=True, text=True, timeout=180)
    if result.returncode:
        raise RuntimeError("PostgreSQL acceptance Docker operation failed; inspect local Docker availability")
    return result.stdout.strip()


try:
    docker(["run", "-d", "--rm", "--name", name, "--memory", "512m", "--cpus", "1", "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_USER=kyro", "--env", "POSTGRES_DB=kyro", "-p", "127.0.0.1::5432", "postgres:18.3-bookworm"])
    for _ in range(60):
        check = subprocess.run(["docker", "exec", name, "pg_isready", "-U", "kyro", "-d", "kyro"], capture_output=True)
        if check.returncode == 0:
            break
        time.sleep(1)
    else:
        raise RuntimeError("PostgreSQL did not become ready")
    port = json.loads(docker(["inspect", name]))[0]["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
    from sqlalchemy.engine import URL
    url = URL.create("postgresql+psycopg", username="kyro", password=password, host="127.0.0.1", port=int(port), database="kyro").render_as_string(hide_password=False)
    result = subprocess.run([str(ROOT / "backend" / ".venv" / "Scripts" / "alembic.exe") if os.name == "nt" else str(ROOT / "backend" / ".venv" / "bin" / "alembic"), "upgrade", "head"], cwd=ROOT / "backend", env={**environment, "KYRO_DATABASE_URL": url, "KYRO_DATA_DIR": str(ROOT / "data" / "postgres-acceptance")}, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError("PostgreSQL migration failed: " + result.stderr.replace(password, "[REDACTED]")[-1000:])
    engine = create_engine(url)
    with engine.begin() as connection:
        version = connection.execute(text("select version_num from alembic_version")).scalar_one()
        connection.execute(text("insert into users (id,email,password_hash,created_at) values (:id,:email,:hash,:at)"), {"id": "controlled-user", "email": "postgres@kyro.local", "hash": "not-a-login", "at": datetime.now(UTC).isoformat()})
        tables = inspect(connection).get_table_names()
        foreign_keys = inspect(connection).get_foreign_keys("findings")
        indexes = inspect(connection).get_indexes("jobs")
        assert foreign_keys and any(index["name"] == "uq_jobs_active_resource" and index["unique"] for index in indexes)
    engine.dispose()
    evidence = {"created_at": datetime.now(UTC).isoformat(), "target": "Disposable local PostgreSQL 18.3 container", "migration_head": version, "tables": tables, "findings_foreign_keys": foreign_keys, "active_job_unique_index": True, "transaction_insert": "PASSED", "status": "PASSED", "limitations": ["Checks migration, constraints and transaction basics; full PostgreSQL application workflow not exercised"]}
    (ROOT / "docs" / "evidence" / "postgres-acceptance.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print("PostgreSQL migrations, foreign keys, active-job index and transaction passed")
finally:
    # Remove only the uniquely named disposable container created by this harness.
    subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30)
