from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Request

from agent_protocol.envelope import make_response
from agent_protocol.errors import AgentError

from services.client_agent.models import BriefOut, ClientTraceEventOut, CreateBrief
from services.client_agent.runner import ClientAgentRunner
from services.client_agent.state import ClientBriefState

router = APIRouter()


def _out(state: ClientBriefState) -> BriefOut:
    return BriefOut(
        id=state.brief_id,
        brief=state.brief,
        status=state.status,
        orchestration_job_id=state.orchestration_job_id,
        final_summary=state.final_summary,
    )


@router.post("/client/briefs", status_code=202)
async def submit_brief(payload: CreateBrief, request: Request):
    brief_id = f"cb_{uuid.uuid4().hex[:8]}"
    state = ClientBriefState(brief_id=brief_id, brief=payload.brief, status="running")
    request.app.state.briefs[brief_id] = state

    runner = ClientAgentRunner(
        llm=request.app.state.llm,
        bus=request.app.state.trace_bus,
        http_client=request.app.state.http_client,
        orchestrator_base=request.app.state.orchestrator_base,
    )

    async def _background():
        try:
            await runner.run(state)
        except Exception as exc:
            state.status = "failed"
            state.final_summary = f"Runner error: {exc!r}"

    asyncio.create_task(_background())

    return make_response(
        data=_out(state).model_dump(),
        self_link=str(request.url_for("find_brief", brief_id=brief_id)),
        related=[
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
            {"rel": "orchestrator", "href": request.app.state.orchestrator_base + "/", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "find_brief", "href": f"/client/briefs/{brief_id}", "verb": "GET"},
            {"rel": "trace_brief", "href": f"/client/briefs/{brief_id}/trace", "verb": "GET"},
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
        ],
    )


@router.get("/client/briefs/{brief_id}", name="find_brief")
def find_brief(brief_id: str, request: Request):
    state: ClientBriefState | None = request.app.state.briefs.get(brief_id)
    if state is None:
        raise AgentError(
            status_code=404,
            error="brief_not_found",
            message=f"No brief with id={brief_id!r}.",
            why="The id does not match any submitted brief.",
            try_instead="GET /client/briefs — list recent briefs to find the right id.",
            related=[{"rel": "list_briefs", "href": "/client/briefs", "verb": "GET"}],
        )

    return make_response(
        data=_out(state).model_dump(),
        self_link=str(request.url),
        related=[
            {"rel": "trace_brief", "href": f"/client/briefs/{brief_id}/trace", "verb": "GET"},
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "trace_brief", "href": f"/client/briefs/{brief_id}/trace", "verb": "GET"},
        ],
    )


@router.get("/client/briefs")
def list_briefs(request: Request):
    states: dict[str, ClientBriefState] = request.app.state.briefs
    out = [_out(s).model_dump() for s in states.values()]

    return make_response(
        data=out,
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "submit_brief", "href": "/client/briefs", "verb": "POST"},
        ],
    )


@router.get("/client/briefs/{brief_id}/trace", name="trace_brief")
def trace_brief(brief_id: str, request: Request):
    state: ClientBriefState | None = request.app.state.briefs.get(brief_id)
    if state is None:
        raise AgentError(
            status_code=404,
            error="brief_not_found",
            message=f"No brief with id={brief_id!r}.",
            why="The id does not match any submitted brief.",
            try_instead="GET /client/briefs — list recent briefs to find the right id.",
            related=[{"rel": "list_briefs", "href": "/client/briefs", "verb": "GET"}],
        )

    events = [
        ClientTraceEventOut(
            brief_id=e.brief_id,
            kind=e.kind,
            summary=e.summary,
            detail=e.detail,
            at=e.at,
        ).model_dump(mode="json")
        for e in state.trace
    ]

    return make_response(
        data=events,
        self_link=str(request.url),
        related=[{"rel": "find_brief", "href": f"/client/briefs/{brief_id}", "verb": "GET"}],
        suggested_next=[],
    )
