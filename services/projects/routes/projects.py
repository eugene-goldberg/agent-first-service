from __future__ import annotations

import secrets

from fastapi import APIRouter, Request, Response

from agent_protocol.envelope import AgentResponse
from agent_protocol.errors import AgentError
from services.projects.db import ProjectRow
from services.projects.models import CreateProject, ProjectOut

router = APIRouter()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


def _to_out(row: ProjectRow) -> ProjectOut:
    return ProjectOut(id=row.id, name=row.name, description=row.description)


@router.post("/projects", status_code=201)
def create_project(body: CreateProject, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = ProjectRow(
            id=_new_id("proj"),
            name=body.name,
            description=body.description,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[ProjectOut](
        data=out,
        self_link=f"/projects/{out.id}",
        related=["/projects"],
        suggested_next={
            "add_tasks": f"/projects/{out.id}/tasks",
            "view_project": f"/projects/{out.id}",
        },
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/projects")
def list_projects(request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        rows = s.query(ProjectRow).all()
        items = [_to_out(r) for r in rows]

    envelope = AgentResponse[list[ProjectOut]](
        data=items,
        self_link="/projects",
        related=[f"/projects/{p.id}" for p in items],
        suggested_next={"create_project": "/projects"},
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = s.get(ProjectRow, project_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="project_not_found",
                message=f"no project with id {project_id}",
                why=f"the project id {project_id} does not exist in this service",
                try_instead="call GET /projects to list existing project ids",
                related=["/projects"],
            )
        out = _to_out(row)

    envelope = AgentResponse[ProjectOut](
        data=out,
        self_link=f"/projects/{out.id}",
        related=[f"/projects/{out.id}/tasks", "/projects"],
        suggested_next={
            "list_tasks": f"/projects/{out.id}/tasks",
            "update": f"/projects/{out.id}",
        },
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: dict, request: Request) -> dict:
    allowed = {"name", "description"}
    bad = set(body.keys()) - allowed
    if bad:
        raise AgentError(
            status_code=400,
            error="unknown_fields",
            message=f"unknown field(s): {sorted(bad)}",
            why=f"the fields {sorted(bad)} are not editable on a project",
            try_instead=f"use only {sorted(allowed)} in the request body",
            valid_values=sorted(allowed),
            example={"name": "New Name"},
        )

    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = s.get(ProjectRow, project_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="project_not_found",
                message=f"no project with id {project_id}",
                why=f"the project id {project_id} does not exist in this service",
                try_instead="call GET /projects to list existing project ids",
                related=["/projects"],
            )
        for k, v in body.items():
            setattr(row, k, v)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[ProjectOut](
        data=out,
        self_link=f"/projects/{out.id}",
        related=[f"/projects/{out.id}/tasks"],
    )
    return envelope.model_dump(by_alias=True, mode="json")
