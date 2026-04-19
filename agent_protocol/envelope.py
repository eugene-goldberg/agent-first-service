from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AgentResponse(BaseModel, Generic[T]):
    """Envelope wrapping every success response with hypermedia discovery metadata.

    Attribute names are human-friendly; JSON aliases use leading underscores
    (`_self`, `_related`, `_suggested_next`, `_generated_at`) so the wire format
    makes agent-facing fields visually distinct from the business payload.
    """

    model_config = ConfigDict(populate_by_name=True)

    data: T
    self_link: str = Field(alias="_self")
    related: list[str] = Field(default_factory=list, alias="_related")
    suggested_next: dict[str, Any] = Field(
        default_factory=dict, alias="_suggested_next"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="_generated_at",
    )
