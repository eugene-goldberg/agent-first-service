from __future__ import annotations

import os

import httpx
from fastapi import FastAPI

from agent_protocol.errors import register_error_handler

from services.client_agent.llm import ClientLLMClient
from services.client_agent.routes import capabilities as capabilities_router
from services.client_agent.routes import briefs as briefs_router
from services.client_agent.routes import sse as sse_router
from services.client_agent.trace_bus import ClientTraceBus


def create_app(
    *,
    llm: ClientLLMClient | None = None,
    http_client: httpx.AsyncClient | None = None,
    orchestrator_base: str | None = None,
) -> FastAPI:
    if llm is None:
        llm = ClientLLMClient.from_env()
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=10.0)

    app = FastAPI(title="Client Agent", version="0.1.0")
    app.state.llm = llm
    app.state.http_client = http_client
    app.state.trace_bus = ClientTraceBus()
    app.state.briefs = {}  # brief_id → ClientBriefState (in-memory; no DB on the client agent)
    app.state.orchestrator_base = orchestrator_base or os.environ.get(
        "ORCHESTRATOR_BASE_URL", "http://127.0.0.1:8000"
    )

    @app.middleware("http")
    async def cors_headers(request, call_next):
        response = await call_next(request)
        response.headers["access-control-allow-origin"] = "*"
        response.headers["access-control-allow-methods"] = "GET, POST, PATCH, OPTIONS"
        response.headers["access-control-allow-headers"] = "*"
        return response

    register_error_handler(app)
    app.include_router(capabilities_router.router)
    app.include_router(briefs_router.router)
    app.include_router(sse_router.router)

    return app
