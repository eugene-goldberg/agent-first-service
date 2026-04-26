from __future__ import annotations

import os
import pathlib

from fastapi import FastAPI

from agent_protocol.errors import register_error_handler
from services.projects.db import (
    Base,
    ensure_backward_compatible_schema,
    make_engine,
    make_sessionmaker,
)
from services.projects.routes import (
    capabilities as capabilities_routes,
    milestones as milestones_routes,
    projects as projects_routes,
    tasks as tasks_routes,
)


def create_app(*, sqlite_path: pathlib.Path | str) -> FastAPI:
    engine = make_engine(sqlite_path)
    Base.metadata.create_all(engine)
    ensure_backward_compatible_schema(engine)
    session_maker = make_sessionmaker(engine)

    app = FastAPI(title="Projects")
    app.state.session_maker = session_maker
    app.state.people_base_url = os.environ.get(
        "PROJECTS_PEOPLE_BASE_URL", "http://127.0.0.1:8002"
    )

    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handler(app)
    app.include_router(capabilities_routes.router)
    app.include_router(projects_routes.router)
    app.include_router(milestones_routes.router)
    app.include_router(tasks_routes.router)

    return app
