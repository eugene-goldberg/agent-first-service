from __future__ import annotations

import pathlib

from fastapi import FastAPI

from agent_protocol.errors import register_error_handler
from services.projects.db import Base, make_engine, make_sessionmaker
from services.projects.routes import capabilities as capabilities_routes


def create_app(*, sqlite_path: pathlib.Path | str) -> FastAPI:
    engine = make_engine(sqlite_path)
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)

    app = FastAPI(title="Projects")
    app.state.session_maker = session_maker

    register_error_handler(app)
    app.include_router(capabilities_routes.router)

    return app
