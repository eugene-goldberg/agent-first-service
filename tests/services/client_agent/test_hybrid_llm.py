"""Tests for client_agent HybridLLMClient — live-primary + replay-fallback.

Failure injected via empty-directory ClientReplayLLM — real exception, no mocks.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.client_agent.llm import (
    ClientHybridLLM,
    ClientLLMClient,
    ClientReplayLLM,
    ClientReplayMiss,
)


def _write_fixture(dir_path: Path, step: str, content: str) -> None:
    (dir_path / f"{step}.json").write_text(json.dumps({
        "messages": [],
        "response": {"content": content},
    }))


def test_hybrid_returns_primary_when_primary_succeeds(tmp_path):
    primary_dir = tmp_path / "primary"
    fallback_dir = tmp_path / "fallback"
    primary_dir.mkdir()
    fallback_dir.mkdir()
    _write_fixture(primary_dir, "discover", "primary-reasoning")
    _write_fixture(fallback_dir, "discover", "fallback-reasoning")

    hybrid = ClientHybridLLM(
        primary=ClientReplayLLM(recordings_dir=str(primary_dir)),
        fallback=ClientReplayLLM(recordings_dir=str(fallback_dir)),
    )
    result = hybrid.invoke(step="discover", messages=[])
    assert result["content"] == "primary-reasoning"
    assert result["_path"] == "live"


def test_hybrid_falls_back_when_primary_raises(tmp_path):
    primary_dir = tmp_path / "primary"
    fallback_dir = tmp_path / "fallback"
    primary_dir.mkdir()
    fallback_dir.mkdir()
    _write_fixture(fallback_dir, "discover", "fallback-reasoning")

    hybrid = ClientHybridLLM(
        primary=ClientReplayLLM(recordings_dir=str(primary_dir)),
        fallback=ClientReplayLLM(recordings_dir=str(fallback_dir)),
    )
    result = hybrid.invoke(step="discover", messages=[])
    assert result["content"] == "fallback-reasoning"
    assert result["_path"] == "replay_fallback"
    assert "primary_error" in result


def test_hybrid_raises_primary_error_when_fallback_also_fails(tmp_path):
    primary_dir = tmp_path / "primary"
    fallback_dir = tmp_path / "fallback"
    primary_dir.mkdir()
    fallback_dir.mkdir()

    hybrid = ClientHybridLLM(
        primary=ClientReplayLLM(recordings_dir=str(primary_dir)),
        fallback=ClientReplayLLM(recordings_dir=str(fallback_dir)),
    )
    with pytest.raises(ClientReplayMiss):
        hybrid.invoke(step="discover", messages=[])


def test_hybrid_is_client_llm_subclass():
    assert issubclass(ClientHybridLLM, ClientLLMClient)


def test_from_env_returns_hybrid_when_mode_set(monkeypatch, tmp_path):
    fallback_dir = tmp_path / "fallback"
    fallback_dir.mkdir()
    _write_fixture(fallback_dir, "discover", "reasoning")

    monkeypatch.setenv("CLIENT_AGENT_LLM_MODE", "hybrid")
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", str(fallback_dir))
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    client = ClientLLMClient.from_env()
    assert isinstance(client, ClientHybridLLM)


def test_from_env_hybrid_requires_replay_dir(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_LLM_MODE", "hybrid")
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    monkeypatch.setenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

    with pytest.raises(RuntimeError, match="CLIENT_AGENT_REPLAY_DIR"):
        ClientLLMClient.from_env()
