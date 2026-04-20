from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_protocol.field_docs import DocumentedField


class CreateBrief(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brief: str = DocumentedField(
        description="Natural-language work request typed by the presenter.",
        examples=[
            "Build a marketing landing page for our Q3 launch.",
            "Find someone with design skill who has bandwidth.",
        ],
        min_length=1,
    )


class BriefOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    brief: str
    status: str
    orchestration_job_id: str | None
    final_summary: str | None


class ClientTraceEventOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brief_id: str
    kind: str
    summary: str
    detail: dict[str, Any]
    at: datetime
