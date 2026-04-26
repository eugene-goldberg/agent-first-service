"""Tool registry for the People MCP server.

The tool registry maps each tool name (as derived by
``agent_protocol.mcp_adapter.capability_to_tool``) to the 5-tuple
``ToolRegistryEntry`` describing how the adapter should dispatch an
MCP ``tools/call`` invocation into the wrapped People FastAPI app.

Both the stdio/SSE ``mcp_server.build_people_mcp_server`` factory and the
adapter-level unit tests import ``build_tool_registry`` from here so there is
exactly one source of truth for the People service's tool surface.
"""

from __future__ import annotations

from agent_protocol.mcp_adapter import ToolRegistryEntry
from services.people.models import CreatePerson, UpdatePerson


def build_tool_registry() -> dict[str, ToolRegistryEntry]:
    """Return the full tool_registry for the People service.

    Keys match the tool names derived by ``capability_to_tool`` for the six
    entries in ``services.people.routes.capabilities.PEOPLE_CAPABILITIES``.

    Note: ``filter_by_skill`` and ``filter_by_availability`` both dispatch
    into ``GET /people`` because the People HTTP route exposes the filters
    as query parameters on the same underlying endpoint. The adapter routes
    ``skill`` / ``available`` arguments into the querystring via the
    ``query_params`` tuple.
    """

    return {
        "list_people": ("/people", "GET", None, [], ["skill", "available"]),
        "find_person": (
            "/people/{person_id}",
            "GET",
            None,
            ["person_id"],
            [],
        ),
        "create_person": ("/people", "POST", CreatePerson, [], []),
        "update_person": (
            "/people/{person_id}",
            "PATCH",
            UpdatePerson,
            ["person_id"],
            [],
        ),
        "filter_by_skill": ("/people", "GET", None, [], ["skill"]),
        "filter_by_availability": (
            "/people",
            "GET",
            None,
            [],
            ["available", "skill"],
        ),
    }
