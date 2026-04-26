"""End-to-end tests for ``services.orchestrator.mcp_tools.MCPToolbox`` (Inc 8).

Spawns the real People MCP SSE server as a subprocess and drives it through
``MCPToolbox``. No mocks. Real SQLite DB in ``tmp_path``.

Uses port 9092 to avoid clashing with the People HTTP port (8002), the
production/dev People MCP SSE port (9002), and the Projects MCP test port
(9091). The subprocess is shared across tests 1-3 via a module-scoped async
fixture so we pay the ~1s spawn cost once. Test 4 uses an unreachable port
and spawns no subprocess. Test 5 exercises the unknown-server fail-fast path.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pytest

from services.orchestrator.mcp_tools import MCPToolbox
from tests.mcp._sse_helpers import port_is_free, wait_for_port


REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"

TEST_PORT = 9092
TEST_HOST = "127.0.0.1"
BASE_URL = f"http://{TEST_HOST}:{TEST_PORT}"

ENVELOPE_KEYS = {"data", "_self", "_related", "_suggested_next", "_generated_at"}


pytestmark = pytest.mark.skipif(
    not VENV_PYTHON.exists(),
    reason=f"venv python not found at {VENV_PYTHON}",
)


@pytest.fixture
async def people_mcp_server(tmp_path):
    """Spawn the People MCP SSE server as a subprocess, teardown on exit.

    Function-scoped because pytest-asyncio's default event-loop scope is
    per-function; sharing a subprocess across tests would require matching
    fixture and loop scopes, which is avoidable complexity for three
    fast tests.
    """

    assert port_is_free(TEST_HOST, TEST_PORT), (
        f"test port {TEST_HOST}:{TEST_PORT} is already in use — a prior "
        "test run may have leaked the MCP SSE subprocess. Kill it and retry."
    )

    db_path = tmp_path / "people.db"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)

    proc = await asyncio.create_subprocess_exec(
        str(VENV_PYTHON),
        "-m",
        "services.people.mcp_main",
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
        try:
            await wait_for_port(TEST_HOST, TEST_PORT, timeout=15.0)
        except TimeoutError as exc:
            stderr_bytes: bytes
            try:
                stderr_bytes = (
                    await asyncio.wait_for(proc.stderr.read(4096), timeout=1.0)
                    if proc.stderr
                    else b""
                )
            except asyncio.TimeoutError:
                stderr_bytes = b""
            pytest.fail(
                f"{exc}\nsubprocess stderr (first 4KB): "
                f"{stderr_bytes.decode('utf-8', errors='replace')}"
            )

        yield BASE_URL
    finally:
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()


async def test_list_tools_returns_people_tools(people_mcp_server) -> None:
    """``list_tools`` returns well-formed tool specs including create_person."""

    toolbox = MCPToolbox({"people": people_mcp_server})

    tools = await asyncio.wait_for(toolbox.list_tools("people"), timeout=30.0)

    assert isinstance(tools, list)
    assert len(tools) > 0
    names = {t["name"] for t in tools}
    assert "create_person" in names, f"create_person missing from tools: {names}"
    # Spot-check other known People tools so a silent registry regression
    # would surface here.
    for expected in ("list_people", "find_person", "update_person"):
        assert expected in names, f"{expected} missing from tools: {names}"

    for t in tools:
        assert "name" in t and isinstance(t["name"], str)
        assert "description" in t
        assert "inputSchema" in t
        assert isinstance(t["inputSchema"], dict)
        assert t["inputSchema"].get("type") == "object"


async def test_call_tool_happy_path(people_mcp_server) -> None:
    """``call_tool`` returns status=ok with a full envelope on success."""

    toolbox = MCPToolbox({"people": people_mcp_server})

    result = await asyncio.wait_for(
        toolbox.call_tool(
            "people",
            "create_person",
            {
                "name": "Toolbox Tester",
                "role": "senior engineer",
                "skills": ["python", "mcp"],
            },
        ),
        timeout=30.0,
    )

    assert result["status"] == "ok", f"expected ok, got: {result}"
    content = result["content"]
    assert isinstance(content, dict)
    missing = ENVELOPE_KEYS - set(content.keys())
    assert not missing, f"envelope missing keys: {missing}; got: {content}"
    assert content["data"]["name"] == "Toolbox Tester"
    assert content["data"]["role"] == "senior engineer"


async def test_call_tool_protocol_error_is_ok_with_error_envelope(
    people_mcp_server,
) -> None:
    """A leaf-service domain-level rejection is PROTOCOL success — status=ok
    with an error envelope carrying ``_why`` (and likely ``_try_instead``).

    We force a 404 ``AgentError`` by calling ``find_person`` with an id that
    is known not to exist. The MCP tools/call round-trip completes; the
    envelope is the hypermedia error shape the leaf service emits. This is
    distinct from a transport/SDK error (see test_call_tool_transport_error)
    and from an MCP-layer schema rejection (those surface with
    ``isError=True`` on ``CallToolResult`` — not exercised here because
    unwrapping jsonschema rejections belongs to the MCP server handler, not
    the toolbox contract).
    """

    toolbox = MCPToolbox({"people": people_mcp_server})

    result = await asyncio.wait_for(
        toolbox.call_tool(
            "people",
            "find_person",
            # Schema-valid but application-level invalid: no such id.
            {"person_id": "person_does_not_exist"},
        ),
        timeout=30.0,
    )

    # Critical distinction: protocol SUCCESS even though the leaf service
    # rejected the id at the application layer. Transport status 'error' is
    # reserved for SDK/transport faults.
    assert result["status"] == "ok", (
        f"expected protocol success with error envelope, got: {result}"
    )
    content = result["content"]
    assert isinstance(content, dict), f"expected dict envelope, got: {content!r}"
    assert "_why" in content, (
        f"expected error envelope with _why, got keys: {list(content.keys())}; "
        f"full content: {content}"
    )
    assert "_try_instead" in content, (
        f"expected error envelope with _try_instead, got keys: "
        f"{list(content.keys())}; full content: {content}"
    )


async def test_call_tool_transport_error() -> None:
    """Unreachable SSE endpoint yields status=error with non-empty message."""

    # Port 1 is reserved / non-listening on every sane host. No subprocess.
    toolbox = MCPToolbox({"people": "http://127.0.0.1:1"})

    result = await asyncio.wait_for(
        toolbox.call_tool(
            "people",
            "create_person",
            {"name": "n/a", "role": "n/a", "skills": []},
        ),
        timeout=30.0,
    )

    assert result["status"] == "error", f"expected error, got: {result}"
    assert isinstance(result.get("message"), str)
    assert result["message"], "error message should be a non-empty string"


async def test_unknown_server_raises() -> None:
    """Unknown server names fail fast with KeyError — orchestrator wiring bug,
    not a runtime transport blip."""

    toolbox = MCPToolbox({"people": BASE_URL})

    with pytest.raises((KeyError, ValueError)):
        await toolbox.call_tool(
            "projects",
            "create_project",
            {"name": "irrelevant"},
        )
