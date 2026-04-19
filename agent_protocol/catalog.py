from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Capability:
    intent: str
    method: str
    path: str
    returns: str
    example_body: dict[str, Any] | None = None


def build_catalog(
    *,
    service: str,
    description: str,
    capabilities: list[Capability],
    related: list[str] | None = None,
) -> dict[str, Any]:
    """Build a capabilities catalog document served at `GET /` on every service."""

    cap_payloads: list[dict[str, Any]] = []
    for cap in capabilities:
        payload = {
            "intent": cap.intent,
            "method": cap.method,
            "path": cap.path,
            "returns": cap.returns,
        }
        if cap.example_body is not None:
            payload["example_body"] = cap.example_body
        cap_payloads.append(payload)

    return {
        "service": service,
        "description": description,
        "capabilities": cap_payloads,
        "_self": "/",
        "_related": list(related or []),
    }
