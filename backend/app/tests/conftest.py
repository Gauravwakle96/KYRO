import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

TEST_DATA = tempfile.TemporaryDirectory(prefix="kyro-tests-")
os.environ["KYRO_DATABASE_URL"] = "sqlite:///" + TEST_DATA.name.replace("\\", "/") + "/tests.db"
os.environ["KYRO_DATA_DIR"] = TEST_DATA.name
os.environ["KYRO_ENABLE_WORKER"] = "false"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import REQUESTS, app  # noqa: E402


def pytest_sessionfinish(session, exitstatus):
    engine.dispose()
    TEST_DATA.cleanup()


@pytest.fixture
def client():
    Base.metadata.drop_all(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
    REQUESTS.clear()
    with TestClient(app, raise_server_exceptions=False) as browser:
        yield browser


@pytest.fixture
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        yield session


@pytest.fixture
def owner(client):
    response = client.post("/api/auth/register", json={"email": "owner@example.test", "password": "correct horse local fixture"})
    assert response.status_code == 201, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return response.json()["user"]
