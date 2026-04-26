"""Tests for ``agent_protocol.mcp_adapter.capability_to_tool``.

Exercises the adapter against the real, module-level capability lists from
each leaf service (Projects, People, Communications) — no mocks, no
hand-built ``Capability`` objects.
"""

from __future__ import annotations

import pytest
from mcp.types import Tool
from pydantic import BaseModel

from agent_protocol.catalog import Capability
from agent_protocol.mcp_adapter import capability_to_tool
from services.communications.routes.capabilities import COMMUNICATIONS_CAPABILITIES
from services.people.routes.capabilities import PEOPLE_CAPABILITIES
from services.projects.routes.capabilities import _CAPABILITIES as PROJECTS_CAPABILITIES


ALL_SERVICE_CAPABILITIES: list[tuple[str, list[Capability]]] = [
    ("projects", PROJECTS_CAPABILITIES),
    ("people", PEOPLE_CAPABILITIES),
    ("communications", COMMUNICATIONS_CAPABILITIES),
]


def _flatten() -> list[tuple[str, Capability]]:
    out: list[tuple[str, Capability]] = []
    for service, caps in ALL_SERVICE_CAPABILITIES:
        for cap in caps:
            out.append((service, cap))
    return out


@pytest.mark.parametrize("service,cap", _flatten())
def test_every_capability_produces_valid_mcp_tool(service: str, cap: Capability) -> None:
    """Every real capability must map to a dict that constructs a valid Tool."""

    spec = capability_to_tool(cap)
    tool = Tool(**spec)

    assert tool.name == spec["name"]
    assert tool.name != ""
    schema = tool.inputSchema
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "required" in schema
    assert isinstance(schema["properties"], dict)
    assert isinstance(schema["required"], list)


@pytest.mark.parametrize("service,caps", ALL_SERVICE_CAPABILITIES)
def test_tool_names_unique_within_service(
    service: str, caps: list[Capability]
) -> None:
    names = [capability_to_tool(c)["name"] for c in caps]
    assert len(names) == len(set(names)), (
        f"{service}: duplicate tool names produced: {names}"
    )


def test_projects_exact_derived_names() -> None:
    """Per-capability name assertions covering every Projects entry."""

    expected = [
        "get_projects",
        "post_projects",
        "get_projects_id",
        "patch_projects_id",
        "get_projects_id_tasks",
        "post_projects_id_tasks",
        "patch_tasks_id",
        "get_tasks_assignee_id_status_status_milestone_id",
    ]
    actual = [capability_to_tool(c)["name"] for c in PROJECTS_CAPABILITIES]
    assert actual == expected


def _find_cap(caps: list[Capability], cap_id: str) -> Capability:
    for c in caps:
        if c.id == cap_id:
            return c
    raise AssertionError(f"capability id {cap_id!r} not found")


def test_find_person_path_param_required() -> None:
    """Passing path_params must inject the parameter as required."""

    cap = _find_cap(PEOPLE_CAPABILITIES, "find_person")
    spec = capability_to_tool(cap, path_params=["person_id"])
    schema = spec["inputSchema"]

    assert "person_id" in schema["properties"]
    assert schema["properties"]["person_id"]["type"] == "string"
    assert "person_id" in schema["required"]

    Tool(**spec)  # still a valid Tool


class _SendBody(BaseModel):
    recipient_id: str
    body: str


def test_send_message_request_model_fields_hoisted() -> None:
    """Body fields from a Pydantic model show up in properties + required."""

    cap = _find_cap(COMMUNICATIONS_CAPABILITIES, "send_message")
    spec = capability_to_tool(cap, request_model=_SendBody)
    schema = spec["inputSchema"]

    assert "recipient_id" in schema["properties"]
    assert "body" in schema["properties"]
    assert "recipient_id" in schema["required"]
    assert "body" in schema["required"]

    Tool(**spec)


def test_filter_by_skill_query_param_optional() -> None:
    """Query params are added to properties but NOT to required."""

    cap = _find_cap(PEOPLE_CAPABILITIES, "filter_by_skill")
    spec = capability_to_tool(cap, query_params=["skill"])
    schema = spec["inputSchema"]

    assert "skill" in schema["properties"]
    assert schema["properties"]["skill"]["type"] == "string"
    assert "skill" not in schema["required"]

    Tool(**spec)


def test_create_person_description_concatenates_summary_and_hints() -> None:
    """Description is ``summary + ' '.join(hints)`` joined by a single space."""

    cap = _find_cap(PEOPLE_CAPABILITIES, "create_person")
    spec = capability_to_tool(cap)

    expected = cap.summary + " " + " ".join(cap.hints)
    assert spec["description"] == expected
