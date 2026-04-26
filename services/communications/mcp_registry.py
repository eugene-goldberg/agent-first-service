"""Tool registry for the Communications MCP server.

The tool registry maps each tool name (as derived by
``agent_protocol.mcp_adapter.capability_to_tool``) to the 5-tuple
``ToolRegistryEntry`` describing how the adapter should dispatch an
MCP ``tools/call`` invocation into the wrapped Communications FastAPI app.

Both the stdio/SSE ``mcp_server.build_communications_mcp_server`` factory
and the adapter-level unit tests import ``build_tool_registry`` from here
so there is exactly one source of truth for the Communications service's
tool surface.
"""

from __future__ import annotations

from agent_protocol.mcp_adapter import ToolRegistryEntry
from services.communications.models import CreateMessage


def build_tool_registry() -> dict[str, ToolRegistryEntry]:
    """Return the full tool_registry for the Communications service.

    Keys match the tool names derived by ``capability_to_tool`` for the five
    entries in ``services.communications.routes.capabilities.COMMUNICATIONS_CAPABILITIES``.

    Note: ``filter_by_recipient`` and ``filter_by_project`` both dispatch
    into ``GET /messages`` because the Communications HTTP route exposes the
    filters as query parameters on the same underlying endpoint. The adapter
    routes ``recipient_id`` / ``project_id`` arguments into the querystring
    via the ``query_params`` tuple.
    """

    return {
        "list_messages": (
            "/messages",
            "GET",
            None,
            [],
            ["recipient_id", "project_id"],
        ),
        "find_message": (
            "/messages/{message_id}",
            "GET",
            None,
            ["message_id"],
            [],
        ),
        "send_message": ("/messages", "POST", CreateMessage, [], []),
        "filter_by_recipient": (
            "/messages",
            "GET",
            None,
            [],
            ["recipient_id"],
        ),
        "filter_by_project": (
            "/messages",
            "GET",
            None,
            [],
            ["project_id"],
        ),
    }
