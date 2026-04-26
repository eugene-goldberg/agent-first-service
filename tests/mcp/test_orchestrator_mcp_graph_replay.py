"""End-to-end replay test for MCP-mode orchestrator graph (Inc 9).

Spins up all three leaf-service MCP SSE subprocesses (Projects on 9091,
People on 9092, Communications on 9093) against per-test SQLite DBs and
drives them through ``OrchestrationGraph(mode="mcp", ...)`` using a
``ReplayLLMClient`` pointed at ``fixtures/llm_recordings/mcp_landing_page``.

The test exercises the full MCP-mode graph:
- Pre-plan discovery via ``MCPToolbox.list_tools`` (× 3 servers)
- Planner prompt with ``PLANNER_SYSTEM_MCP`` and tool-name substitution
- Actor loop with ``ACTOR_SYSTEM_MCP`` emitting {server, tool, arguments, ...}
- Polymorphic ``_dispatch`` routing through ``MCPToolbox.call_tool``
- ``is_final`` termination

Real subprocesses, real SQLite DBs, real MCP SSE transport. No mocks.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid
from pathlib import Path

import httpx
import pytest

from services.orchestrator.graph import OrchestrationGraph
from services.orchestrator.llm import ReplayLLMClient
from services.orchestrator.mcp_tools import MCPToolbox
from services.orchestrator.state import OrchestrationState
from services.orchestrator.tools import HTTPToolbox
from services.orchestrator.trace_bus import TraceBus
from tests.mcp._sse_helpers import port_is_free, wait_for_port


REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"

TEST_HOST = "127.0.0.1"
PROJECTS_PORT = 9091
PEOPLE_PORT = 9092
COMMS_PORT = 9093


pytestmark = pytest.mark.skipif(
    not VENV_PYTHON.exists(),
    reason=f"venv python not found at {VENV_PYTHON}",
)


async def _spawn_mcp_server(
    module: str,
    host: str,
    port: int,
    sqlite_path: Path,
) -> asyncio.subprocess.Process:
    assert port_is_free(host, port), (
        f"test port {host}:{port} is already in use — a prior test run may "
        "have leaked an MCP SSE subprocess. Kill it and retry."
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    proc = await asyncio.create_subprocess_exec(
        str(VENV_PYTHON),
        "-m",
        module,
        "--sse",
        "--host",
        host,
        "--port",
        str(port),
        "--sqlite-path",
        str(sqlite_path),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return proc


async def _terminate(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


@pytest.fixture
async def three_mcp_servers(tmp_path):
    """Spawn Projects/People/Communications MCP SSE subprocesses.

    Yields ``(projects_url, people_url, comms_url, projects_db, people_db,
    comms_db)`` so the test can both hit the MCP surfaces and read the
    underlying SQLite DBs for side-effect verification.
    """

    projects_db = tmp_path / "projects.db"
    people_db = tmp_path / "people.db"
    comms_db = tmp_path / "comms.db"

    procs: list[asyncio.subprocess.Process] = []
    try:
        procs.append(await _spawn_mcp_server(
            "services.projects.mcp_main", TEST_HOST, PROJECTS_PORT, projects_db,
        ))
        procs.append(await _spawn_mcp_server(
            "services.people.mcp_main", TEST_HOST, PEOPLE_PORT, people_db,
        ))
        procs.append(await _spawn_mcp_server(
            "services.communications.mcp_main", TEST_HOST, COMMS_PORT, comms_db,
        ))

        try:
            await wait_for_port(TEST_HOST, PROJECTS_PORT, timeout=15.0)
            await wait_for_port(TEST_HOST, PEOPLE_PORT, timeout=15.0)
            await wait_for_port(TEST_HOST, COMMS_PORT, timeout=15.0)
        except TimeoutError as exc:
            stderr_dumps = []
            for i, p in enumerate(procs):
                if p.stderr is not None:
                    try:
                        data = await asyncio.wait_for(
                            p.stderr.read(4096), timeout=1.0,
                        )
                    except asyncio.TimeoutError:
                        data = b""
                    stderr_dumps.append(
                        f"proc[{i}] stderr: "
                        f"{data.decode('utf-8', errors='replace')}"
                    )
            pytest.fail(f"{exc}\n" + "\n".join(stderr_dumps))

        yield {
            "projects_url": f"http://{TEST_HOST}:{PROJECTS_PORT}",
            "people_url": f"http://{TEST_HOST}:{PEOPLE_PORT}",
            "comms_url": f"http://{TEST_HOST}:{COMMS_PORT}",
            "projects_db": projects_db,
            "people_db": people_db,
            "comms_db": comms_db,
        }
    finally:
        for p in procs:
            await _terminate(p)


async def test_mcp_mode_replay_drives_graph_to_completion(
    three_mcp_servers,
) -> None:
    """MCP-mode graph uses list_tools discovery, emits MCP-shaped action
    events, dispatches via MCPToolbox.call_tool, and terminates via
    is_final — with a real SQLite side effect in the Projects DB to confirm
    the MCP subprocesses actually executed tool calls.
    """

    mcp_toolbox = MCPToolbox({
        "projects": three_mcp_servers["projects_url"],
        "people": three_mcp_servers["people_url"],
        "communications": three_mcp_servers["comms_url"],
    })

    # HTTPToolbox is required by the constructor even in MCP mode; it must
    # never be dispatched against. Wire it with an empty AsyncClient so a
    # stray HTTP call would immediately manifest as a transport error rather
    # than silently succeeding.
    async with httpx.AsyncClient(timeout=5.0) as http_client:
        http_toolbox = HTTPToolbox(client=http_client)
        bus = TraceBus()
        llm = ReplayLLMClient(
            recordings_dir=str(
                REPO_ROOT / "fixtures" / "llm_recordings" / "mcp_landing_page"
            ),
        )

        graph = OrchestrationGraph(
            llm=llm,
            toolbox=http_toolbox,
            bus=bus,
            projects_base=three_mcp_servers["projects_url"],
            people_base=three_mcp_servers["people_url"],
            comms_base=three_mcp_servers["comms_url"],
            max_steps=6,
            mode="mcp",
            mcp_toolbox=mcp_toolbox,
        )

        state = OrchestrationState(
            job_id=f"job_{uuid.uuid4().hex[:6]}",
            brief="Set up a Q3 launch project and notify Alice.",
        )

        result = await asyncio.wait_for(graph.run(state), timeout=60.0)

    # Terminal state
    assert result.completed is True
    assert result.final_summary, "final_summary should be non-empty"

    kinds = [e.kind for e in result.trace]
    assert "observation" in kinds
    assert "thought" in kinds
    assert "action" in kinds
    assert kinds[-1] == "final"

    # Pre-plan discovery event — first observation, carries tool-name lists
    discovery = next(e for e in result.trace if e.kind == "observation")
    assert "projects_capabilities" in discovery.detail
    assert "people_capabilities" in discovery.detail
    assert "comms_capabilities" in discovery.detail
    # Projects MCP server advertises post_projects / get_projects / etc.
    projects_names = discovery.detail["projects_capabilities"]
    assert "post_projects" in projects_names, (
        f"post_projects missing from discovered Projects tools: {projects_names}"
    )
    people_names = discovery.detail["people_capabilities"]
    assert "list_people" in people_names, (
        f"list_people missing from discovered People tools: {people_names}"
    )
    comms_names = discovery.detail["comms_capabilities"]
    assert "send_message" in comms_names, (
        f"send_message missing from discovered Communications tools: {comms_names}"
    )

    # At least one action event carries server/tool in detail
    actions = [e for e in result.trace if e.kind == "action"]
    assert actions, "expected at least one action event in MCP mode"
    first_action = actions[0]
    assert first_action.detail.get("server") == "projects"
    assert first_action.detail.get("tool") == "post_projects"
    assert isinstance(first_action.detail.get("arguments"), dict)

    # Observation events from _dispatch carry the MCP status envelope
    # ("ok" for the successful projects.post_projects call at minimum).
    dispatch_observations = [
        e for e in result.trace
        if e.kind == "observation" and e.detail.get("status") in ("ok", "error")
    ]
    assert dispatch_observations, (
        "expected at least one dispatch-level observation with status in MCP mode"
    )
    assert any(
        e.detail.get("status") == "ok" for e in dispatch_observations
    ), f"expected at least one ok status, got: {dispatch_observations}"

    # Real side effect: read the Projects SQLite DB directly. The MCP
    # subprocess wrote a row when post_projects was called; we see it here
    # via the filesystem-shared SQLite file.
    conn = sqlite3.connect(str(three_mcp_servers["projects_db"]))
    try:
        rows = conn.execute(
            "SELECT id, name, description FROM projects"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) >= 1, (
        f"expected >=1 project row written by MCP post_projects call, got: {rows}"
    )
    names = {r[1] for r in rows}
    assert "Q3 Launch" in names, (
        f"expected 'Q3 Launch' project written by MCP call; got: {names}"
    )
