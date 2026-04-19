from __future__ import annotations

from fastapi import FastAPI

from agent_protocol.errors import register_error_handler

from services.people.db import Base, make_engine, make_sessionmaker
from services.people.routes import capabilities as capabilities_router
from services.people.routes import people as people_router


def create_app(*, sqlite_path: str | None = None, session_maker=None) -> FastAPI:
    if session_maker is None:
        if sqlite_path is None:
            sqlite_path = "./people.db"
        engine = make_engine(f"sqlite:///{sqlite_path}")
        Base.metadata.create_all(engine)
        session_maker = make_sessionmaker(engine)

    app = FastAPI(title="People Service", version="0.1.0")
    app.state.session_maker = session_maker

    register_error_handler(app)
    app.include_router(capabilities_router.router)
    app.include_router(people_router.router)

    return app
