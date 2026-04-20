import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_app(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    from services.client_agent.app import create_app
    return create_app()


def test_root_lists_client_agent_capabilities(client_app):
    client = TestClient(client_app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["service"] == "client_agent"
    ids = {c["id"] for c in body["data"]["capabilities"]}
    assert ids == {
        "submit_brief",
        "list_briefs",
        "find_brief",
        "trace_brief",
        "stream_client_trace",
    }
    related_rels = {r["rel"] for r in body["_related"]}
    assert "orchestrator" in related_rels
