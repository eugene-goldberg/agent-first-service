from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ClientTraceKind = Literal["discovery", "decision", "invocation", "observation", "summary", "error"]


class ClientTraceEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brief_id: str
    kind: ClientTraceKind
    summary: str = Field(..., description="One-line human-readable summary.")
    detail: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClientBriefState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    brief_id: str
    brief: str
    orchestration_job_id: str | None = None
    trace: list[ClientTraceEvent] = Field(default_factory=list)
    status: str = "pending"
    final_summary: str | None = None
