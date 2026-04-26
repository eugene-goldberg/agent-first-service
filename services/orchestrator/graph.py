from __future__ import annotations

import json
import uuid
from typing import Any, Callable, Awaitable, Literal

from services.orchestrator.llm import LLMClient
from services.orchestrator.mcp_tools import MCPToolbox
from services.orchestrator.state import OrchestrationState, OrchestrationStep, TraceEvent
from services.orchestrator.tools import HTTPToolbox
from services.orchestrator.trace_bus import TraceBus


PLANNER_SYSTEM = """You are the planner for an agent-first SaaS project management system.
You have access to three leaf services over HTTP:
- Projects service at {projects_base}
- People service at {people_base}
- Communications service at {comms_base}

The catalogs below list EVERY endpoint each service exposes. You MUST plan using
only these exact paths. Do NOT invent URLs like /pages, /marketing, /launches —
if a concept isn't in a catalog, map it to the closest real endpoint (a project
or a task) or skip that step.

=== Projects catalog ===
{projects_catalog}

=== People catalog ===
{people_catalog}

=== Communications catalog ===
{comms_catalog}

Your job: given a natural-language brief, produce a short JSON plan like:

{{"steps": [
  {{"verb": "POST", "url": "{projects_base}/projects", "rationale": "..."}},
  ...
]}}

Keep the plan to 6 steps or fewer. Return ONLY the JSON."""


ACTOR_SYSTEM = """You are executing the plan one step at a time.
For the next step, produce ONLY a JSON object of the form:

{"verb": "GET"|"POST"|"PATCH"|"DELETE", "url": "...", "body": {...} | null, "rationale": "...", "is_final": false}

Hard rules:
- Only use URLs whose path appears in the catalogs shown in the plan's system prompt.
- If an earlier observation returned 404, do NOT retry the same path — pick a different real endpoint or signal completion.
- If the brief cannot be fulfilled with the available endpoints, emit is_final:true with a summary explaining what was accomplished and what's out of scope.

When you believe all necessary work is done, emit {"is_final": true, "summary": "one-sentence result"}."""


PLANNER_SYSTEM_MCP = """You are the planner for an agent-first SaaS project management system.
You have access to three leaf services via MCP (Model Context Protocol). Tools are
invoked via MCP ``tools/call``; each tool name below is authoritative.

The tool lists below enumerate EVERY tool each server exposes. You MUST plan using
only these exact (server, tool) pairs. Do NOT invent tool names — if a concept is
not in a list, map it to the closest real tool or skip that step.

=== Projects server tools ===
{projects_tools}

=== People server tools ===
{people_tools}

=== Communications server tools ===
{comms_tools}

Your job: given a natural-language brief, produce a short JSON plan like:

{{"steps": [
  {{"server": "projects", "tool": "post_projects", "rationale": "..."}},
  ...
]}}

Keep the plan to 6 steps or fewer. Return ONLY the JSON."""


ACTOR_SYSTEM_MCP = """You are executing the plan one step at a time via MCP tools/call.
For the next step, produce ONLY a JSON object of the form:

{"server": "...", "tool": "...", "arguments": {...}, "rationale": "...", "is_final": false}

Hard rules:
- Only use (server, tool) pairs whose tool name appears in the tool lists shown in the plan's system prompt.
- The ``arguments`` keys MUST match the required/optional argument names shown in the ``tool_schemas`` field of the user message. Do NOT invent field names (e.g. do not send ``name`` if the schema lists ``title``).
- If an earlier observation returned an error envelope (status=error or content._why), do NOT retry the same call — pick a different tool or signal completion.
- If the brief cannot be fulfilled with the available tools, emit is_final:true with a summary explaining what was accomplished and what's out of scope.

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
        mode: Literal["http", "mcp"] = "http",
        mcp_toolbox: MCPToolbox | None = None,
    ) -> None:
        self._llm = llm
        self._toolbox = toolbox
        self._bus = bus
        self._projects_base = projects_base
        self._people_base = people_base
        self._comms_base = comms_base
        self._max_steps = max_steps
        self._mode = mode
        self._mcp_toolbox = mcp_toolbox
        if mode == "mcp":
            assert mcp_toolbox is not None, (
                "OrchestrationGraph(mode='mcp', ...) requires mcp_toolbox"
            )

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

        # Node: pre-plan discovery — fetch live catalogs so the planner is grounded
        # in the actual advertised endpoints (no more hallucinated /pages).
        if self._mode == "mcp":
            assert self._mcp_toolbox is not None  # narrowed by constructor
            projects_tools_list = await self._mcp_toolbox.list_tools("projects")
            people_tools_list = await self._mcp_toolbox.list_tools("people")
            comms_tools_list = await self._mcp_toolbox.list_tools("communications")

            await emit(TraceEvent(
                job_id=state.job_id,
                kind="observation",
                summary="Fetched 3 leaf-service MCP tool lists for planner grounding.",
                detail={
                    "projects_capabilities": [t["name"] for t in projects_tools_list],
                    "people_capabilities": [t["name"] for t in people_tools_list],
                    "comms_capabilities": [t["name"] for t in comms_tools_list],
                },
            ))

            plan_messages = [
                {"role": "system", "content": PLANNER_SYSTEM_MCP.format(
                    projects_tools=_mcp_tools_summary(projects_tools_list),
                    people_tools=_mcp_tools_summary(people_tools_list),
                    comms_tools=_mcp_tools_summary(comms_tools_list),
                )},
                {"role": "user", "content": state.brief},
            ]
        else:
            projects_catalog = await self._toolbox.http_get(f"{self._projects_base}/")
            people_catalog = await self._toolbox.http_get(f"{self._people_base}/")
            comms_catalog = await self._toolbox.http_get(f"{self._comms_base}/")

            await emit(TraceEvent(
                job_id=state.job_id,
                kind="observation",
                summary="Fetched 3 leaf-service catalogs for planner grounding.",
                detail={
                    "projects_capabilities": _catalog_paths(projects_catalog),
                    "people_capabilities": _catalog_paths(people_catalog),
                    "comms_capabilities": _catalog_paths(comms_catalog),
                },
            ))

            # Node: plan
            plan_messages = [
                {"role": "system", "content": PLANNER_SYSTEM.format(
                    projects_base=self._projects_base,
                    people_base=self._people_base,
                    comms_base=self._comms_base,
                    projects_catalog=_catalog_summary(projects_catalog),
                    people_catalog=_catalog_summary(people_catalog),
                    comms_catalog=_catalog_summary(comms_catalog),
                )},
                {"role": "user", "content": state.brief},
            ]
        plan_response = self._llm.invoke(step="plan", messages=plan_messages)
        plan_json = _parse_json(plan_response["content"])

        await emit(TraceEvent(
            job_id=state.job_id,
            kind="thought",
            summary=f"Planned {len(plan_json.get('steps', []))} step(s).",
            detail=_with_llm_path({"plan": plan_json}, plan_response),
        ))
        state.transcript.append({"role": "assistant", "content": plan_response["content"]})

        # Node: act/observe loop
        actor_system = ACTOR_SYSTEM_MCP if self._mode == "mcp" else ACTOR_SYSTEM
        # In MCP mode, every actor turn also receives a compact tool-schema
        # summary so it picks the right argument names (e.g. ``title`` for
        # tasks rather than ``name``). The planner's system prompt includes
        # this info, but the actor's user message is a JSON blob that does
        # not replay that prompt, so we re-inject it here.
        actor_user_extra: dict[str, Any] = {}
        if self._mode == "mcp":
            actor_user_extra["tool_schemas"] = {
                "projects": _mcp_tools_summary(projects_tools_list),
                "people": _mcp_tools_summary(people_tools_list),
                "communications": _mcp_tools_summary(comms_tools_list),
            }
        for step_index in range(self._max_steps):
            actor_messages = [
                {"role": "system", "content": actor_system},
                {"role": "user", "content": json.dumps({
                    "brief": state.brief,
                    "plan": plan_json,
                    "step_index": step_index,
                    "recent_observations": state.transcript[-4:],
                    **actor_user_extra,
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
                    detail=_with_llm_path({"summary": summary}, act_response),
                ))
                state.completed = True
                state.final_summary = summary
                return state

            if self._mode == "mcp":
                step = OrchestrationStep(
                    server=decision["server"],
                    tool=decision["tool"],
                    body=decision.get("arguments") or {},
                    rationale=decision.get("rationale"),
                )

                await emit(TraceEvent(
                    job_id=state.job_id,
                    kind="action",
                    summary=f"{step.server}.{step.tool}",
                    detail=_with_llm_path(
                        {"server": step.server, "tool": step.tool,
                         "arguments": step.body, "rationale": step.rationale},
                        act_response,
                    ),
                ))

                observation = await self._dispatch(step)
                obs_status = observation.get("status", "error")
                await emit(TraceEvent(
                    job_id=state.job_id,
                    kind="observation",
                    summary=f"← {obs_status} from {step.server}.{step.tool}",
                    detail=observation,
                ))
            else:
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
                    detail=_with_llm_path(
                        {"verb": step.verb, "url": step.url, "body": step.body,
                         "rationale": step.rationale},
                        act_response,
                    ),
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
            detail=_with_llm_path({"summary": summary, "reason": "max_steps_reached"}, fin),
        ))
        state.completed = True
        state.final_summary = summary
        return state

    async def _dispatch(self, step: OrchestrationStep) -> dict[str, Any]:
        if self._mode == "mcp":
            assert self._mcp_toolbox is not None  # narrowed by constructor
            assert step.server is not None and step.tool is not None, (
                f"MCP-mode step missing server/tool: {step!r}"
            )
            return await self._mcp_toolbox.call_tool(
                step.server, step.tool, step.body or {}
            )
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


def _with_llm_path(detail: dict[str, Any], llm_response: dict[str, Any]) -> dict[str, Any]:
    """Carry HybridLLMClient's `_path` annotation (if present) into trace detail."""
    path = llm_response.get("_path")
    if path is not None:
        return {**detail, "llm_path": path}
    return detail


def _catalog_body(observation: dict[str, Any]) -> dict[str, Any]:
    body = observation.get("body") if isinstance(observation, dict) else None
    if not isinstance(body, dict):
        return {}
    return body.get("data") if isinstance(body.get("data"), dict) else body


def _catalog_summary(observation: dict[str, Any]) -> str:
    body = _catalog_body(observation)
    caps = body.get("capabilities", []) or []
    lines = []
    for c in caps:
        verb = c.get("verb") or c.get("method") or "?"
        path = c.get("path") or "?"
        summary = c.get("summary") or c.get("intent") or c.get("returns") or ""
        lines.append(f"{verb} {path} — {summary}")
    return "\n".join(lines) if lines else "(no capabilities reported)"


def _catalog_paths(observation: dict[str, Any]) -> list[str]:
    body = _catalog_body(observation)
    caps = body.get("capabilities", []) or []
    return [f"{c.get('verb') or c.get('method') or '?'} {c.get('path') or '?'}" for c in caps]


def _mcp_tools_summary(tools: list[dict[str, Any]]) -> str:
    """Render ``[{name, description, inputSchema}, ...]`` as a plain-text list
    for injection into ``PLANNER_SYSTEM_MCP``. Mirrors ``_catalog_summary``'s
    role in HTTP mode — one line per tool, name + short description + the
    argument-name summary (required vs optional) so the LLM picks the right
    field names without having to guess from the tool name alone. Without
    the argument summary the LLM confuses HTTP-body field names (e.g.
    ``name`` for a task) with MCP-schema field names (e.g. ``title``)."""
    if not tools:
        return "(no tools advertised)"
    lines = []
    for t in tools:
        name = t.get("name", "?")
        description = (t.get("description") or "").strip()
        schema = t.get("inputSchema") or {}
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        if props:
            required_names = sorted(p for p in props if p in required)
            optional_names = sorted(p for p in props if p not in required)
            parts = []
            if required_names:
                parts.append("required=" + ",".join(required_names))
            if optional_names:
                parts.append("optional=" + ",".join(optional_names))
            args_summary = " [" + "; ".join(parts) + "]" if parts else ""
        else:
            args_summary = ""
        if description:
            lines.append(f"- {name} — {description}{args_summary}")
        else:
            lines.append(f"- {name}{args_summary}")
    return "\n".join(lines)
