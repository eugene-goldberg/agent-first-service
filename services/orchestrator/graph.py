from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Awaitable

from services.orchestrator.llm import LLMClient
from services.orchestrator.state import OrchestrationState, OrchestrationStep, TraceEvent
from services.orchestrator.tools import HTTPToolbox
from services.orchestrator.trace_bus import TraceBus


PLANNER_SYSTEM = """You are the planner for an agent-first SaaS project management system.
You have access to three leaf services over HTTP:
- Projects service at {projects_base}
- People service at {people_base}
- Communications service at {comms_base}

Each service exposes a self-describing capability catalog at GET /.
Your job: given a natural-language brief, produce a short JSON plan like:

{{"steps": [
  {{"verb": "GET", "url": "<base>/", "rationale": "discover capabilities"}},
  ...
]}}

Keep the plan to 6 steps or fewer. Return ONLY the JSON."""


ACTOR_SYSTEM = """You are executing the plan one step at a time.
For the next step, produce ONLY a JSON object of the form:

{"verb": "GET"|"POST"|"PATCH"|"DELETE", "url": "...", "body": {...} | null, "rationale": "...", "is_final": false}

When you believe all necessary work is done, emit {"is_final": true, "summary": "one-sentence result"}."""


class OrchestrationGraph:
    def __init__(
        self,
        *,
        llm: LLMClient,
        toolbox: HTTPToolbox,
        bus: TraceBus,
        projects_base: str,
        people_base: str,
        comms_base: str,
        max_steps: int = 8,
    ) -> None:
        self._llm = llm
        self._toolbox = toolbox
        self._bus = bus
        self._projects_base = projects_base
        self._people_base = people_base
        self._comms_base = comms_base
        self._max_steps = max_steps

    async def run(
        self,
        state: OrchestrationState,
        *,
        persist_event: Callable[[TraceEvent], Awaitable[None]] | None = None,
    ) -> OrchestrationState:
        async def emit(event: TraceEvent) -> None:
            state.trace.append(event)
            await self._bus.publish(event)
            if persist_event is not None:
                await persist_event(event)

        # Node: plan
        plan_messages = [
            {"role": "system", "content": PLANNER_SYSTEM.format(
                projects_base=self._projects_base,
                people_base=self._people_base,
                comms_base=self._comms_base,
            )},
            {"role": "user", "content": state.brief},
        ]
        plan_response = self._llm.invoke(step="plan", messages=plan_messages)
        plan_json = _parse_json(plan_response["content"])

        await emit(TraceEvent(
            job_id=state.job_id,
            kind="thought",
            summary=f"Planned {len(plan_json.get('steps', []))} step(s).",
            detail={"plan": plan_json},
        ))
        state.transcript.append({"role": "assistant", "content": plan_response["content"]})

        # Node: act/observe loop
        for step_index in range(self._max_steps):
            actor_messages = [
                {"role": "system", "content": ACTOR_SYSTEM},
                {"role": "user", "content": json.dumps({
                    "brief": state.brief,
                    "plan": plan_json,
                    "step_index": step_index,
                    "recent_observations": state.transcript[-4:],
                })},
            ]
            act_response = self._llm.invoke(step=f"act_{step_index + 1}", messages=actor_messages)
            decision = _parse_json(act_response["content"])

            if decision.get("is_final"):
                summary = decision.get("summary", "done")
                await emit(TraceEvent(
                    job_id=state.job_id,
                    kind="final",
                    summary=summary,
                    detail={"summary": summary},
                ))
                state.completed = True
                state.final_summary = summary
                return state

            step = OrchestrationStep(
                verb=decision["verb"],
                url=decision["url"],
                body=decision.get("body"),
                rationale=decision.get("rationale"),
            )

            await emit(TraceEvent(
                job_id=state.job_id,
                kind="action",
                summary=f"{step.verb} {step.url}",
                detail={"verb": step.verb, "url": step.url, "body": step.body,
                        "rationale": step.rationale},
            ))

            observation = await self._dispatch(step)

            await emit(TraceEvent(
                job_id=state.job_id,
                kind="observation",
                summary=f"← {observation['status_code']} from {step.url}",
                detail=observation,
            ))
            state.transcript.append({
                "role": "tool",
                "content": json.dumps({"request": decision, "response": observation})[:4000],
            })

        # Node: finalize (fallback if LLM didn't signal completion)
        fin_messages = [
            {"role": "system", "content": "Summarize what happened in one sentence."},
            {"role": "user", "content": json.dumps({
                "brief": state.brief,
                "trace": [e.model_dump(mode="json") for e in state.trace],
            })},
        ]
        fin = self._llm.invoke(step="finalize", messages=fin_messages)
        summary = fin["content"].strip()
        await emit(TraceEvent(
            job_id=state.job_id,
            kind="final",
            summary=summary,
            detail={"summary": summary, "reason": "max_steps_reached"},
        ))
        state.completed = True
        state.final_summary = summary
        return state

    async def _dispatch(self, step: OrchestrationStep) -> dict[str, Any]:
        if step.verb == "GET":
            return await self._toolbox.http_get(step.url)
        if step.verb == "POST":
            return await self._toolbox.http_post(step.url, body=step.body)
        if step.verb == "PATCH":
            return await self._toolbox.http_patch(step.url, body=step.body)
        if step.verb == "DELETE":
            return await self._toolbox.http_delete(step.url)
        raise ValueError(f"Unknown verb {step.verb!r}")


def _parse_json(text: str) -> dict[str, Any]:
    """Tolerant parser: strip ```json fences if present, then json.loads."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        first_newline = stripped.find("\n")
        if first_newline != -1:
            stripped = stripped[first_newline + 1 :]
        if stripped.endswith("```"):
            stripped = stripped[:-3]
    return json.loads(stripped.strip())
