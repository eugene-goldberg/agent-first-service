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
                try_instead="GET /people — list all people and pick an id from the result.",
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
                try_instead="GET /people — list all people first.",
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
