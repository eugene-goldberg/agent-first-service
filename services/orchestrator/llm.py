from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ReplayMissError(RuntimeError):
    pass


class LLMClient:
    """Abstract interface used by the graph. See AzureLLMClient / ReplayLLMClient."""

    @classmethod
    def from_env(cls) -> "LLMClient":
        mode = os.environ.get("ORCHESTRATOR_LLM_MODE", "").strip().lower()
        replay_dir = os.environ.get("ORCHESTRATOR_REPLAY_DIR", "").strip()
        if mode == "hybrid":
            if not replay_dir:
                raise RuntimeError(
                    "ORCHESTRATOR_LLM_MODE=hybrid requires ORCHESTRATOR_REPLAY_DIR to point at a fixtures directory."
                )
            return HybridLLMClient(
                primary=AzureLLMClient.from_env(),
                fallback=ReplayLLMClient(recordings_dir=replay_dir),
            )
        if replay_dir:
            return ReplayLLMClient(recordings_dir=replay_dir)
        return AzureLLMClient.from_env()

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError


class ReplayLLMClient(LLMClient):
    def __init__(self, recordings_dir: str) -> None:
        self.recordings_dir = Path(recordings_dir)

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        path = self.recordings_dir / f"{step}.json"
        if not path.exists():
            raise ReplayMissError(
                f"No recorded response for step={step!r} at {path}. "
                f"Record a fixture or switch to live mode."
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        return data["response"]


class AzureLLMClient(LLMClient):
    def __init__(self, *, endpoint: str, api_key: str, deployment: str, api_version: str) -> None:
        from langchain_openai import AzureChatOpenAI

        self._client = AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            azure_deployment=deployment,
            api_version=api_version,
            temperature=0,
            max_retries=3,
            timeout=90,
        )

    @classmethod
    def from_env(cls) -> "AzureLLMClient":
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION")
        missing = [k for k, v in {
            "AZURE_OPENAI_ENDPOINT": endpoint,
            "AZURE_OPENAI_API_KEY": api_key,
            "AZURE_OPENAI_DEPLOYMENT": deployment,
            "AZURE_OPENAI_API_VERSION": api_version,
        }.items() if not v]
        if missing:
            raise RuntimeError(
                f"Azure OpenAI configuration incomplete. Missing env vars: {', '.join(missing)}. "
                f"Set them in .env or set ORCHESTRATOR_REPLAY_DIR to run offline."
            )
        return cls(endpoint=endpoint, api_key=api_key, deployment=deployment, api_version=api_version)

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        lc_messages = []
        for m in messages:
            role = m["role"]
            content = m["content"]
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "user":
                lc_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                raise ValueError(f"Unknown message role: {role!r}")

        result = self._client.invoke(lc_messages)
        return {"content": result.content}


class HybridLLMClient(LLMClient):
    """Tries primary (live Azure) first, falls back to replay on error.

    The return dict is annotated with `_path` = "live" | "replay_fallback" so
    callers can surface which route produced the response in trace events.
    """

    def __init__(self, *, primary: LLMClient, fallback: LLMClient) -> None:
        self._primary = primary
        self._fallback = fallback

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        try:
            result = self._primary.invoke(step=step, messages=messages)
            result["_path"] = "live"
            return result
        except Exception as primary_err:
            try:
                result = self._fallback.invoke(step=step, messages=messages)
            except Exception:
                raise primary_err
            result["_path"] = "replay_fallback"
            result["primary_error"] = f"{type(primary_err).__name__}: {primary_err}"
            return result
