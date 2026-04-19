import json
from pathlib import Path

import pytest

from services.orchestrator.llm import (
    LLMClient,
    ReplayLLMClient,
    ReplayMissError,
)


def test_replay_client_returns_recorded_response(tmp_path):
    recording = tmp_path / "plan.json"
    recording.write_text(json.dumps({
        "messages": [{"role": "system", "content": "you are a planner"}],
        "response": {"content": '{"steps": []}'},
    }))

    client = ReplayLLMClient(recordings_dir=str(tmp_path))
    result = client.invoke(
        step="plan",
        messages=[{"role": "system", "content": "you are a planner"}],
    )
    assert result["content"] == '{"steps": []}'


def test_replay_client_raises_on_missing_step(tmp_path):
    client = ReplayLLMClient(recordings_dir=str(tmp_path))
    with pytest.raises(ReplayMissError):
        client.invoke(step="plan", messages=[])


def test_llm_client_is_abstract_factory():
    # Factory returns ReplayLLMClient when ORCHESTRATOR_REPLAY_DIR is set.
    import os

    old = os.environ.get("ORCHESTRATOR_REPLAY_DIR")
    os.environ["ORCHESTRATOR_REPLAY_DIR"] = "fixtures/llm_recordings/landing_page"
    try:
        client = LLMClient.from_env()
        assert isinstance(client, ReplayLLMClient)
    finally:
        if old is None:
            os.environ.pop("ORCHESTRATOR_REPLAY_DIR", None)
        else:
            os.environ["ORCHESTRATOR_REPLAY_DIR"] = old
