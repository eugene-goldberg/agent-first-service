from fastapi.testclient import TestClient

from services.projects.app import create_app


def _client(sqlite_path):
    return TestClient(create_app(sqlite_path=sqlite_path))


def test_create_project_returns_envelope_and_suggested_next(sqlite_path):
    client = _client(sqlite_path)

    r = client.post("/projects", json={"name": "Q3 Launch", "description": "Landing page"})
    assert r.status_code == 201

    body = r.json()
    assert body["_self"].startswith("/projects/proj_")
    assert body["data"]["name"] == "Q3 Launch"
    assert "add_tasks" in body["_suggested_next"]
    assert body["_suggested_next"]["add_tasks"].endswith("/tasks")


def test_list_projects_returns_items_wrapped_in_envelope(sqlite_path):
    client = _client(sqlite_path)

    client.post("/projects", json={"name": "One", "description": "a"})
    client.post("/projects", json={"name": "Two", "description": "b"})

    r = client.get("/projects")
    assert r.status_code == 200
    body = r.json()
    assert body["_self"] == "/projects"
    assert len(body["data"]) == 2
    names = {p["name"] for p in body["data"]}
    assert names == {"One", "Two"}


def test_get_project_by_id(sqlite_path):
    client = _client(sqlite_path)
    created = client.post("/projects", json={"name": "Solo", "description": ""}).json()
    pid = created["data"]["id"]

    r = client.get(f"/projects/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["id"] == pid
    assert body["_self"] == f"/projects/{pid}"


def test_patch_project_updates_fields(sqlite_path):
    client = _client(sqlite_path)
    pid = client.post("/projects", json={"name": "Old", "description": "x"}).json()["data"]["id"]

    r = client.patch(f"/projects/{pid}", json={"name": "New"})
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "New"
    assert r.json()["data"]["description"] == "x"
