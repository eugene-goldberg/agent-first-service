"""MCP server entrypoint for the Communications service (stdio + SSE).

Run in stdio mode (default — Claude Desktop, local subprocess drivers)::

    python -m services.communications.mcp_main --sqlite-path /path/to/communications.db

Run in SSE mode (orchestrator integration, long-running network transport)::

    python -m services.communications.mcp_main --sse --port 9003 \
        --sqlite-path /path/to/communications.db

Stdio transport notes
---------------------
The stdio process speaks MCP JSON-RPC over stdio: it reads framed JSON-RPC
messages from stdin and writes responses to stdout. Anything else written
to stdout would corrupt the framing, so before the stdio transport starts
we capture the real stdout and then redirect ``sys.stdout`` to ``sys.stderr``
so that any accidental ``print(...)`` from application startup code
(FastAPI/Starlette banners, SQLAlchemy informational output, etc.) lands
on stderr instead of corrupting the JSON-RPC framing.

The captured real stdout is handed to ``mcp.server.stdio.stdio_server`` via
its ``stdout=`` parameter so the MCP transport still writes JSON-RPC frames
to the actual process stdout.

SSE transport notes
-------------------
In SSE mode the MCP protocol travels over an HTTP response body, not stdout,
so the stdio defensive redirect is NOT applied. We build a Starlette ASGI
app via ``agent_protocol.mcp_sse.build_mcp_sse_app`` and serve it with
``uvicorn.Server`` on ``--host`` / ``--port``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from io import TextIOWrapper
from pathlib import Path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Communications MCP server (stdio by default, --sse for HTTP/SSE)"
    )
    parser.add_argument(
        "--sqlite-path",
        type=Path,
        default=Path("communications.db"),
        help="Path to the SQLite database backing the Communications service.",
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Serve MCP over HTTP/SSE instead of stdio.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9003,
        help="Port to bind when running in --sse mode (default: 9003).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host interface to bind when running in --sse mode "
        "(default: 127.0.0.1).",
    )
    return parser.parse_args(argv)


async def _run_stdio(sqlite_path: Path) -> None:
    # Import lazily so argparse / --help runs cheaply.
    import anyio
    from mcp.server.stdio import stdio_server

    from services.communications.mcp_server import build_communications_mcp_server

    # Capture the real stdout (as a UTF-8 text stream) BEFORE redirecting
    # ``sys.stdout`` — this handle is what MCP will use to emit JSON-RPC
    # frames.
    real_stdout = anyio.wrap_file(
        TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    )
    # Now redirect application-level stdout to stderr so that any stray
    # print(...) from startup code does not corrupt MCP framing.
    sys.stdout = sys.stderr

    server, _adapter = build_communications_mcp_server(sqlite_path=sqlite_path)
    async with stdio_server(stdout=real_stdout) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def _run_sse(sqlite_path: Path, host: str, port: int) -> None:
    # Import lazily so argparse / --help / stdio paths do not pay the cost.
    import uvicorn

    from agent_protocol.mcp_sse import build_mcp_sse_app
    from services.communications.mcp_server import build_communications_mcp_server

    server, _adapter = build_communications_mcp_server(sqlite_path=sqlite_path)
    app = build_mcp_sse_app(server)
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    await uvicorn.Server(config).serve()


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.sse:
        asyncio.run(_run_sse(args.sqlite_path, args.host, args.port))
    else:
        asyncio.run(_run_stdio(args.sqlite_path))


if __name__ == "__main__":
    main()
