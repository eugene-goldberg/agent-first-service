"""End-to-end SSE-transport test for the Communications MCP server.

Launches ``python -m services.communications.mcp_main --sse --port 9093``.
Uses the ``mcp`` SSE client to repeat the ``tools/list`` + ``tools/call``
assertions. Uses port 9093 to avoid clashing with:

* 8003 — Communications HTTP service
* 9003 — Communications MCP SSE port used in production / dev runs
* 9091 — Projects MCP SSE test port
* 9092 — People MCP SSE test port
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.types import TextContent, Tool

from tests.mcp._sse_helpers import port_is_free, wait_for_port


REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"

TEST_PORT = 9093
TEST_HOST = "127.0.0.1"

ENVELOPE_KEYS = {"data", "_self", "_related", "_suggested_next", "_generated_at"}


@pytest.mark.skipif(
    not VENV_PYTHON.exists(),
    reason=f"venv python not found at {VENV_PYTHON}",
)
async def test_sse_transport_list_and_call_communications(tmp_path) -> None:
    """Full MCP SSE round-trip: list_tools + call_tool send/list messages."""

    # 1) Pre-flight: fail fast if the test port is already in use.
    assert port_is_free(TEST_HOST, TEST_PORT), (
        f"test port {TEST_HOST}:{TEST_PORT} is already in use — a prior "
        "test run may have leaked the MCP SSE subprocess. Kill it and retry."
    )

    db_path = tmp_path / "communications.db"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    # 2) Spawn the SSE server as a subprocess.
    proc = await asyncio.create_subprocess_exec(
        str(VENV_PYTHON),
        "-m",
        "services.communications.mcp_main",
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
                        "send_message",
                        "list_messages",
                        "find_message",
                        "filter_by_recipient",
                    }
                    assert required.issubset(names), (
                        f"missing expected tools over SSE: "
                        f"{required - names}"
                    )
                    for t in tools:
                        assert isinstance(t, Tool)
                        assert t.inputSchema["type"] == "object"

                    # 4b) tools/call send_message -------------------------
                    create_result = await session.call_tool(
                        "send_message",
                        {
                            "recipient_id": "person_sse",
                            "project_id": "proj_sse",
                            "subject": "SSE subject",
                            "body": "SSE body.",
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
                        create_envelope["data"]["recipient_id"]
                        == "person_sse"
                    )

                    # 4c) tools/call list_messages -----------------------
                    list_messages_result = await session.call_tool(
                        "list_messages", {}
                    )
                    assert list_messages_result.isError is False
                    list_block = list_messages_result.content[0]
                    assert isinstance(list_block, TextContent)
                    list_envelope = json.loads(list_block.text)
                    assert ENVELOPE_KEYS.issubset(list_envelope.keys())
                    assert isinstance(list_envelope["data"], list)
                    recipients_seen = {
                        m.get("recipient_id") for m in list_envelope["data"]
                    }
                    assert "person_sse" in recipients_seen

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
