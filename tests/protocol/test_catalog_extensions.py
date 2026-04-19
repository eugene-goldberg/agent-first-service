"""Tests for the extended Capability schema and build_catalog service_name alias."""

import pytest

from agent_protocol.catalog import Capability, build_catalog


# ---------------------------------------------------------------------------
# Capability new optional fields
# ---------------------------------------------------------------------------

def test_capability_accepts_new_fields():
    cap = Capability(id="list_people", verb="GET", path="/people", summary="List all people", hints=["paginate"])
    assert cap.id == "list_people"
    assert cap.verb == "GET"
    assert cap.path == "/people"
    assert cap.summary == "List all people"
    assert cap.hints == ["paginate"]


def test_capability_new_fields_have_defaults():
    cap = Capability(intent="do something", method="POST", path="/x", returns="thing")
    assert cap.id is None
    assert cap.verb is None
    assert cap.summary is None
    assert cap.hints == []


def test_capability_all_fields_optional():
    cap = Capability()
    assert cap.intent is None
    assert cap.method is None
    assert cap.path is None
    assert cap.returns is None
    assert cap.example_body is None
    assert cap.id is None
    assert cap.verb is None
    assert cap.summary is None
    assert cap.hints == []


# ---------------------------------------------------------------------------
# build_catalog service_name alias
# ---------------------------------------------------------------------------

def test_build_catalog_accepts_service_name():
    caps = [Capability(id="list_people", verb="GET", path="/people", summary="List people")]
    doc = build_catalog(service_name="people", description="Manage people", capabilities=caps)
    assert doc["service"] == "people"
    assert doc["description"] == "Manage people"


def test_build_catalog_service_name_and_service_raises():
    caps = [Capability(id="x", verb="GET", path="/x", summary="x")]
    with pytest.raises(TypeError):
        build_catalog(service="A", service_name="B", description="desc", capabilities=caps)


def test_build_catalog_requires_one_of_service_or_service_name():
    caps = [Capability(id="x", verb="GET", path="/x", summary="x")]
    with pytest.raises(TypeError):
        build_catalog(description="desc", capabilities=caps)


# ---------------------------------------------------------------------------
# Capability payload shape: new fields only emit new keys; old fields only old keys
# ---------------------------------------------------------------------------

def test_new_shape_capability_payload_contains_only_new_fields():
    cap = Capability(id="list_people", verb="GET", path="/people", summary="List people", hints=["paginate"])
    doc = build_catalog(service_name="people", description="People service", capabilities=[cap])
    payload = doc["capabilities"][0]
    assert payload["id"] == "list_people"
    assert payload["verb"] == "GET"
    assert payload["path"] == "/people"
    assert payload["summary"] == "List people"
    assert payload["hints"] == ["paginate"]
    # old fields not supplied — must not appear
    assert "intent" not in payload
    assert "method" not in payload
    assert "returns" not in payload
    assert "example_body" not in payload


def test_old_shape_capability_payload_contains_only_old_fields():
    cap = Capability(intent="list projects", method="GET", path="/projects", returns="list of projects")
    doc = build_catalog(service="Projects", description="Project service", capabilities=[cap])
    payload = doc["capabilities"][0]
    assert payload["intent"] == "list projects"
    assert payload["method"] == "GET"
    assert payload["path"] == "/projects"
    assert payload["returns"] == "list of projects"
    # new fields not supplied — must not appear
    assert "id" not in payload
    assert "verb" not in payload
    assert "summary" not in payload
    assert "hints" not in payload


def test_empty_hints_list_not_emitted():
    cap = Capability(id="x", verb="GET", path="/x", summary="x")
    doc = build_catalog(service_name="svc", description="svc", capabilities=[cap])
    assert "hints" not in doc["capabilities"][0]
