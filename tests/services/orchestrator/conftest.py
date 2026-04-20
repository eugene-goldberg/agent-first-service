"""Shared fixtures for orchestrator tests.

Spins up the three leaf service ASGI apps and runs them in the same process as
the orchestrator, using a custom httpx AsyncClient transport so the orchestrator
can hit them by URL without binding a real network port.
"""

from __future__ import annotations

import pytest
import httpx

from services.communications.app import create_app as create_communications_app
from services.communications.db import (
    Base as CommsBase,
    make_engine as make_comms_engine,
    make_sessionmaker as make_comms_sm,
)
from services.people.app import create_app as create_people_app
from services.people.db import Base as PeopleBase, make_engine as make_people_engine, make_sessionmaker as make_people_sm
from services.projects.app import create_app as create_projects_app


@pytest.fixture
def leaf_apps(tmp_path):
    # Projects — create_app manages its own engine/session from sqlite_path
    projects_db_path = f"{tmp_path}/projects.db"
    projects_app = create_projects_app(sqlite_path=projects_db_path)

    # People — pre-seed Dan for the fixture scenario
    pe_engine = make_people_engine(f"sqlite:///{tmp_path}/people.db")
    PeopleBase.metadata.create_all(pe_engine)
    pe_sm = make_people_sm(pe_engine)
    import json as _json
    from services.people.db import PersonRow
    with pe_sm() as session:
        session.add(PersonRow(
            id="person_dan", name="Dan Park", role="marketing lead",
            skills_json=_json.dumps(["copywriting", "launches"]),
            available=True, current_load=1,
        ))
        session.commit()
    people_app = create_people_app(session_maker=pe_sm)

    # Communications
    c_engine = make_comms_engine(f"sqlite:///{tmp_path}/comms.db")
    CommsBase.metadata.create_all(c_engine)
    comms_app = create_communications_app(session_maker=make_comms_sm(c_engine))

    return {
        "projects_app": projects_app,
        "people_app": people_app,
        "comms_app": comms_app,
    }


@pytest.fixture
async def leaf_http_client(leaf_apps):
    """A single httpx AsyncClient that routes by host:port to the right ASGI app."""

    transports_by_host = {
        "127.0.0.1:8001": httpx.ASGITransport(app=leaf_apps["projects_app"]),
        "127.0.0.1:8002": httpx.ASGITransport(app=leaf_apps["people_app"]),
        "127.0.0.1:8003": httpx.ASGITransport(app=leaf_apps["comms_app"]),
    }

    class RoutingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            host = request.url.host
            port = request.url.port
            key = f"{host}:{port}"
            transport = transports_by_host.get(key)
            if transport is None:
                raise RuntimeError(f"No leaf app registered for {key}")
            return await transport.handle_async_request(request)

    async with httpx.AsyncClient(transport=RoutingTransport()) as client:
        yield client
