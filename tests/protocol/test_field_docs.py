import pytest
from pydantic import BaseModel, ValidationError

from agent_protocol.field_docs import DocumentedField


def test_documented_field_requires_description_and_examples():
    with pytest.raises(ValueError, match="description"):
        DocumentedField(description="", examples=["x"])

    with pytest.raises(ValueError, match="examples"):
        DocumentedField(description="a thing", examples=[])


def test_documented_field_exposes_description_and_examples_in_schema():
    class Project(BaseModel):
        name: str = DocumentedField(
            description="The project's short human-readable name.",
            examples=["Q3 Landing Page", "SSO rollout"],
        )

    schema = Project.model_json_schema()
    name_field = schema["properties"]["name"]
    assert name_field["description"].startswith("The project's short")
    assert name_field["examples"] == ["Q3 Landing Page", "SSO rollout"]


def test_documented_field_validates_payloads_normally():
    class Project(BaseModel):
        name: str = DocumentedField(description="x", examples=["y"])

    assert Project(name="hello").name == "hello"
    with pytest.raises(ValidationError):
        Project()
