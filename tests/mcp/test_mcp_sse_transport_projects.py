"""End-to-end SSE-transport test for the Projects MCP server.

Per spec §8.6:

    Launches ``python -m services.projects.mcp_main --sse --port 9091``. Uses
    the ``mcp`` SSE client to repeat the ``tools/list`` + ``tools/call``
    assertions from 8.5. Uses port 9091 to avoid clashing with the HTTP
    service on 8001.

The test:

1. Pre-flight: ensure nothing is already listening on the chosen test port,
   so a leaked process from a prior run produces a fast, explicit failure
   instead of a hang.
2. Spawn ``.venv/bin/python3 -m services.projects.mcp_main --sse
   --port 9091 --sqlite-path <tmp_path>/projects.db`` via
   ``asyncio.create_subprocess_exec``.
3. Poll the port (TCP connect) until the server is accepting connections,
   with a bounded timeout — do NOT sleep blindly.
4. Drive the server via ``mcp.client.sse.sse_client`` + ``mcp.ClientSession``:
   * ``tools/list`` — assert the four core tool names are present.
   * ``tools/call post_projects`` — assert an envelope-shaped result.
   * ``tools/call get_projects`` — assert the just-created project is listed
     (i.e. the subprocess really is persisting to the ``tmp_path`` SQLite DB).
5. Cleanly terminate the subprocess in a ``finally`` block.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent, Tool

from tests.mcp._sse_helpers import port_is_free, wait_for_port


REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"

# Use 9091 (test port) deliberately to avoid colliding with:
#   * 8001 — Projects HTTP service
#   * 9001 — Projects MCP SSE port used in production / dev runs
TEST_PORT = 9091
TEST_HOST = "127.0.0.1"

ENVELOPE_KEYS = {"data", "_self", "_related", "_suggested_next", "_generated_at"}


@pytest.mark.skipif(
    not VENV_PYTHON.exists(),
    reason=f"venv python not found at {VENV_PYTHON}",
)
async def test_sse_transport_list_and_call_projects(tmp_path) -> None:
    """Full MCP SSE round-trip: list_tools + call_tool post/get projects."""

    # 1) Pre-flight: fail fast if the test port is already in use.
    assert port_is_free(TEST_HOST, TEST_PORT), (
        f"test port {TEST_HOST}:{TEST_PORT} is already in use — a prior "
        "test run may have leaked the MCP SSE subprocess. Kill it and retry."
    )

    db_path = tmp_path / "projects.db"

    env = os.environ.copy()
    # Ensure ``-m services.projects.mcp_main`` resolves our package even if
    # the ambient environment has a weird PYTHONPATH.
    env["PYTHONPATH"] = str(REPO_ROOT)

    # 2) Spawn the SSE server as a subprocess.
    proc = await asyncio.create_subprocess_exec(
        str(VENV_PYTHON),
        "-m",
        "services.projects.mcp_main",
        "--sse",
        "--host",
        TEST_HOST,
        "--port",
        str(TEST_PORT),
        "--sqlite-path",
        str(db_path),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        # 3) Wait for readiness via TCP probe (no blind sleep).
        try:
            await wait_for_port(TEST_HOST, TEST_PORT, timeout=15.0)
        except TimeoutError as exc:
            # Surface any stderr output so a startup failure is diagnosable.
            stderr_bytes: bytes
            try:
                stderr_bytes = await asyncio.wait_for(
                    proc.stderr.read(4096), timeout=1.0
                ) if proc.stderr else b""
            except asyncio.TimeoutError:
                stderr_bytes = b""
            pytest.fail(
                f"{exc}\nsubprocess stderr (first 4KB): "
                f"{stderr_bytes.decode('utf-8', errors='replace')}"
            )

        # 4) Drive the server via the MCP SSE client.
        sse_url = f"http://{TEST_HOST}:{TEST_PORT}/sse"

        async def _run_session() -> None:
            async with sse_client(sse_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()

                    # 4a) tools/list -------------------------------------
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
                        f"missing expected tools over SSE: {required - names}"
                    )
                    for t in tools:
                        assert isinstance(t, Tool)
                        assert t.inputSchema["type"] == "object"

                    # 4b) tools/call post_projects ------------------------
                    create_result = await session.call_tool(
                        "post_projects",
                        {
                            "name": "SSE transport project",
                            "description": "created via MCP SSE",
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
                    assert (
                        create_envelope["data"]["name"]
                        == "SSE transport project"
                    )

                    # 4c) tools/call get_projects -------------------------
                    list_projects_result = await session.call_tool(
                        "get_projects", {}
                    )
                    assert list_projects_result.isError is False
                    list_block = list_projects_result.content[0]
                    assert isinstance(list_block, TextContent)
                    list_envelope = json.loads(list_block.text)
                    assert ENVELOPE_KEYS.issubset(list_envelope.keys())
                    assert isinstance(list_envelope["data"], list)
                    names_seen = {
                        p.get("name") for p in list_envelope["data"]
                    }
                    assert "SSE transport project" in names_seen

        try:
            await asyncio.wait_for(_run_session(), timeout=30.0)
        except asyncio.TimeoutError as exc:  # pragma: no cover - only on hang
            pytest.fail(f"MCP SSE round-trip timed out: {exc}")

    finally:
        # 5) Terminate the subprocess cleanly.
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
