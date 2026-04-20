from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from services.client_agent.state import ClientTraceEvent


class ClientTraceBus:
    """Same shape as the orchestrator's TraceBus but for the client agent's own
    thinking. Kept in its own module so the two services stay independent."""

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[ClientTraceEvent]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: ClientTraceEvent) -> None:
        async with self._lock:
            targets = list(self._subs)
        for q in targets:
            await q.put(event)

    @asynccontextmanager
    async def subscribe(self):
        queue: asyncio.Queue[ClientTraceEvent] = asyncio.Queue()
        async with self._lock:
            self._subs.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subs.discard(queue)

    def subscriber_count(self) -> int:
        return len(self._subs)
