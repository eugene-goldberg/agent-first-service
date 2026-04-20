from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()

_IDLE_TIMEOUT = 0.3  # seconds without a new event before the generator closes


@router.get("/sse/client")
async def stream_client_trace(request: Request):
    bus = request.app.state.trace_bus

    async def event_generator():
        async with bus.subscribe() as queue:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    break
                yield {
                    "event": event.kind,
                    "data": event.model_dump_json(),
                }

    return EventSourceResponse(event_generator())
