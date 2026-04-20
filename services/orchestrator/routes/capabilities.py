from __future__ import annotations

from fastapi import APIRouter, Request

from agent_protocol.catalog import Capability, build_catalog
from agent_protocol.envelope import make_response

router = APIRouter()


ORCHESTRATOR_CAPABILITIES: list[Capability] = [
    Capability(
        id="start_orchestration",
        verb="POST",
        path="/orchestrations",
        summary="Start a new multi-step orchestration from a natural-language brief.",
        hints=["Returns a job id; poll /orchestrations/{id} or subscribe to /sse/orchestrator."],
    ),
    Capability(
        id="list_orchestrations",
        verb="GET",
        path="/orchestrations",
        summary="List recent orchestration jobs.",
        hints=["Most recent first."],
    ),
    Capability(
        id="find_orchestration",
        verb="GET",
        path="/orchestrations/{job_id}",
        summary="Fetch a single orchestration with its current status.",
        hints=["Status values: queued, running, completed, failed."],
    ),
    Capability(
        id="trace_orchestration",
        verb="GET",
        path="/orchestrations/{job_id}/trace",
        summary="Fetch the full trace (thoughts/actions/observations/final) for a job.",
        hints=["Use /sse/orchestrator for live streaming instead of polling."],
    ),
    Capability(
        id="stream_trace",
        verb="GET",
        path="/sse/orchestrator",
        summary="Server-Sent Events stream of every orchestration's trace events.",
        hints=["EventSource-compatible; each event is a JSON-encoded TraceEvent."],
    ),
]


@router.get("/")
def root(request: Request):
    return make_response(
        data=build_catalog(
            service_name="orchestrator",
            description=(
                "Agent-first orchestrator. Accepts natural-language briefs, plans "
                "multi-step work against the Projects/People/Communications services, "
                "and streams its reasoning trace over SSE. Exposes itself using the "
                "SAME hypermedia protocol as the leaf services so the client agent "
                "can consume it identically."
            ),
            capabilities=ORCHESTRATOR_CAPABILITIES,
        ),
        self_link=str(request.url),
        related=[
            {"rel": "projects_service", "href": "http://127.0.0.1:8001/", "verb": "GET"},
            {"rel": "people_service", "href": "http://127.0.0.1:8002/", "verb": "GET"},
            {"rel": "communications_service", "href": "http://127.0.0.1:8003/", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "start_orchestration", "href": "/orchestrations", "verb": "POST",
             "example_body": {"brief": "Build a marketing landing page for our Q3 launch."}},
        ],
    )
