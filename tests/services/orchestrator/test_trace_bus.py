import asyncio

import pytest

from services.orchestrator.state import TraceEvent
from services.orchestrator.trace_bus import TraceBus


@pytest.mark.asyncio
async def test_subscriber_receives_published_event():
    bus = TraceBus()

    async def collect(n):
        out = []
        async with bus.subscribe() as queue:
            for _ in range(n):
                out.append(await queue.get())
        return out

    task = asyncio.create_task(collect(2))
    await asyncio.sleep(0)

    await bus.publish(TraceEvent(job_id="j1", kind="thought", summary="thinking"))
    await bus.publish(TraceEvent(job_id="j1", kind="action", summary="GET /"))

    events = await asyncio.wait_for(task, timeout=1.0)
    assert [e.kind for e in events] == ["thought", "action"]


@pytest.mark.asyncio
async def test_multiple_subscribers_each_get_events():
    bus = TraceBus()

    async def collect_one():
        async with bus.subscribe() as queue:
            return await queue.get()

    t1 = asyncio.create_task(collect_one())
    t2 = asyncio.create_task(collect_one())
    await asyncio.sleep(0)

    await bus.publish(TraceEvent(job_id="j", kind="thought", summary="x"))

    e1, e2 = await asyncio.wait_for(asyncio.gather(t1, t2), timeout=1.0)
    assert e1.summary == "x"
    assert e2.summary == "x"


@pytest.mark.asyncio
async def test_unsubscribe_after_context_exit():
    bus = TraceBus()
    async with bus.subscribe() as _:
        assert bus.subscriber_count() == 1
    assert bus.subscriber_count() == 0
