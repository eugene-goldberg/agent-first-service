from __future__ import annotations

import os

import httpx
from fastapi import FastAPI

from agent_protocol.errors import register_error_handler

from services.orchestrator.db import Base, make_engine, make_sessionmaker
from services.orchestrator.llm import LLMClient
from services.orchestrator.routes import capabilities as capabilities_router
from services.orchestrator.routes import orchestrations as orchestrations_router
from services.orchestrator.routes import sse as sse_router
from services.orchestrator.runner import OrchestrationRunner
from services.orchestrator.trace_bus import TraceBus


def create_app(
    *,
    sqlite_path: str | None = None,
    session_maker=None,
    llm: LLMClient | None = None,
    http_client: httpx.AsyncClient | None = None,
    projects_base: str | None = None,
    people_base: str | None = None,
    comms_base: str | None = None,
) -> FastAPI:
    if session_maker is None:
        if sqlite_path is None:
            sqlite_path = "./orchestrator.db"
        engine = make_engine(f"sqlite:///{sqlite_path}")
        Base.metadata.create_all(engine)
        session_maker = make_sessionmaker(engine)

    if llm is None:
        llm = LLMClient.from_env()

    if http_client is None:
        http_client = httpx.AsyncClient(timeout=10.0)

    app = FastAPI(title="Orchestrator Service", version="0.1.0")
    app.state.session_maker = session_maker
    app.state.trace_bus = TraceBus()

    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.runner = OrchestrationRunner(
        session_maker=session_maker,
        llm=llm,
        bus=app.state.trace_bus,
        http_client=http_client,
        projects_base=projects_base or os.environ.get("PROJECTS_BASE_URL", "http://127.0.0.1:8001"),
        people_base=people_base or os.environ.get("PEOPLE_BASE_URL", "http://127.0.0.1:8002"),
        comms_base=comms_base or os.environ.get("COMMUNICATIONS_BASE_URL", "http://127.0.0.1:8003"),
    )

    register_error_handler(app)
    app.include_router(capabilities_router.router)
    app.include_router(orchestrations_router.router)
    app.include_router(sse_router.router)

    return app
