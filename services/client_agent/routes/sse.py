from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

router = APIRouter()

_IDLE_TIMEOUT = 0.3  # poll interval; on timeout we yield a heartbeat, not close


@router.get("/sse/client")
async def stream_client_trace(request: Request):
    bus = request.app.state.trace_bus

    async def event_generator():
        async with bus.subscribe() as queue:
            # Prime the stream immediately for in-process test transports.
            yield b": stream-open\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    # Keep the connection active during idle windows.
                    yield b": keepalive\n\n"
                    continue
                payload = (
                    f"event: {event.kind}\n"
                    f"data: {event.model_dump_json()}\n\n"
                ).encode("utf-8")
                yield payload

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
