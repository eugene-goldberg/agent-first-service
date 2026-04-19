from __future__ import annotations

from typing import Any

import httpx


class HTTPToolbox:
    """Generic HTTP tools exposed to the LLM. Only four: GET/POST/PATCH/DELETE.

    The LLM discovers URLs via the hypermedia protocol (capability catalog +
    `_suggested_next`). No service-specific tools are pre-registered — this
    is the whole point of the agent-first design.
    """

    def __init__(self, client: httpx.AsyncClient, timeout_seconds: float = 10.0) -> None:
        self._client = client
        self._timeout = timeout_seconds

    async def http_get(self, url: str) -> dict[str, Any]:
        return await self._request("GET", url, body=None)

    async def http_post(self, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("POST", url, body=body)

    async def http_patch(self, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("PATCH", url, body=body)

    async def http_delete(self, url: str) -> dict[str, Any]:
        return await self._request("DELETE", url, body=None)

    async def _request(
        self,
        method: str,
        url: str,
        *,
        body: dict[str, Any] | None,
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method,
                url,
                json=body,
                timeout=self._timeout,
            )
        except httpx.RequestError as exc:
            return {
                "status_code": 0,
                "body": {
                    "error": "transport_error",
                    "message": str(exc),
                    "_why": "The HTTP call failed before reaching the server.",
                },
            }

        try:
            parsed = response.json()
        except ValueError:
            parsed = {"raw_text": response.text}

        return {
            "status_code": response.status_code,
            "body": parsed,
        }
