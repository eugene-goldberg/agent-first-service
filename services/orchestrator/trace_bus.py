from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from services.orchestrator.state import TraceEvent


class TraceBus:
    """Async pub/sub fan-out for trace events. One bus per orchestrator process."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[TraceEvent]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: TraceEvent) -> None:
        async with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            await q.put(event)

    @asynccontextmanager
    async def subscribe(self):
        queue: asyncio.Queue[TraceEvent] = asyncio.Queue()
        async with self._lock:
            self._subscribers.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subscribers.discard(queue)

    def subscriber_count(self) -> int:
        return len(self._subscribers)
