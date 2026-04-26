from __future__ import annotations

from fastapi import APIRouter

from agent_protocol.catalog import Capability, build_catalog

router = APIRouter()

_CAPABILITIES = [
    Capability(
        intent="list all projects",
        method="GET",
        path="/projects",
        returns="list of Project resources wrapped in the agent response envelope",
    ),
    Capability(
        intent="create a new project",
        method="POST",
        path="/projects",
        example_body={"name": "Q3 Launch Landing Page", "description": "Marketing launch"},
        returns="Project resource with _suggested_next link to add tasks",
    ),
    Capability(
        intent="get a project by id",
        method="GET",
        path="/projects/{id}",
        returns="Project resource with links to its tasks and milestones",
    ),
    Capability(
        intent="update a project",
        method="PATCH",
        path="/projects/{id}",
        example_body={"name": "Updated Name", "description": "Updated description"},
        returns="Updated Project resource",
    ),
    Capability(
        intent="list tasks belonging to a project",
        method="GET",
        path="/projects/{id}/tasks",
        returns="list of Task resources",
    ),
    Capability(
        intent="create a task under a project",
        method="POST",
        path="/projects/{id}/tasks",
        example_body={
            "title": "Write copy",
            "assignee_id": None,
            "due_date": "2026-05-20",
            "milestone_id": "ms_abc123",
        },
        returns="Task resource",
    ),
    Capability(
        intent="list milestones belonging to a project plan",
        method="GET",
        path="/projects/{id}/milestones",
        returns="list of Milestone resources",
    ),
    Capability(
        intent="create a milestone under a project",
        method="POST",
        path="/projects/{id}/milestones",
        example_body={
            "title": "Design approved",
            "due_date": "2026-05-15",
            "status": "planned",
            "order_index": 1,
        },
        returns="Milestone resource",
    ),
    Capability(
        intent="update a milestone",
        method="PATCH",
        path="/milestones/{id}",
        example_body={"status": "in_progress"},
        returns="Updated Milestone resource",
    ),
    Capability(
        intent="update a task",
        method="PATCH",
        path="/tasks/{id}",
        example_body={"status": "in_progress", "assignee_id": "alice"},
        returns="Updated Task resource",
    ),
    Capability(
        intent="query tasks across all projects",
        method="GET",
        path="/tasks?assignee={id}&status={status}&milestone={id}",
        returns="list of Task resources matching filters",
    ),
]


@router.get("/")
def capabilities() -> dict:
    return build_catalog(
        service="Projects",
        description=(
            "Create and manage projects, tasks, and milestones for the business entity. "
            "All responses are wrapped in the agent response envelope; follow "
            "_suggested_next links to perform multi-step workflows."
        ),
        capabilities=_CAPABILITIES,
        related=["/projects", "/tasks", "/milestones"],
    )
