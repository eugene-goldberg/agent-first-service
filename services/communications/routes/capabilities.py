from __future__ import annotations

from fastapi import APIRouter, Request

from agent_protocol.catalog import Capability, build_catalog
from agent_protocol.envelope import make_response

router = APIRouter()


COMMUNICATIONS_CAPABILITIES: list[Capability] = [
    Capability(
        id="list_messages",
        verb="GET",
        path="/messages",
        summary="List every message, most recent first.",
        hints=["Combine with filters to narrow scope."],
    ),
    Capability(
        id="find_message",
        verb="GET",
        path="/messages/{message_id}",
        summary="Fetch a single message by id.",
        hints=["Returns 404 with `_try_instead` pointing to `GET /messages`."],
    ),
    Capability(
        id="send_message",
        verb="POST",
        path="/messages",
        summary="Send a new message to a person (optionally about a project).",
        hints=["Body fields: recipient_id, subject, body, project_id (optional)."],
    ),
    Capability(
        id="filter_by_recipient",
        verb="GET",
        path="/messages?recipient_id={person_id}",
        summary="List all messages sent to a specific person.",
        hints=["Matches the exact person id string."],
    ),
    Capability(
        id="filter_by_project",
        verb="GET",
        path="/messages?project_id={project_id}",
        summary="List all messages about a specific project.",
        hints=["Useful for building a project status timeline."],
    ),
]


@router.get("/")
def root(request: Request):
    return make_response(
        data=build_catalog(
            service_name="communications",
            description="Notifications, assignments, and status updates sent to team members.",
            capabilities=COMMUNICATIONS_CAPABILITIES,
        ),
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "list_messages", "href": "/messages", "verb": "GET"},
            {"rel": "send_message", "href": "/messages", "verb": "POST"},
        ],
    )
