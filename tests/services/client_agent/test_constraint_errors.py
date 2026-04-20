import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    from services.client_agent.app import create_app
    return TestClient(create_app())


def test_brief_not_found_envelope(client):
    resp = client.get("/client/briefs/missing")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "brief_not_found"
    assert "/client/briefs" in body["_try_instead"]


def test_trace_brief_not_found_envelope(client):
    resp = client.get("/client/briefs/missing/trace")
    assert resp.status_code == 404
    assert resp.json()["error"] == "brief_not_found"


def test_empty_brief_is_422(client):
    resp = client.post("/client/briefs", json={"brief": ""})
    assert resp.status_code == 422
