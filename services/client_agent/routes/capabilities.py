from __future__ import annotations

from fastapi import APIRouter, Request

from agent_protocol.catalog import Capability, build_catalog
from agent_protocol.envelope import make_response

router = APIRouter()


CLIENT_AGENT_CAPABILITIES: list[Capability] = [
    Capability(
        id="submit_brief",
        verb="POST",
        path="/client/briefs",
        summary="Submit a natural-language work brief to the client agent.",
        hints=["Returns a brief id; subscribe to /sse/client for live reasoning."],
    ),
    Capability(
        id="list_briefs",
        verb="GET",
        path="/client/briefs",
        summary="List recent briefs submitted to the client agent.",
        hints=["Most recent first."],
    ),
    Capability(
        id="find_brief",
        verb="GET",
        path="/client/briefs/{brief_id}",
        summary="Fetch a brief's status and final summary.",
        hints=["Status values: pending, running, completed, failed."],
    ),
    Capability(
        id="trace_brief",
        verb="GET",
        path="/client/briefs/{brief_id}/trace",
        summary="Fetch the full reasoning trace for a brief.",
        hints=["Use /sse/client for live streaming."],
    ),
    Capability(
        id="stream_client_trace",
        verb="GET",
        path="/sse/client",
        summary="SSE stream of every client-agent reasoning event.",
        hints=["EventSource-compatible; each event is a JSON ClientTraceEvent."],
    ),
]


@router.get("/")
def root(request: Request):
    return make_response(
        data=build_catalog(
            service_name="client_agent",
            description=(
                "The 'user-facing' agent. Takes a natural-language brief, "
                "discovers the orchestrator's capabilities through the hypermedia "
                "protocol, forwards the brief, and streams a summary. The presenter "
                "types into its POST /client/briefs endpoint."
            ),
            capabilities=CLIENT_AGENT_CAPABILITIES,
        ),
        self_link=str(request.url),
        related=[
            {"rel": "orchestrator", "href": "http://127.0.0.1:8000/", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "submit_brief", "href": "/client/briefs", "verb": "POST",
             "example_body": {"brief": "Build a marketing landing page for our Q3 launch."}},
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
        ],
    )
