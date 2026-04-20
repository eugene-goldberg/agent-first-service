import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def orchestrator_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    from services.orchestrator.app import create_app
    return TestClient(create_app(sqlite_path=str(tmp_path / "o.db")))


def test_orchestration_not_found(orchestrator_client):
    resp = orchestrator_client.get("/orchestrations/nope")
    body = resp.json()
    assert resp.status_code == 404
    assert body["error"] == "orchestration_not_found"
    assert "/orchestrations" in body["_try_instead"]


def test_trace_not_found(orchestrator_client):
    resp = orchestrator_client.get("/orchestrations/nope/trace")
    assert resp.status_code == 404
    assert resp.json()["error"] == "orchestration_not_found"


def test_blank_brief_is_validation_error(orchestrator_client):
    resp = orchestrator_client.post("/orchestrations", json={"brief": ""})
    assert resp.status_code == 422
