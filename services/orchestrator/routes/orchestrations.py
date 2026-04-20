from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sqlalchemy import select

from agent_protocol.envelope import make_response
from agent_protocol.errors import AgentError

from services.orchestrator.db import JobRow, TraceEventRow
from services.orchestrator.models import CreateOrchestration, OrchestrationOut, TraceEventOut

router = APIRouter()


def _row_to_out(row: JobRow) -> OrchestrationOut:
    return OrchestrationOut(
        id=row.id,
        brief=row.brief,
        status=row.status,
        final_summary=row.final_summary,
    )


@router.post("/orchestrations", status_code=202)
def start_orchestration(payload: CreateOrchestration, request: Request):
    runner = request.app.state.runner
    job_id = runner.start(brief=payload.brief)

    session_maker = request.app.state.session_maker
    with session_maker() as session:
        row = session.get(JobRow, job_id)
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(),
        self_link=str(request.url_for("get_orchestration", job_id=job_id)),
        related=[
            {"rel": "stream_trace", "href": "/sse/orchestrator", "verb": "GET"},
            {"rel": "list_orchestrations", "href": "/orchestrations", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "find_orchestration", "href": f"/orchestrations/{job_id}", "verb": "GET"},
            {"rel": "trace_orchestration", "href": f"/orchestrations/{job_id}/trace", "verb": "GET"},
            {"rel": "stream_trace", "href": "/sse/orchestrator", "verb": "GET"},
        ],
    )


@router.get("/orchestrations/{job_id}", name="get_orchestration")
def get_orchestration(job_id: str, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        row = session.get(JobRow, job_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="orchestration_not_found",
                message=f"No orchestration with id={job_id!r}.",
                why="The id does not match any started job.",
                try_instead="GET /orchestrations — list recent orchestrations to find the right id.",
                related=[{"rel": "list_orchestrations", "href": "/orchestrations", "verb": "GET"}],
            )
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(),
        self_link=str(request.url),
        related=[
            {"rel": "trace_orchestration", "href": f"/orchestrations/{job_id}/trace", "verb": "GET"},
            {"rel": "stream_trace", "href": "/sse/orchestrator", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "trace_orchestration", "href": f"/orchestrations/{job_id}/trace", "verb": "GET"},
        ],
    )


@router.get("/orchestrations")
def list_orchestrations(request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        rows = session.execute(select(JobRow).order_by(JobRow.created_at.desc())).scalars().all()
        results = [_row_to_out(r) for r in rows]

    return make_response(
        data=[r.model_dump() for r in results],
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "find_orchestration", "href": "/orchestrations/{job_id}", "verb": "GET"},
        ],
    )


@router.get("/orchestrations/{job_id}/trace", name="trace_orchestration")
def trace_orchestration(job_id: str, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        job = session.get(JobRow, job_id)
        if job is None:
            raise AgentError(
                status_code=404,
                error="orchestration_not_found",
                message=f"No orchestration with id={job_id!r}.",
                why="The id does not match any started job.",
                try_instead="GET /orchestrations — list recent orchestrations first.",
                related=[{"rel": "list_orchestrations", "href": "/orchestrations", "verb": "GET"}],
            )
        events = session.execute(
            select(TraceEventRow).where(TraceEventRow.job_id == job_id).order_by(TraceEventRow.at)
        ).scalars().all()

    out = [
        TraceEventOut(
            id=e.id,
            job_id=e.job_id,
            kind=e.kind,
            summary=e.summary,
            detail=json.loads(e.detail_json),
            at=e.at,
        ).model_dump(mode="json")
        for e in events
    ]

    return make_response(
        data=out,
        self_link=str(request.url),
        related=[
            {"rel": "find_orchestration", "href": f"/orchestrations/{job_id}", "verb": "GET"},
            {"rel": "stream_trace", "href": "/sse/orchestrator", "verb": "GET"},
        ],
        suggested_next=[],
    )
