"""Verifies the graph surfaces HybridLLMClient's `_path` into trace events."""
from __future__ import annotations

import uuid

import pytest

from services.orchestrator.graph import OrchestrationGraph
from services.orchestrator.llm import HybridLLMClient, ReplayLLMClient
from services.orchestrator.state import OrchestrationState
from services.orchestrator.tools import HTTPToolbox
from services.orchestrator.trace_bus import TraceBus


@pytest.mark.asyncio
async def test_trace_events_carry_llm_path_when_hybrid_falls_back(leaf_http_client, tmp_path):
    toolbox = HTTPToolbox(client=leaf_http_client)
    bus = TraceBus()

    # Primary = empty fixture dir → raises ReplayMissError → forces fallback.
    # Fallback = real landing_page fixtures.
    empty_dir = tmp_path / "primary"
    empty_dir.mkdir()
    llm = HybridLLMClient(
        primary=ReplayLLMClient(recordings_dir=str(empty_dir)),
        fallback=ReplayLLMClient(recordings_dir="fixtures/llm_recordings/landing_page"),
    )

    graph = OrchestrationGraph(
        llm=llm,
        toolbox=toolbox,
        bus=bus,
        projects_base="http://127.0.0.1:8001",
        people_base="http://127.0.0.1:8002",
        comms_base="http://127.0.0.1:8003",
        max_steps=6,
    )

    await leaf_http_client.post(
        "http://127.0.0.1:8001/projects",
        json={"name": "Q3 Launch (seed)", "description": "fixture alias"},
    )

    state = OrchestrationState(
        job_id=f"job_{uuid.uuid4().hex[:6]}",
        brief="Build a marketing landing page for our Q3 launch.",
    )
    result = await graph.run(state)

    thought_events = [e for e in result.trace if e.kind == "thought"]
    action_events = [e for e in result.trace if e.kind == "action"]
    assert thought_events, "expected at least one thought event"
    assert action_events, "expected at least one action event"

    # Every LLM-originated event (thought, action, final) should carry llm_path.
    assert thought_events[0].detail.get("llm_path") == "replay_fallback"
    assert action_events[0].detail.get("llm_path") == "replay_fallback"
