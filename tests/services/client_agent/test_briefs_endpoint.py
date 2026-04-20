import asyncio

import pytest
import httpx

from services.orchestrator.app import create_app as create_orch_app


@pytest.fixture
def orchestrator_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    return create_orch_app(sqlite_path=str(tmp_path / "o.db"))


@pytest.fixture
def client_agent_with_local_orchestrator(orchestrator_app, monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    import httpx as _httpx

    from services.client_agent.app import create_app

    transport = _httpx.ASGITransport(app=orchestrator_app)
    http_client = _httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000")

    app = create_app(http_client=http_client, orchestrator_base="http://127.0.0.1:8000")
    return app


@pytest.mark.asyncio
async def test_submit_brief_returns_envelope(client_agent_with_local_orchestrator):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=client_agent_with_local_orchestrator),
                            base_url="http://testserver") as c:
        resp = await c.post("/client/briefs", json={"brief": "Build a landing page."})
        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["brief"] == "Build a landing page."
        assert body["data"]["status"] in {"pending", "running", "completed"}
        assert body["_self"].endswith(f"/client/briefs/{body['data']['id']}")
        suggested = {s["rel"] for s in body["_suggested_next"]}
        assert "find_brief" in suggested
        assert "stream_client_trace" in suggested


@pytest.mark.asyncio
async def test_get_missing_brief_returns_404_envelope(client_agent_with_local_orchestrator):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=client_agent_with_local_orchestrator),
                            base_url="http://testserver") as c:
        resp = await c.get("/client/briefs/nope")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "brief_not_found"


@pytest.mark.asyncio
async def test_brief_completes_and_reports_orchestration_job_id(client_agent_with_local_orchestrator):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=client_agent_with_local_orchestrator),
                            base_url="http://testserver") as c:
        resp = await c.post("/client/briefs", json={"brief": "Build a landing page."})
        brief_id = resp.json()["data"]["id"]

        # Give the background task a moment to run.
        for _ in range(20):
            await asyncio.sleep(0.05)
            get_resp = await c.get(f"/client/briefs/{brief_id}")
            if get_resp.json()["data"]["status"] == "completed":
                break
        assert get_resp.json()["data"]["status"] == "completed"
        assert get_resp.json()["data"]["orchestration_job_id"] is not None
