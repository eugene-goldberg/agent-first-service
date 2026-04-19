from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_protocol.errors import AgentError, register_error_handler


def _build_app() -> FastAPI:
    app = FastAPI()
    register_error_handler(app)

    @app.get("/raise/validation")
    def raise_validation():
        raise AgentError(
            status_code=400,
            error="missing_required_field",
            message="field 'name' is required",
            why="the 'name' field was not present in the request body",
            try_instead="include a 'name' string in the request body",
            example={"name": "My Project"},
        )

    @app.get("/raise/conflict")
    def raise_conflict():
        raise AgentError(
            status_code=409,
            error="capacity_exceeded",
            message="person is overbooked",
            why="Alice is at 120% capacity for the requested window",
            try_instead="try Bob (65%) or Carol (80%) instead",
            valid_values=["bob", "carol"],
            related=["/people/search"],
        )

    return app


def test_agent_error_renders_full_envelope():
    client = TestClient(_build_app())

    r = client.get("/raise/validation")
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "missing_required_field"
    assert body["message"] == "field 'name' is required"
    assert body["_why"].startswith("the 'name' field")
    assert body["_try_instead"].startswith("include a 'name'")
    assert body["_example"] == {"name": "My Project"}


def test_agent_error_includes_optional_fields_only_when_set():
    client = TestClient(_build_app())

    r = client.get("/raise/conflict")
    assert r.status_code == 409
    body = r.json()
    assert body["_valid_values"] == ["bob", "carol"]
    assert body["_related"] == ["/people/search"]
    assert "_example" not in body
