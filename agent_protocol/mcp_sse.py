"""Service-agnostic helper to wrap an ``mcp.server.Server`` in a Starlette SSE app.

The MCP SDK's SSE transport (``mcp.server.sse.SseServerTransport``) is the same
regardless of which leaf service is being exposed — only the backing
``mcp.Server`` differs. This module centralises the wiring so each service's
``mcp_main.py`` can simply do::

    from agent_protocol.mcp_sse import build_mcp_sse_app

    app = build_mcp_sse_app(server)

and hand ``app`` to ``uvicorn.Server``.

Per the SDK docstring (``.venv/.../mcp/server/sse.py``) the canonical pattern is:

* Instantiate ``SseServerTransport("/messages/")``.
* Expose a GET ``/sse`` route whose handler enters ``connect_sse(...)`` and
  drives ``server.run(read, write, server.create_initialization_options())``.
* Mount ``sse.handle_post_message`` at ``/messages/`` so the client can POST
  back over the session the SSE stream opened.

The ``handle_sse`` endpoint MUST return a ``Response`` after the SSE context
manager exits, per the SDK's own note; otherwise Starlette raises
``TypeError: 'NoneType' object is not callable`` on client disconnect.
"""

from __future__ import annotations

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.responses import Response
from starlette.routing import Mount, Route


def build_mcp_sse_app(
    mcp_server: Server,
    *,
    sse_path: str = "/sse",
    message_path: str = "/messages/",
) -> Starlette:
    """Wrap an ``mcp.Server`` in a Starlette ASGI app serving MCP over SSE.

    Parameters
    ----------
    mcp_server:
        The ``mcp.server.Server`` whose ``list_tools`` / ``call_tool`` handlers
        have already been registered (e.g. via
        ``services.projects.mcp_server.build_projects_mcp_server``).
    sse_path:
        Path at which the server accepts the long-lived SSE GET. Default
        ``"/sse"`` matches the SDK docstring and the ``mcp.client.sse``
        reference.
    message_path:
        Path at which the server accepts client POSTs over the SSE session.
        Default ``"/messages/"`` (trailing slash matters — this is a Mount).

    Returns
    -------
    Starlette
        An ASGI app ready to be served by ``uvicorn.Server``.
    """

    sse = SseServerTransport(message_path)

    async def handle_sse(request):  # pragma: no cover - exercised via subprocess
        async with sse.connect_sse(
            request.scope, request.receive, request._send
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )
        # Required by the SDK docstring: return a Response after the stream
        # ends to avoid ``TypeError: 'NoneType' object is not callable``.
        return Response()

    return Starlette(
        routes=[
            Route(sse_path, endpoint=handle_sse, methods=["GET"]),
            Mount(message_path, app=sse.handle_post_message),
        ]
    )
