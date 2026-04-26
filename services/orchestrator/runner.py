from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, Literal, TYPE_CHECKING

import httpx

from services.orchestrator.db import JobRow, TraceEventRow
from services.orchestrator.graph import OrchestrationGraph
from services.orchestrator.llm import LLMClient
from services.orchestrator.state import OrchestrationState, TraceEvent
from services.orchestrator.tools import HTTPToolbox
from services.orchestrator.trace_bus import TraceBus

if TYPE_CHECKING:
    from services.orchestrator.mcp_tools import MCPToolbox


class OrchestrationRunner:
    def __init__(
        self,
        *,
        session_maker,
        llm: LLMClient,
        bus: TraceBus,
        http_client: httpx.AsyncClient,
        projects_base: str,
        people_base: str,
        comms_base: str,
        mode: Literal["http", "mcp"] = "http",
        mcp_toolbox: "MCPToolbox | None" = None,
    ) -> None:
        self._session_maker = session_maker
        self._llm = llm
        self._bus = bus
        self._http_client = http_client
        self._projects_base = projects_base
        self._people_base = people_base
        self._comms_base = comms_base
        self._mode = mode
        self._mcp_toolbox = mcp_toolbox
        self._ready = False
        self._ready_lock = asyncio.Lock()

    async def ensure_ready(self) -> None:
        """Fail fast if required MCP backends are unreachable."""
        if self._ready:
            return
        async with self._ready_lock:
            if self._ready:
                return
            if self._mode != "mcp" or self._mcp_toolbox is None:
                raise RuntimeError("Orchestrator is configured without MCP toolbox.")
            for server in ("projects", "people", "communications"):
                tools = await self._mcp_toolbox.list_tools(server)
                if not tools:
                    raise RuntimeError(
                        f"MCP server {server!r} is reachable but advertises no tools."
                    )
            self._ready = True

    def start(self, brief: str) -> str:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        with self._session_maker() as session:
            session.add(JobRow(id=job_id, brief=brief, status="running"))
            session.commit()

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._run(job_id=job_id, brief=brief))
        except RuntimeError:
            # No running event loop (e.g. sync test context); run in background thread.
            import threading
            threading.Thread(
                target=asyncio.run,
                args=(self._run(job_id=job_id, brief=brief),),
                daemon=True,
            ).start()
        return job_id

    async def _run(self, *, job_id: str, brief: str) -> None:
        toolbox = HTTPToolbox(client=self._http_client)
        graph = OrchestrationGraph(
            llm=self._llm,
            toolbox=toolbox,
            bus=self._bus,
            projects_base=self._projects_base,
            people_base=self._people_base,
            comms_base=self._comms_base,
            mode=self._mode,
            mcp_toolbox=self._mcp_toolbox,
        )
        state = OrchestrationState(job_id=job_id, brief=brief)

        async def persist(event: TraceEvent) -> None:
            with self._session_maker() as session:
                session.add(TraceEventRow(
                    id=f"ev_{uuid.uuid4().hex[:10]}",
                    job_id=event.job_id,
                    kind=event.kind,
                    summary=event.summary,
                    detail_json=json.dumps(event.detail, default=str),
                    at=event.at,
                ))
                session.commit()

        try:
            await graph.run(state, persist_event=persist)
            final_status = "completed"
        except Exception as exc:
            await self._bus.publish(TraceEvent(
                job_id=job_id, kind="error",
                summary=f"Orchestration crashed: {exc!r}",
                detail={"exception": str(exc)},
            ))
            final_status = "failed"

        with self._session_maker() as session:
            row = session.get(JobRow, job_id)
            if row is not None:
                row.status = final_status
                row.final_summary = state.final_summary
                session.commit()
