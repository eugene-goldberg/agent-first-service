from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

_IDLE_TIMEOUT = 0.3  # poll interval; on timeout we yield a heartbeat, not close


@router.get("/sse/client")
async def stream_client_trace(request: Request):
    bus = request.app.state.trace_bus

    async def event_generator():
        async with bus.subscribe() as queue:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    continue
                yield {
                    "event": event.kind,
                    "data": event.model_dump_json(),
                }

    return EventSourceResponse(event_generator(), ping=15)
