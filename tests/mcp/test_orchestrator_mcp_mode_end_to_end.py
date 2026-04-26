"""End-to-end MCP-mode test against LIVE Azure OpenAI (Inc 10).

Exercises the full MCP-mode stack:
- Three real MCP SSE subprocesses (Projects/People/Communications on 9091/9092/9093),
  each with its own ``tmp_path`` SQLite DB.
- Real orchestrator FastAPI app constructed in-process via ``create_app`` in MCP
  mode (``ORCHESTRATOR_TOOL_MODE=mcp`` + the three ``ORCHESTRATOR_MCP_*_URL`` vars).
- Real Azure OpenAI calls via ``AzureLLMClient`` (same config loader as
  ``services/orchestrator/llm.py``).
- Real side-effect assertions: after orchestration completes, query the three
  leaf MCP servers via ``MCPToolbox`` and assert non-empty projects / tasks /
  messages plus ``status == "completed"``.

No mocks, no hardcoded tool-call sequences. The LLM is non-deterministic; we
assert on OUTCOMES (rows written, completed flag) not on specific tool names.

Cost note: marked ``@pytest.mark.live`` — burns real tokens per run. The
marker is registered in ``pyproject.toml`` so CI can filter it out later via
``-m "not live"``, but the default ``pytest tests/`` run INCLUDES it.
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport

from services.orchestrator.app import create_app
from services.orchestrator.mcp_tools import MCPToolbox
from tests.mcp._sse_helpers import port_is_free, wait_for_port


REPO_ROOT = Path(__file__).resolve().parents[2]
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"

TEST_HOST = "127.0.0.1"
PROJECTS_PORT = 9091
PEOPLE_PORT = 9092
COMMS_PORT = 9093

BRIEF = "Set up a Q3 landing page project with three tasks and notify Alice."

REQUIRED_AZURE_VARS = (
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_DEPLOYMENT",
    "AZURE_OPENAI_API_VERSION",
)

# Mark as live (burns real Azure tokens each run). The marker is registered in
# pyproject.toml so test selection can include/exclude this test explicitly.
pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not VENV_PYTHON.exists(),
        reason=f"venv python not found at {VENV_PYTHON}",
    ),
]


async def _spawn_mcp_server(
    module: str,
    host: str,
    port: int,
    sqlite_path: Path,
) -> asyncio.subprocess.Process:
    """Spawn one leaf-service MCP SSE subprocess against ``sqlite_path``."""
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
    """Terminate an MCP subprocess, escalating to kill on timeout."""
    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


def _seed_people_db(people_db: Path) -> None:
    """Pre-create the People SQLite schema and insert Alice.

    The MCP subprocess creates the schema on startup, but we need Alice
    present BEFORE the orchestrator tries to find her (to send her a
    message). The production demo seeds ``fixtures/demo-seed/people.json``
    via ``services.people.main --seed-from``, but ``mcp_main.py`` has no
    equivalent flag. Writing a single INSERT directly is the simplest way
    to give the LLM a real ``person_id`` to address — and it matches what
    the production seed file contains.
    """
    conn = sqlite3.connect(str(people_db))
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS people (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                skills_json TEXT NOT NULL DEFAULT '[]',
                available INTEGER NOT NULL DEFAULT 1,
                current_load INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            "INSERT OR REPLACE INTO people (id, name, role, skills_json, available, current_load) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                "person_alice",
                "Alice Chen",
                "senior engineer",
                '["python", "fastapi", "langgraph"]',
                1,
                1,
            ),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
async def three_mcp_servers(tmp_path):
    """Spawn Projects/People/Communications MCP SSE subprocesses.

    Yields a dict of URLs + SQLite paths. Guarantees subprocess termination
    and re-asserts the ports are free after teardown so a failing assertion
    cannot leave dangling processes.
    """
    projects_db = tmp_path / "projects.db"
    people_db = tmp_path / "people.db"
    comms_db = tmp_path / "comms.db"

    # Pre-seed Alice so the "notify Alice" step has a real ``person_id``
    # to target. Must happen BEFORE the People MCP subprocess starts so
    # the row is visible from the first ``list_people`` call.
    _seed_people_db(people_db)

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
        # Re-assert ports are free after teardown so the next run starts clean.
        # Small delay to let the OS reclaim the sockets.
        for _ in range(10):
            if all(port_is_free(TEST_HOST, p) for p in (PROJECTS_PORT, PEOPLE_PORT, COMMS_PORT)):
                break
            await asyncio.sleep(0.1)


def _check_azure_env_or_skip() -> None:
    """Skip live test when required Azure env vars are not available.

    This keeps default local/CI test runs stable while still running the
    live integration whenever credentials are configured.
    """
    missing = [v for v in REQUIRED_AZURE_VARS if not os.environ.get(v)]
    if missing:
        pytest.skip(
            f"Live E2E requires these Azure OpenAI env vars to be exported: "
            f"{', '.join(missing)}. "
            f"Load from .env before running, e.g. "
            f"`set -a && source .env && set +a && pytest {Path(__file__).name}`."
        )


async def test_mcp_mode_end_to_end_against_live_azure(three_mcp_servers, tmp_path, monkeypatch) -> None:
    """Submit the landing-page brief to a LIVE Azure-backed orchestrator in
    MCP mode and assert real side effects across all three leaf services.

    Orchestrator is constructed in-process via ``create_app(...)`` and driven
    through ``httpx.AsyncClient(transport=ASGITransport(app=app))`` — no 4th
    subprocess is spawned. The three MCP subprocesses own their SQLite files;
    we re-read them via ``MCPToolbox`` after orchestration completes.
    """

    # Pre-flight: env vars must be present for live execution.
    _check_azure_env_or_skip()

    # Point the orchestrator at our MCP subprocesses and flip to MCP mode.
    # Use monkeypatch so we don't pollute the environment for other tests.
    monkeypatch.setenv("ORCHESTRATOR_TOOL_MODE", "mcp")
    monkeypatch.setenv("ORCHESTRATOR_MCP_PROJECTS_URL", three_mcp_servers["projects_url"])
    monkeypatch.setenv("ORCHESTRATOR_MCP_PEOPLE_URL", three_mcp_servers["people_url"])
    monkeypatch.setenv("ORCHESTRATOR_MCP_COMMUNICATIONS_URL", three_mcp_servers["comms_url"])
    # Force live mode (not hybrid/replay) so the primary is Azure.
    monkeypatch.delenv("ORCHESTRATOR_LLM_MODE", raising=False)
    monkeypatch.delenv("ORCHESTRATOR_REPLAY_DIR", raising=False)

    orchestrator_db = tmp_path / "orchestrator.db"

    app = create_app(sqlite_path=str(orchestrator_db))

    # Use ASGITransport for in-process HTTP. Long timeout: live Azure planner
    # + 4-6 actor steps can take 60s+ on a slow day, and we're polling on
    # top of that. The outer asyncio.wait_for caps the whole workflow.
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://orchestrator.local",
        timeout=120.0,
    ) as client:
        # Submit the brief.
        start_resp = await client.post(
            "/orchestrations",
            json={"brief": BRIEF},
        )
        assert start_resp.status_code == 202, (
            f"POST /orchestrations failed: {start_resp.status_code} "
            f"{start_resp.text}"
        )
        job_id = start_resp.json()["data"]["id"]
        assert job_id.startswith("job_"), f"unexpected job_id shape: {job_id!r}"

        # Poll until completed or failed. 120s budget for live Azure.
        async def _wait_for_terminal_status() -> dict:
            deadline = asyncio.get_event_loop().time() + 120.0
            last_status: str | None = None
            while asyncio.get_event_loop().time() < deadline:
                r = await client.get(f"/orchestrations/{job_id}")
                assert r.status_code == 200, (
                    f"GET /orchestrations/{job_id} failed: "
                    f"{r.status_code} {r.text}"
                )
                data = r.json()["data"]
                last_status = data["status"]
                if last_status in ("completed", "failed"):
                    return data
                await asyncio.sleep(1.0)
            pytest.fail(
                f"Orchestration {job_id} did not reach terminal status within "
                f"120s; last status: {last_status!r}"
            )

        final = await _wait_for_terminal_status()

    # Give subprocesses a beat to flush SQLite writes from the last tool call.
    await asyncio.sleep(0.2)

    # Orchestrator-level assertion: completed (not failed).
    assert final["status"] == "completed", (
        f"expected completed orchestration, got status={final['status']!r} "
        f"with final_summary={final.get('final_summary')!r}"
    )
    # Treat the runner's "completed" status as the authoritative "completed flag"
    # (§8.8: "orchestration run's completed flag is true"). The OrchestrationState
    # stores this in the DB column ``status`` which the /orchestrations/{id}
    # endpoint surfaces; an explicit non-None final_summary confirms the graph
    # reached a terminal state rather than crashing mid-loop.
    assert final.get("final_summary"), (
        f"completed run should have a non-empty final_summary; got: {final!r}"
    )

    # Outcome assertions via MCP (§8.8: "at least one project / task / message").
    # We use a fresh MCPToolbox pointed at the same subprocesses and invoke the
    # leaf services' list tools. This reuses Inc 8 infrastructure and avoids
    # spawning HTTP leaf subprocesses just for assertions.
    verify_toolbox = MCPToolbox({
        "projects": three_mcp_servers["projects_url"],
        "people": three_mcp_servers["people_url"],
        "communications": three_mcp_servers["comms_url"],
    })

    # ---- Projects: at least one project row ----
    projects_result = await asyncio.wait_for(
        verify_toolbox.call_tool("projects", "get_projects", {}),
        timeout=30.0,
    )
    assert projects_result["status"] == "ok", (
        f"projects.get_projects returned non-ok: {projects_result!r}"
    )
    projects_content = projects_result["content"]
    projects_data = projects_content.get("data", [])
    assert isinstance(projects_data, list) and len(projects_data) >= 1, (
        f"expected >=1 project written by the orchestration, got: {projects_data!r}"
    )
    project_id = projects_data[0].get("id")
    assert project_id, (
        f"first project row missing id: {projects_data[0]!r}"
    )

    # ---- Tasks: at least one task under that project ----
    # The Projects MCP registry exposes "get_projects_id_tasks" for
    # GET /projects/{project_id}/tasks.
    tasks_result = await asyncio.wait_for(
        verify_toolbox.call_tool(
            "projects", "get_projects_id_tasks", {"project_id": project_id},
        ),
        timeout=30.0,
    )
    if tasks_result["status"] != "ok" or not tasks_result["content"].get("data"):
        # Fall back to the project-agnostic tasks list in case the LLM created
        # tasks under a different project id (unlikely but plausible given
        # planner autonomy). Assert against the aggregate.
        agg = await asyncio.wait_for(
            verify_toolbox.call_tool(
                "projects",
                "get_tasks_assignee_id_status_status_milestone_id",
                {},
            ),
            timeout=30.0,
        )
        assert agg["status"] == "ok", (
            f"fallback get_tasks call failed: {agg!r}"
        )
        agg_tasks = agg["content"].get("data", [])
        assert isinstance(agg_tasks, list) and len(agg_tasks) >= 1, (
            f"expected >=1 task written by the orchestration (across all "
            f"projects); per-project result was {tasks_result!r}, aggregate "
            f"was {agg_tasks!r}"
        )
    else:
        per_project_tasks = tasks_result["content"]["data"]
        assert isinstance(per_project_tasks, list) and len(per_project_tasks) >= 1, (
            f"expected >=1 task under project {project_id}, got: "
            f"{per_project_tasks!r}"
        )

    # ---- Messages: at least one message sent ----
    messages_result = await asyncio.wait_for(
        verify_toolbox.call_tool("communications", "list_messages", {}),
        timeout=30.0,
    )
    assert messages_result["status"] == "ok", (
        f"communications.list_messages returned non-ok: {messages_result!r}"
    )
    messages_data = messages_result["content"].get("data", [])
    assert isinstance(messages_data, list) and len(messages_data) >= 1, (
        f"expected >=1 message sent by the orchestration, got: {messages_data!r}"
    )
