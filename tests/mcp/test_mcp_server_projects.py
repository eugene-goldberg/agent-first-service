"""Integration tests for ``CatalogBackedMCPServer`` against the Projects app.

No mocks. Every test creates a real SQLite DB in ``tmp_path``, instantiates
the Projects FastAPI app, wraps it in :class:`CatalogBackedMCPServer`, and
exercises the adapter's ``list_tools`` / ``call_tool`` methods. Structural
parity against ``TestClient`` is asserted for each envelope-returning call so
the MCP path returns exactly the same shape as the underlying HTTP route.

`pytest.ini_options.asyncio_mode = "auto"` in ``pyproject.toml`` means any
``async def test_*`` function is collected as an async test automatically; no
``@pytest.mark.asyncio`` decorator is required.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient
from mcp.types import Tool

from agent_protocol.mcp_adapter import (
    CatalogBackedMCPServer,
    capability_to_tool,
)
from services.projects.app import create_app
from services.projects.mcp_registry import build_tool_registry
from services.projects.routes.capabilities import _CAPABILITIES as PROJECTS_CAPABILITIES


# --- fixtures ------------------------------------------------------------


def _build_server(tmp_path) -> tuple[CatalogBackedMCPServer, Any]:
    """Create a Projects app + server wrapper backed by a real SQLite DB."""

    db_path = tmp_path / "projects.db"
    app = create_app(sqlite_path=db_path)
    registry = build_tool_registry()
    server = CatalogBackedMCPServer(
        app=app,
        server_name="projects",
        tool_registry=registry,
        capabilities=PROJECTS_CAPABILITIES,
    )
    return server, app


def _parse_single_text_block(content: list[dict[str, Any]]) -> dict[str, Any]:
    """Helper: the adapter returns a single-element list with a ``text`` JSON."""

    assert isinstance(content, list)
    assert len(content) == 1
    block = content[0]
    assert block["type"] == "text"
    assert block["annotations"] == {"contentType": "application/json"}
    return json.loads(block["text"])


ENVELOPE_KEYS = {"data", "_self", "_related", "_suggested_next", "_generated_at"}


def _assert_envelope_parity(
    mcp_envelope: dict[str, Any],
    http_envelope: dict[str, Any],
    *,
    data_is_list: bool = False,
) -> None:
    """Both envelopes must share top-level keys and equivalent ``data`` shape.

    ``_generated_at`` may differ (generated per-call). ``_suggested_next``
    must match structurally (same keys). The ``data`` payload must match.
    """

    # Top-level keys present on both (allowing for absent optional keys, but
    # the core ones must match).
    assert "data" in mcp_envelope and "data" in http_envelope
    assert set(mcp_envelope.keys()) == set(http_envelope.keys())

    # Core envelope keys from the spec must be present.
    assert ENVELOPE_KEYS.issubset(set(mcp_envelope.keys()))

    # data parity
    if data_is_list:
        assert isinstance(mcp_envelope["data"], list)
        assert isinstance(http_envelope["data"], list)
        assert len(mcp_envelope["data"]) == len(http_envelope["data"])
    else:
        assert mcp_envelope["data"] == http_envelope["data"]

    # self + related must match.
    assert mcp_envelope["_self"] == http_envelope["_self"]
    assert mcp_envelope["_related"] == http_envelope["_related"]

    # suggested_next shape parity (same keys).
    if mcp_envelope.get("_suggested_next") is None:
        assert http_envelope.get("_suggested_next") is None
    else:
        assert set(mcp_envelope["_suggested_next"].keys()) == set(
            http_envelope["_suggested_next"].keys()
        )


# --- tests ---------------------------------------------------------------


async def test_list_tools_returns_all_projects_capabilities(tmp_path) -> None:
    """``list_tools`` must emit a valid Tool for every capability."""

    server, _app = _build_server(tmp_path)
    tools = await server.list_tools()

    expected_names = [capability_to_tool(c)["name"] for c in PROJECTS_CAPABILITIES]
    actual_names = [t["name"] for t in tools]
    assert actual_names == expected_names

    # Every spec must construct a valid mcp.types.Tool.
    for spec in tools:
        tool = Tool.model_validate(spec)
        assert tool.name == spec["name"]
        assert tool.inputSchema["type"] == "object"


async def test_call_tool_post_projects_matches_testclient_envelope(tmp_path) -> None:
    """``post_projects`` via MCP returns the same envelope as POST /projects."""

    server, app = _build_server(tmp_path)

    body = {"name": "Q3 Launch", "description": "Q3 launch landing page"}

    # MCP path
    mcp_content = await server.call_tool("post_projects", dict(body))
    mcp_env = _parse_single_text_block(mcp_content)

    # HTTP path against a fresh app/DB to avoid id collisions. Use a new
    # tmp_path subdirectory (must exist; create it first).
    sub = tmp_path / "sub_a"
    sub.mkdir()
    _server2, app2 = _build_server(sub)
    with TestClient(app2) as http:
        http_env = http.post("/projects", json=body).json()

    # Envelope keys present
    assert ENVELOPE_KEYS.issubset(mcp_env.keys())

    # data shape parity (ids will differ but the field set should match)
    assert set(mcp_env["data"].keys()) == set(http_env["data"].keys())
    assert mcp_env["data"]["name"] == http_env["data"]["name"]
    assert mcp_env["data"]["description"] == http_env["data"]["description"]

    # Top-level keys match and _suggested_next keys match.
    assert set(mcp_env.keys()) == set(http_env.keys())
    assert set(mcp_env["_suggested_next"].keys()) == set(
        http_env["_suggested_next"].keys()
    )


async def test_call_tool_get_projects_matches_testclient_envelope(tmp_path) -> None:
    """Seed a project via MCP, then list via both MCP and TestClient."""

    server, app = _build_server(tmp_path)

    # Seed one project.
    await server.call_tool(
        "post_projects",
        {"name": "Seeded project", "description": "seed for GET test"},
    )

    # MCP list
    mcp_content = await server.call_tool("get_projects", {})
    mcp_env = _parse_single_text_block(mcp_content)

    # Same app via TestClient
    with TestClient(app) as http:
        http_env = http.get("/projects").json()

    # Both lists must have identical length and matching project names.
    assert isinstance(mcp_env["data"], list)
    assert isinstance(http_env["data"], list)
    assert len(mcp_env["data"]) == len(http_env["data"]) == 1
    assert mcp_env["data"][0]["name"] == "Seeded project"

    _assert_envelope_parity(mcp_env, http_env, data_is_list=True)


async def test_call_tool_post_projects_id_tasks_substitutes_path_param(
    tmp_path,
) -> None:
    """``post_projects_id_tasks`` must hoist ``project_id`` into the URL path."""

    server, app = _build_server(tmp_path)

    # Create project via MCP so we have a real id.
    create_env = _parse_single_text_block(
        await server.call_tool(
            "post_projects",
            {"name": "Hosting tasks", "description": "parent for tasks"},
        )
    )
    project_id = create_env["data"]["id"]

    # MCP: arguments carry the path param inline alongside body fields.
    mcp_content = await server.call_tool(
        "post_projects_id_tasks",
        {
            "project_id": project_id,
            "title": "Write hero copy",
            "assignee_id": None,
            "due_date": "2026-05-20",
        },
    )
    mcp_env = _parse_single_text_block(mcp_content)

    # Path-param hoisting should have landed the URL at /projects/{pid}/tasks.
    assert mcp_env["_self"] == f"/tasks/{mcp_env['data']['id']}"
    assert mcp_env["data"]["project_id"] == project_id
    assert mcp_env["data"]["title"] == "Write hero copy"

    # HTTP path: same app via TestClient — must produce structurally identical
    # envelope (except ids differ).
    with TestClient(app) as http:
        http_env = http.post(
            f"/projects/{project_id}/tasks",
            json={
                "title": "Write hero copy 2",
                "assignee_id": None,
                "due_date": "2026-05-20",
            },
        ).json()

    assert set(mcp_env.keys()) == set(http_env.keys())
    assert ENVELOPE_KEYS.issubset(mcp_env.keys())
    assert set(mcp_env["data"].keys()) == set(http_env["data"].keys())


async def test_call_tool_get_projects_id_tasks(tmp_path) -> None:
    """Parity test for listing tasks under a project."""

    server, app = _build_server(tmp_path)

    create_env = _parse_single_text_block(
        await server.call_tool(
            "post_projects",
            {"name": "Task list test", "description": ""},
        )
    )
    project_id = create_env["data"]["id"]
    await server.call_tool(
        "post_projects_id_tasks",
        {"project_id": project_id, "title": "First task"},
    )

    mcp_env = _parse_single_text_block(
        await server.call_tool("get_projects_id_tasks", {"project_id": project_id})
    )

    with TestClient(app) as http:
        http_env = http.get(f"/projects/{project_id}/tasks").json()

    # Envelope parity.
    _assert_envelope_parity(mcp_env, http_env, data_is_list=True)
    # Both should see the one task we created.
    assert len(mcp_env["data"]) == 1
    assert mcp_env["data"][0]["title"] == "First task"


async def test_call_tool_patch_tasks_id_separates_path_and_body_params(
    tmp_path,
) -> None:
    """Plan §10 risk test: ``task_id`` must go to path, others to body."""

    server, app = _build_server(tmp_path)

    # Create a project and a task via MCP to get real ids.
    project_env = _parse_single_text_block(
        await server.call_tool(
            "post_projects",
            {"name": "Patch test", "description": ""},
        )
    )
    project_id = project_env["data"]["id"]

    task_env = _parse_single_text_block(
        await server.call_tool(
            "post_projects_id_tasks",
            {
                "project_id": project_id,
                "title": "Original title",
                "assignee_id": None,
                "due_date": "2026-04-30",
            },
        )
    )
    task_id = task_env["data"]["id"]

    # Patch via MCP: task_id is a path param; status/assignee_id/due_date are body.
    patch_env = _parse_single_text_block(
        await server.call_tool(
            "patch_tasks_id",
            {
                "task_id": task_id,
                "status": "done",
                "assignee_id": "person_alice",
                "due_date": "2026-05-01",
            },
        )
    )

    # The path param must have ended up in the URL: the returned envelope's
    # _self references the task id we supplied (proving no stray task_id
    # leaked into the body and the URL substitution worked).
    assert patch_env["_self"] == f"/tasks/{task_id}"
    assert patch_env["data"]["id"] == task_id
    # Body fields must have actually been applied (proving they made it into
    # the JSON body and were NOT hoisted into the URL).
    assert patch_env["data"]["status"] == "done"
    assert patch_env["data"]["assignee_id"] == "person_alice"
    assert patch_env["data"]["due_date"] == "2026-05-01"

    # Structural parity vs. TestClient PATCH on the same app/DB.
    with TestClient(app) as http:
        http_env = http.patch(
            f"/tasks/{task_id}",
            json={"status": "in_progress"},
        ).json()

    assert set(patch_env.keys()) == set(http_env.keys())
    assert ENVELOPE_KEYS.issubset(patch_env.keys())
    assert set(patch_env["data"].keys()) == set(http_env["data"].keys())


async def test_call_tool_returns_error_envelope_without_raising(tmp_path) -> None:
    """Non-2xx responses must be returned verbatim — no exception raised."""

    server, _app = _build_server(tmp_path)

    # Missing required ``name`` field on CreateProject -> FastAPI 422.
    content = await server.call_tool("post_projects", {"description": "no name"})
    payload = _parse_single_text_block(content)

    # FastAPI's default 422 for pydantic validation uses the ``detail`` key.
    # The adapter MUST return the response body verbatim, so we should see
    # either ``detail`` (FastAPI validation error) or the AgentError keys.
    assert isinstance(payload, dict)
    # No exception was raised to reach this assertion. Either the FastAPI
    # default 422 body (``detail``) or the AgentError envelope
    # (``_why`` + ``_try_instead``) is acceptable.
    assert "detail" in payload or (
        "_why" in payload and "_try_instead" in payload
    )
