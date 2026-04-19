from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agent_protocol.field_docs import DocumentedField


class CreateMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient_id: str = DocumentedField(
        description="Id of the person who should receive this message (from the people service).",
        examples=["person_alice", "person_bob"],
        min_length=1,
    )
    project_id: str | None = DocumentedField(
        description="Optional id of the project this message is about (from the projects service).",
        examples=["proj_alpha", "proj_q3_launch"],
        default=None,
    )
    subject: str = DocumentedField(
        description="Short subject line shown to the recipient.",
        examples=["You've been assigned", "Milestone update"],
        min_length=1,
    )
    body: str = DocumentedField(
        description="Full message body in plain text.",
        examples=["You've been assigned to milestone #2 of proj_alpha."],
        min_length=1,
    )


class MessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Stable message identifier.")
    recipient_id: str
    project_id: str | None
    subject: str
    body: str
    sent_at: datetime
    status: str
