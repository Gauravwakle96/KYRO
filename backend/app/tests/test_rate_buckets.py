import time
from collections import deque

from app.main import REQUESTS


def test_api_exhaustion_does_not_replace_frontend_with_json(client):
    REQUESTS["testclient:api"] = deque([time.monotonic()] * 300)
    assert client.get("/api/health").status_code == 429
    assert client.get("/").status_code != 429
