"""End-to-end stdio-transport test for the People MCP server.

Spawns ``.venv/bin/python3 -m services.people.mcp_main --sqlite-path ...``
as a subprocess and drives it via the official ``mcp`` Python client over
stdio. This exercises the full stack: argparse -> factory -> adapter ->
FastAPI app -> SQLite, and back out as MCP JSON-RPC frames on stdout.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import TextContent, Tool


REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"


ENVELOPE_KEYS = {"data", "_self", "_related", "_suggested_next", "_generated_at"}


def _server_params(db_path: Path) -> StdioServerParameters:
    """Build stdio launch parameters for the People MCP server subprocess."""

    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "PYTHONPATH": str(REPO_ROOT),
    }
    return StdioServerParameters(
        command=str(VENV_PYTHON),
        args=[
            "-m",
            "services.people.mcp_main",
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
async def test_stdio_transport_list_and_call_people(tmp_path) -> None:
    """Full MCP stdio round-trip: list_tools + call_tool create/list people."""

    db_path = tmp_path / "people.db"
    params = _server_params(db_path)

    async def _run() -> None:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # 1) tools/list -----------------------------------------------
                list_result = await session.list_tools()
                tools = list_result.tools
                names = {t.name for t in tools}
                required = {
                    "create_person",
                    "list_people",
                    "find_person",
                    "update_person",
                }
                assert required.issubset(names), (
                    f"missing expected tools: {required - names}"
                )
                # Every entry should round-trip through ``Tool.model_validate``.
                for t in tools:
                    assert isinstance(t, Tool)
                    assert t.inputSchema["type"] == "object"

                # 2) tools/call create_person --------------------------------
                create_result = await session.call_tool(
                    "create_person",
                    {
                        "name": "Stdio Person",
                        "role": "engineer",
                        "skills": ["python"],
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
                assert create_envelope["data"]["name"] == "Stdio Person"
                assert create_envelope["data"]["available"] is True

                # 3) tools/call list_people ----------------------------------
                list_people_result = await session.call_tool(
                    "list_people", {}
                )
                assert list_people_result.isError is False
                list_block = list_people_result.content[0]
                assert isinstance(list_block, TextContent)
                list_envelope = json.loads(list_block.text)
                assert ENVELOPE_KEYS.issubset(list_envelope.keys())
                assert isinstance(list_envelope["data"], list)
                names_seen = {p.get("name") for p in list_envelope["data"]}
                assert "Stdio Person" in names_seen

    try:
        await asyncio.wait_for(_run(), timeout=30.0)
    except asyncio.TimeoutError as exc:  # pragma: no cover - only on hang
        pytest.fail(f"MCP stdio round-trip timed out: {exc}")
