from __future__ import annotations

import secrets

import httpx
from fastapi import APIRouter, Request

from agent_protocol.envelope import AgentResponse
from agent_protocol.errors import AgentError
from services.projects.db import MilestoneRow, ProjectRow, TaskRow
from services.projects.models import CreateTask, TaskOut, UpdateTask

router = APIRouter()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


def _to_out(row: TaskRow) -> TaskOut:
    return TaskOut(
        id=row.id,
        project_id=row.project_id,
        title=row.title,
        status=row.status,
        assignee_id=row.assignee_id,
        due_date=row.due_date,
        milestone_id=row.milestone_id,
    )


def _task_suggested_next(task_id: str) -> dict:
    return {
        "update_status": {
            "method": "PATCH",
            "path": f"/tasks/{task_id}",
            "body_hint": {"status": "in_progress|done|blocked"},
        },
        "assign": {
            "method": "PATCH",
            "path": f"/tasks/{task_id}",
            "body_hint": {"assignee_id": "<person_id from People service>"},
        },
    }


def _validate_assignee(request: Request, assignee_id: str | None) -> None:
    if assignee_id is None:
        return
    base = request.app.state.people_base_url.rstrip("/")
    url = f"{base}/people/{assignee_id}"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
    except httpx.HTTPError as exc:
        raise AgentError(
            status_code=503,
            error="people_service_unreachable",
            message="cannot validate task assignee because People service is unreachable",
            why=str(exc),
            try_instead="start People service and retry assignment",
            related=[f"{base}/"],
        ) from exc

    if resp.status_code == 404:
        raise AgentError(
            status_code=422,
            error="assignee_not_found",
            message=f"cannot assign task: person {assignee_id} does not exist",
            why=f"People service has no person with id {assignee_id}",
            try_instead="use GET /people to select a valid person id",
            related=[f"{base}/people"],
        )
    if resp.status_code >= 400:
        raise AgentError(
            status_code=503,
            error="people_service_error",
            message="cannot validate task assignee due to People service error",
            why=f"People service returned status {resp.status_code}",
            try_instead="retry after People service recovers",
            related=[f"{base}/"],
        )
    payload = resp.json().get("data", {})
    if not payload.get("available", False):
        raise AgentError(
            status_code=422,
            error="assignee_unavailable",
            message=f"cannot assign task: person {assignee_id} is unavailable",
            why=f"People record {assignee_id} is currently unavailable",
            try_instead="pick another available person from GET /people?available=true",
            related=[f"{base}/people?available=true"],
        )


@router.post("/projects/{project_id}/tasks", status_code=201)
def create_task(project_id: str, body: CreateTask, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        if s.get(ProjectRow, project_id) is None:
            raise AgentError(
                status_code=422,
                error="project_missing",
                message=f"cannot add task: project {project_id} does not exist",
                why=f"the parent project {project_id} was not found",
                try_instead="create the project first via POST /projects, then add tasks under it",
                related=["/projects"],
            )
        if body.milestone_id is not None:
            milestone = s.get(MilestoneRow, body.milestone_id)
            if milestone is None or milestone.project_id != project_id:
                raise AgentError(
                    status_code=422,
                    error="milestone_missing",
                    message=f"cannot add task: milestone {body.milestone_id} is invalid for project {project_id}",
                    why="task milestone must exist and belong to the same project",
                    try_instead="create/select a milestone under this project first",
                    related=[f"/projects/{project_id}/milestones"],
                )
        _validate_assignee(request, body.assignee_id)
        row = TaskRow(
            id=_new_id("task"),
            project_id=project_id,
            title=body.title,
            assignee_id=body.assignee_id,
            due_date=body.due_date,
            milestone_id=body.milestone_id,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[TaskOut](
        data=out,
        self_link=f"/tasks/{out.id}",
        related=[f"/projects/{project_id}/tasks", f"/projects/{project_id}"],
        suggested_next=_task_suggested_next(out.id),
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/projects/{project_id}/tasks")
def list_tasks_for_project(project_id: str, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        if s.get(ProjectRow, project_id) is None:
            raise AgentError(
                status_code=404,
                error="project_not_found",
                message=f"no project with id {project_id}",
                why="cannot list tasks for a project that does not exist",
                try_instead="call GET /projects to see available projects",
                related=["/projects"],
            )
        rows = s.query(TaskRow).filter(TaskRow.project_id == project_id).all()
        items = [_to_out(r) for r in rows]

    envelope = AgentResponse[list[TaskOut]](
        data=items,
        self_link=f"/projects/{project_id}/tasks",
        related=[f"/projects/{project_id}"],
        suggested_next={"add_task": f"/projects/{project_id}/tasks"},
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, body: UpdateTask, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = s.get(TaskRow, task_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="task_not_found",
                message=f"no task with id {task_id}",
                why=f"the task id {task_id} does not exist",
                try_instead="call GET /tasks or GET /projects/{id}/tasks to list task ids",
                related=["/tasks", "/projects"],
            )
        updates = body.model_dump(exclude_none=True)
        if "milestone_id" in updates:
            milestone = s.get(MilestoneRow, updates["milestone_id"])
            if milestone is None or milestone.project_id != row.project_id:
                raise AgentError(
                    status_code=422,
                    error="milestone_missing",
                    message=f"cannot move task to milestone {updates['milestone_id']}",
                    why="target milestone must exist and belong to the same project as the task",
                    try_instead=f"use GET /projects/{row.project_id}/milestones to pick a valid milestone",
                    related=[f"/projects/{row.project_id}/milestones"],
                )
        if "assignee_id" in updates:
            _validate_assignee(request, updates["assignee_id"])
        for k, v in updates.items():
            setattr(row, k, v)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[TaskOut](
        data=out,
        self_link=f"/tasks/{out.id}",
        related=[f"/projects/{out.project_id}/tasks", f"/projects/{out.project_id}"],
        suggested_next=_task_suggested_next(out.id),
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/tasks")
def query_tasks(
    request: Request,
    assignee: str | None = None,
    status: str | None = None,
    milestone: str | None = None,
) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        q = s.query(TaskRow)
        if assignee is not None:
            q = q.filter(TaskRow.assignee_id == assignee)
        if status is not None:
            q = q.filter(TaskRow.status == status)
        if milestone is not None:
            q = q.filter(TaskRow.milestone_id == milestone)
        rows = q.all()
        items = [_to_out(r) for r in rows]

    envelope = AgentResponse[list[TaskOut]](
        data=items,
        self_link="/tasks",
        related=["/projects"],
    )
    return envelope.model_dump(by_alias=True, mode="json")
