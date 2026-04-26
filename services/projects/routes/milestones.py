from __future__ import annotations

import secrets

from fastapi import APIRouter, Request

from agent_protocol.envelope import AgentResponse
from agent_protocol.errors import AgentError
from services.projects.db import MilestoneRow, ProjectRow
from services.projects.models import (
    CreateMilestone,
    MilestoneOut,
    UpdateMilestone,
)

router = APIRouter()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


def _to_out(row: MilestoneRow) -> MilestoneOut:
    return MilestoneOut(
        id=row.id,
        project_id=row.project_id,
        title=row.name,
        due_date=row.due_date,
        status=row.status,
        order_index=row.order_index,
    )


@router.post("/projects/{project_id}/milestones", status_code=201)
def create_milestone(project_id: str, body: CreateMilestone, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        if s.get(ProjectRow, project_id) is None:
            raise AgentError(
                status_code=422,
                error="project_missing",
                message=f"cannot add milestone: project {project_id} does not exist",
                why=f"the parent project {project_id} was not found",
                try_instead="create the project first via POST /projects, then add milestones",
                related=["/projects"],
            )
        row = MilestoneRow(
            id=_new_id("ms"),
            project_id=project_id,
            name=body.title,
            due_date=body.due_date,
            status=body.status,
            order_index=body.order_index,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[MilestoneOut](
        data=out,
        self_link=f"/milestones/{out.id}",
        related=[f"/projects/{project_id}/milestones", f"/projects/{project_id}"],
        suggested_next={
            "update_milestone": f"/milestones/{out.id}",
            "list_milestones": f"/projects/{project_id}/milestones",
        },
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/projects/{project_id}/milestones")
def list_milestones_for_project(project_id: str, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        if s.get(ProjectRow, project_id) is None:
            raise AgentError(
                status_code=404,
                error="project_not_found",
                message=f"no project with id {project_id}",
                why="cannot list milestones for a project that does not exist",
                try_instead="call GET /projects to see available projects",
                related=["/projects"],
            )
        rows = (
            s.query(MilestoneRow)
            .filter(MilestoneRow.project_id == project_id)
            .order_by(MilestoneRow.order_index.asc().nulls_last(), MilestoneRow.id.asc())
            .all()
        )
        items = [_to_out(r) for r in rows]

    envelope = AgentResponse[list[MilestoneOut]](
        data=items,
        self_link=f"/projects/{project_id}/milestones",
        related=[f"/projects/{project_id}"],
        suggested_next={"add_milestone": f"/projects/{project_id}/milestones"},
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.patch("/milestones/{milestone_id}")
def patch_milestone(milestone_id: str, body: UpdateMilestone, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = s.get(MilestoneRow, milestone_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="milestone_not_found",
                message=f"no milestone with id {milestone_id}",
                why=f"the milestone id {milestone_id} does not exist",
                try_instead="call GET /projects/{id}/milestones to list milestone ids",
                related=["/projects"],
            )
        updates = body.model_dump(exclude_none=True)
        if "title" in updates:
            updates["name"] = updates.pop("title")
        for k, v in updates.items():
            setattr(row, k, v)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[MilestoneOut](
        data=out,
        self_link=f"/milestones/{out.id}",
        related=[f"/projects/{out.project_id}/milestones", f"/projects/{out.project_id}"],
        suggested_next={
            "list_milestones": f"/projects/{out.project_id}/milestones",
        },
    )
    return envelope.model_dump(by_alias=True, mode="json")
