"""Verifies the client runner surfaces ClientHybridLLM's `_path` into trace events."""
from __future__ import annotations

import uuid

import pytest

from services.client_agent.llm import ClientHybridLLM, ClientReplayLLM
from services.client_agent.runner import ClientAgentRunner
from services.client_agent.state import ClientBriefState
from services.client_agent.trace_bus import ClientTraceBus


@pytest.mark.asyncio
async def test_trace_events_carry_llm_path_when_hybrid_falls_back(orchestrator_transport, tmp_path):
    bus = ClientTraceBus()
    empty_dir = tmp_path / "primary"
    empty_dir.mkdir()
    llm = ClientHybridLLM(
        primary=ClientReplayLLM(recordings_dir=str(empty_dir)),
        fallback=ClientReplayLLM(recordings_dir="fixtures/llm_recordings/client_landing_page"),
    )

    runner = ClientAgentRunner(
        llm=llm,
        bus=bus,
        http_client=orchestrator_transport,
        orchestrator_base="http://127.0.0.1:8000",
    )

    state = ClientBriefState(
        brief_id=f"cb_{uuid.uuid4().hex[:6]}",
        brief="Build a marketing landing page for our Q3 launch.",
    )
    result = await runner.run(state)

    llm_paths = [e.detail.get("llm_path") for e in result.trace if e.detail.get("llm_path")]
    assert "replay_fallback" in llm_paths
    # At least one event per LLM call (discover, decide, summarize) should be annotated.
    assert sum(1 for p in llm_paths if p == "replay_fallback") >= 3
