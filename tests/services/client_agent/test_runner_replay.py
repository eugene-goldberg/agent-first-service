import uuid

import pytest

from services.client_agent.llm import ClientReplayLLM
from services.client_agent.runner import ClientAgentRunner
from services.client_agent.state import ClientBriefState
from services.client_agent.trace_bus import ClientTraceBus


@pytest.mark.asyncio
async def test_runner_discovers_orchestrator_and_forwards_brief(orchestrator_transport):
    bus = ClientTraceBus()
    llm = ClientReplayLLM(recordings_dir="fixtures/llm_recordings/client_landing_page")

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
    assert result.orchestration_job_id is not None
    kinds = [e.kind for e in result.trace]
    assert kinds[0] == "discovery"
    assert "decision" in kinds
    assert "invocation" in kinds
    assert kinds[-1] == "summary"
    assert result.final_summary is not None
