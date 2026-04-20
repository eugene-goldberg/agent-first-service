from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import httpx

from services.orchestrator.db import JobRow, TraceEventRow
from services.orchestrator.graph import OrchestrationGraph
from services.orchestrator.llm import LLMClient
from services.orchestrator.state import OrchestrationState, TraceEvent
from services.orchestrator.tools import HTTPToolbox
from services.orchestrator.trace_bus import TraceBus


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
    ) -> None:
        self._session_maker = session_maker
        self._llm = llm
        self._bus = bus
        self._http_client = http_client
        self._projects_base = projects_base
        self._people_base = people_base
        self._comms_base = comms_base

    def start(self, brief: str) -> str:
        job_id = f"job_{uuid.uuid4().hex[:8]}"
        with self._session_maker() as session:
            session.add(JobRow(id=job_id, brief=brief, status="running"))
            session.commit()

        asyncio.create_task(self._run(job_id=job_id, brief=brief))
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
