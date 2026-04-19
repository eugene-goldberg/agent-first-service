from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AgentError(Exception):
    """Semantic error that renders as the agent error envelope.

    Fields marked optional are omitted from the response when not supplied,
    keeping responses minimal while still self-documenting.
    """

    def __init__(
        self,
        *,
        status_code: int,
        error: str,
        message: str,
        why: str,
        try_instead: str,
        valid_values: list[Any] | None = None,
        example: dict[str, Any] | None = None,
        related: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.why = why
        self.try_instead = try_instead
        self.valid_values = valid_values
        self.example = example
        self.related = related

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.error,
            "message": self.message,
            "_why": self.why,
            "_try_instead": self.try_instead,
        }
        if self.valid_values is not None:
            payload["_valid_values"] = self.valid_values
        if self.example is not None:
            payload["_example"] = self.example
        if self.related is not None:
            payload["_related"] = self.related
        return payload


def register_error_handler(app: FastAPI) -> None:
    @app.exception_handler(AgentError)
    async def _handle(request: Request, exc: AgentError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
