from fastapi.testclient import TestClient

from services.projects.app import create_app


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


def test_patch_task_updates_status_and_assignee(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)
    tid = client.post(f"/projects/{pid}/tasks", json={"title": "x"}).json()["data"]["id"]

    r = client.patch(f"/tasks/{tid}", json={"status": "in_progress", "assignee_id": "alice"})
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["status"] == "in_progress"
    assert body["data"]["assignee_id"] == "alice"


def test_filter_tasks_by_assignee_and_status(sqlite_path):
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
