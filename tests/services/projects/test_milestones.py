from fastapi.testclient import TestClient

from services.projects.app import create_app


def _client(sqlite_path):
    return TestClient(create_app(sqlite_path=sqlite_path))


def _new_project(client) -> str:
    return client.post("/projects", json={"name": "P", "description": ""}).json()["data"]["id"]


def test_create_list_patch_milestones(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)

    created = client.post(
        f"/projects/{pid}/milestones",
        json={"title": "Design signoff", "due_date": "2026-06-01", "order_index": 1},
    )
    assert created.status_code == 201
    ms_id = created.json()["data"]["id"]
    assert created.json()["data"]["title"] == "Design signoff"

    listed = client.get(f"/projects/{pid}/milestones")
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == 1
    assert listed.json()["data"][0]["id"] == ms_id

    patched = client.patch(
        f"/milestones/{ms_id}",
        json={"status": "in_progress"},
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "in_progress"
