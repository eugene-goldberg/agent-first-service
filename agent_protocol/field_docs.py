from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo


def DocumentedField(
    *,
    description: str,
    examples: list[Any],
    default: Any = ...,
    **kwargs: Any,
) -> FieldInfo:
    """Pydantic ``Field()`` wrapper enforcing non-empty description + examples.

    Using this instead of plain ``Field`` makes the agent protocol's documentation
    requirement explicit at the type level. Responses from services built with
    Pydantic models using this helper will produce rich OpenAPI / JSON Schema
    output that agents can reason about.
    """

    if not description or not description.strip():
        raise ValueError("description is required and must be non-empty")
    if not examples:
        raise ValueError("examples is required and must be non-empty")
    return Field(default, description=description, examples=examples, **kwargs)
