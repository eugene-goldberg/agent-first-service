from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


TraceKind = Literal["thought", "action", "observation", "error", "final"]


class TraceEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    job_id: str
    kind: TraceKind
    summary: str = Field(..., description="One-line human-readable summary.")
    detail: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrchestrationStep(BaseModel):
    # HTTP-mode fields: verb/url populated for HTTP dispatch.
    # MCP-mode fields: server/tool populated; verb/url left as None. ``body``
    # is repurposed to carry MCP ``arguments`` so ``_dispatch`` can remain a
    # thin dispatch without copying fields around.
    verb: Literal["GET", "POST", "PATCH", "DELETE"] | None = None
    url: str | None = None
    body: dict[str, Any] | None = None
    rationale: str | None = None
    server: str | None = None
    tool: str | None = None


class OrchestrationState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    job_id: str
    brief: str
    transcript: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[TraceEvent] = Field(default_factory=list)
    completed: bool = False
    final_summary: str | None = None
