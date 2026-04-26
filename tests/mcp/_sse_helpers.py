"""Shared helpers for MCP SSE subprocess tests.

These helpers were originally inlined in ``test_mcp_sse_transport_projects.py``
and extracted in Inc 6 so the People (and later Communications) SSE tests
can reuse them unchanged. Keeping them module-private (underscored filename)
signals these are test-internal utilities rather than a public API.
"""

from __future__ import annotations

import asyncio
import socket


def port_is_free(host: str, port: int) -> bool:
    """Return True iff nothing is currently accepting TCP connections on
    ``host:port``. Used as a pre-flight guard so a leaked server from a
    prior run fails the test fast rather than producing confusing behaviour.
    """

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.connect((host, port))
        except (ConnectionRefusedError, socket.timeout, OSError):
            return True
        return False


async def wait_for_port(host: str, port: int, *, timeout: float = 10.0) -> None:
    """Poll TCP-connect until the SSE server is accepting connections.

    Raises ``TimeoutError`` if the server never becomes ready within
    ``timeout`` seconds.
    """

    deadline = asyncio.get_event_loop().time() + timeout
    last_exc: Exception | None = None
    while asyncio.get_event_loop().time() < deadline:
        try:
            reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # pragma: no cover - best-effort close
                pass
            return
        except (ConnectionRefusedError, OSError) as exc:
            last_exc = exc
            await asyncio.sleep(0.1)
    raise TimeoutError(
        f"MCP SSE server at {host}:{port} did not become ready within "
        f"{timeout}s (last error: {last_exc!r})"
    )
