import asyncio
import json
import sys

import pytest
import httpx

from services.orchestrator.state import TraceEvent


@pytest.mark.skipif(
    sys.version_info >= (3, 14),
    reason="httpx ASGITransport streaming hangs for SSE on Python 3.14+ in-process",
)
@pytest.mark.asyncio
async def test_sse_stream_emits_published_events(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    from services.orchestrator.app import create_app

    app = create_app(sqlite_path=str(tmp_path / "o.db"))

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        async def reader():
            async with client.stream("GET", "/sse/orchestrator") as response:
                assert response.status_code == 200
                events = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        events.append(json.loads(line[len("data: "):]))
                    if len(events) >= 2:
                        break
                return events

        reader_task = asyncio.create_task(reader())
        await asyncio.sleep(0.1)  # let subscriber register

        bus = app.state.trace_bus
        await bus.publish(TraceEvent(job_id="j1", kind="thought", summary="first"))
        await bus.publish(TraceEvent(job_id="j1", kind="action", summary="GET /"))

        received = await asyncio.wait_for(reader_task, timeout=2.0)
        assert [e["summary"] for e in received] == ["first", "GET /"]
