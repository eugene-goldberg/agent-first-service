from fastapi.testclient import TestClient

from services.projects.app import create_app


def _client(sqlite_path):
    return TestClient(create_app(sqlite_path=sqlite_path))


def test_project_not_found_returns_semantic_error(sqlite_path):
    client = _client(sqlite_path)
    r = client.get("/projects/proj_nope")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "project_not_found"
    assert "GET /projects" in body["_try_instead"]
    assert body["_related"] == ["/projects"]


def test_task_not_found_returns_semantic_error(sqlite_path):
    client = _client(sqlite_path)
    r = client.patch("/tasks/task_nope", json={"status": "done"})
    assert r.status_code == 404
    assert r.json()["error"] == "task_not_found"


def test_missing_project_when_creating_task_returns_422(sqlite_path):
    client = _client(sqlite_path)
    r = client.post("/projects/proj_nope/tasks", json={"title": "x"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "project_missing"
    assert "POST /projects" in body["_try_instead"]


def test_patch_project_with_unknown_fields_returns_400(sqlite_path):
    client = _client(sqlite_path)
    pid = client.post("/projects", json={"name": "p", "description": ""}).json()["data"]["id"]
    r = client.patch(f"/projects/{pid}", json={"owner": "alice"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "unknown_fields"
    assert "owner" in body["message"]
    assert body["_valid_values"] == ["description", "name"]
