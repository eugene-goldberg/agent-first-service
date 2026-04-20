from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ClientReplayMiss(RuntimeError):
    pass


class ClientLLMClient:
    @classmethod
    def from_env(cls) -> "ClientLLMClient":
        replay_dir = os.environ.get("CLIENT_AGENT_REPLAY_DIR", "").strip()
        if replay_dir:
            return ClientReplayLLM(recordings_dir=replay_dir)
        return ClientAzureLLM.from_env()

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError


class ClientReplayLLM(ClientLLMClient):
    def __init__(self, recordings_dir: str) -> None:
        self.dir = Path(recordings_dir)

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        path = self.dir / f"{step}.json"
        if not path.exists():
            raise ClientReplayMiss(
                f"No recorded response for client step={step!r} at {path}."
            )
        return json.loads(path.read_text(encoding="utf-8"))["response"]


class ClientAzureLLM(ClientLLMClient):
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
    def from_env(cls) -> "ClientAzureLLM":
        required = {
            "AZURE_OPENAI_ENDPOINT": os.environ.get("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_API_KEY": os.environ.get("AZURE_OPENAI_API_KEY"),
            "AZURE_OPENAI_DEPLOYMENT": os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
            "AZURE_OPENAI_API_VERSION": os.environ.get("AZURE_OPENAI_API_VERSION"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(
                f"Azure OpenAI config incomplete for client agent: missing {', '.join(missing)}. "
                f"Set CLIENT_AGENT_REPLAY_DIR to run offline."
            )
        return cls(
            endpoint=required["AZURE_OPENAI_ENDPOINT"],
            api_key=required["AZURE_OPENAI_API_KEY"],
            deployment=required["AZURE_OPENAI_DEPLOYMENT"],
            api_version=required["AZURE_OPENAI_API_VERSION"],
        )

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        lc = []
        for m in messages:
            role = m["role"]
            if role == "system":
                lc.append(SystemMessage(content=m["content"]))
            elif role == "user":
                lc.append(HumanMessage(content=m["content"]))
            elif role == "assistant":
                lc.append(AIMessage(content=m["content"]))
            else:
                raise ValueError(f"Unknown role {role!r}")
        result = self._client.invoke(lc)
        return {"content": result.content}
