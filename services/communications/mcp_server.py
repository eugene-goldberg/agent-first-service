"""Build an MCP server for the Communications service.

This module is transport-agnostic in the sense that it produces an
``mcp.server.Server`` instance with its ``list_tools`` and ``call_tool``
handlers wired to a :class:`~agent_protocol.mcp_adapter.CatalogBackedMCPServer`
bound to a real Communications FastAPI app. Transport selection (stdio / SSE)
is the responsibility of the entrypoint module
(:mod:`services.communications.mcp_main`).
"""

from __future__ import annotations

from pathlib import Path

from mcp.server import Server
from mcp.types import TextContent, Tool

from agent_protocol.mcp_adapter import CatalogBackedMCPServer
from services.communications.app import create_app
from services.communications.mcp_registry import build_tool_registry
from services.communications.routes.capabilities import COMMUNICATIONS_CAPABILITIES


def build_communications_mcp_server(
    *, sqlite_path: Path
) -> tuple[Server, CatalogBackedMCPServer]:
    """Construct an ``mcp.server.Server`` wired to a real Communications app.

    Returns a 2-tuple ``(server, adapter)`` where:

    * ``server`` is an ``mcp.server.Server`` with its ``list_tools`` and
      ``call_tool`` handlers registered to delegate to ``adapter``.
    * ``adapter`` is the underlying :class:`CatalogBackedMCPServer` — returned
      so callers (tests, SSE wrapper) can exercise it directly without going
      through the JSON-RPC transport.
    """

    app = create_app(sqlite_path=str(sqlite_path))
    registry = build_tool_registry()
    adapter = CatalogBackedMCPServer(
        app=app,
        server_name="communications",
        tool_registry=registry,
        capabilities=COMMUNICATIONS_CAPABILITIES,
    )

    server: Server = Server("communications")

    @server.list_tools()
    async def _handle_list_tools() -> list[Tool]:
        specs = await adapter.list_tools()
        return [Tool.model_validate(spec) for spec in specs]

    @server.call_tool()
    async def _handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
        items = await adapter.call_tool(name, arguments)
        return [
            TextContent(type="text", text=item["text"]) for item in items
        ]

    return server, adapter
