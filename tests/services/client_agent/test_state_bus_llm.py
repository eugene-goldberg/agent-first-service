import asyncio
import json
import os

import pytest

from services.client_agent.llm import ClientLLMClient, ClientReplayLLM, ClientReplayMiss
from services.client_agent.state import ClientBriefState, ClientTraceEvent
from services.client_agent.trace_bus import ClientTraceBus


def test_client_brief_state_defaults():
    state = ClientBriefState(brief_id="cb_1", brief="do the thing")
    assert state.orchestration_job_id is None
    assert state.trace == []
    assert state.status == "pending"


def test_client_trace_event_has_kind():
    ev = ClientTraceEvent(brief_id="cb_1", kind="discovery", summary="GET /")
    assert ev.kind == "discovery"


@pytest.mark.asyncio
async def test_client_trace_bus_fanout():
    bus = ClientTraceBus()

    async def consume():
        async with bus.subscribe() as q:
            return await q.get()

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)

    await bus.publish(ClientTraceEvent(brief_id="cb_1", kind="decision", summary="x"))
    got = await asyncio.wait_for(task, timeout=1.0)
    assert got.summary == "x"


def test_client_replay_llm_reads_recording(tmp_path):
    rec = tmp_path / "discover.json"
    rec.write_text(json.dumps({
        "messages": [],
        "response": {"content": "hello"},
    }))

    client = ClientReplayLLM(recordings_dir=str(tmp_path))
    out = client.invoke(step="discover", messages=[])
    assert out["content"] == "hello"


def test_client_replay_llm_miss_raises(tmp_path):
    client = ClientReplayLLM(recordings_dir=str(tmp_path))
    with pytest.raises(ClientReplayMiss):
        client.invoke(step="missing", messages=[])


def test_client_llm_factory_picks_replay_when_env_set(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    client = ClientLLMClient.from_env()
    assert isinstance(client, ClientReplayLLM)
