import json

import httpx
import pytest
from sqlalchemy import select

from app.agents import models
from app.core.config import settings
from app.database import ModelUsage, User


@pytest.mark.parametrize("routing,local_only,authorized,finding,expected", [
    ("auto", True, True, {"file_path": "app.py"}, "local"),
    ("auto", False, True, {"file_path": "app.py"}, "cloud"),
    ("auto", False, True, {"package_name": "package", "severity": "LOW"}, "local"),
    ("auto", False, False, {"file_path": "app.py"}, "local"),
])
def test_routing_respects_privacy_and_authorization(monkeypatch, routing, local_only, authorized, finding, expected):
    monkeypatch.setattr(settings, "model_routing", routing)
    monkeypatch.setattr(settings, "local_only", local_only)
    monkeypatch.setattr(settings, "cloud_authorized", authorized)
    assert models.select_provider(finding) == expected


def test_responses_contract_usage_and_unknown_cost(db, monkeypatch):
    """Protocol unit fixture; does not claim successful live cloud access."""
    user = User(email="responses@unit.test", password_hash="unusable")
    db.add(user)
    db.commit()
    for key, value in {"local_only": False, "cloud_authorized": True, "cloud_model_url": "https://provider.example/v1", "cloud_model": "unit-model", "cloud_api_key": "unit-credential", "cloud_protocol": "responses", "cloud_request_limit": 1, "cloud_input_price_per_million": None, "cloud_output_price_per_million": None}.items():
        monkeypatch.setattr(settings, key, value)
    original = httpx.Client
    def handler(request):
        assert request.url.path == "/v1/responses"
        payload = json.loads(request.content)
        assert payload["max_output_tokens"] <= settings.max_model_tokens
        return httpx.Response(200, json={"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": '{"fixture":true}'}]}], "usage": {"input_tokens": 11, "output_tokens": 7}})
    monkeypatch.setattr(models.httpx, "Client", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert models.complete(db, user.id, [{"role": "user", "content": "unit fixture"}], provider="cloud") == {"fixture": True}
    usage = db.scalar(select(ModelUsage))
    assert usage.input_tokens == 11 and usage.output_tokens == 7 and usage.estimated_cost is None
    with pytest.raises(ValueError, match="request limit"):
        models.complete(db, user.id, [], provider="cloud")
