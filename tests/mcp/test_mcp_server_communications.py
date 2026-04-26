"""Integration tests for ``CatalogBackedMCPServer`` against Communications.

No mocks. Every test creates a real SQLite DB in ``tmp_path``, instantiates
the Communications FastAPI app, wraps it in :class:`CatalogBackedMCPServer`,
and exercises the adapter's ``list_tools`` / ``call_tool`` methods.
Structural parity against ``TestClient`` is asserted for each
envelope-returning call so the MCP path returns exactly the same shape as
the underlying HTTP route.

Communications stores ``recipient_id`` and ``project_id`` as free-form
strings (no foreign-key referential integrity against People/Projects), so
no cross-service FK seeding is required.

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
from services.communications.app import create_app
from services.communications.mcp_registry import build_tool_registry
from services.communications.routes.capabilities import (
    COMMUNICATIONS_CAPABILITIES,
)


# --- fixtures ------------------------------------------------------------


def _build_server(tmp_path) -> tuple[CatalogBackedMCPServer, Any]:
    """Create a Communications app + server wrapper backed by a real SQLite DB."""

    db_path = tmp_path / "communications.db"
    app = create_app(sqlite_path=str(db_path))
    registry = build_tool_registry()
    server = CatalogBackedMCPServer(
        app=app,
        server_name="communications",
        tool_registry=registry,
        capabilities=COMMUNICATIONS_CAPABILITIES,
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
    """Both envelopes must share top-level keys and equivalent ``data`` shape."""

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


async def test_list_tools_returns_all_communications_capabilities(tmp_path) -> None:
    """``list_tools`` must emit a valid Tool for every Communications capability."""

    server, _app = _build_server(tmp_path)
    tools = await server.list_tools()

    expected_names = [
        capability_to_tool(c)["name"] for c in COMMUNICATIONS_CAPABILITIES
    ]
    actual_names = [t["name"] for t in tools]
    assert actual_names == expected_names

    for spec in tools:
        tool = Tool.model_validate(spec)
        assert tool.name == spec["name"]
        assert tool.inputSchema["type"] == "object"

    assert set(actual_names) == {
        "list_messages",
        "find_message",
        "send_message",
        "filter_by_recipient",
        "filter_by_project",
    }


async def test_call_tool_send_message_matches_testclient_envelope(tmp_path) -> None:
    """``send_message`` via MCP returns the same envelope as POST /messages."""

    server, _app = _build_server(tmp_path)

    body = {
        "recipient_id": "person_alice",
        "project_id": "proj_alpha",
        "subject": "You have been assigned",
        "body": "Please take a look at milestone #2.",
    }

    # MCP path
    mcp_content = await server.call_tool("send_message", dict(body))
    mcp_env = _parse_single_text_block(mcp_content)

    # HTTP path against a fresh app/DB to avoid id collisions.
    sub = tmp_path / "sub_a"
    sub.mkdir()
    _server2, app2 = _build_server(sub)
    with TestClient(app2) as http:
        http_env = http.post("/messages", json=body).json()

    # Envelope keys present
    assert ENVELOPE_KEYS.issubset(mcp_env.keys())

    # data shape parity (ids will differ but the field set should match).
    assert set(mcp_env["data"].keys()) == set(http_env["data"].keys())
    assert mcp_env["data"]["recipient_id"] == http_env["data"]["recipient_id"]
    assert mcp_env["data"]["project_id"] == http_env["data"]["project_id"]
    assert mcp_env["data"]["subject"] == http_env["data"]["subject"]
    assert mcp_env["data"]["body"] == http_env["data"]["body"]
    assert mcp_env["data"]["status"] == "sent"

    # Top-level envelope keys match.
    assert set(mcp_env.keys()) == set(http_env.keys())


async def test_call_tool_list_messages_matches_testclient_envelope(
    tmp_path,
) -> None:
    """Seed a message via MCP, then list via both MCP and TestClient."""

    server, app = _build_server(tmp_path)

    await server.call_tool(
        "send_message",
        {
            "recipient_id": "person_bob",
            "subject": "Hi",
            "body": "Ping.",
        },
    )

    # MCP list
    mcp_content = await server.call_tool("list_messages", {})
    mcp_env = _parse_single_text_block(mcp_content)

    # Same app via TestClient
    with TestClient(app) as http:
        http_env = http.get("/messages").json()

    # Both lists must have identical length and matching recipient_id.
    assert isinstance(mcp_env["data"], list)
    assert isinstance(http_env["data"], list)
    assert len(mcp_env["data"]) == len(http_env["data"]) == 1
    assert mcp_env["data"][0]["recipient_id"] == "person_bob"

    _assert_envelope_parity(mcp_env, http_env, data_is_list=True)


async def test_call_tool_find_message_substitutes_path_param(tmp_path) -> None:
    """``find_message`` must hoist ``message_id`` into the URL path."""

    server, app = _build_server(tmp_path)

    create_env = _parse_single_text_block(
        await server.call_tool(
            "send_message",
            {
                "recipient_id": "person_carol",
                "subject": "Subject",
                "body": "Hello.",
            },
        )
    )
    message_id = create_env["data"]["id"]

    # MCP: arguments carry only the path param.
    mcp_content = await server.call_tool(
        "find_message", {"message_id": message_id}
    )
    mcp_env = _parse_single_text_block(mcp_content)

    assert mcp_env["data"]["id"] == message_id
    assert mcp_env["data"]["recipient_id"] == "person_carol"
    # _self should reference the single-message URL.
    assert mcp_env["_self"].endswith(f"/messages/{message_id}")

    # HTTP parity on the same app/DB.
    with TestClient(app) as http:
        http_env = http.get(f"/messages/{message_id}").json()

    assert set(mcp_env.keys()) == set(http_env.keys())
    assert ENVELOPE_KEYS.issubset(mcp_env.keys())
    assert mcp_env["data"] == http_env["data"]


async def test_call_tool_filter_by_recipient(tmp_path) -> None:
    """Query-param passthrough: ``filter_by_recipient`` narrows by recipient_id."""

    server, _app = _build_server(tmp_path)

    await server.call_tool(
        "send_message",
        {
            "recipient_id": "person_alice",
            "subject": "To Alice #1",
            "body": "msg1",
        },
    )
    await server.call_tool(
        "send_message",
        {
            "recipient_id": "person_bob",
            "subject": "To Bob",
            "body": "msg2",
        },
    )
    await server.call_tool(
        "send_message",
        {
            "recipient_id": "person_alice",
            "subject": "To Alice #2",
            "body": "msg3",
        },
    )

    # Filter by "person_alice" — should return 2 messages.
    mcp_env = _parse_single_text_block(
        await server.call_tool(
            "filter_by_recipient", {"recipient_id": "person_alice"}
        )
    )
    assert isinstance(mcp_env["data"], list)
    subjects = {m["subject"] for m in mcp_env["data"]}
    assert subjects == {"To Alice #1", "To Alice #2"}

    # Filter by "person_bob" — should return 1 message.
    mcp_env2 = _parse_single_text_block(
        await server.call_tool(
            "filter_by_recipient", {"recipient_id": "person_bob"}
        )
    )
    assert {m["subject"] for m in mcp_env2["data"]} == {"To Bob"}


async def test_call_tool_filter_by_project(tmp_path) -> None:
    """Query-param passthrough: ``filter_by_project`` narrows by project_id."""

    server, _app = _build_server(tmp_path)

    await server.call_tool(
        "send_message",
        {
            "recipient_id": "person_alice",
            "project_id": "proj_alpha",
            "subject": "Alpha status",
            "body": "On track.",
        },
    )
    await server.call_tool(
        "send_message",
        {
            "recipient_id": "person_bob",
            "project_id": "proj_beta",
            "subject": "Beta status",
            "body": "Behind.",
        },
    )
    await server.call_tool(
        "send_message",
        {
            "recipient_id": "person_carol",
            "project_id": "proj_alpha",
            "subject": "Alpha milestone",
            "body": "Milestone complete.",
        },
    )

    # Filter by project "proj_alpha" — should return 2 messages.
    mcp_env = _parse_single_text_block(
        await server.call_tool(
            "filter_by_project", {"project_id": "proj_alpha"}
        )
    )
    assert isinstance(mcp_env["data"], list)
    subjects = {m["subject"] for m in mcp_env["data"]}
    assert subjects == {"Alpha status", "Alpha milestone"}

    # Filter by project "proj_beta" — should return 1 message.
    mcp_env2 = _parse_single_text_block(
        await server.call_tool(
            "filter_by_project", {"project_id": "proj_beta"}
        )
    )
    assert {m["subject"] for m in mcp_env2["data"]} == {"Beta status"}


async def test_call_tool_returns_error_envelope_without_raising(
    tmp_path,
) -> None:
    """Non-2xx responses must be returned verbatim — no exception raised."""

    server, _app = _build_server(tmp_path)

    # Missing required ``subject`` / ``body`` on CreateMessage -> FastAPI 422.
    content = await server.call_tool(
        "send_message", {"recipient_id": "person_alice"}
    )
    payload = _parse_single_text_block(content)

    assert isinstance(payload, dict)
    # Either the FastAPI default 422 body (``detail``) or the AgentError
    # envelope (``_why`` + ``_try_instead``) is acceptable.
    assert "detail" in payload or (
        "_why" in payload and "_try_instead" in payload
    )

    # find_message with an unknown id must return an error envelope (404),
    # not raise.
    not_found_env = _parse_single_text_block(
        await server.call_tool(
            "find_message", {"message_id": "msg_does_not_exist"}
        )
    )
    assert isinstance(not_found_env, dict)
    # AgentError envelope includes _why / _try_instead (per the route).
    assert "_why" in not_found_env and "_try_instead" in not_found_env
