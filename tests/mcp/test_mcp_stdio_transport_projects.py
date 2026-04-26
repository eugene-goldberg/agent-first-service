"""End-to-end stdio-transport test for the Projects MCP server.

Spawns ``.venv/bin/python3 -m services.projects.mcp_main --sqlite-path ...``
as a subprocess and drives it via the official ``mcp`` Python client over
stdio. This exercises the full stack: argparse -> factory -> adapter ->
FastAPI app -> SQLite, and back out as MCP JSON-RPC frames on stdout.

Per spec §8.5:

  * ``tools/list`` must include at least ``post_projects``, ``get_projects``,
    ``post_projects_id_tasks`` and ``get_projects_id_tasks``, and each entry
    must be a valid ``mcp.types.Tool``.
  * ``tools/call post_projects`` must return a list of ``TextContent`` blocks
    whose JSON-decoded text contains the agent envelope keys.
  * ``tools/call get_projects`` must return the previously-created project.
  * The subprocess must be terminated cleanly in a ``finally`` block.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent, Tool


REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"


ENVELOPE_KEYS = {"data", "_self", "_related", "_suggested_next", "_generated_at"}


def _server_params(db_path: Path) -> StdioServerParameters:
    """Build stdio launch parameters for the Projects MCP server subprocess."""

    # Inherit PATH / HOME / etc. so the subprocess can locate shared libs.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        # Ensure ``-m services.projects.mcp_main`` resolves our package.
        "PYTHONPATH": str(REPO_ROOT),
    }
    return StdioServerParameters(
        command=str(VENV_PYTHON),
        args=[
            "-m",
            "services.projects.mcp_main",
            "--sqlite-path",
            str(db_path),
        ],
        cwd=str(REPO_ROOT),
        env=env,
    )


@pytest.mark.skipif(
    not VENV_PYTHON.exists(),
    reason=f"venv python not found at {VENV_PYTHON}",
)
async def test_stdio_transport_list_and_call_projects(tmp_path) -> None:
    """Full MCP stdio round-trip: list_tools + call_tool post/get projects."""

    db_path = tmp_path / "projects.db"
    params = _server_params(db_path)

    # A generous-but-bounded initialization + round-trip timeout so a hung
    # subprocess produces a test failure rather than hanging the whole suite.
    async def _run() -> None:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1) tools/list -----------------------------------------------
                list_result = await session.list_tools()
                tools = list_result.tools
                names = {t.name for t in tools}
                required = {
                    "post_projects",
                    "get_projects",
                    "post_projects_id_tasks",
                    "get_projects_id_tasks",
                }
                assert required.issubset(names), (
                    f"missing expected tools: {required - names}"
                )
                # Every entry should round-trip through ``Tool.model_validate``.
                for t in tools:
                    assert isinstance(t, Tool)
                    assert t.inputSchema["type"] == "object"

                # 2) tools/call post_projects ---------------------------------
                create_result = await session.call_tool(
                    "post_projects",
                    {
                        "name": "Stdio transport project",
                        "description": "created via MCP stdio",
                    },
                )
                assert create_result.isError is False
                assert isinstance(create_result.content, list)
                assert len(create_result.content) == 1
                block = create_result.content[0]
                assert isinstance(block, TextContent)
                assert block.type == "text"
                create_envelope = json.loads(block.text)
                assert isinstance(create_envelope, dict)
                assert ENVELOPE_KEYS.issubset(create_envelope.keys()), (
                    f"create envelope missing keys: "
                    f"{ENVELOPE_KEYS - set(create_envelope.keys())}"
                )
                assert create_envelope["data"]["name"] == "Stdio transport project"

                # 3) tools/call get_projects ----------------------------------
                list_projects_result = await session.call_tool(
                    "get_projects", {}
                )
                assert list_projects_result.isError is False
                list_block = list_projects_result.content[0]
                assert isinstance(list_block, TextContent)
                list_envelope = json.loads(list_block.text)
                assert ENVELOPE_KEYS.issubset(list_envelope.keys())
                assert isinstance(list_envelope["data"], list)
                names_seen = {p.get("name") for p in list_envelope["data"]}
                assert "Stdio transport project" in names_seen

    try:
        await asyncio.wait_for(_run(), timeout=30.0)
    except asyncio.TimeoutError as exc:  # pragma: no cover - only on hang
        pytest.fail(f"MCP stdio round-trip timed out: {exc}")
