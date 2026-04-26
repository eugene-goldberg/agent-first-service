from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import httpx

from agent_protocol.local_env import load_local_env

@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def _check_http_json(client: httpx.Client, name: str, url: str) -> CheckResult:
    try:
        resp = client.get(url)
        if resp.status_code >= 400:
            return CheckResult(name=name, ok=False, detail=f"HTTP {resp.status_code} ({url})")
        return CheckResult(name=name, ok=True, detail=f"HTTP {resp.status_code} ({url})")
    except Exception as exc:  # pragma: no cover - network failure path
        return CheckResult(name=name, ok=False, detail=f"{type(exc).__name__}: {exc}")


def _check_sse_endpoint(client: httpx.Client, name: str, url: str) -> CheckResult:
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                return CheckResult(name=name, ok=False, detail=f"HTTP {resp.status_code} ({url})")
            content_type = resp.headers.get("content-type", "")
            if "text/event-stream" not in content_type:
                return CheckResult(
                    name=name,
                    ok=False,
                    detail=f"unexpected content-type {content_type!r} ({url})",
                )
            return CheckResult(name=name, ok=True, detail=f"HTTP {resp.status_code} ({url})")
    except Exception as exc:  # pragma: no cover - network failure path
        return CheckResult(name=name, ok=False, detail=f"{type(exc).__name__}: {exc}")


def _check_azure_env() -> CheckResult:
    required = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
    ]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        return CheckResult(
            name="Azure OpenAI env",
            ok=False,
            detail=f"missing {', '.join(missing)}",
        )
    return CheckResult(name="Azure OpenAI env", ok=True, detail="all required vars set")


def main() -> int:
    load_local_env(explicit_path=os.environ.get("AGENT_FIRST_ENV_FILE"))
    timeout = httpx.Timeout(2.5, connect=1.0)
    with httpx.Client(timeout=timeout) as client:
        results = [
            _check_sse_endpoint(client, "Projects MCP SSE (:9001)", "http://127.0.0.1:9001/sse"),
            _check_sse_endpoint(client, "People MCP SSE (:9002)", "http://127.0.0.1:9002/sse"),
            _check_sse_endpoint(
                client, "Communications MCP SSE (:9003)", "http://127.0.0.1:9003/sse"
            ),
            _check_http_json(client, "People HTTP (:8002)", "http://127.0.0.1:8002/people"),
            _check_http_json(client, "Orchestrator HTTP (:8000)", "http://127.0.0.1:8000/"),
            _check_http_json(client, "Client Agent HTTP (:8080)", "http://127.0.0.1:8080/"),
            _check_http_json(client, "Dashboard HTTP (:3000)", "http://127.0.0.1:3000/"),
            _check_azure_env(),
        ]

    failures = [r for r in results if not r.ok]
    for r in results:
        status = "OK " if r.ok else "ERR"
        print(f"[{status}] {r.name}: {r.detail}")

    if failures:
        print(f"\nLive stack check failed: {len(failures)} issue(s).")
        return 1

    print("\nLive stack check passed. You can submit briefs in the dashboard.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
