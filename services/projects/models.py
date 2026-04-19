from __future__ import annotations

from pydantic import BaseModel

from agent_protocol.field_docs import DocumentedField


class CreateProject(BaseModel):
    name: str = DocumentedField(
        description="Short human-readable name for the project.",
        examples=["Q3 Launch Landing Page", "SSO rollout"],
    )
    description: str = DocumentedField(
        description="One-paragraph description of the project's goal.",
        examples=["Marketing landing page for the Q3 launch campaign."],
        default="",
    )


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str


class CreateTask(BaseModel):
    title: str = DocumentedField(
        description="Short imperative task title.",
        examples=["Write landing page copy", "Implement hero section"],
    )
    assignee_id: str | None = DocumentedField(
        description="ID of the person assigned to this task. Null if unassigned.",
        examples=["alice", None],
        default=None,
    )
    due_date: str | None = DocumentedField(
        description="ISO 8601 date (YYYY-MM-DD) by which the task should be complete.",
        examples=["2026-05-20", None],
        default=None,
    )


class TaskOut(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    assignee_id: str | None = None
    due_date: str | None = None


class UpdateTask(BaseModel):
    status: str | None = DocumentedField(
        description="New task status.",
        examples=["todo", "in_progress", "done"],
        default=None,
    )
    assignee_id: str | None = DocumentedField(
        description="New assignee ID; set to null to unassign.",
        examples=["alice", None],
        default=None,
    )
    due_date: str | None = DocumentedField(
        description="New due date in ISO 8601 (YYYY-MM-DD).",
        examples=["2026-05-20"],
        default=None,
    )
