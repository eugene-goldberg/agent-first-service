import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def orchestrator_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    from services.orchestrator.app import create_app
    app = create_app(sqlite_path=str(tmp_path / "orch.db"))
    return app


def test_root_lists_orchestrator_capabilities(orchestrator_app):
    client = TestClient(orchestrator_app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["service"] == "orchestrator"
    ids = {c["id"] for c in body["data"]["capabilities"]}
    assert ids == {
        "start_orchestration",
        "list_orchestrations",
        "find_orchestration",
        "trace_orchestration",
        "stream_trace",
    }
    related_rels = {r["rel"] for r in body["_related"]}
    assert related_rels == {"projects_service", "people_service", "communications_service"}
    assert any(s["rel"] == "start_orchestration" for s in body["_suggested_next"])
