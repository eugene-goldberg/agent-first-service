from fastapi.testclient import TestClient

from services.projects.app import create_app


def test_capabilities_endpoint_returns_catalog(sqlite_path):
    app = create_app(sqlite_path=sqlite_path)
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200

    body = r.json()
    assert body["service"] == "Projects"
    assert body["_self"] == "/"
    assert body["_related"] == ["/projects", "/tasks"]
    assert isinstance(body["capabilities"], list)
    assert any(cap["path"] == "/projects" and cap["method"] == "POST"
               for cap in body["capabilities"])
    assert any(cap["path"] == "/projects/{id}/tasks" and cap["method"] == "POST"
               for cap in body["capabilities"])
