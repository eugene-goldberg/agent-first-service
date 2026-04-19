# Leaf Services Implementation Plan — People & Communications

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build two additional leaf services that reuse the `agent_protocol/` library from Plan 1: a People service (port 8002) managing team members with skills and availability, and a Communications service (port 8003) managing notifications and status updates. Both services expose the hypermedia agent protocol identically to the Projects service.

**Architecture:** Each service is an independent FastAPI process with its own SQLite database. Both reuse `agent_protocol/` (envelope, errors, catalog, field_docs) and follow the same layout established by the Projects service: `services/<name>/{app,db,models,main,seed}.py` and `services/<name>/routes/*.py`. Services are stateless beyond their own SQLite file; they do NOT call each other — cross-service coordination is the Orchestrator's job (Plan 3).

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite (stdlib), pytest, pytest-asyncio, httpx.

**Spec:** `docs/superpowers/specs/2026-04-19-agent-first-services-design.md`

**Prerequisite:** Plan 1 (`2026-04-19-foundation-and-projects-service.md`) must be complete. This plan assumes `agent_protocol/` exists and works, and that the `services/` and `tests/services/` package structure is in place.

---

## File structure for this plan

New files created by this plan (grouped):

**People service:**
- `services/people/__init__.py`
- `services/people/main.py`
- `services/people/app.py`
- `services/people/db.py`
- `services/people/models.py`
- `services/people/seed.py`
- `services/people/routes/__init__.py`
- `services/people/routes/capabilities.py`
- `services/people/routes/people.py`

**Communications service:**
- `services/communications/__init__.py`
- `services/communications/main.py`
- `services/communications/app.py`
- `services/communications/db.py`
- `services/communications/models.py`
- `services/communications/seed.py`
- `services/communications/routes/__init__.py`
- `services/communications/routes/capabilities.py`
- `services/communications/routes/messages.py`

**Fixtures:**
- `fixtures/demo-seed/people.json`
- `fixtures/demo-seed/communications.json`

**Tests:**
- `tests/services/people/__init__.py`
- `tests/services/people/conftest.py`
- `tests/services/people/test_capabilities.py`
- `tests/services/people/test_people_crud.py`
- `tests/services/people/test_people_filters.py`
- `tests/services/people/test_seed.py`
- `tests/services/people/test_constraint_errors.py`
- `tests/services/communications/__init__.py`
- `tests/services/communications/conftest.py`
- `tests/services/communications/test_capabilities.py`
- `tests/services/communications/test_messages_crud.py`
- `tests/services/communications/test_messages_filters.py`
- `tests/services/communications/test_seed.py`
- `tests/services/communications/test_constraint_errors.py`

**Modified files:**
- `Makefile` (add `run-people`, `run-communications`, `test-people`, `test-communications` targets)
- `.env.example` (add `PEOPLE_SEED`, `COMMUNICATIONS_SEED`)
- `docs/test_inventory.md` (append entries)
- `docs/implementation_status.md` (append increment completion)

---

## Task 1: People service — DB layer

**Files:**
- Create: `services/people/__init__.py` (empty)
- Create: `services/people/db.py`
- Create: `tests/services/people/__init__.py` (empty)
- Create: `tests/services/people/conftest.py`
- Create: `tests/services/people/test_people_db.py`

- [ ] **Step 1: Write failing test for DB schema**

Create `tests/services/people/test_people_db.py`:

```python
import json

from sqlalchemy import select

from services.people.db import Base, PersonRow, make_engine, make_sessionmaker


def test_create_person_row(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/people.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    with SessionMaker() as session:
        session.add(
            PersonRow(
                id="person_alice",
                name="Alice Chen",
                role="senior engineer",
                skills_json=json.dumps(["python", "langgraph"]),
                available=True,
                current_load=2,
            )
        )
        session.commit()

    with SessionMaker() as session:
        row = session.execute(
            select(PersonRow).where(PersonRow.id == "person_alice")
        ).scalar_one()
        assert row.name == "Alice Chen"
        assert json.loads(row.skills_json) == ["python", "langgraph"]
        assert row.available is True
        assert row.current_load == 2
```

- [ ] **Step 2: Write conftest for the people test package**

Create `tests/services/people/conftest.py`:

```python
import pytest

from services.people.app import create_app
from services.people.db import Base, make_engine, make_sessionmaker


@pytest.fixture
def people_app(tmp_path):
    db_path = tmp_path / "people.db"
    engine = make_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)
    app = create_app(session_maker=session_maker)
    return app


@pytest.fixture
def people_client(people_app):
    from fastapi.testclient import TestClient

    return TestClient(people_app)
```

(The conftest references `create_app` and `db` which we build in the next steps; the test above does not need them yet.)

- [ ] **Step 3: Run the DB test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/people/test_people_db.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.people.db'`

- [ ] **Step 4: Implement `services/people/db.py`**

Create `services/people/db.py`:

```python
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class PersonRow(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    skills_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def make_engine(url: str):
    return create_engine(url, future=True)


def make_sessionmaker(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
```

- [ ] **Step 5: Run the DB test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/people/test_people_db.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add services/people/__init__.py services/people/db.py tests/services/people/__init__.py tests/services/people/conftest.py tests/services/people/test_people_db.py
git commit -m "feat(people): add SQLAlchemy schema for people service"
```

---

## Task 2: People service — Pydantic models

**Files:**
- Create: `services/people/models.py`
- Create: `tests/services/people/test_models.py`

- [ ] **Step 1: Write failing test for models**

Create `tests/services/people/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from services.people.models import CreatePerson, PersonOut


def test_create_person_accepts_valid_payload():
    payload = CreatePerson(
        name="Alice Chen",
        role="senior engineer",
        skills=["python", "langgraph"],
    )
    assert payload.name == "Alice Chen"
    assert payload.skills == ["python", "langgraph"]


def test_create_person_rejects_empty_name():
    with pytest.raises(ValidationError):
        CreatePerson(name="", role="engineer", skills=[])


def test_person_out_defaults():
    out = PersonOut(
        id="person_alice",
        name="Alice Chen",
        role="engineer",
        skills=["python"],
        available=True,
        current_load=0,
    )
    dumped = out.model_dump()
    assert dumped["available"] is True
    assert dumped["current_load"] == 0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/people/test_models.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.people.models'`

- [ ] **Step 3: Implement `services/people/models.py`**

Create `services/people/models.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agent_protocol.field_docs import DocumentedField


class CreatePerson(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = DocumentedField(
        description="Full name of the team member.",
        examples=["Alice Chen", "Bob Patel"],
        min_length=1,
    )
    role: str = DocumentedField(
        description="Job role or title, used for natural-language routing.",
        examples=["senior engineer", "product manager", "designer"],
        min_length=1,
    )
    skills: list[str] = DocumentedField(
        description="Free-form skill tags used to match people to project work.",
        examples=[["python", "langgraph"], ["figma", "accessibility"]],
        default_factory=list,
    )


class UpdatePerson(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool | None = DocumentedField(
        description="Whether the person can take on new work right now.",
        examples=[True, False],
        default=None,
    )
    current_load: int | None = DocumentedField(
        description="Current number of active assignments (>=0).",
        examples=[0, 3],
        default=None,
        ge=0,
    )
    skills: list[str] | None = DocumentedField(
        description="Full replacement list of skill tags.",
        examples=[["python", "fastapi"]],
        default=None,
    )


class PersonOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Stable person identifier.")
    name: str
    role: str
    skills: list[str]
    available: bool
    current_load: int
```

- [ ] **Step 4: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/people/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/people/models.py tests/services/people/test_models.py
git commit -m "feat(people): add Pydantic models (CreatePerson/UpdatePerson/PersonOut)"
```

---

## Task 3: People service — App factory and capabilities

**Files:**
- Create: `services/people/app.py`
- Create: `services/people/main.py`
- Create: `services/people/routes/__init__.py` (empty)
- Create: `services/people/routes/capabilities.py`
- Create: `tests/services/people/test_capabilities.py`

- [ ] **Step 1: Write failing test for capabilities endpoint**

Create `tests/services/people/test_capabilities.py`:

```python
def test_root_lists_all_capabilities(people_client):
    resp = people_client.get("/")
    assert resp.status_code == 200
    body = resp.json()

    assert body["data"]["service"] == "people"
    capability_ids = {c["id"] for c in body["data"]["capabilities"]}
    assert capability_ids == {
        "list_people",
        "find_person",
        "create_person",
        "update_person",
        "filter_by_skill",
        "filter_by_availability",
    }
    assert body["_self"] == "http://testserver/"
    assert isinstance(body["_related"], list)
    assert "_generated_at" in body
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/people/test_capabilities.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.people.app'`

- [ ] **Step 3: Implement `services/people/routes/capabilities.py`**

Create `services/people/routes/capabilities.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from agent_protocol.catalog import Capability, build_catalog
from agent_protocol.envelope import make_response

router = APIRouter()


PEOPLE_CAPABILITIES: list[Capability] = [
    Capability(
        id="list_people",
        verb="GET",
        path="/people",
        summary="List every team member.",
        hints=["Use filters (skill, available) to narrow the list."],
    ),
    Capability(
        id="find_person",
        verb="GET",
        path="/people/{person_id}",
        summary="Fetch a single person by id.",
        hints=["Returns 404 with `_try_instead` pointing to `GET /people`."],
    ),
    Capability(
        id="create_person",
        verb="POST",
        path="/people",
        summary="Add a new team member.",
        hints=["Body fields: name, role, skills."],
    ),
    Capability(
        id="update_person",
        verb="PATCH",
        path="/people/{person_id}",
        summary="Update availability, current_load, or skills.",
        hints=["Partial updates — send only fields you want to change."],
    ),
    Capability(
        id="filter_by_skill",
        verb="GET",
        path="/people?skill={skill}",
        summary="List people whose skills include a given tag.",
        hints=["Case-insensitive match against the skills array."],
    ),
    Capability(
        id="filter_by_availability",
        verb="GET",
        path="/people?available=true",
        summary="List only people marked as available.",
        hints=["Combine with `skill` to find a free specialist."],
    ),
]


@router.get("/")
def root(request: Request):
    return make_response(
        data=build_catalog(
            service_name="people",
            description="Team members, roles, skills, availability, and current load.",
            capabilities=PEOPLE_CAPABILITIES,
        ),
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "list_people", "href": "/people", "verb": "GET"},
        ],
    )
```

- [ ] **Step 4: Implement `services/people/app.py`**

Create `services/people/app.py`:

```python
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
```

Note: `people_router` does not yet exist; the app will fail to import until Task 4. That's fine — the capabilities test imports `create_app`, so we need a stub router now.

- [ ] **Step 5: Create a stub `services/people/routes/people.py`**

Create `services/people/routes/people.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

# Handlers implemented in Task 4.
```

- [ ] **Step 6: Implement `services/people/main.py`**

Create `services/people/main.py`:

```python
from __future__ import annotations

import argparse
import os

import uvicorn

from services.people.app import create_app
from services.people.db import Base, make_engine, make_sessionmaker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--sqlite", default=os.environ.get("PEOPLE_SQLITE", "./people.db"))
    parser.add_argument("--seed-from", default=os.environ.get("PEOPLE_SEED"))
    args = parser.parse_args()

    engine = make_engine(f"sqlite:///{args.sqlite}")
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)

    if args.seed_from:
        from services.people.seed import load_seed

        load_seed(session_maker, args.seed_from)

    app = create_app(session_maker=session_maker)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/people/test_capabilities.py -v`
Expected: 1 passed

- [ ] **Step 8: Commit**

```bash
git add services/people/app.py services/people/main.py services/people/routes/__init__.py services/people/routes/capabilities.py services/people/routes/people.py tests/services/people/test_capabilities.py
git commit -m "feat(people): add app factory, capabilities endpoint, main entry point"
```

---

## Task 4: People service — CRUD routes

**Files:**
- Modify: `services/people/routes/people.py`
- Create: `tests/services/people/test_people_crud.py`

- [ ] **Step 1: Write failing test for CRUD flow**

Create `tests/services/people/test_people_crud.py`:

```python
def test_create_get_patch_person(people_client):
    create_resp = people_client.post(
        "/people",
        json={"name": "Alice Chen", "role": "senior engineer", "skills": ["python", "langgraph"]},
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["data"]["name"] == "Alice Chen"
    assert created["data"]["available"] is True
    assert created["data"]["current_load"] == 0
    person_id = created["data"]["id"]
    assert created["_self"].endswith(f"/people/{person_id}")
    assert any(s["rel"] == "update_person" for s in created["_suggested_next"])

    get_resp = people_client.get(f"/people/{person_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == person_id

    patch_resp = people_client.patch(
        f"/people/{person_id}",
        json={"available": False, "current_load": 3},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["data"]["available"] is False
    assert patch_resp.json()["data"]["current_load"] == 3


def test_list_people_returns_envelope(people_client):
    people_client.post("/people", json={"name": "A", "role": "r", "skills": []})
    people_client.post("/people", json={"name": "B", "role": "r", "skills": []})

    list_resp = people_client.get("/people")
    assert list_resp.status_code == 200
    body = list_resp.json()
    assert len(body["data"]) == 2
    assert body["_self"] == "http://testserver/people"
    assert isinstance(body["_related"], list)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/people/test_people_crud.py -v`
Expected: FAIL — `405 Method Not Allowed` (stub router has no handlers).

- [ ] **Step 3: Implement the full `services/people/routes/people.py`**

Replace `services/people/routes/people.py`:

```python
from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from agent_protocol.envelope import make_response
from agent_protocol.errors import AgentError

from services.people.db import PersonRow
from services.people.models import CreatePerson, PersonOut, UpdatePerson

router = APIRouter()


def _row_to_out(row: PersonRow) -> PersonOut:
    return PersonOut(
        id=row.id,
        name=row.name,
        role=row.role,
        skills=json.loads(row.skills_json),
        available=row.available,
        current_load=row.current_load,
    )


def _person_suggested_next(person_id: str) -> list[dict]:
    return [
        {"rel": "update_person", "href": f"/people/{person_id}", "verb": "PATCH",
         "example_body": {"available": False, "current_load": 3}},
        {"rel": "list_people", "href": "/people", "verb": "GET"},
    ]


@router.post("/people", status_code=201)
def create_person(payload: CreatePerson, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        person_id = f"person_{uuid.uuid4().hex[:8]}"
        row = PersonRow(
            id=person_id,
            name=payload.name,
            role=payload.role,
            skills_json=json.dumps(payload.skills),
            available=True,
            current_load=0,
        )
        session.add(row)
        session.commit()
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(),
        self_link=str(request.url_for("get_person", person_id=person_id)),
        related=[{"rel": "list_people", "href": "/people", "verb": "GET"}],
        suggested_next=_person_suggested_next(person_id),
    )


@router.get("/people/{person_id}", name="get_person")
def get_person(person_id: str, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        row = session.get(PersonRow, person_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="person_not_found",
                message=f"No person with id={person_id!r}.",
                why="The id does not match any stored person.",
                try_instead={
                    "rel": "list_people",
                    "href": "/people",
                    "verb": "GET",
                    "hint": "List all people and pick an id from the result.",
                },
                related=[{"rel": "list_people", "href": "/people", "verb": "GET"}],
            )
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(),
        self_link=str(request.url),
        related=[{"rel": "list_people", "href": "/people", "verb": "GET"}],
        suggested_next=_person_suggested_next(person_id),
    )


@router.patch("/people/{person_id}")
def update_person(person_id: str, payload: UpdatePerson, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        row = session.get(PersonRow, person_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="person_not_found",
                message=f"No person with id={person_id!r}.",
                why="The id does not match any stored person.",
                try_instead={
                    "rel": "list_people",
                    "href": "/people",
                    "verb": "GET",
                    "hint": "List all people first.",
                },
                related=[{"rel": "list_people", "href": "/people", "verb": "GET"}],
            )
        if payload.available is not None:
            row.available = payload.available
        if payload.current_load is not None:
            row.current_load = payload.current_load
        if payload.skills is not None:
            row.skills_json = json.dumps(payload.skills)
        session.commit()
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(),
        self_link=str(request.url_for("get_person", person_id=person_id)),
        related=[{"rel": "list_people", "href": "/people", "verb": "GET"}],
        suggested_next=_person_suggested_next(person_id),
    )


@router.get("/people")
def list_people(
    request: Request,
    skill: str | None = Query(default=None),
    available: bool | None = Query(default=None),
):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        stmt = select(PersonRow)
        if available is not None:
            stmt = stmt.where(PersonRow.available == available)
        rows = session.execute(stmt).scalars().all()

    results = [_row_to_out(r) for r in rows]

    if skill is not None:
        needle = skill.lower()
        results = [p for p in results if any(s.lower() == needle for s in p.skills)]

    return make_response(
        data=[p.model_dump() for p in results],
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "find_person", "href": "/people/{person_id}", "verb": "GET"},
        ],
    )
```

- [ ] **Step 4: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/people/test_people_crud.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add services/people/routes/people.py tests/services/people/test_people_crud.py
git commit -m "feat(people): add CRUD routes with hypermedia envelope and suggested_next"
```

---

## Task 5: People service — filter tests and constraint errors

**Files:**
- Create: `tests/services/people/test_people_filters.py`
- Create: `tests/services/people/test_constraint_errors.py`

- [ ] **Step 1: Write filter test**

Create `tests/services/people/test_people_filters.py`:

```python
def test_filter_by_skill_case_insensitive(people_client):
    people_client.post("/people", json={"name": "Alice", "role": "eng", "skills": ["Python", "LangGraph"]})
    people_client.post("/people", json={"name": "Bob", "role": "pm", "skills": ["figma"]})

    resp = people_client.get("/people?skill=python")
    assert resp.status_code == 200
    names = {p["name"] for p in resp.json()["data"]}
    assert names == {"Alice"}


def test_filter_by_availability(people_client):
    r1 = people_client.post("/people", json={"name": "A", "role": "r", "skills": []})
    r2 = people_client.post("/people", json={"name": "B", "role": "r", "skills": []})
    id_a = r1.json()["data"]["id"]

    people_client.patch(f"/people/{id_a}", json={"available": False})

    resp = people_client.get("/people?available=true")
    assert [p["name"] for p in resp.json()["data"]] == ["B"]


def test_combine_skill_and_availability(people_client):
    r1 = people_client.post("/people", json={"name": "A", "role": "r", "skills": ["python"]})
    r2 = people_client.post("/people", json={"name": "B", "role": "r", "skills": ["python"]})
    id_a = r1.json()["data"]["id"]

    people_client.patch(f"/people/{id_a}", json={"available": False})

    resp = people_client.get("/people?skill=python&available=true")
    names = {p["name"] for p in resp.json()["data"]}
    assert names == {"B"}
```

- [ ] **Step 2: Run filter test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/people/test_people_filters.py -v`
Expected: 3 passed

- [ ] **Step 3: Write constraint-error test**

Create `tests/services/people/test_constraint_errors.py`:

```python
def test_person_not_found_returns_semantic_envelope(people_client):
    resp = people_client.get("/people/person_doesnt_exist")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "person_not_found"
    assert body["_try_instead"]["href"] == "/people"
    assert body["_try_instead"]["verb"] == "GET"
    assert isinstance(body["_related"], list)


def test_patch_unknown_person_returns_semantic_envelope(people_client):
    resp = people_client.patch("/people/nope", json={"available": False})
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "person_not_found"


def test_invalid_current_load_returns_validation_error(people_client):
    r = people_client.post("/people", json={"name": "A", "role": "r", "skills": []})
    person_id = r.json()["data"]["id"]

    resp = people_client.patch(f"/people/{person_id}", json={"current_load": -1})
    assert resp.status_code == 422


def test_create_with_empty_name_returns_validation_error(people_client):
    resp = people_client.post("/people", json={"name": "", "role": "r", "skills": []})
    assert resp.status_code == 422
```

- [ ] **Step 4: Run constraint-error test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/people/test_constraint_errors.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add tests/services/people/test_people_filters.py tests/services/people/test_constraint_errors.py
git commit -m "test(people): verify filters and constraint-error envelope semantics"
```

---

## Task 6: People service — seed loader

**Files:**
- Create: `services/people/seed.py`
- Create: `fixtures/demo-seed/people.json`
- Create: `tests/services/people/test_seed.py`

- [ ] **Step 1: Write failing test for seed loader**

Create `tests/services/people/test_seed.py`:

```python
import json
from pathlib import Path

from services.people.db import Base, PersonRow, make_engine, make_sessionmaker
from services.people.seed import load_seed


def test_load_seed_creates_people(tmp_path):
    fixture = tmp_path / "people.json"
    fixture.write_text(json.dumps({
        "people": [
            {
                "id": "person_seed_alice",
                "name": "Alice Seed",
                "role": "senior engineer",
                "skills": ["python", "langgraph"],
                "available": True,
                "current_load": 0,
            },
            {
                "id": "person_seed_bob",
                "name": "Bob Seed",
                "role": "product manager",
                "skills": ["roadmaps"],
                "available": True,
                "current_load": 1,
            },
        ]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/people.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        rows = session.query(PersonRow).order_by(PersonRow.id).all()
        assert [r.id for r in rows] == ["person_seed_alice", "person_seed_bob"]
        assert rows[0].name == "Alice Seed"


def test_load_seed_is_idempotent(tmp_path):
    fixture = tmp_path / "people.json"
    fixture.write_text(json.dumps({
        "people": [{
            "id": "person_seed_alice", "name": "Alice", "role": "eng",
            "skills": ["python"], "available": True, "current_load": 0,
        }]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/people.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))
    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        assert session.query(PersonRow).count() == 1
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/people/test_seed.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.people.seed'`

- [ ] **Step 3: Implement `services/people/seed.py`**

Create `services/people/seed.py`:

```python
from __future__ import annotations

import json

from services.people.db import PersonRow


def load_seed(session_maker, fixture_path: str) -> None:
    with open(fixture_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    with session_maker() as session:
        for item in payload.get("people", []):
            existing = session.get(PersonRow, item["id"])
            if existing is None:
                session.add(
                    PersonRow(
                        id=item["id"],
                        name=item["name"],
                        role=item["role"],
                        skills_json=json.dumps(item.get("skills", [])),
                        available=bool(item.get("available", True)),
                        current_load=int(item.get("current_load", 0)),
                    )
                )
            else:
                existing.name = item["name"]
                existing.role = item["role"]
                existing.skills_json = json.dumps(item.get("skills", []))
                existing.available = bool(item.get("available", True))
                existing.current_load = int(item.get("current_load", 0))
        session.commit()
```

- [ ] **Step 4: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/people/test_seed.py -v`
Expected: 2 passed

- [ ] **Step 5: Create the demo fixture**

Create `fixtures/demo-seed/people.json`:

```json
{
  "people": [
    {
      "id": "person_alice",
      "name": "Alice Chen",
      "role": "senior engineer",
      "skills": ["python", "fastapi", "langgraph"],
      "available": true,
      "current_load": 1
    },
    {
      "id": "person_bob",
      "name": "Bob Patel",
      "role": "designer",
      "skills": ["figma", "accessibility", "branding"],
      "available": true,
      "current_load": 0
    },
    {
      "id": "person_carol",
      "name": "Carol Ruiz",
      "role": "product manager",
      "skills": ["roadmaps", "discovery"],
      "available": false,
      "current_load": 3
    },
    {
      "id": "person_dan",
      "name": "Dan Park",
      "role": "marketing lead",
      "skills": ["copywriting", "launches", "messaging"],
      "available": true,
      "current_load": 1
    }
  ]
}
```

- [ ] **Step 6: Commit**

```bash
git add services/people/seed.py fixtures/demo-seed/people.json tests/services/people/test_seed.py
git commit -m "feat(people): add idempotent JSON seed loader with demo fixture"
```

---

## Task 7: Communications service — DB layer

**Files:**
- Create: `services/communications/__init__.py` (empty)
- Create: `services/communications/db.py`
- Create: `tests/services/communications/__init__.py` (empty)
- Create: `tests/services/communications/conftest.py`
- Create: `tests/services/communications/test_communications_db.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/communications/test_communications_db.py`:

```python
from datetime import datetime, timezone

from sqlalchemy import select

from services.communications.db import (
    Base,
    MessageRow,
    make_engine,
    make_sessionmaker,
)


def test_create_message_row(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/communications.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    with SessionMaker() as session:
        session.add(
            MessageRow(
                id="msg_001",
                recipient_id="person_alice",
                project_id="proj_alpha",
                subject="Assignment",
                body="You've been assigned to milestone #2.",
                sent_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
                status="sent",
            )
        )
        session.commit()

    with SessionMaker() as session:
        row = session.execute(select(MessageRow).where(MessageRow.id == "msg_001")).scalar_one()
        assert row.recipient_id == "person_alice"
        assert row.project_id == "proj_alpha"
        assert row.status == "sent"
```

- [ ] **Step 2: Write conftest**

Create `tests/services/communications/conftest.py`:

```python
import pytest

from services.communications.app import create_app
from services.communications.db import Base, make_engine, make_sessionmaker


@pytest.fixture
def communications_app(tmp_path):
    db_path = tmp_path / "communications.db"
    engine = make_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)
    return create_app(session_maker=session_maker)


@pytest.fixture
def communications_client(communications_app):
    from fastapi.testclient import TestClient

    return TestClient(communications_app)
```

- [ ] **Step 3: Run DB test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_communications_db.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.communications.db'`

- [ ] **Step 4: Implement `services/communications/db.py`**

Create `services/communications/db.py`:

```python
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")


def make_engine(url: str):
    return create_engine(url, future=True)


def make_sessionmaker(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
```

- [ ] **Step 5: Run DB test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_communications_db.py -v`
Expected: 1 passed

- [ ] **Step 6: Commit**

```bash
git add services/communications/__init__.py services/communications/db.py tests/services/communications/__init__.py tests/services/communications/conftest.py tests/services/communications/test_communications_db.py
git commit -m "feat(communications): add SQLAlchemy schema for messages"
```

---

## Task 8: Communications service — Pydantic models

**Files:**
- Create: `services/communications/models.py`
- Create: `tests/services/communications/test_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/communications/test_models.py`:

```python
import pytest
from pydantic import ValidationError

from services.communications.models import CreateMessage, MessageOut


def test_create_message_requires_recipient_subject_and_body():
    msg = CreateMessage(
        recipient_id="person_alice",
        subject="Assignment",
        body="You've been assigned to milestone #2.",
    )
    assert msg.recipient_id == "person_alice"
    assert msg.project_id is None


def test_create_message_rejects_blank_subject():
    with pytest.raises(ValidationError):
        CreateMessage(recipient_id="person_alice", subject="", body="hello")


def test_message_out_serializes_datetime_iso():
    from datetime import datetime, timezone

    out = MessageOut(
        id="msg_001",
        recipient_id="person_alice",
        project_id=None,
        subject="Hi",
        body="Hello.",
        sent_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
        status="sent",
    )
    dumped = out.model_dump(mode="json")
    assert dumped["sent_at"].startswith("2026-04-19T10:00:00")
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_models.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.communications.models'`

- [ ] **Step 3: Implement `services/communications/models.py`**

Create `services/communications/models.py`:

```python
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from agent_protocol.field_docs import DocumentedField


class CreateMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    recipient_id: str = DocumentedField(
        description="Id of the person who should receive this message (from the people service).",
        examples=["person_alice", "person_bob"],
        min_length=1,
    )
    project_id: str | None = DocumentedField(
        description="Optional id of the project this message is about (from the projects service).",
        examples=["proj_alpha", "proj_q3_launch"],
        default=None,
    )
    subject: str = DocumentedField(
        description="Short subject line shown to the recipient.",
        examples=["You've been assigned", "Milestone update"],
        min_length=1,
    )
    body: str = DocumentedField(
        description="Full message body in plain text.",
        examples=["You've been assigned to milestone #2 of proj_alpha."],
        min_length=1,
    )


class MessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Stable message identifier.")
    recipient_id: str
    project_id: str | None
    subject: str
    body: str
    sent_at: datetime
    status: str
```

- [ ] **Step 4: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_models.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/communications/models.py tests/services/communications/test_models.py
git commit -m "feat(communications): add Pydantic models for messages"
```

---

## Task 9: Communications service — App factory and capabilities

**Files:**
- Create: `services/communications/app.py`
- Create: `services/communications/main.py`
- Create: `services/communications/routes/__init__.py` (empty)
- Create: `services/communications/routes/capabilities.py`
- Create: `services/communications/routes/messages.py` (stub)
- Create: `tests/services/communications/test_capabilities.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/communications/test_capabilities.py`:

```python
def test_root_lists_all_capabilities(communications_client):
    resp = communications_client.get("/")
    assert resp.status_code == 200
    body = resp.json()

    assert body["data"]["service"] == "communications"
    capability_ids = {c["id"] for c in body["data"]["capabilities"]}
    assert capability_ids == {
        "list_messages",
        "find_message",
        "send_message",
        "filter_by_recipient",
        "filter_by_project",
    }
    assert "_generated_at" in body
    assert isinstance(body["_related"], list)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_capabilities.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.communications.app'`

- [ ] **Step 3: Implement `services/communications/routes/capabilities.py`**

Create `services/communications/routes/capabilities.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from agent_protocol.catalog import Capability, build_catalog
from agent_protocol.envelope import make_response

router = APIRouter()


COMMUNICATIONS_CAPABILITIES: list[Capability] = [
    Capability(
        id="list_messages",
        verb="GET",
        path="/messages",
        summary="List every message, most recent first.",
        hints=["Combine with filters to narrow scope."],
    ),
    Capability(
        id="find_message",
        verb="GET",
        path="/messages/{message_id}",
        summary="Fetch a single message by id.",
        hints=["Returns 404 with `_try_instead` pointing to `GET /messages`."],
    ),
    Capability(
        id="send_message",
        verb="POST",
        path="/messages",
        summary="Send a new message to a person (optionally about a project).",
        hints=["Body fields: recipient_id, subject, body, project_id (optional)."],
    ),
    Capability(
        id="filter_by_recipient",
        verb="GET",
        path="/messages?recipient_id={person_id}",
        summary="List all messages sent to a specific person.",
        hints=["Matches the exact person id string."],
    ),
    Capability(
        id="filter_by_project",
        verb="GET",
        path="/messages?project_id={project_id}",
        summary="List all messages about a specific project.",
        hints=["Useful for building a project status timeline."],
    ),
]


@router.get("/")
def root(request: Request):
    return make_response(
        data=build_catalog(
            service_name="communications",
            description="Notifications, assignments, and status updates sent to team members.",
            capabilities=COMMUNICATIONS_CAPABILITIES,
        ),
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "list_messages", "href": "/messages", "verb": "GET"},
            {"rel": "send_message", "href": "/messages", "verb": "POST"},
        ],
    )
```

- [ ] **Step 4: Stub `services/communications/routes/messages.py`**

Create `services/communications/routes/messages.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

# Handlers implemented in Task 10.
```

- [ ] **Step 5: Implement `services/communications/app.py`**

Create `services/communications/app.py`:

```python
from __future__ import annotations

from fastapi import FastAPI

from agent_protocol.errors import register_error_handler

from services.communications.db import Base, make_engine, make_sessionmaker
from services.communications.routes import capabilities as capabilities_router
from services.communications.routes import messages as messages_router


def create_app(*, sqlite_path: str | None = None, session_maker=None) -> FastAPI:
    if session_maker is None:
        if sqlite_path is None:
            sqlite_path = "./communications.db"
        engine = make_engine(f"sqlite:///{sqlite_path}")
        Base.metadata.create_all(engine)
        session_maker = make_sessionmaker(engine)

    app = FastAPI(title="Communications Service", version="0.1.0")
    app.state.session_maker = session_maker

    register_error_handler(app)
    app.include_router(capabilities_router.router)
    app.include_router(messages_router.router)

    return app
```

- [ ] **Step 6: Implement `services/communications/main.py`**

Create `services/communications/main.py`:

```python
from __future__ import annotations

import argparse
import os

import uvicorn

from services.communications.app import create_app
from services.communications.db import Base, make_engine, make_sessionmaker


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8003)
    parser.add_argument("--sqlite", default=os.environ.get("COMMUNICATIONS_SQLITE", "./communications.db"))
    parser.add_argument("--seed-from", default=os.environ.get("COMMUNICATIONS_SEED"))
    args = parser.parse_args()

    engine = make_engine(f"sqlite:///{args.sqlite}")
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)

    if args.seed_from:
        from services.communications.seed import load_seed

        load_seed(session_maker, args.seed_from)

    app = create_app(session_maker=session_maker)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_capabilities.py -v`
Expected: 1 passed

- [ ] **Step 8: Commit**

```bash
git add services/communications/app.py services/communications/main.py services/communications/routes/__init__.py services/communications/routes/capabilities.py services/communications/routes/messages.py tests/services/communications/test_capabilities.py
git commit -m "feat(communications): add app factory and capabilities endpoint"
```

---

## Task 10: Communications service — send and retrieve messages

**Files:**
- Modify: `services/communications/routes/messages.py`
- Create: `tests/services/communications/test_messages_crud.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/communications/test_messages_crud.py`:

```python
def test_send_and_get_message(communications_client):
    send_resp = communications_client.post(
        "/messages",
        json={
            "recipient_id": "person_alice",
            "project_id": "proj_alpha",
            "subject": "Assignment",
            "body": "You've been assigned to milestone #2.",
        },
    )
    assert send_resp.status_code == 201
    body = send_resp.json()
    assert body["data"]["recipient_id"] == "person_alice"
    assert body["data"]["status"] == "sent"
    assert body["_self"].endswith(f"/messages/{body['data']['id']}")
    suggested_rels = {s["rel"] for s in body["_suggested_next"]}
    assert "list_messages" in suggested_rels
    assert "filter_by_recipient" in suggested_rels

    message_id = body["data"]["id"]
    get_resp = communications_client.get(f"/messages/{message_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["subject"] == "Assignment"


def test_list_messages_returns_envelope(communications_client):
    communications_client.post(
        "/messages",
        json={"recipient_id": "person_a", "subject": "s", "body": "b"},
    )
    communications_client.post(
        "/messages",
        json={"recipient_id": "person_b", "subject": "s", "body": "b"},
    )

    resp = communications_client.get("/messages")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    assert body["_self"] == "http://testserver/messages"
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_messages_crud.py -v`
Expected: FAIL — `405 Method Not Allowed`.

- [ ] **Step 3: Implement `services/communications/routes/messages.py`**

Replace `services/communications/routes/messages.py`:

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from sqlalchemy import select

from agent_protocol.envelope import make_response
from agent_protocol.errors import AgentError

from services.communications.db import MessageRow
from services.communications.models import CreateMessage, MessageOut

router = APIRouter()


def _row_to_out(row: MessageRow) -> MessageOut:
    return MessageOut(
        id=row.id,
        recipient_id=row.recipient_id,
        project_id=row.project_id,
        subject=row.subject,
        body=row.body,
        sent_at=row.sent_at,
        status=row.status,
    )


def _message_suggested_next(message: MessageOut) -> list[dict]:
    suggestions: list[dict] = [
        {"rel": "list_messages", "href": "/messages", "verb": "GET"},
        {
            "rel": "filter_by_recipient",
            "href": f"/messages?recipient_id={message.recipient_id}",
            "verb": "GET",
        },
    ]
    if message.project_id:
        suggestions.append({
            "rel": "filter_by_project",
            "href": f"/messages?project_id={message.project_id}",
            "verb": "GET",
        })
    return suggestions


@router.post("/messages", status_code=201)
def send_message(payload: CreateMessage, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        message_id = f"msg_{uuid.uuid4().hex[:8]}"
        row = MessageRow(
            id=message_id,
            recipient_id=payload.recipient_id,
            project_id=payload.project_id,
            subject=payload.subject,
            body=payload.body,
            sent_at=datetime.now(timezone.utc),
            status="sent",
        )
        session.add(row)
        session.commit()
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(mode="json"),
        self_link=str(request.url_for("get_message", message_id=message_id)),
        related=[{"rel": "list_messages", "href": "/messages", "verb": "GET"}],
        suggested_next=_message_suggested_next(out),
    )


@router.get("/messages/{message_id}", name="get_message")
def get_message(message_id: str, request: Request):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        row = session.get(MessageRow, message_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="message_not_found",
                message=f"No message with id={message_id!r}.",
                why="The id does not match any stored message.",
                try_instead={
                    "rel": "list_messages",
                    "href": "/messages",
                    "verb": "GET",
                    "hint": "List all messages and pick an id from the result.",
                },
                related=[{"rel": "list_messages", "href": "/messages", "verb": "GET"}],
            )
        out = _row_to_out(row)

    return make_response(
        data=out.model_dump(mode="json"),
        self_link=str(request.url),
        related=[{"rel": "list_messages", "href": "/messages", "verb": "GET"}],
        suggested_next=_message_suggested_next(out),
    )


@router.get("/messages")
def list_messages(
    request: Request,
    recipient_id: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
):
    session_maker = request.app.state.session_maker
    with session_maker() as session:
        stmt = select(MessageRow).order_by(MessageRow.sent_at.desc())
        if recipient_id is not None:
            stmt = stmt.where(MessageRow.recipient_id == recipient_id)
        if project_id is not None:
            stmt = stmt.where(MessageRow.project_id == project_id)
        rows = session.execute(stmt).scalars().all()
        results = [_row_to_out(r) for r in rows]

    return make_response(
        data=[m.model_dump(mode="json") for m in results],
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "find_message", "href": "/messages/{message_id}", "verb": "GET"},
        ],
    )
```

- [ ] **Step 4: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_messages_crud.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add services/communications/routes/messages.py tests/services/communications/test_messages_crud.py
git commit -m "feat(communications): add send/list/find message routes with envelope"
```

---

## Task 11: Communications service — filters and constraint errors

**Files:**
- Create: `tests/services/communications/test_messages_filters.py`
- Create: `tests/services/communications/test_constraint_errors.py`

- [ ] **Step 1: Write filter test**

Create `tests/services/communications/test_messages_filters.py`:

```python
def _send(client, recipient_id, project_id=None, subject="s", body="b"):
    return client.post(
        "/messages",
        json={
            "recipient_id": recipient_id,
            "project_id": project_id,
            "subject": subject,
            "body": body,
        },
    )


def test_filter_by_recipient(communications_client):
    _send(communications_client, "person_alice", project_id="proj_a")
    _send(communications_client, "person_bob", project_id="proj_a")
    _send(communications_client, "person_alice", project_id="proj_b")

    resp = communications_client.get("/messages?recipient_id=person_alice")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 2
    assert all(m["recipient_id"] == "person_alice" for m in data)


def test_filter_by_project(communications_client):
    _send(communications_client, "person_alice", project_id="proj_a")
    _send(communications_client, "person_bob", project_id="proj_b")

    resp = communications_client.get("/messages?project_id=proj_b")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["recipient_id"] == "person_bob"


def test_combine_recipient_and_project(communications_client):
    _send(communications_client, "person_alice", project_id="proj_a")
    _send(communications_client, "person_alice", project_id="proj_b")
    _send(communications_client, "person_bob", project_id="proj_a")

    resp = communications_client.get("/messages?recipient_id=person_alice&project_id=proj_b")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["project_id"] == "proj_b"
```

- [ ] **Step 2: Run filter test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_messages_filters.py -v`
Expected: 3 passed

- [ ] **Step 3: Write constraint-error test**

Create `tests/services/communications/test_constraint_errors.py`:

```python
def test_message_not_found_returns_semantic_envelope(communications_client):
    resp = communications_client.get("/messages/msg_unknown")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "message_not_found"
    assert body["_try_instead"]["href"] == "/messages"
    assert body["_try_instead"]["verb"] == "GET"
    assert isinstance(body["_related"], list)


def test_missing_required_fields_returns_validation_error(communications_client):
    resp = communications_client.post("/messages", json={"recipient_id": "person_a"})
    assert resp.status_code == 422


def test_blank_subject_returns_validation_error(communications_client):
    resp = communications_client.post(
        "/messages",
        json={"recipient_id": "person_a", "subject": "", "body": "hi"},
    )
    assert resp.status_code == 422
```

- [ ] **Step 4: Run constraint-error test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_constraint_errors.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/services/communications/test_messages_filters.py tests/services/communications/test_constraint_errors.py
git commit -m "test(communications): verify filters and constraint-error envelope semantics"
```

---

## Task 12: Communications service — seed loader

**Files:**
- Create: `services/communications/seed.py`
- Create: `fixtures/demo-seed/communications.json`
- Create: `tests/services/communications/test_seed.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/communications/test_seed.py`:

```python
import json
from pathlib import Path

from services.communications.db import Base, MessageRow, make_engine, make_sessionmaker
from services.communications.seed import load_seed


def test_load_seed_creates_messages(tmp_path):
    fixture = tmp_path / "communications.json"
    fixture.write_text(json.dumps({
        "messages": [
            {
                "id": "msg_seed_001",
                "recipient_id": "person_seed_alice",
                "project_id": "proj_seed_alpha",
                "subject": "Welcome",
                "body": "Welcome to the project.",
                "sent_at": "2026-04-19T10:00:00+00:00",
                "status": "sent",
            }
        ]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/communications.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        rows = session.query(MessageRow).all()
        assert len(rows) == 1
        assert rows[0].subject == "Welcome"


def test_load_seed_is_idempotent(tmp_path):
    fixture = tmp_path / "communications.json"
    fixture.write_text(json.dumps({
        "messages": [{
            "id": "msg_seed_001",
            "recipient_id": "p", "project_id": None, "subject": "s", "body": "b",
            "sent_at": "2026-04-19T10:00:00+00:00", "status": "sent",
        }]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/communications.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))
    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        assert session.query(MessageRow).count() == 1
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_seed.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.communications.seed'`

- [ ] **Step 3: Implement `services/communications/seed.py`**

Create `services/communications/seed.py`:

```python
from __future__ import annotations

import json
from datetime import datetime

from services.communications.db import MessageRow


def load_seed(session_maker, fixture_path: str) -> None:
    with open(fixture_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    with session_maker() as session:
        for item in payload.get("messages", []):
            sent_at = datetime.fromisoformat(item["sent_at"])
            existing = session.get(MessageRow, item["id"])
            if existing is None:
                session.add(
                    MessageRow(
                        id=item["id"],
                        recipient_id=item["recipient_id"],
                        project_id=item.get("project_id"),
                        subject=item["subject"],
                        body=item["body"],
                        sent_at=sent_at,
                        status=item.get("status", "sent"),
                    )
                )
            else:
                existing.recipient_id = item["recipient_id"]
                existing.project_id = item.get("project_id")
                existing.subject = item["subject"]
                existing.body = item["body"]
                existing.sent_at = sent_at
                existing.status = item.get("status", "sent")
        session.commit()
```

- [ ] **Step 4: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/communications/test_seed.py -v`
Expected: 2 passed

- [ ] **Step 5: Create the demo fixture**

Create `fixtures/demo-seed/communications.json`:

```json
{
  "messages": [
    {
      "id": "msg_seed_001",
      "recipient_id": "person_carol",
      "project_id": "proj_seed_alpha",
      "subject": "Kickoff",
      "body": "Project alpha is kicking off this week. You are the PM.",
      "sent_at": "2026-04-15T09:00:00+00:00",
      "status": "sent"
    }
  ]
}
```

- [ ] **Step 6: Commit**

```bash
git add services/communications/seed.py fixtures/demo-seed/communications.json tests/services/communications/test_seed.py
git commit -m "feat(communications): add idempotent JSON seed loader with demo fixture"
```

---

## Task 13: Wire up Makefile + env + documentation

**Files:**
- Modify: `Makefile`
- Modify: `.env.example`
- Modify: `docs/test_inventory.md`
- Modify: `docs/implementation_status.md`

- [ ] **Step 1: Append new Makefile targets**

Open `Makefile` and add these targets (append to the end):

```makefile
run-people:
	. .venv/bin/activate && PEOPLE_SEED=fixtures/demo-seed/people.json python3 -m services.people.main

run-communications:
	. .venv/bin/activate && COMMUNICATIONS_SEED=fixtures/demo-seed/communications.json python3 -m services.communications.main

test-people:
	. .venv/bin/activate && pytest tests/services/people -v

test-communications:
	. .venv/bin/activate && pytest tests/services/communications -v

test-leaf-services:
	. .venv/bin/activate && pytest tests/services -v
```

- [ ] **Step 2: Append new env vars**

Open `.env.example` and add (append to the end):

```bash
# People service
PEOPLE_SQLITE=./people.db
PEOPLE_SEED=fixtures/demo-seed/people.json

# Communications service
COMMUNICATIONS_SQLITE=./communications.db
COMMUNICATIONS_SEED=fixtures/demo-seed/communications.json
```

- [ ] **Step 3: Update `docs/test_inventory.md`**

Append the following section:

```markdown
## People service (`tests/services/people/`)

| Test file | Covers | Type | Run |
|---|---|---|---|
| `test_people_db.py` | SQLAlchemy PersonRow create/read | Integration (sqlite) | `pytest tests/services/people/test_people_db.py -v` |
| `test_models.py` | Pydantic model validation | Unit | `pytest tests/services/people/test_models.py -v` |
| `test_capabilities.py` | `GET /` capability catalog | Integration (TestClient) | `pytest tests/services/people/test_capabilities.py -v` |
| `test_people_crud.py` | Create/get/patch/list with envelope | Integration | `pytest tests/services/people/test_people_crud.py -v` |
| `test_people_filters.py` | `skill` and `available` query filters | Integration | `pytest tests/services/people/test_people_filters.py -v` |
| `test_constraint_errors.py` | 404 / 422 envelope semantics | Integration | `pytest tests/services/people/test_constraint_errors.py -v` |
| `test_seed.py` | JSON seed loader idempotence | Integration | `pytest tests/services/people/test_seed.py -v` |

External deps: none (sqlite is stdlib).

## Communications service (`tests/services/communications/`)

| Test file | Covers | Type | Run |
|---|---|---|---|
| `test_communications_db.py` | SQLAlchemy MessageRow create/read | Integration (sqlite) | `pytest tests/services/communications/test_communications_db.py -v` |
| `test_models.py` | Pydantic model validation | Unit | `pytest tests/services/communications/test_models.py -v` |
| `test_capabilities.py` | `GET /` capability catalog | Integration | `pytest tests/services/communications/test_capabilities.py -v` |
| `test_messages_crud.py` | Send/get/list with envelope | Integration | `pytest tests/services/communications/test_messages_crud.py -v` |
| `test_messages_filters.py` | `recipient_id` and `project_id` filters | Integration | `pytest tests/services/communications/test_messages_filters.py -v` |
| `test_constraint_errors.py` | 404 / 422 envelope semantics | Integration | `pytest tests/services/communications/test_constraint_errors.py -v` |
| `test_seed.py` | JSON seed loader idempotence | Integration | `pytest tests/services/communications/test_seed.py -v` |

External deps: none.
```

- [ ] **Step 4: Update `docs/implementation_status.md`**

Append:

```markdown
## 2026-04-19 — Leaf services increment (Plan 2 complete)

**Plan:** `docs/superpowers/plans/2026-04-19-leaf-services.md`

**Completed:**
- People service (port 8002): DB, models, app factory, capabilities catalog, CRUD routes, skill/availability filters, semantic error envelopes, JSON seed loader, demo fixture.
- Communications service (port 8003): DB, models, app factory, capabilities catalog, send/list/find routes, recipient/project filters, semantic error envelopes, JSON seed loader, demo fixture.
- Makefile targets: `run-people`, `run-communications`, `test-people`, `test-communications`, `test-leaf-services`.

**Evidence:** see Task 14 Step 3 below — full `pytest tests/services -v` output captured in terminal log.

**Next:** Plan 3 — Orchestrator service (`docs/superpowers/plans/2026-04-19-orchestrator-service.md`).
```

- [ ] **Step 5: Commit**

```bash
git add Makefile .env.example docs/test_inventory.md docs/implementation_status.md
git commit -m "docs(leaf-services): wire up Makefile, env vars, test inventory, status"
```

---

## Task 14: Full regression and live smoke test

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `. .venv/bin/activate && pytest tests/ -v`
Expected: All tests from Plan 1 (29+) plus ~30 new tests from this plan pass. Target: **59+ passed, 0 failed**.

Concrete count expected in the new tests:
- people/test_people_db: 1
- people/test_models: 3
- people/test_capabilities: 1
- people/test_people_crud: 2
- people/test_people_filters: 3
- people/test_constraint_errors: 4
- people/test_seed: 2
- communications/test_communications_db: 1
- communications/test_models: 3
- communications/test_capabilities: 1
- communications/test_messages_crud: 2
- communications/test_messages_filters: 3
- communications/test_constraint_errors: 3
- communications/test_seed: 2
- **New total: 31**

- [ ] **Step 2: Start the People service and smoke-test capabilities**

Run in a separate shell:

```bash
rm -f people.db
make run-people
```

Then, from another shell:

```bash
curl -s http://127.0.0.1:8002/ | python3 -m json.tool
```

Expected output contains:

```json
{
    "data": {
        "service": "people",
        "description": "Team members, roles, skills, availability, and current load.",
        "capabilities": [
            {"id": "list_people", "verb": "GET", "path": "/people", ...},
            ...
        ]
    },
    "_self": "http://127.0.0.1:8002/",
    "_related": [],
    "_suggested_next": [...],
    "_generated_at": "2026-04-19T..."
}
```

Then:

```bash
curl -s http://127.0.0.1:8002/people | python3 -m json.tool
```

Expected: `data` array contains the four seeded people (Alice, Bob, Carol, Dan).

Then test a filter:

```bash
curl -s "http://127.0.0.1:8002/people?skill=python&available=true" | python3 -m json.tool
```

Expected: data array includes Alice Chen, excludes Bob Patel and Carol Ruiz.

Stop the people service (Ctrl-C) before proceeding.

- [ ] **Step 3: Start the Communications service and smoke-test**

```bash
rm -f communications.db
make run-communications
```

From another shell:

```bash
curl -s -X POST http://127.0.0.1:8003/messages \
  -H 'content-type: application/json' \
  -d '{"recipient_id":"person_alice","project_id":"proj_alpha","subject":"Hi","body":"test."}' \
  | python3 -m json.tool
```

Expected: 201 response with envelope including `_self` pointing at `/messages/msg_...`, `_suggested_next` including `list_messages`, `filter_by_recipient`, and `filter_by_project`.

```bash
curl -s "http://127.0.0.1:8003/messages?recipient_id=person_alice" | python3 -m json.tool
```

Expected: data array with 1 message, envelope fields populated.

Stop the communications service.

- [ ] **Step 4: Declare the increment done**

The increment is done when:
- `pytest tests/ -v` reports **59+ passed, 0 failed**.
- `make run-people` serves `/` and `/people` with envelope.
- `make run-communications` serves `/` and `/messages` with envelope.
- Capability catalogs are accurate and filters work.

No commit needed for this step — nothing changed on disk.

---

## Self-review checklist

Before declaring this plan ready:

1. **Spec coverage** — Does every capability in the People and Communications sections of the spec (`docs/superpowers/specs/2026-04-19-agent-first-services-design.md` §6.3, §6.4) have a corresponding task?
   - People: list, find, create, update, filter-by-skill, filter-by-availability ✓
   - Communications: list, find, send, filter-by-recipient, filter-by-project ✓

2. **Placeholder scan** — No TBDs, no "implement later", every code block is complete. ✓

3. **Type consistency** — Field names match between DB, models, fixtures, and test assertions: `recipient_id`, `project_id`, `sent_at`, `status` all consistent. ✓

4. **Pattern parity with Plan 1** — Same layout (`db.py`/`models.py`/`app.py`/`main.py`/`seed.py`/`routes/`), same `create_app(session_maker=...)` factory, same envelope, same error semantics. ✓

5. **Port assignment** — People on 8002, Communications on 8003 (per spec §6.1). ✓

---

## Definition of Done

- All ~31 new tests pass in isolation and in the full suite.
- Both services serve valid hypermedia envelopes via curl.
- Test inventory, env example, Makefile, implementation status updated.
- Plan 3 (Orchestrator) is unblocked.
