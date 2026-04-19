from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from agent_protocol.envelope import make_response
from agent_protocol.errors import AgentError

from services.communications.db import MessageRow
from services.communications.models import CreateMessage, MessageOut

router = APIRouter()


def _row_to_out(row: MessageRow) -> MessageOut:
    return MessageOut(
        id=row.id,
        recipient_id=row.recipient_id,
        project_id=row.project_id,
        subject=row.subject,
        body=row.body,
        sent_at=row.sent_at,
        status=row.status,
    )


def _message_suggested_next(message: MessageOut) -> list[dict]:
    suggestions: list[dict] = [
        {"rel": "list_messages", "href": "/messages", "verb": "GET"},
        {
            "rel": "filter_by_recipient",
            "href": f"/messages?recipient_id={message.recipient_id}",
            "verb": "GET",
        },
    ]
    if message.project_id:
        suggestions.append({
            "rel": "filter_by_project",
            "href": f"/messages?project_id={message.project_id}",
            "verb": "GET",
        })
    return suggestions


@router.post("/messages", status_code=201)
def send_message(payload: CreateMessage, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        row = MessageRow(
            id=message_id,
            recipient_id=payload.recipient_id,
            project_id=payload.project_id,
            subject=payload.subject,
            body=payload.body,
            sent_at=datetime.now(timezone.utc),
            status="sent",
        )
        session.add(row)
        session.commit()
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(mode="json"),
        self_link=str(request.url_for("get_message", message_id=message_id)),
        related=[{"rel": "list_messages", "href": "/messages", "verb": "GET"}],
        suggested_next=_message_suggested_next(out),
    )


@router.get("/messages/{message_id}", name="get_message")
def get_message(message_id: str, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        row = session.get(MessageRow, message_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="message_not_found",
                message=f"No message with id={message_id!r}.",
                why="The id does not match any stored message.",
                try_instead="GET /messages — list all messages and pick an id from the result.",
                related=[{"rel": "list_messages", "href": "/messages", "verb": "GET"}],
            )
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(mode="json"),
        self_link=str(request.url),
        related=[{"rel": "list_messages", "href": "/messages", "verb": "GET"}],
        suggested_next=_message_suggested_next(out),
    )


@router.get("/messages")
def list_messages(
    request: Request,
    recipient_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        stmt = select(MessageRow).order_by(MessageRow.sent_at.desc())
        if recipient_id is not None:
            stmt = stmt.where(MessageRow.recipient_id == recipient_id)
        if project_id is not None:
            stmt = stmt.where(MessageRow.project_id == project_id)
        rows = session.execute(stmt).scalars().all()
        results = [_row_to_out(r) for r in rows]

    return make_response(
        data=[m.model_dump(mode="json") for m in results],
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "find_message", "href": "/messages/{message_id}", "verb": "GET"},
        ],
    )
