"""Tests for HybridLLMClient — live-primary + replay-fallback wrapper.

Failure is injected by pointing the primary at an empty directory so it raises
ReplayMissError (a real exception from real code — no mocks).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.orchestrator.llm import (
    HybridLLMClient,
    LLMClient,
    ReplayLLMClient,
    ReplayMissError,
)


def _write_fixture(dir_path: Path, step: str, content: str) -> None:
    (dir_path / f"{step}.json").write_text(json.dumps({
        "messages": [],
        "response": {"content": content},
    }))


def test_hybrid_returns_primary_response_when_primary_succeeds(tmp_path):
    primary_dir = tmp_path / "primary"
    fallback_dir = tmp_path / "fallback"
    primary_dir.mkdir()
    fallback_dir.mkdir()
    _write_fixture(primary_dir, "plan", '{"steps":["primary"]}')
    _write_fixture(fallback_dir, "plan", '{"steps":["fallback"]}')

    hybrid = HybridLLMClient(
        primary=ReplayLLMClient(recordings_dir=str(primary_dir)),
        fallback=ReplayLLMClient(recordings_dir=str(fallback_dir)),
    )
    result = hybrid.invoke(step="plan", messages=[])
    assert result["content"] == '{"steps":["primary"]}'
    assert result["_path"] == "live"


def test_hybrid_falls_back_when_primary_raises(tmp_path):
    primary_dir = tmp_path / "primary"
    fallback_dir = tmp_path / "fallback"
    primary_dir.mkdir()
    fallback_dir.mkdir()
    _write_fixture(fallback_dir, "plan", '{"steps":["fallback"]}')

    hybrid = HybridLLMClient(
        primary=ReplayLLMClient(recordings_dir=str(primary_dir)),
        fallback=ReplayLLMClient(recordings_dir=str(fallback_dir)),
    )
    result = hybrid.invoke(step="plan", messages=[])
    assert result["content"] == '{"steps":["fallback"]}'
    assert result["_path"] == "replay_fallback"
    assert "primary_error" in result
    assert "plan.json" in result["primary_error"]


def test_hybrid_raises_primary_error_when_fallback_also_fails(tmp_path):
    primary_dir = tmp_path / "primary"
    fallback_dir = tmp_path / "fallback"
    primary_dir.mkdir()
    fallback_dir.mkdir()

    hybrid = HybridLLMClient(
        primary=ReplayLLMClient(recordings_dir=str(primary_dir)),
        fallback=ReplayLLMClient(recordings_dir=str(fallback_dir)),
    )
    with pytest.raises(ReplayMissError) as exc_info:
        hybrid.invoke(step="plan", messages=[])
    assert str(primary_dir / "plan.json") in str(exc_info.value)


def test_hybrid_is_llm_client_subclass():
    assert issubclass(HybridLLMClient, LLMClient)


def test_from_env_returns_hybrid_when_mode_set(monkeypatch, tmp_path):
    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    _write_fixture(fallback_dir, "plan", '{"steps":[]}')

    monkeypatch.setenv("ORCHESTRATOR_LLM_MODE", "hybrid")
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", str(fallback_dir))
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    client = LLMClient.from_env()
    assert isinstance(client, HybridLLMClient)


def test_from_env_hybrid_requires_replay_dir(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_LLM_MODE", "hybrid")
    monkeypatch.delenv("ORCHESTRATOR_REPLAY_DIR", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    with pytest.raises(RuntimeError, match="ORCHESTRATOR_REPLAY_DIR"):
        LLMClient.from_env()
