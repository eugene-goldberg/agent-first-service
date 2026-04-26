"""In-process tests for ``services.projects.mcp_server.build_projects_mcp_server``.

These tests exercise the factory directly (no subprocess, no stdio transport)
to give fast coverage of the wiring between the adapter and the
``mcp.server.Server`` instance.
"""

from __future__ import annotations

from mcp.server import Server
from mcp.types import Tool

from agent_protocol.mcp_adapter import CatalogBackedMCPServer
from services.projects.mcp_server import build_projects_mcp_server
from services.projects.routes.capabilities import _CAPABILITIES as PROJECTS_CAPABILITIES


def test_build_projects_mcp_server_returns_server_and_adapter(tmp_path) -> None:
    """Factory returns a 2-tuple: ``(mcp.server.Server, CatalogBackedMCPServer)``."""

    db_path = tmp_path / "projects.db"
    server, adapter = build_projects_mcp_server(sqlite_path=db_path)

    assert isinstance(server, Server)
    assert isinstance(adapter, CatalogBackedMCPServer)
    assert adapter.server_name == "projects"
    assert len(adapter.capabilities) == len(PROJECTS_CAPABILITIES)
    assert len(adapter.capabilities) > 0


async def test_build_factory_adapter_list_tools_exposes_expected_tools(
    tmp_path,
) -> None:
    """The returned adapter yields the eight Projects tools via ``list_tools``."""

    db_path = tmp_path / "projects.db"
    _server, adapter = build_projects_mcp_server(sqlite_path=db_path)

    tools = await adapter.list_tools()
    names = {t["name"] for t in tools}

    expected = {
        "get_projects",
        "post_projects",
        "get_projects_id",
        "patch_projects_id",
        "get_projects_id_tasks",
        "post_projects_id_tasks",
        "patch_tasks_id",
        "get_tasks_assignee_id_status_status_milestone_id",
    }
    assert expected.issubset(names), f"missing tools: {expected - names}"

    # Every spec must construct a valid mcp.types.Tool.
    for spec in tools:
        tool = Tool.model_validate(spec)
        assert tool.name == spec["name"]
        assert tool.inputSchema["type"] == "object"


async def test_build_factory_adapter_call_tool_round_trip(tmp_path) -> None:
    """The factory-returned adapter dispatches ``call_tool`` into the real app."""

    db_path = tmp_path / "projects.db"
    _server, adapter = build_projects_mcp_server(sqlite_path=db_path)

    # Create a project via the adapter (same surface the MCP handlers will use).
    content = await adapter.call_tool(
        "post_projects",
        {"name": "Factory test", "description": "from in-process factory test"},
    )
    assert isinstance(content, list) and len(content) == 1
    assert content[0]["type"] == "text"
    # The adapter serialises the envelope to JSON in the ``text`` field.
    import json

    envelope = json.loads(content[0]["text"])
    for key in ("data", "_self", "_related", "_suggested_next", "_generated_at"):
        assert key in envelope, f"missing envelope key: {key}"
    assert envelope["data"]["name"] == "Factory test"
