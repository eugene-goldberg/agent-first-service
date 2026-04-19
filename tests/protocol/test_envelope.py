from datetime import datetime

from pydantic import BaseModel

from agent_protocol.envelope import AgentResponse


class _Payload(BaseModel):
    id: str
    name: str


def test_envelope_wraps_payload_and_defaults():
    response = AgentResponse[_Payload](
        data=_Payload(id="proj_1", name="Demo"),
        self_link="/projects/proj_1",
    )

    assert response.data.id == "proj_1"
    assert response.self_link == "/projects/proj_1"
    assert response.related == []
    assert response.suggested_next == {}
    assert isinstance(response.generated_at, datetime)
    assert response.generated_at.tzinfo is not None


def test_envelope_serialises_with_underscore_aliases():
    response = AgentResponse[_Payload](
        data=_Payload(id="proj_1", name="Demo"),
        self_link="/projects/proj_1",
        related=["/projects"],
        suggested_next={"add_tasks": "/projects/proj_1/tasks"},
    )

    dumped = response.model_dump(by_alias=True, mode="json")

    assert dumped["_self"] == "/projects/proj_1"
    assert dumped["_related"] == ["/projects"]
    assert dumped["_suggested_next"] == {"add_tasks": "/projects/proj_1/tasks"}
    assert "_generated_at" in dumped
    assert dumped["data"]["id"] == "proj_1"


def test_envelope_accepts_underscore_aliases_as_input():
    response = AgentResponse[_Payload].model_validate(
        {
            "data": {"id": "proj_1", "name": "Demo"},
            "_self": "/projects/proj_1",
            "_related": ["/projects"],
        }
    )
    assert response.self_link == "/projects/proj_1"
    assert response.related == ["/projects"]
