from fastapi.testclient import TestClient

from services.projects.app import create_app
from services.projects.routes import tasks as task_routes


def _client(sqlite_path):
    return TestClient(create_app(sqlite_path=sqlite_path))


def _new_project(client) -> str:
    return client.post("/projects", json={"name": "P", "description": ""}).json()["data"]["id"]


def test_create_task_under_project(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)

    r = client.post(f"/projects/{pid}/tasks", json={"title": "write copy"})
    assert r.status_code == 201
    body = r.json()
    assert body["data"]["title"] == "write copy"
    assert body["data"]["status"] == "todo"
    assert body["_self"].startswith("/tasks/task_")
    assert "assign" in body["_suggested_next"]
    assert "update_status" in body["_suggested_next"]


def test_list_tasks_under_project(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)
    client.post(f"/projects/{pid}/tasks", json={"title": "a"})
    client.post(f"/projects/{pid}/tasks", json={"title": "b"})

    r = client.get(f"/projects/{pid}/tasks")
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]) == 2


def test_patch_task_updates_status_and_assignee(sqlite_path, monkeypatch):
    monkeypatch.setattr(task_routes, "_validate_assignee", lambda request, assignee_id: None)
    client = _client(sqlite_path)
    pid = _new_project(client)
    tid = client.post(f"/projects/{pid}/tasks", json={"title": "x"}).json()["data"]["id"]

    r = client.patch(f"/tasks/{tid}", json={"status": "in_progress", "assignee_id": "alice"})
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["status"] == "in_progress"
    assert body["data"]["assignee_id"] == "alice"


def test_filter_tasks_by_assignee_and_status(sqlite_path, monkeypatch):
    monkeypatch.setattr(task_routes, "_validate_assignee", lambda request, assignee_id: None)
    client = _client(sqlite_path)
    pid = _new_project(client)
    t1 = client.post(f"/projects/{pid}/tasks", json={"title": "a"}).json()["data"]["id"]
    t2 = client.post(f"/projects/{pid}/tasks", json={"title": "b"}).json()["data"]["id"]
    client.patch(f"/tasks/{t1}", json={"status": "done", "assignee_id": "alice"})
    client.patch(f"/tasks/{t2}", json={"status": "todo", "assignee_id": "alice"})

    r = client.get("/tasks", params={"assignee": "alice", "status": "done"})
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == t1


def test_create_task_with_milestone_and_filter_by_milestone(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)
    ms = client.post(
        f"/projects/{pid}/milestones",
        json={"title": "Phase 1", "order_index": 1},
    ).json()["data"]["id"]

    t1 = client.post(f"/projects/{pid}/tasks", json={"title": "a", "milestone_id": ms}).json()["data"]["id"]
    client.post(f"/projects/{pid}/tasks", json={"title": "b"})

    r = client.get("/tasks", params={"milestone": ms})
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == t1
    assert items[0]["milestone_id"] == ms


def test_create_task_rejects_invalid_assignee(sqlite_path, monkeypatch):
    class _Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            class _Resp:
                status_code = 404

                def json(self):
                    return {}

            return _Resp()

    monkeypatch.setattr(task_routes.httpx, "Client", _Client)
    client = _client(sqlite_path)
    pid = _new_project(client)

    r = client.post(
        f"/projects/{pid}/tasks",
        json={"title": "x", "assignee_id": "person_missing"},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "assignee_not_found"


def test_create_task_rejects_unavailable_assignee(sqlite_path, monkeypatch):
    class _Client:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url):
            class _Resp:
                status_code = 200

                def json(self):
                    return {"data": {"id": "person_1", "available": False}}

            return _Resp()

    monkeypatch.setattr(task_routes.httpx, "Client", _Client)
    client = _client(sqlite_path)
    pid = _new_project(client)
    r = client.post(
        f"/projects/{pid}/tasks",
        json={"title": "x", "assignee_id": "person_1"},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "assignee_unavailable"
