from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agent_protocol.field_docs import DocumentedField


class CreatePerson(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = DocumentedField(
        description="Full name of the team member.",
        examples=["Alice Chen", "Bob Patel"],
        min_length=1,
    )
    role: str = DocumentedField(
        description="Job role or title, used for natural-language routing.",
        examples=["senior engineer", "product manager", "designer"],
        min_length=1,
    )
    skills: list[str] = DocumentedField(
        description="Free-form skill tags used to match people to project work.",
        examples=[["python", "langgraph"], ["figma", "accessibility"]],
        default_factory=list,
    )


class UpdatePerson(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    available: bool | None = DocumentedField(
        description="Whether the person can take on new work right now.",
        examples=[True, False],
        default=None,
    )
    current_load: int | None = DocumentedField(
        description="Current number of active assignments (>=0).",
        examples=[0, 3],
        default=None,
        ge=0,
    )
    skills: list[str] | None = DocumentedField(
        description="Full replacement list of skill tags.",
        examples=[["python", "fastapi"]],
        default=None,
    )


class PersonOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="Stable person identifier.")
    name: str
    role: str
    skills: list[str]
    available: bool
    current_load: int
