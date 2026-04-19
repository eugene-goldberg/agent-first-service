from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


PEOPLE_CAPABILITIES: list[dict[str, Any]] = [
    {
        "id": "list_people",
        "verb": "GET",
        "path": "/people",
        "summary": "List every team member.",
        "hints": ["Use filters (skill, available) to narrow the list."],
    },
    {
        "id": "find_person",
        "verb": "GET",
        "path": "/people/{person_id}",
        "summary": "Fetch a single person by id.",
        "hints": ["Returns 404 with `_try_instead` pointing to `GET /people`."],
    },
    {
        "id": "create_person",
        "verb": "POST",
        "path": "/people",
        "summary": "Add a new team member.",
        "hints": ["Body fields: name, role, skills."],
    },
    {
        "id": "update_person",
        "verb": "PATCH",
        "path": "/people/{person_id}",
        "summary": "Update availability, current_load, or skills.",
        "hints": ["Partial updates — send only fields you want to change."],
    },
    {
        "id": "filter_by_skill",
        "verb": "GET",
        "path": "/people?skill={skill}",
        "summary": "List people whose skills include a given tag.",
        "hints": ["Case-insensitive match against the skills array."],
    },
    {
        "id": "filter_by_availability",
        "verb": "GET",
        "path": "/people?available=true",
        "summary": "List only people marked as available.",
        "hints": ["Combine with `skill` to find a free specialist."],
    },
]


@router.get("/")
def root(request: Request) -> dict[str, Any]:
    return {
        "data": {
            "service": "people",
            "description": "Team members, roles, skills, availability, and current load.",
            "capabilities": PEOPLE_CAPABILITIES,
        },
        "_self": str(request.url),
        "_related": [],
        "_suggested_next": [
            {"rel": "list_people", "href": "/people", "verb": "GET"},
        ],
        "_generated_at": datetime.now(timezone.utc).isoformat(),
    }
