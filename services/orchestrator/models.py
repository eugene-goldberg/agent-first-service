from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_protocol.field_docs import DocumentedField


class CreateOrchestration(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brief: str = DocumentedField(
        description="Natural-language work request from the client agent.",
        examples=[
            "Build a marketing landing page for our Q3 launch.",
            "Assign someone with design skill to the onboarding redesign project.",
        ],
        min_length=1,
    )


class OrchestrationOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    brief: str
    status: str
    final_summary: str | None


class TraceEventOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    job_id: str
    kind: str
    summary: str
    detail: dict[str, Any]
    at: datetime
