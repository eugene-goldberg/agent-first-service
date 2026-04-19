from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


def make_response(
    *,
    data: Any,
    self_link: str,
    related: list[str] | None = None,
    suggested_next: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a plain dict envelope with underscored agent-facing keys.

    This is the Plan-2 convenience helper; AgentResponse (Plan 1) is unchanged.
    """
    return {
        "data": data,
        "_self": self_link,
        "_related": list(related or []),
        "_suggested_next": list(suggested_next or []),
        "_generated_at": datetime.now(timezone.utc).isoformat(),
    }


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
