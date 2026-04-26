"""MCP adapter utilities shared across leaf-service MCP servers.

This module exposes:

* :func:`capability_to_tool`, a helper that converts an
  :class:`agent_protocol.catalog.Capability` into an MCP tool spec dict
  (keys: ``name``, ``description``, ``inputSchema``) suitable for passing to
  ``mcp.types.Tool(**spec)``.
* :class:`CatalogBackedMCPServer`, a transport-agnostic adapter that wraps a
  FastAPI app and exposes it as an MCP-style server via two awaitable methods:
  :meth:`CatalogBackedMCPServer.list_tools` and
  :meth:`CatalogBackedMCPServer.call_tool`. Transport wiring
  (``stdio_server`` / ``SseServerTransport``) belongs to the per-service
  ``mcp_server.py`` / ``mcp_main.py`` modules introduced in later increments.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, Sequence

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

from agent_protocol.catalog import Capability


_NON_ALNUM_RUN = re.compile(r"[^a-z0-9]+")


def _derive_tool_name(cap: Capability) -> str:
    """Derive a tool name from a Capability per the plan's §3.1 rules."""

    if cap.id:
        return cap.id

    verb = (cap.verb or cap.method or "").lower()
    path = cap.path or ""
    raw = f"{verb}_{path}".lower()
    collapsed = _NON_ALNUM_RUN.sub("_", raw)
    return collapsed.strip("_")


def _build_description(cap: Capability, fallback_name: str) -> str:
    """Compose the tool description from summary/intent plus hints."""

    base = cap.summary or cap.intent or ""
    hints_joined = " ".join(cap.hints) if cap.hints else ""

    parts: list[str] = []
    if base:
        parts.append(base)
    if hints_joined:
        parts.append(hints_joined)

    if not parts:
        return fallback_name
    return " ".join(parts)


def capability_to_tool(
    cap: Capability,
    request_model: type[BaseModel] | None = None,
    path_params: Iterable[str] | None = None,
    query_params: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Convert a Capability to an MCP tool spec dict.

    Returns a plain dict with keys ``name``, ``description``, ``inputSchema``.
    ``inputSchema`` is always an object-typed JSON schema with ``type``,
    ``properties``, and ``required`` keys (and optionally ``$defs`` when the
    supplied ``request_model`` contributes one).
    """

    name = _derive_tool_name(cap)
    description = _build_description(cap, fallback_name=name)

    properties: dict[str, Any] = {}
    required: list[str] = []
    defs: dict[str, Any] | None = None

    if request_model is not None:
        body_schema = request_model.model_json_schema()
        body_props = body_schema.get("properties") or {}
        if isinstance(body_props, dict):
            properties.update(body_props)
        body_required = body_schema.get("required") or []
        for req_name in body_required:
            if req_name not in required:
                required.append(req_name)
        if "$defs" in body_schema:
            defs = body_schema["$defs"]

    if path_params:
        for pname in path_params:
            if pname not in properties:
                properties[pname] = {
                    "type": "string",
                    "description": f"Path parameter: {pname}",
                }
            if pname not in required:
                required.append(pname)

    if query_params:
        for qname in query_params:
            if qname not in properties:
                properties[qname] = {
                    "type": "string",
                    "description": f"Query parameter: {qname}",
                }

    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": required,
    }
    if defs is not None:
        input_schema["$defs"] = defs

    return {
        "name": name,
        "description": description,
        "inputSchema": input_schema,
    }


# --- tool_registry entry shape --------------------------------------------
# A `tool_registry` maps tool_name -> ToolRegistryEntry, a 5-tuple of:
#   (route_path_template, http_verb, request_model | None, path_params, query_params)
# e.g. ("/projects/{project_id}/tasks", "POST", CreateTask, ["project_id"], [])
ToolRegistryEntry = tuple[
    str,                        # route_path_template, e.g. "/projects/{project_id}/tasks"
    str,                        # http_verb, e.g. "GET" | "POST" | "PATCH"
    type[BaseModel] | None,     # request_model (body), or None for bodyless verbs
    Sequence[str],              # path_params, ordered
    Sequence[str],              # query_params
]


class CatalogBackedMCPServer:
    """Transport-agnostic MCP server adapter for a FastAPI app.

    Constructor signature:

        CatalogBackedMCPServer(
            app: FastAPI,
            server_name: str,
            tool_registry: dict[str, ToolRegistryEntry],
            capabilities: list[Capability],
        )

    * ``app`` — the FastAPI app that will handle dispatched HTTP calls via
      ``httpx.ASGITransport``.
    * ``server_name`` — logical name for this MCP server (e.g. ``"projects"``).
    * ``tool_registry`` — maps tool name to
      ``(route_path_template, http_verb, request_model | None,
         path_params, query_params)``. The tool name MUST match the name
      derived by :func:`capability_to_tool` for the corresponding Capability.
    * ``capabilities`` — the service's module-level capability list (e.g.
      ``services.projects.routes.capabilities._CAPABILITIES``). Used by
      :meth:`list_tools` to produce full tool specs via
      :func:`capability_to_tool`.

    This class intentionally does NOT instantiate ``mcp.Server`` or bind any
    transport (``stdio_server`` / ``SseServerTransport``). Instead it exposes
    two awaitable methods — :meth:`list_tools` and :meth:`call_tool` — that
    a per-service ``mcp_server.py`` (introduced in a later increment) will
    register as the backing handlers for ``mcp.Server``.
    """

    def __init__(
        self,
        app: FastAPI,
        server_name: str,
        tool_registry: dict[str, ToolRegistryEntry],
        capabilities: list[Capability],
    ) -> None:
        self.app = app
        self.server_name = server_name
        self.tool_registry = dict(tool_registry)
        self.capabilities = list(capabilities)

    async def list_tools(self) -> list[dict[str, Any]]:
        """Return the full list of MCP tool specs for this server.

        For every Capability supplied at construction time, this looks up the
        matching ``tool_registry`` entry (by derived tool name) and calls
        :func:`capability_to_tool` with the matching ``request_model``,
        ``path_params``, and ``query_params``. Capabilities with no registry
        entry are emitted with the bare Capability (no hoisted body / path /
        query params).
        """

        tools: list[dict[str, Any]] = []
        for cap in self.capabilities:
            tool_name = _derive_tool_name(cap)
            entry = self.tool_registry.get(tool_name)
            if entry is None:
                tools.append(capability_to_tool(cap))
                continue

            _path_template, _verb, request_model, path_params, query_params = entry
            spec = capability_to_tool(
                cap,
                request_model=request_model,
                path_params=list(path_params) or None,
                query_params=list(query_params) or None,
            )
            tools.append(spec)
        return tools

    async def call_tool(
        self, name: str, arguments: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Dispatch an MCP tool call into the wrapped FastAPI app.

        Steps:
          1. Look up ``(path_template, verb, request_model, path_params,
             query_params)`` in the registry.
          2. Substitute ``path_params`` into ``path_template``.
          3. Extract ``query_params`` values from ``arguments`` for the
             querystring.
          4. Remaining fields in ``arguments`` form the JSON body (only for
             verbs that have a ``request_model``).
          5. Dispatch via ``httpx.AsyncClient`` with ``ASGITransport(app)``.
          6. Return a single-element list containing a text content block
             whose ``text`` is the JSON-serialised response body (envelope or
             error envelope). Non-2xx responses are NOT raised — their error
             envelope is returned verbatim so the caller sees ``_why`` /
             ``_try_instead`` etc.
        """

        if name not in self.tool_registry:
            raise KeyError(f"unknown tool for server {self.server_name!r}: {name!r}")

        path_template, verb, request_model, path_params, query_params = (
            self.tool_registry[name]
        )

        args = dict(arguments or {})

        # 2) Substitute path params.
        path_values: dict[str, Any] = {}
        for pname in path_params:
            if pname not in args:
                raise KeyError(
                    f"tool {name!r} requires path param {pname!r}, "
                    f"not found in arguments"
                )
            path_values[pname] = args.pop(pname)
        url_path = path_template.format(**path_values)

        # 3) Query param subset.
        query: dict[str, Any] = {}
        for qname in query_params:
            if qname in args:
                query[qname] = args.pop(qname)

        # 4) Remaining args become the JSON body (only when there is a body).
        verb_upper = verb.upper()
        body: dict[str, Any] | None
        if request_model is not None and verb_upper in {"POST", "PUT", "PATCH"}:
            body = args
        else:
            # Any leftover args for a bodyless verb are silently dropped; the
            # HTTP layer would reject them anyway, and path/query have already
            # been consumed above.
            body = None

        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            if body is None:
                response = await client.request(
                    verb_upper, url_path, params=query or None
                )
            else:
                response = await client.request(
                    verb_upper,
                    url_path,
                    params=query or None,
                    json=body,
                )

        # 6) Return the envelope (or error envelope) as a single text content
        # block. Do NOT raise on non-2xx — the AgentError envelope is the
        # payload the agent must see.
        try:
            envelope: Any = response.json()
        except ValueError:
            envelope = {"error": "non_json_response", "message": response.text}

        return [
            {
                "type": "text",
                "text": json.dumps(envelope, default=str),
                "annotations": {"contentType": "application/json"},
            }
        ]
