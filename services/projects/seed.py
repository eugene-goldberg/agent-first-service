from __future__ import annotations

import json
import pathlib

from sqlalchemy.orm import sessionmaker

from services.projects.db import MilestoneRow, ProjectRow, TaskRow


def load_seed(session_maker: sessionmaker, fixture_path: pathlib.Path | str) -> None:
    """Load a seed JSON file into the DB. Safe to call on an empty or primed DB:
    pre-existing rows with the same primary key are replaced.
    """

    data = json.loads(pathlib.Path(fixture_path).read_text())
    with session_maker() as s:
        for p in data.get("projects", []):
            project = s.get(ProjectRow, p["id"])
            if project is None:
                project = ProjectRow(id=p["id"], name=p["name"], description=p.get("description", ""))
                s.add(project)
            else:
                project.name = p["name"]
                project.description = p.get("description", "")

            for t in p.get("tasks", []):
                task = s.get(TaskRow, t["id"])
                if task is None:
                    task = TaskRow(
                        id=t["id"],
                        project_id=p["id"],
                        title=t["title"],
                        status=t.get("status", "todo"),
                        assignee_id=t.get("assignee_id"),
                        due_date=t.get("due_date"),
                    )
                    s.add(task)
                else:
                    task.title = t["title"]
                    task.status = t.get("status", "todo")
                    task.assignee_id = t.get("assignee_id")
                    task.due_date = t.get("due_date")

            for m in p.get("milestones", []):
                milestone = s.get(MilestoneRow, m["id"])
                if milestone is None:
                    milestone = MilestoneRow(
                        id=m["id"], project_id=p["id"], name=m["name"], due_date=m.get("due_date")
                    )
                    s.add(milestone)
                else:
                    milestone.name = m["name"]
                    milestone.due_date = m.get("due_date")
        s.commit()
