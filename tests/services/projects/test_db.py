from services.projects.db import ProjectRow, TaskRow, MilestoneRow


def test_can_insert_project_task_milestone(session):
    proj = ProjectRow(id="proj_1", name="Demo", description="seed")
    task = TaskRow(
        id="task_1",
        project_id="proj_1",
        title="copy",
        status="todo",
        assignee_id=None,
    )
    milestone = MilestoneRow(id="ms_1", project_id="proj_1", name="v1 launch")

    session.add_all([proj, task, milestone])
    session.commit()

    assert session.get(ProjectRow, "proj_1").name == "Demo"
    assert session.get(TaskRow, "task_1").title == "copy"
    assert session.get(MilestoneRow, "ms_1").name == "v1 launch"


def test_task_status_defaults_to_todo(session):
    session.add(ProjectRow(id="p", name="n", description="d"))
    session.add(TaskRow(id="t", project_id="p", title="q"))
    session.commit()
    assert session.get(TaskRow, "t").status == "todo"
