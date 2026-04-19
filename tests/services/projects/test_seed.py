import json

from fastapi.testclient import TestClient

from services.projects.app import create_app
from services.projects.seed import load_seed


def test_load_seed_populates_db(tmp_path, sqlite_path):
    fixture = tmp_path / "seed.json"
    fixture.write_text(json.dumps({
        "projects": [
            {"id": "proj_x", "name": "X", "description": "d",
             "tasks": [{"id": "task_x1", "title": "t", "status": "todo", "assignee_id": None, "due_date": None}],
             "milestones": []}
        ]
    }))

    app = create_app(sqlite_path=sqlite_path)
    load_seed(app.state.session_maker, fixture)

    client = TestClient(app)
    r = client.get("/projects/proj_x")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "X"

    r2 = client.get("/projects/proj_x/tasks")
    assert len(r2.json()["data"]) == 1
    assert r2.json()["data"][0]["id"] == "task_x1"
