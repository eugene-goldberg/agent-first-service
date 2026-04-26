from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

import httpx

from services.client_agent.llm import ClientLLMClient
from services.client_agent.state import ClientBriefState, ClientTraceEvent
from services.client_agent.trace_bus import ClientTraceBus


DISCOVERY_SYSTEM = """You are the client agent. Your only protocol contract is:
the orchestrator advertises its capabilities at GET /. Read the catalog and
identify which capability is the right next hop for the user's brief.
Respond with one short paragraph of reasoning."""


DECISION_SYSTEM = """Emit a JSON object of the form:
{"action": "post_orchestration", "url": "/orchestrations",
 "body": {"brief": "<pass-through>"}, "rationale": "..."}

Keep it minimal. The pass-through token `<pass-through>` means the user's
brief should be substituted verbatim before sending."""


SUMMARY_SYSTEM = """Summarize the user-visible outcome of this brief in one
paragraph of plain English. Mention milestone planning and assignment outcomes
when present. No markdown. No emojis."""


class ClientAgentRunner:
    def __init__(
        self,
        *,
        llm: ClientLLMClient,
        bus: ClientTraceBus,
        http_client: httpx.AsyncClient,
        orchestrator_base: str,
    ) -> None:
        self._llm = llm
        self._bus = bus
        self._http = http_client
        self._orchestrator_base = orchestrator_base.rstrip("/")

    async def run(
        self,
        state: ClientBriefState,
        *,
        persist_event: Callable[[ClientTraceEvent], Awaitable[None]] | None = None,
    ) -> ClientBriefState:
        async def emit(event: ClientTraceEvent) -> None:
            state.trace.append(event)
            await self._bus.publish(event)
            if persist_event is not None:
                await persist_event(event)

        # Step 1: discovery — read orchestrator catalog.
        catalog_resp = await self._http.get(f"{self._orchestrator_base}/")
        catalog = catalog_resp.json()
        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="discovery",
            summary=f"GET {self._orchestrator_base}/ → {len(catalog['data']['capabilities'])} capabilities",
            detail={"catalog_preview": [c["id"] for c in catalog["data"]["capabilities"]]},
        ))

        discover_resp = self._llm.invoke(
            step="discover",
            messages=[
                {"role": "system", "content": DISCOVERY_SYSTEM},
                {"role": "user", "content": json.dumps({"brief": state.brief, "catalog": catalog["data"]})},
            ],
        )
        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="discovery",
            summary="Reviewed orchestrator capabilities.",
            detail=_with_llm_path({"reasoning": discover_resp["content"]}, discover_resp),
        ))

        # Step 2: decide what to do next.
        decide_resp = self._llm.invoke(
            step="decide",
            messages=[
                {"role": "system", "content": DECISION_SYSTEM},
                {"role": "user", "content": json.dumps({"brief": state.brief})},
            ],
        )
        decision = json.loads(decide_resp["content"])
        if decision["action"] != "post_orchestration":
            raise RuntimeError(f"Unsupported decision action: {decision['action']!r}")

        body = dict(decision["body"])
        if body.get("brief") == "<pass-through>":
            body["brief"] = state.brief

        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="decision",
            summary=f"Will POST {decision['url']} with the user's brief.",
            detail=_with_llm_path(
                {"rationale": decision.get("rationale"), "body": body},
                decide_resp,
            ),
        ))

        # Step 3: invoke orchestrator.
        invoke_url = f"{self._orchestrator_base}{decision['url']}"
        invoke_resp = await self._http.post(invoke_url, json=body)
        invoke_body = invoke_resp.json()
        state.orchestration_job_id = invoke_body["data"]["id"]

        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="invocation",
            summary=f"POST {invoke_url} → job {state.orchestration_job_id}",
            detail={"status_code": invoke_resp.status_code, "response": invoke_body},
        ))

        # Step 4: summary.
        summary_resp = self._llm.invoke(
            step="summarize",
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": json.dumps({
                    "brief": state.brief,
                    "orchestration_job_id": state.orchestration_job_id,
                })},
            ],
        )
        state.final_summary = summary_resp["content"].strip()
        state.status = "completed"
        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="summary",
            summary=state.final_summary[:120],
            detail=_with_llm_path({"summary": state.final_summary}, summary_resp),
        ))

        return state


def _with_llm_path(detail: dict, llm_response: dict) -> dict:
    """Carry ClientHybridLLM's `_path` annotation (if present) into trace detail."""
    path = llm_response.get("_path")
    if path is not None:
        return {**detail, "llm_path": path}
    return detail
