import asyncio
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def orchestrator_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    from services.orchestrator.app import create_app
    app = create_app(sqlite_path=str(tmp_path / "orch.db"))
    
    async def _ready_noop() -> None:
        return None
    app.state.runner.ensure_ready = _ready_noop

    return TestClient(app)


def test_create_orchestration_returns_envelope_with_job_id(orchestrator_client):
    resp = orchestrator_client.post(
        "/orchestrations",
        json={"brief": "Build a landing page."},
    )
    assert resp.status_code == 202
    body = resp.json()
    assert body["data"]["brief"] == "Build a landing page."
    assert body["data"]["status"] in {"queued", "running"}
    job_id = body["data"]["id"]
    assert body["_self"].endswith(f"/orchestrations/{job_id}")
    suggested = {s["rel"] for s in body["_suggested_next"]}
    assert "find_orchestration" in suggested
    assert "stream_trace" in suggested


def test_get_orchestration_returns_404_envelope(orchestrator_client):
    resp = orchestrator_client.get("/orchestrations/does_not_exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "orchestration_not_found"


def test_list_orchestrations_returns_envelope(orchestrator_client):
    orchestrator_client.post("/orchestrations", json={"brief": "a"})
    orchestrator_client.post("/orchestrations", json={"brief": "b"})

    resp = orchestrator_client.get("/orchestrations")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) >= 2
    assert isinstance(body["_related"], list)
