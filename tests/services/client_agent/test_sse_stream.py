import asyncio
import json
import sys

import pytest
import httpx

from services.client_agent.state import ClientTraceEvent


@pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="httpx ASGITransport streaming hangs for SSE on Python 3.14+ in-process",
)
@pytest.mark.asyncio
async def test_client_sse_delivers_published_events(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    from services.client_agent.app import create_app
    app = create_app()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        async def reader():
            async with client.stream("GET", "/sse/client") as response:
                assert response.status_code == 200
                got = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        got.append(json.loads(line[len("data: ") :]))
                    if len(got) >= 2:
                        break
                return got

        task = asyncio.create_task(reader())
        await asyncio.sleep(0.1)

        bus = app.state.trace_bus
        await bus.publish(ClientTraceEvent(brief_id="b1", kind="discovery", summary="first"))
        await bus.publish(ClientTraceEvent(brief_id="b1", kind="decision", summary="second"))

        got = await asyncio.wait_for(task, timeout=2.0)
        assert [e["summary"] for e in got] == ["first", "second"]
