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
