from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Capability:
    # Original fields (kept for backward compatibility with Plan 1)
    intent: str | None = None
    method: str | None = None
    path: str | None = None
    returns: str | None = None
    example_body: dict[str, Any] | None = None
    # New agent-facing fields (Plan 2)
    id: str | None = None
    verb: str | None = None
    summary: str | None = None
    hints: list[str] = field(default_factory=list)


def build_catalog(
    *,
    service: str | None = None,
    service_name: str | None = None,
    description: str,
    capabilities: list[Capability],
    related: list[str] | None = None,
) -> dict[str, Any]:
    """Build a capabilities catalog document served at `GET /` on every service."""

    if service is not None and service_name is not None:
        raise TypeError("build_catalog() got both 'service' and 'service_name'; supply only one")
    effective_service = service if service is not None else service_name
    if effective_service is None:
        raise TypeError("build_catalog() requires either 'service' or 'service_name'")

    cap_payloads: list[dict[str, Any]] = []
    for cap in capabilities:
        payload: dict[str, Any] = {}
        # Emit only non-None / non-empty values
        if cap.intent is not None:
            payload["intent"] = cap.intent
        if cap.method is not None:
            payload["method"] = cap.method
        if cap.path is not None:
            payload["path"] = cap.path
        if cap.returns is not None:
            payload["returns"] = cap.returns
        if cap.example_body is not None:
            payload["example_body"] = cap.example_body
        if cap.id is not None:
            payload["id"] = cap.id
        if cap.verb is not None:
            payload["verb"] = cap.verb
        if cap.summary is not None:
            payload["summary"] = cap.summary
        if cap.hints:
            payload["hints"] = cap.hints
        cap_payloads.append(payload)

    return {
        "service": effective_service,
        "description": description,
        "capabilities": cap_payloads,
        "_self": "/",
        "_related": list(related or []),
    }
