"""Integration tests for ``CatalogBackedMCPServer`` against the People app.

No mocks. Every test creates a real SQLite DB in ``tmp_path``, instantiates
the People FastAPI app, wraps it in :class:`CatalogBackedMCPServer`, and
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
from services.people.app import create_app
from services.people.mcp_registry import build_tool_registry
from services.people.routes.capabilities import PEOPLE_CAPABILITIES


# --- fixtures ------------------------------------------------------------


def _build_server(tmp_path) -> tuple[CatalogBackedMCPServer, Any]:
    """Create a People app + server wrapper backed by a real SQLite DB."""

    db_path = tmp_path / "people.db"
    app = create_app(sqlite_path=str(db_path))
    registry = build_tool_registry()
    server = CatalogBackedMCPServer(
        app=app,
        server_name="people",
        tool_registry=registry,
        capabilities=PEOPLE_CAPABILITIES,
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
    must match structurally (same keys). The ``data`` payload must match for
    scalar data; for list data only length parity is asserted here — callers
    can add stronger content-level assertions as needed.
    """

    assert "data" in mcp_envelope and "data" in http_envelope
    assert set(mcp_envelope.keys()) == set(http_envelope.keys())

    assert ENVELOPE_KEYS.issubset(set(mcp_envelope.keys()))

    if data_is_list:
        assert isinstance(mcp_envelope["data"], list)
        assert isinstance(http_envelope["data"], list)
        assert len(mcp_envelope["data"]) == len(http_envelope["data"])
    else:
        assert mcp_envelope["data"] == http_envelope["data"]

    assert mcp_envelope["_self"] == http_envelope["_self"]
    assert mcp_envelope["_related"] == http_envelope["_related"]

    if mcp_envelope.get("_suggested_next") is None:
        assert http_envelope.get("_suggested_next") is None
    else:
        # _suggested_next may be a list of dicts (People uses list form) or
        # a single dict. Compare structurally based on actual shape.
        mcp_sn = mcp_envelope["_suggested_next"]
        http_sn = http_envelope["_suggested_next"]
        if isinstance(mcp_sn, list):
            assert isinstance(http_sn, list)
            assert len(mcp_sn) == len(http_sn)
            for m, h in zip(mcp_sn, http_sn):
                assert set(m.keys()) == set(h.keys())
        else:
            assert set(mcp_sn.keys()) == set(http_sn.keys())


# --- tests ---------------------------------------------------------------


async def test_list_tools_returns_all_people_capabilities(tmp_path) -> None:
    """``list_tools`` must emit a valid Tool for every People capability."""

    server, _app = _build_server(tmp_path)
    tools = await server.list_tools()

    expected_names = [capability_to_tool(c)["name"] for c in PEOPLE_CAPABILITIES]
    actual_names = [t["name"] for t in tools]
    assert actual_names == expected_names

    # Every spec must construct a valid mcp.types.Tool.
    for spec in tools:
        tool = Tool.model_validate(spec)
        assert tool.name == spec["name"]
        assert tool.inputSchema["type"] == "object"

    # All six capabilities must be present as derived tool names.
    assert set(actual_names) == {
        "list_people",
        "find_person",
        "create_person",
        "update_person",
        "filter_by_skill",
        "filter_by_availability",
    }


async def test_call_tool_create_person_matches_testclient_envelope(tmp_path) -> None:
    """``create_person`` via MCP returns the same envelope as POST /people."""

    server, app = _build_server(tmp_path)

    body = {
        "name": "Alice Chen",
        "role": "senior engineer",
        "skills": ["python", "fastapi"],
    }

    # MCP path
    mcp_content = await server.call_tool("create_person", dict(body))
    mcp_env = _parse_single_text_block(mcp_content)

    # HTTP path against a fresh app/DB to avoid id collisions.
    sub = tmp_path / "sub_a"
    sub.mkdir()
    _server2, app2 = _build_server(sub)
    with TestClient(app2) as http:
        http_env = http.post("/people", json=body).json()

    # Envelope keys present
    assert ENVELOPE_KEYS.issubset(mcp_env.keys())

    # data shape parity (ids will differ but the field set should match).
    assert set(mcp_env["data"].keys()) == set(http_env["data"].keys())
    assert mcp_env["data"]["name"] == http_env["data"]["name"]
    assert mcp_env["data"]["role"] == http_env["data"]["role"]
    assert mcp_env["data"]["skills"] == http_env["data"]["skills"]
    # New person defaults:
    assert mcp_env["data"]["available"] is True
    assert mcp_env["data"]["current_load"] == 0

    # Top-level envelope keys match.
    assert set(mcp_env.keys()) == set(http_env.keys())


async def test_call_tool_list_people_matches_testclient_envelope(tmp_path) -> None:
    """Seed a person via MCP, then list via both MCP and TestClient."""

    server, app = _build_server(tmp_path)

    await server.call_tool(
        "create_person",
        {"name": "Seeded Person", "role": "designer", "skills": ["figma"]},
    )

    # MCP list
    mcp_content = await server.call_tool("list_people", {})
    mcp_env = _parse_single_text_block(mcp_content)

    # Same app via TestClient
    with TestClient(app) as http:
        http_env = http.get("/people").json()

    # Both lists must have identical length and matching person names.
    assert isinstance(mcp_env["data"], list)
    assert isinstance(http_env["data"], list)
    assert len(mcp_env["data"]) == len(http_env["data"]) == 1
    assert mcp_env["data"][0]["name"] == "Seeded Person"

    _assert_envelope_parity(mcp_env, http_env, data_is_list=True)


async def test_call_tool_find_person_substitutes_path_param(tmp_path) -> None:
    """``find_person`` must hoist ``person_id`` into the URL path."""

    server, app = _build_server(tmp_path)

    create_env = _parse_single_text_block(
        await server.call_tool(
            "create_person",
            {"name": "Bob Patel", "role": "PM", "skills": ["roadmap"]},
        )
    )
    person_id = create_env["data"]["id"]

    # MCP: arguments carry only the path param.
    mcp_content = await server.call_tool("find_person", {"person_id": person_id})
    mcp_env = _parse_single_text_block(mcp_content)

    assert mcp_env["data"]["id"] == person_id
    assert mcp_env["data"]["name"] == "Bob Patel"
    # _self should reference the single-person URL.
    assert mcp_env["_self"].endswith(f"/people/{person_id}")

    # HTTP parity on the same app/DB.
    with TestClient(app) as http:
        http_env = http.get(f"/people/{person_id}").json()

    assert set(mcp_env.keys()) == set(http_env.keys())
    assert ENVELOPE_KEYS.issubset(mcp_env.keys())
    assert mcp_env["data"] == http_env["data"]


async def test_call_tool_update_person_separates_path_and_body_params(
    tmp_path,
) -> None:
    """Plan §10 risk test: ``person_id`` must go to path, others to body."""

    server, app = _build_server(tmp_path)

    create_env = _parse_single_text_block(
        await server.call_tool(
            "create_person",
            {"name": "Carol", "role": "engineer", "skills": ["go"]},
        )
    )
    person_id = create_env["data"]["id"]

    # Patch via MCP: person_id is a path param; available/current_load/skills
    # are body.
    patch_env = _parse_single_text_block(
        await server.call_tool(
            "update_person",
            {
                "person_id": person_id,
                "available": False,
                "current_load": 2,
                "skills": ["go", "rust"],
            },
        )
    )

    # Path param was hoisted into the URL (no stray person_id in body).
    assert patch_env["data"]["id"] == person_id
    # Body fields were actually applied.
    assert patch_env["data"]["available"] is False
    assert patch_env["data"]["current_load"] == 2
    assert patch_env["data"]["skills"] == ["go", "rust"]

    # Structural parity vs. TestClient PATCH on the same app/DB.
    with TestClient(app) as http:
        http_env = http.patch(
            f"/people/{person_id}",
            json={"available": True},
        ).json()

    assert set(patch_env.keys()) == set(http_env.keys())
    assert ENVELOPE_KEYS.issubset(patch_env.keys())
    assert set(patch_env["data"].keys()) == set(http_env["data"].keys())


async def test_call_tool_filter_by_skill(tmp_path) -> None:
    """Query-param passthrough: ``filter_by_skill`` narrows results by skill."""

    server, _app = _build_server(tmp_path)

    await server.call_tool(
        "create_person",
        {"name": "Py Pro", "role": "eng", "skills": ["python", "fastapi"]},
    )
    await server.call_tool(
        "create_person",
        {"name": "JS Pro", "role": "eng", "skills": ["javascript", "react"]},
    )
    await server.call_tool(
        "create_person",
        {"name": "Poly Glot", "role": "eng", "skills": ["python", "rust"]},
    )

    # Filter by "python" skill — should return 2 people.
    mcp_env = _parse_single_text_block(
        await server.call_tool("filter_by_skill", {"skill": "python"})
    )

    assert isinstance(mcp_env["data"], list)
    names = {p["name"] for p in mcp_env["data"]}
    assert names == {"Py Pro", "Poly Glot"}

    # Filter by "rust" — should return 1 person.
    mcp_env2 = _parse_single_text_block(
        await server.call_tool("filter_by_skill", {"skill": "rust"})
    )
    names2 = {p["name"] for p in mcp_env2["data"]}
    assert names2 == {"Poly Glot"}


async def test_call_tool_filter_by_availability(tmp_path) -> None:
    """Query-param passthrough: ``filter_by_availability`` narrows by available."""

    server, _app = _build_server(tmp_path)

    # Create three people.
    p1 = _parse_single_text_block(
        await server.call_tool(
            "create_person",
            {"name": "Alpha", "role": "eng", "skills": ["python"]},
        )
    )["data"]["id"]
    _p2 = _parse_single_text_block(
        await server.call_tool(
            "create_person",
            {"name": "Beta", "role": "eng", "skills": ["python"]},
        )
    )["data"]["id"]
    p3 = _parse_single_text_block(
        await server.call_tool(
            "create_person",
            {"name": "Gamma", "role": "eng", "skills": ["ruby"]},
        )
    )["data"]["id"]

    # Mark Alpha and Gamma as unavailable.
    await server.call_tool(
        "update_person", {"person_id": p1, "available": False}
    )
    await server.call_tool(
        "update_person", {"person_id": p3, "available": False}
    )

    # Filter by available=true — should return only Beta.
    mcp_env = _parse_single_text_block(
        await server.call_tool(
            "filter_by_availability", {"available": "true"}
        )
    )
    assert isinstance(mcp_env["data"], list)
    names = {p["name"] for p in mcp_env["data"]}
    assert names == {"Beta"}

    # Combine available=true + skill=python — still only Beta.
    mcp_env2 = _parse_single_text_block(
        await server.call_tool(
            "filter_by_availability",
            {"available": "true", "skill": "python"},
        )
    )
    names2 = {p["name"] for p in mcp_env2["data"]}
    assert names2 == {"Beta"}


async def test_call_tool_returns_error_envelope_without_raising(tmp_path) -> None:
    """Non-2xx responses must be returned verbatim — no exception raised."""

    server, _app = _build_server(tmp_path)

    # Missing required ``name`` / ``role`` on CreatePerson -> FastAPI 422.
    content = await server.call_tool(
        "create_person", {"skills": ["python"]}
    )
    payload = _parse_single_text_block(content)

    assert isinstance(payload, dict)
    # Either the FastAPI default 422 body (``detail``) or the AgentError
    # envelope (``_why`` + ``_try_instead``) is acceptable.
    assert "detail" in payload or (
        "_why" in payload and "_try_instead" in payload
    )

    # find_person with an unknown id must return an error envelope (404),
    # not raise.
    not_found_env = _parse_single_text_block(
        await server.call_tool(
            "find_person", {"person_id": "person_does_not_exist"}
        )
    )
    assert isinstance(not_found_env, dict)
    # AgentError envelope includes _why / _try_instead (per the route).
    assert "_why" in not_found_env and "_try_instead" in not_found_env
