import pytest
from pydantic import ValidationError

from services.projects.models import (
    CreateMilestone,
    CreateProject,
    CreateTask,
    MilestoneOut,
    ProjectOut,
    TaskOut,
    UpdateMilestone,
    UpdateTask,
)


def test_create_project_requires_name():
    with pytest.raises(ValidationError):
        CreateProject(description="no name")


def test_project_out_serialises_all_fields():
    p = ProjectOut(id="proj_1", name="Q3 Launch", description="Landing page")
    dumped = p.model_dump()
    assert dumped == {
        "id": "proj_1",
        "name": "Q3 Launch",
        "description": "Landing page",
    }


def test_task_out_includes_optional_fields():
    t = TaskOut(
        id="task_1",
        project_id="proj_1",
        title="copy",
        status="in_progress",
        assignee_id="alice",
        due_date="2026-05-20",
    )
    assert t.status == "in_progress"
    assert t.assignee_id == "alice"
    assert t.milestone_id is None


def test_update_task_allows_partial_payload():
    u = UpdateTask(status="done")
    assert u.status == "done"
    assert u.assignee_id is None
    assert u.due_date is None


def test_milestone_models_round_trip():
    m = CreateMilestone(title="Launch", status="planned", order_index=1)
    assert m.title == "Launch"

    out = MilestoneOut(
        id="ms_1",
        project_id="proj_1",
        title="Launch",
        status="planned",
        order_index=1,
    )
    assert out.model_dump()["title"] == "Launch"

    patch = UpdateMilestone(status="done")
    assert patch.status == "done"
