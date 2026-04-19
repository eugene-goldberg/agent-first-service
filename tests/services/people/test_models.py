import pytest
from pydantic import ValidationError

from services.people.models import CreatePerson, PersonOut


def test_create_person_accepts_valid_payload():
    payload = CreatePerson(
        name="Alice Chen",
        role="senior engineer",
        skills=["python", "langgraph"],
    )
    assert payload.name == "Alice Chen"
    assert payload.skills == ["python", "langgraph"]


def test_create_person_rejects_empty_name():
    with pytest.raises(ValidationError):
        CreatePerson(name="", role="engineer", skills=[])


def test_person_out_defaults():
    out = PersonOut(
        id="person_alice",
        name="Alice Chen",
        role="engineer",
        skills=["python"],
        available=True,
        current_load=0,
    )
    dumped = out.model_dump()
    assert dumped["available"] is True
    assert dumped["current_load"] == 0
