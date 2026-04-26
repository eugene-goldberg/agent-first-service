"""MCP-client toolbox for the orchestrator (Inc 8 of the MCP wrapping plan).

``MCPToolbox`` mirrors ``HTTPToolbox``'s role: it is the thin, generic
"transport" surface the orchestrator graph hands to the LLM in MCP mode.
Instead of four HTTP verbs, MCP mode exposes ``list_tools(server)`` and
``call_tool(server, tool, arguments)`` where ``server`` selects one of the
three leaf-service MCP SSE endpoints configured at construction time.

Lifecycle model: a *fresh SSE session per call*. No persistent sessions are
cached keyed by server name — this mirrors how ``HTTPToolbox`` uses
``httpx.AsyncClient`` per request and keeps teardown trivial. If Inc 10
surfaces latency issues we can revisit, but per the plan the simpler
lifecycle wins by default.

Error taxonomy (critical — do not collapse these two cases):
  * **Protocol success** — ``{"status": "ok", "content": <envelope>}``.
    Includes leaf-service 422 error envelopes (``_why`` / ``_try_instead``)
    because those reached us as a successfully-decoded MCP tools/call
    response. Unwrapping ``_why`` / ``_try_instead`` belongs to the
    orchestrator graph in Inc 9, not here.
  * **Transport / SDK error** — ``{"status": "error", "message": "..."}``.
    Only for exceptions raised during connection, session initialisation,
    or the tools/call round-trip itself.

Unknown server names raise ``KeyError`` (fail fast — this is an orchestrator
wiring bug, not a runtime transport blip).
"""

from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client


class MCPToolbox:
    """MCP-client counterpart to ``HTTPToolbox``.

    ``server_urls`` maps a logical server name (``"projects"`` / ``"people"``
    / ``"communications"``) to its SSE *base* URL (e.g.
    ``"http://localhost:9002"``). The ``/sse`` suffix is appended internally.
    """

    def __init__(self, server_urls: dict[str, str]) -> None:
        self._server_urls = dict(server_urls)

    def _resolve(self, server: str) -> str:
        if server not in self._server_urls:
            raise KeyError(
                f"unknown MCP server {server!r}; configured servers: "
                f"{sorted(self._server_urls)}"
            )
        base = self._server_urls[server].rstrip("/")
        return f"{base}/sse"

    async def list_tools(self, server: str) -> list[dict[str, Any]]:
        """Return ``[{name, description, inputSchema}, ...]`` for ``server``.

        Raises ``KeyError`` if ``server`` is not configured. Transport /
        SDK errors propagate — ``list_tools`` is a diagnostic / planner
        helper, not a per-step call path, so surfacing them is more useful
        than wrapping them.
        """

        sse_url = self._resolve(server)
        async with sse_client(sse_url) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                return [
                    {
                        "name": t.name,
                        "description": t.description,
                        "inputSchema": t.inputSchema,
                    }
                    for t in result.tools
                ]

    async def call_tool(
        self, server: str, tool: str, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        """Call ``tool`` on ``server`` with ``arguments`` and return a
        status envelope.

        Returns:
          * ``{"status": "ok", "content": <parsed envelope dict>}`` on any
            successful MCP tools/call round-trip — INCLUDING leaf-service
            422 error envelopes.
          * ``{"status": "error", "message": "..."}`` on transport / SDK
            exceptions.

        Raises ``KeyError`` if ``server`` is not configured (fail fast).
        """

        sse_url = self._resolve(server)
        try:
            async with sse_client(sse_url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool, arguments)

                    # Expect a single TextContent block whose text is the
                    # JSON-serialised envelope (either success envelope or
                    # leaf-service error envelope with _why / _try_instead).
                    if not result.content:
                        return {
                            "status": "error",
                            "message": (
                                f"MCP tools/call returned empty content for "
                                f"{server!r}/{tool!r}"
                            ),
                        }
                    block = result.content[0]
                    text = getattr(block, "text", None)
                    if text is None:
                        return {
                            "status": "error",
                            "message": (
                                f"MCP tools/call returned non-text content "
                                f"for {server!r}/{tool!r}: "
                                f"{type(block).__name__}"
                            ),
                        }
                    envelope = json.loads(text)
                    return {"status": "ok", "content": envelope}
        except KeyError:
            raise
        except Exception as exc:  # transport / SDK / JSON decode errors
            return {"status": "error", "message": str(exc)}
