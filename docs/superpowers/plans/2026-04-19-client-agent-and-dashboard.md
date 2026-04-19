# Client Agent & Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the loop. Build (a) a Client Agent service on port 8080 that accepts the presenter's typed natural-language brief and calls the orchestrator through its hypermedia catalog, and (b) a Next.js dashboard on port 3000 that shows both agents thinking live (five-panel layout with two SSE streams), plus the Makefile wiring needed to bring the full demo up with one command.

**Architecture:** The Client Agent is a thin Python FastAPI service (not a Next.js backend) that: receives a brief via `POST /client/briefs`, discovers the orchestrator's capabilities by GETing `http://127.0.0.1:8000/`, posts the brief to the orchestrator, then streams the orchestrator's trace. Its own reasoning is emitted as trace events on `/sse/client`. The Next.js dashboard is a single page that mounts two `EventSource` connections (one per agent) and renders a live timeline plus a read-only snapshot of each leaf service. No backend logic lives in Next.js; it is a thin viewer.

**Tech Stack:** Python 3.11 + FastAPI (Client Agent), Next.js 14 App Router + TypeScript + Tailwind CSS v3 (dashboard), `sse-starlette` (Client Agent SSE), Browser `EventSource` (dashboard).

**Spec:** `docs/superpowers/specs/2026-04-19-agent-first-services-design.md`

**Prerequisites:** Plans 1, 2, and 3 complete. All three leaf services and the orchestrator must be runnable and healthy.

---

## File structure for this plan

**Client Agent service:**
- `services/client_agent/__init__.py`
- `services/client_agent/main.py`
- `services/client_agent/app.py`
- `services/client_agent/models.py`
- `services/client_agent/state.py`
- `services/client_agent/llm.py`
- `services/client_agent/runner.py`
- `services/client_agent/trace_bus.py`
- `services/client_agent/routes/__init__.py`
- `services/client_agent/routes/capabilities.py`
- `services/client_agent/routes/briefs.py`
- `services/client_agent/routes/sse.py`

**Client Agent LLM fixtures:**
- `fixtures/llm_recordings/client_landing_page/discover.json`
- `fixtures/llm_recordings/client_landing_page/decide.json`
- `fixtures/llm_recordings/client_landing_page/summarize.json`

**Dashboard (Next.js):**
- `dashboard/package.json`
- `dashboard/tsconfig.json`
- `dashboard/next.config.mjs`
- `dashboard/tailwind.config.ts`
- `dashboard/postcss.config.mjs`
- `dashboard/app/layout.tsx`
- `dashboard/app/page.tsx`
- `dashboard/app/globals.css`
- `dashboard/components/BriefPanel.tsx`
- `dashboard/components/TracePanel.tsx`
- `dashboard/components/ServiceSnapshot.tsx`
- `dashboard/components/TraceEvent.tsx`
- `dashboard/lib/useTraceStream.ts`
- `dashboard/lib/useServiceSnapshot.ts`
- `dashboard/lib/types.ts`

**Tests (Client Agent):**
- `tests/services/client_agent/__init__.py`
- `tests/services/client_agent/conftest.py`
- `tests/services/client_agent/test_capabilities.py`
- `tests/services/client_agent/test_briefs_endpoint.py`
- `tests/services/client_agent/test_runner_replay.py`
- `tests/services/client_agent/test_sse_stream.py`
- `tests/services/client_agent/test_constraint_errors.py`

**Modified:**
- `Makefile` (add `run-client`, `run-dashboard`, `run-demo`, `test-client-agent`, `test-all-python`)
- `.env.example` (add `ORCHESTRATOR_BASE_URL`, `CLIENT_AGENT_REPLAY_DIR`, `NEXT_PUBLIC_CLIENT_AGENT_URL`, `NEXT_PUBLIC_ORCHESTRATOR_URL`)
- `docs/test_inventory.md` (append)
- `docs/implementation_status.md` (append)

---

## Task 1: Client Agent — state, trace bus, LLM client

**Files:**
- Create: `services/client_agent/__init__.py` (empty)
- Create: `services/client_agent/state.py`
- Create: `services/client_agent/trace_bus.py`
- Create: `services/client_agent/llm.py`
- Create: `tests/services/client_agent/__init__.py` (empty)
- Create: `tests/services/client_agent/test_state_bus_llm.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/client_agent/test_state_bus_llm.py`:

```python
import asyncio
import json
import os

import pytest

from services.client_agent.llm import ClientLLMClient, ClientReplayLLM, ClientReplayMiss
from services.client_agent.state import ClientBriefState, ClientTraceEvent
from services.client_agent.trace_bus import ClientTraceBus


def test_client_brief_state_defaults():
    state = ClientBriefState(brief_id="cb_1", brief="do the thing")
    assert state.orchestration_job_id is None
    assert state.trace == []
    assert state.status == "pending"


def test_client_trace_event_has_kind():
    ev = ClientTraceEvent(brief_id="cb_1", kind="discovery", summary="GET /")
    assert ev.kind == "discovery"


@pytest.mark.asyncio
async def test_client_trace_bus_fanout():
    bus = ClientTraceBus()

    async def consume():
        async with bus.subscribe() as q:
            return await q.get()

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)

    await bus.publish(ClientTraceEvent(brief_id="cb_1", kind="decision", summary="x"))
    got = await asyncio.wait_for(task, timeout=1.0)
    assert got.summary == "x"


def test_client_replay_llm_reads_recording(tmp_path):
    rec = tmp_path / "discover.json"
    rec.write_text(json.dumps({
        "messages": [],
        "response": {"content": "hello"},
    }))

    client = ClientReplayLLM(recordings_dir=str(tmp_path))
    out = client.invoke(step="discover", messages=[])
    assert out["content"] == "hello"


def test_client_replay_llm_miss_raises(tmp_path):
    client = ClientReplayLLM(recordings_dir=str(tmp_path))
    with pytest.raises(ClientReplayMiss):
        client.invoke(step="missing", messages=[])


def test_client_llm_factory_picks_replay_when_env_set(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    client = ClientLLMClient.from_env()
    assert isinstance(client, ClientReplayLLM)
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_state_bus_llm.py -v`
Expected: ERROR — module imports fail.

- [ ] **Step 3: Implement `services/client_agent/state.py`**

Create `services/client_agent/state.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ClientTraceKind = Literal["discovery", "decision", "invocation", "observation", "summary", "error"]


class ClientTraceEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brief_id: str
    kind: ClientTraceKind
    summary: str = Field(..., description="One-line human-readable summary.")
    detail: dict[str, Any] = Field(default_factory=dict)
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClientBriefState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    brief_id: str
    brief: str
    orchestration_job_id: str | None = None
    trace: list[ClientTraceEvent] = Field(default_factory=list)
    status: str = "pending"
    final_summary: str | None = None
```

- [ ] **Step 4: Implement `services/client_agent/trace_bus.py`**

Create `services/client_agent/trace_bus.py`:

```python
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from services.client_agent.state import ClientTraceEvent


class ClientTraceBus:
    """Same shape as the orchestrator's TraceBus but for the client agent's own
    thinking. Kept in its own module so the two services stay independent."""

    def __init__(self) -> None:
        self._subs: set[asyncio.Queue[ClientTraceEvent]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: ClientTraceEvent) -> None:
        async with self._lock:
            targets = list(self._subs)
        for q in targets:
            await q.put(event)

    @asynccontextmanager
    async def subscribe(self):
        queue: asyncio.Queue[ClientTraceEvent] = asyncio.Queue()
        async with self._lock:
            self._subs.add(queue)
        try:
            yield queue
        finally:
            async with self._lock:
                self._subs.discard(queue)

    def subscriber_count(self) -> int:
        return len(self._subs)
```

- [ ] **Step 5: Implement `services/client_agent/llm.py`**

Create `services/client_agent/llm.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


class ClientReplayMiss(RuntimeError):
    pass


class ClientLLMClient:
    @classmethod
    def from_env(cls) -> "ClientLLMClient":
        replay_dir = os.environ.get("CLIENT_AGENT_REPLAY_DIR", "").strip()
        if replay_dir:
            return ClientReplayLLM(recordings_dir=replay_dir)
        return ClientAzureLLM.from_env()

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        raise NotImplementedError


class ClientReplayLLM(ClientLLMClient):
    def __init__(self, recordings_dir: str) -> None:
        self.dir = Path(recordings_dir)

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        path = self.dir / f"{step}.json"
        if not path.exists():
            raise ClientReplayMiss(
                f"No recorded response for client step={step!r} at {path}."
            )
        return json.loads(path.read_text(encoding="utf-8"))["response"]


class ClientAzureLLM(ClientLLMClient):
    def __init__(self, *, endpoint: str, api_key: str, deployment: str, api_version: str) -> None:
        from langchain_openai import AzureChatOpenAI

        self._client = AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            azure_deployment=deployment,
            api_version=api_version,
            temperature=0,
        )

    @classmethod
    def from_env(cls) -> "ClientAzureLLM":
        required = {
            "AZURE_OPENAI_ENDPOINT": os.environ.get("AZURE_OPENAI_ENDPOINT"),
            "AZURE_OPENAI_API_KEY": os.environ.get("AZURE_OPENAI_API_KEY"),
            "AZURE_OPENAI_DEPLOYMENT": os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
            "AZURE_OPENAI_API_VERSION": os.environ.get("AZURE_OPENAI_API_VERSION"),
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(
                f"Azure OpenAI config incomplete for client agent: missing {', '.join(missing)}. "
                f"Set CLIENT_AGENT_REPLAY_DIR to run offline."
            )
        return cls(
            endpoint=required["AZURE_OPENAI_ENDPOINT"],
            api_key=required["AZURE_OPENAI_API_KEY"],
            deployment=required["AZURE_OPENAI_DEPLOYMENT"],
            api_version=required["AZURE_OPENAI_API_VERSION"],
        )

    def invoke(self, *, step: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        lc = []
        for m in messages:
            role = m["role"]
            if role == "system":
                lc.append(SystemMessage(content=m["content"]))
            elif role == "user":
                lc.append(HumanMessage(content=m["content"]))
            elif role == "assistant":
                lc.append(AIMessage(content=m["content"]))
            else:
                raise ValueError(f"Unknown role {role!r}")
        result = self._client.invoke(lc)
        return {"content": result.content}
```

- [ ] **Step 6: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_state_bus_llm.py -v`
Expected: 6 passed.

- [ ] **Step 7: Commit**

```bash
git add services/client_agent/__init__.py services/client_agent/state.py services/client_agent/trace_bus.py services/client_agent/llm.py tests/services/client_agent/__init__.py tests/services/client_agent/test_state_bus_llm.py
git commit -m "feat(client_agent): add state, trace bus, and pluggable LLM client"
```

---

## Task 2: Client Agent — LLM fixtures for the landing-page scenario

**Files:**
- Create: `fixtures/llm_recordings/client_landing_page/discover.json`
- Create: `fixtures/llm_recordings/client_landing_page/decide.json`
- Create: `fixtures/llm_recordings/client_landing_page/summarize.json`

- [ ] **Step 1: Write `discover.json`**

Create `fixtures/llm_recordings/client_landing_page/discover.json`:

```json
{
  "messages": [
    {"role": "system", "content": "discovery"},
    {"role": "user", "content": "The orchestrator exposes this capability catalog at GET /."}
  ],
  "response": {
    "content": "The orchestrator advertises `start_orchestration` at POST /orchestrations. That matches the user's brief — I'll post the brief there and then watch its trace."
  }
}
```

- [ ] **Step 2: Write `decide.json`**

Create `fixtures/llm_recordings/client_landing_page/decide.json`:

```json
{
  "messages": [
    {"role": "system", "content": "decision"}
  ],
  "response": {
    "content": "{\"action\":\"post_orchestration\",\"url\":\"/orchestrations\",\"body\":{\"brief\":\"<pass-through>\"},\"rationale\":\"Orchestrator is the right next hop; forward the user brief unchanged.\"}"
  }
}
```

- [ ] **Step 3: Write `summarize.json`**

Create `fixtures/llm_recordings/client_landing_page/summarize.json`:

```json
{
  "messages": [
    {"role": "system", "content": "summary"}
  ],
  "response": {
    "content": "I forwarded the brief to the orchestrator and watched it create the Q3 landing page project, assign a copywriter, and notify them. All steps succeeded."
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add fixtures/llm_recordings/client_landing_page/
git commit -m "test(client_agent): add recorded LLM fixtures for landing-page scenario"
```

---

## Task 3: Client Agent — runner that calls the orchestrator

**Files:**
- Create: `services/client_agent/runner.py`
- Create: `services/client_agent/models.py`
- Create: `tests/services/client_agent/conftest.py`
- Create: `tests/services/client_agent/test_runner_replay.py`

- [ ] **Step 1: Implement `services/client_agent/models.py`**

Create `services/client_agent/models.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from agent_protocol.field_docs import DocumentedField


class CreateBrief(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brief: str = DocumentedField(
        description="Natural-language work request typed by the presenter.",
        examples=[
            "Build a marketing landing page for our Q3 launch.",
            "Find someone with design skill who has bandwidth.",
        ],
        min_length=1,
    )


class BriefOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    brief: str
    status: str
    orchestration_job_id: str | None
    final_summary: str | None


class ClientTraceEventOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brief_id: str
    kind: str
    summary: str
    detail: dict[str, Any]
    at: datetime
```

- [ ] **Step 2: Write failing runner test**

Create `tests/services/client_agent/conftest.py`:

```python
import pytest
import httpx

from services.orchestrator.app import create_app as create_orch_app


@pytest.fixture
def orchestrator_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    app = create_orch_app(sqlite_path=str(tmp_path / "o.db"))
    return app


@pytest.fixture
async def orchestrator_transport(orchestrator_app):
    transport = httpx.ASGITransport(app=orchestrator_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        yield client
```

Create `tests/services/client_agent/test_runner_replay.py`:

```python
import uuid

import pytest

from services.client_agent.llm import ClientReplayLLM
from services.client_agent.runner import ClientAgentRunner
from services.client_agent.state import ClientBriefState
from services.client_agent.trace_bus import ClientTraceBus


@pytest.mark.asyncio
async def test_runner_discovers_orchestrator_and_forwards_brief(orchestrator_transport):
    bus = ClientTraceBus()
    llm = ClientReplayLLM(recordings_dir="fixtures/llm_recordings/client_landing_page")

    runner = ClientAgentRunner(
        llm=llm,
        bus=bus,
        http_client=orchestrator_transport,
        orchestrator_base="http://127.0.0.1:8000",
    )

    state = ClientBriefState(
        brief_id=f"cb_{uuid.uuid4().hex[:6]}",
        brief="Build a marketing landing page for our Q3 launch.",
    )

    result = await runner.run(state)
    assert result.orchestration_job_id is not None
    kinds = [e.kind for e in result.trace]
    assert kinds[0] == "discovery"
    assert "decision" in kinds
    assert "invocation" in kinds
    assert kinds[-1] == "summary"
    assert result.final_summary is not None
```

- [ ] **Step 3: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_runner_replay.py -v`
Expected: ERROR — `ModuleNotFoundError: No module named 'services.client_agent.runner'`

- [ ] **Step 4: Implement `services/client_agent/runner.py`**

Create `services/client_agent/runner.py`:

```python
from __future__ import annotations

import json
from typing import Any, Callable, Awaitable

import httpx

from services.client_agent.llm import ClientLLMClient
from services.client_agent.state import ClientBriefState, ClientTraceEvent
from services.client_agent.trace_bus import ClientTraceBus


DISCOVERY_SYSTEM = """You are the client agent. Your only protocol contract is:
the orchestrator advertises its capabilities at GET /. Read the catalog and
identify which capability is the right next hop for the user's brief.
Respond with one short paragraph of reasoning."""


DECISION_SYSTEM = """Emit a JSON object of the form:
{"action": "post_orchestration", "url": "/orchestrations",
 "body": {"brief": "<pass-through>"}, "rationale": "..."}

Keep it minimal. The pass-through token `<pass-through>` means the user's
brief should be substituted verbatim before sending."""


SUMMARY_SYSTEM = """Summarize the user-visible outcome of this brief in one
paragraph of plain English. No markdown. No emojis."""


class ClientAgentRunner:
    def __init__(
        self,
        *,
        llm: ClientLLMClient,
        bus: ClientTraceBus,
        http_client: httpx.AsyncClient,
        orchestrator_base: str,
    ) -> None:
        self._llm = llm
        self._bus = bus
        self._http = http_client
        self._orchestrator_base = orchestrator_base.rstrip("/")

    async def run(
        self,
        state: ClientBriefState,
        *,
        persist_event: Callable[[ClientTraceEvent], Awaitable[None]] | None = None,
    ) -> ClientBriefState:
        async def emit(event: ClientTraceEvent) -> None:
            state.trace.append(event)
            await self._bus.publish(event)
            if persist_event is not None:
                await persist_event(event)

        # Step 1: discovery — read orchestrator catalog.
        catalog_resp = await self._http.get(f"{self._orchestrator_base}/")
        catalog = catalog_resp.json()
        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="discovery",
            summary=f"GET {self._orchestrator_base}/ → {len(catalog['data']['capabilities'])} capabilities",
            detail={"catalog_preview": [c["id"] for c in catalog["data"]["capabilities"]]},
        ))

        discover_resp = self._llm.invoke(
            step="discover",
            messages=[
                {"role": "system", "content": DISCOVERY_SYSTEM},
                {"role": "user", "content": json.dumps({"brief": state.brief, "catalog": catalog["data"]})},
            ],
        )
        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="discovery",
            summary="Reviewed orchestrator capabilities.",
            detail={"reasoning": discover_resp["content"]},
        ))

        # Step 2: decide what to do next.
        decide_resp = self._llm.invoke(
            step="decide",
            messages=[
                {"role": "system", "content": DECISION_SYSTEM},
                {"role": "user", "content": json.dumps({"brief": state.brief})},
            ],
        )
        decision = json.loads(decide_resp["content"])
        if decision["action"] != "post_orchestration":
            raise RuntimeError(f"Unsupported decision action: {decision['action']!r}")

        body = dict(decision["body"])
        if body.get("brief") == "<pass-through>":
            body["brief"] = state.brief

        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="decision",
            summary=f"Will POST {decision['url']} with the user's brief.",
            detail={"rationale": decision.get("rationale"), "body": body},
        ))

        # Step 3: invoke orchestrator.
        invoke_url = f"{self._orchestrator_base}{decision['url']}"
        invoke_resp = await self._http.post(invoke_url, json=body)
        invoke_body = invoke_resp.json()
        state.orchestration_job_id = invoke_body["data"]["id"]

        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="invocation",
            summary=f"POST {invoke_url} → job {state.orchestration_job_id}",
            detail={"status_code": invoke_resp.status_code, "response": invoke_body},
        ))

        # Step 4: summary.
        summary_resp = self._llm.invoke(
            step="summarize",
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM},
                {"role": "user", "content": json.dumps({
                    "brief": state.brief,
                    "orchestration_job_id": state.orchestration_job_id,
                })},
            ],
        )
        state.final_summary = summary_resp["content"].strip()
        state.status = "completed"
        await emit(ClientTraceEvent(
            brief_id=state.brief_id,
            kind="summary",
            summary=state.final_summary[:120],
            detail={"summary": state.final_summary},
        ))

        return state
```

- [ ] **Step 5: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_runner_replay.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add services/client_agent/models.py services/client_agent/runner.py tests/services/client_agent/conftest.py tests/services/client_agent/test_runner_replay.py
git commit -m "feat(client_agent): add runner that discovers orchestrator and forwards briefs"
```

---

## Task 4: Client Agent — app factory, capabilities, routes

**Files:**
- Create: `services/client_agent/app.py`
- Create: `services/client_agent/main.py`
- Create: `services/client_agent/routes/__init__.py` (empty)
- Create: `services/client_agent/routes/capabilities.py`
- Create: `services/client_agent/routes/briefs.py`
- Create: `services/client_agent/routes/sse.py`
- Create: `tests/services/client_agent/test_capabilities.py`
- Create: `tests/services/client_agent/test_briefs_endpoint.py`

- [ ] **Step 1: Implement capabilities router**

Create `services/client_agent/routes/capabilities.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Request

from agent_protocol.catalog import Capability, build_catalog
from agent_protocol.envelope import make_response

router = APIRouter()


CLIENT_AGENT_CAPABILITIES: list[Capability] = [
    Capability(
        id="submit_brief",
        verb="POST",
        path="/client/briefs",
        summary="Submit a natural-language work brief to the client agent.",
        hints=["Returns a brief id; subscribe to /sse/client for live reasoning."],
    ),
    Capability(
        id="list_briefs",
        verb="GET",
        path="/client/briefs",
        summary="List recent briefs submitted to the client agent.",
        hints=["Most recent first."],
    ),
    Capability(
        id="find_brief",
        verb="GET",
        path="/client/briefs/{brief_id}",
        summary="Fetch a brief's status and final summary.",
        hints=["Status values: pending, running, completed, failed."],
    ),
    Capability(
        id="trace_brief",
        verb="GET",
        path="/client/briefs/{brief_id}/trace",
        summary="Fetch the full reasoning trace for a brief.",
        hints=["Use /sse/client for live streaming."],
    ),
    Capability(
        id="stream_client_trace",
        verb="GET",
        path="/sse/client",
        summary="SSE stream of every client-agent reasoning event.",
        hints=["EventSource-compatible; each event is a JSON ClientTraceEvent."],
    ),
]


@router.get("/")
def root(request: Request):
    return make_response(
        data=build_catalog(
            service_name="client_agent",
            description=(
                "The 'user-facing' agent. Takes a natural-language brief, "
                "discovers the orchestrator's capabilities through the hypermedia "
                "protocol, forwards the brief, and streams a summary. The presenter "
                "types into its POST /client/briefs endpoint."
            ),
            capabilities=CLIENT_AGENT_CAPABILITIES,
        ),
        self_link=str(request.url),
        related=[
            {"rel": "orchestrator", "href": "http://127.0.0.1:8000/", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "submit_brief", "href": "/client/briefs", "verb": "POST",
             "example_body": {"brief": "Build a marketing landing page for our Q3 launch."}},
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
        ],
    )
```

- [ ] **Step 2: Stub `briefs.py` and `sse.py`**

Create `services/client_agent/routes/briefs.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
```

Create `services/client_agent/routes/sse.py`:

```python
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()
```

- [ ] **Step 3: Implement `services/client_agent/app.py`**

Create `services/client_agent/app.py`:

```python
from __future__ import annotations

import os

import httpx
from fastapi import FastAPI

from agent_protocol.errors import register_error_handler

from services.client_agent.llm import ClientLLMClient
from services.client_agent.routes import capabilities as capabilities_router
from services.client_agent.routes import briefs as briefs_router
from services.client_agent.routes import sse as sse_router
from services.client_agent.trace_bus import ClientTraceBus


def create_app(
    *,
    llm: ClientLLMClient | None = None,
    http_client: httpx.AsyncClient | None = None,
    orchestrator_base: str | None = None,
) -> FastAPI:
    if llm is None:
        llm = ClientLLMClient.from_env()
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=10.0)

    app = FastAPI(title="Client Agent", version="0.1.0")
    app.state.llm = llm
    app.state.http_client = http_client
    app.state.trace_bus = ClientTraceBus()
    app.state.briefs = {}  # brief_id → ClientBriefState (in-memory; no DB on the client agent)
    app.state.orchestrator_base = orchestrator_base or os.environ.get(
        "ORCHESTRATOR_BASE_URL", "http://127.0.0.1:8000"
    )

    @app.middleware("http")
    async def cors_headers(request, call_next):
        response = await call_next(request)
        response.headers["access-control-allow-origin"] = "*"
        response.headers["access-control-allow-methods"] = "GET, POST, PATCH, OPTIONS"
        response.headers["access-control-allow-headers"] = "*"
        return response

    register_error_handler(app)
    app.include_router(capabilities_router.router)
    app.include_router(briefs_router.router)
    app.include_router(sse_router.router)

    return app
```

- [ ] **Step 4: Implement `services/client_agent/main.py`**

Create `services/client_agent/main.py`:

```python
from __future__ import annotations

import argparse

import uvicorn

from services.client_agent.app import create_app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Write test for capabilities**

Create `tests/services/client_agent/test_capabilities.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_app(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    from services.client_agent.app import create_app
    return create_app()


def test_root_lists_client_agent_capabilities(client_app):
    client = TestClient(client_app)
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["service"] == "client_agent"
    ids = {c["id"] for c in body["data"]["capabilities"]}
    assert ids == {
        "submit_brief",
        "list_briefs",
        "find_brief",
        "trace_brief",
        "stream_client_trace",
    }
    related_rels = {r["rel"] for r in body["_related"]}
    assert "orchestrator" in related_rels
```

- [ ] **Step 6: Run test**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_capabilities.py -v`
Expected: 1 passed.

- [ ] **Step 7: Commit**

```bash
git add services/client_agent/app.py services/client_agent/main.py services/client_agent/routes/__init__.py services/client_agent/routes/capabilities.py services/client_agent/routes/briefs.py services/client_agent/routes/sse.py tests/services/client_agent/test_capabilities.py
git commit -m "feat(client_agent): add app factory, CORS middleware, capabilities catalog"
```

---

## Task 5: Client Agent — briefs endpoint

**Files:**
- Modify: `services/client_agent/routes/briefs.py`
- Create: `tests/services/client_agent/test_briefs_endpoint.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/client_agent/test_briefs_endpoint.py`:

```python
import asyncio

import pytest
import httpx

from services.orchestrator.app import create_app as create_orch_app


@pytest.fixture
def orchestrator_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    return create_orch_app(sqlite_path=str(tmp_path / "o.db"))


@pytest.fixture
def client_agent_with_local_orchestrator(orchestrator_app, monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    import httpx as _httpx

    from services.client_agent.app import create_app

    transport = _httpx.ASGITransport(app=orchestrator_app)
    http_client = _httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000")

    app = create_app(http_client=http_client, orchestrator_base="http://127.0.0.1:8000")
    return app


@pytest.mark.asyncio
async def test_submit_brief_returns_envelope(client_agent_with_local_orchestrator):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=client_agent_with_local_orchestrator),
                            base_url="http://testserver") as c:
        resp = await c.post("/client/briefs", json={"brief": "Build a landing page."})
        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["brief"] == "Build a landing page."
        assert body["data"]["status"] in {"pending", "running", "completed"}
        assert body["_self"].endswith(f"/client/briefs/{body['data']['id']}")
        suggested = {s["rel"] for s in body["_suggested_next"]}
        assert "find_brief" in suggested
        assert "stream_client_trace" in suggested


@pytest.mark.asyncio
async def test_get_missing_brief_returns_404_envelope(client_agent_with_local_orchestrator):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=client_agent_with_local_orchestrator),
                            base_url="http://testserver") as c:
        resp = await c.get("/client/briefs/nope")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"] == "brief_not_found"


@pytest.mark.asyncio
async def test_brief_completes_and_reports_orchestration_job_id(client_agent_with_local_orchestrator):
    from httpx import AsyncClient, ASGITransport

    async with AsyncClient(transport=ASGITransport(app=client_agent_with_local_orchestrator),
                            base_url="http://testserver") as c:
        resp = await c.post("/client/briefs", json={"brief": "Build a landing page."})
        brief_id = resp.json()["data"]["id"]

        # Give the background task a moment to run.
        for _ in range(20):
            await asyncio.sleep(0.05)
            get_resp = await c.get(f"/client/briefs/{brief_id}")
            if get_resp.json()["data"]["status"] == "completed":
                break
        assert get_resp.json()["data"]["status"] == "completed"
        assert get_resp.json()["data"]["orchestration_job_id"] is not None
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_briefs_endpoint.py -v`
Expected: FAIL — 404/405 from the stub router.

- [ ] **Step 3: Implement the real `briefs.py`**

Replace `services/client_agent/routes/briefs.py`:

```python
from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Request

from agent_protocol.envelope import make_response
from agent_protocol.errors import AgentError

from services.client_agent.models import BriefOut, ClientTraceEventOut, CreateBrief
from services.client_agent.runner import ClientAgentRunner
from services.client_agent.state import ClientBriefState

router = APIRouter()


def _out(state: ClientBriefState) -> BriefOut:
    return BriefOut(
        id=state.brief_id,
        brief=state.brief,
        status=state.status,
        orchestration_job_id=state.orchestration_job_id,
        final_summary=state.final_summary,
    )


@router.post("/client/briefs", status_code=202)
def submit_brief(payload: CreateBrief, request: Request):
    brief_id = f"cb_{uuid.uuid4().hex[:8]}"
    state = ClientBriefState(brief_id=brief_id, brief=payload.brief, status="running")
    request.app.state.briefs[brief_id] = state

    runner = ClientAgentRunner(
        llm=request.app.state.llm,
        bus=request.app.state.trace_bus,
        http_client=request.app.state.http_client,
        orchestrator_base=request.app.state.orchestrator_base,
    )

    async def _background():
        try:
            await runner.run(state)
        except Exception as exc:
            state.status = "failed"
            state.final_summary = f"Runner error: {exc!r}"

    asyncio.create_task(_background())

    return make_response(
        data=_out(state).model_dump(),
        self_link=str(request.url_for("find_brief", brief_id=brief_id)),
        related=[
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
            {"rel": "orchestrator", "href": request.app.state.orchestrator_base + "/", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "find_brief", "href": f"/client/briefs/{brief_id}", "verb": "GET"},
            {"rel": "trace_brief", "href": f"/client/briefs/{brief_id}/trace", "verb": "GET"},
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
        ],
    )


@router.get("/client/briefs/{brief_id}", name="find_brief")
def find_brief(brief_id: str, request: Request):
    state: ClientBriefState | None = request.app.state.briefs.get(brief_id)
    if state is None:
        raise AgentError(
            status_code=404,
            error="brief_not_found",
            message=f"No brief with id={brief_id!r}.",
            why="The id does not match any submitted brief.",
            try_instead={
                "rel": "list_briefs",
                "href": "/client/briefs",
                "verb": "GET",
                "hint": "List recent briefs to find the right id.",
            },
            related=[{"rel": "list_briefs", "href": "/client/briefs", "verb": "GET"}],
        )

    return make_response(
        data=_out(state).model_dump(),
        self_link=str(request.url),
        related=[
            {"rel": "trace_brief", "href": f"/client/briefs/{brief_id}/trace", "verb": "GET"},
            {"rel": "stream_client_trace", "href": "/sse/client", "verb": "GET"},
        ],
        suggested_next=[
            {"rel": "trace_brief", "href": f"/client/briefs/{brief_id}/trace", "verb": "GET"},
        ],
    )


@router.get("/client/briefs")
def list_briefs(request: Request):
    states: dict[str, ClientBriefState] = request.app.state.briefs
    out = [_out(s).model_dump() for s in states.values()]

    return make_response(
        data=out,
        self_link=str(request.url),
        related=[],
        suggested_next=[
            {"rel": "submit_brief", "href": "/client/briefs", "verb": "POST"},
        ],
    )


@router.get("/client/briefs/{brief_id}/trace", name="trace_brief")
def trace_brief(brief_id: str, request: Request):
    state: ClientBriefState | None = request.app.state.briefs.get(brief_id)
    if state is None:
        raise AgentError(
            status_code=404,
            error="brief_not_found",
            message=f"No brief with id={brief_id!r}.",
            why="The id does not match any submitted brief.",
            try_instead={
                "rel": "list_briefs",
                "href": "/client/briefs",
                "verb": "GET",
                "hint": "List recent briefs to find the right id.",
            },
            related=[{"rel": "list_briefs", "href": "/client/briefs", "verb": "GET"}],
        )

    events = [
        ClientTraceEventOut(
            brief_id=e.brief_id,
            kind=e.kind,
            summary=e.summary,
            detail=e.detail,
            at=e.at,
        ).model_dump(mode="json")
        for e in state.trace
    ]

    return make_response(
        data=events,
        self_link=str(request.url),
        related=[{"rel": "find_brief", "href": f"/client/briefs/{brief_id}", "verb": "GET"}],
        suggested_next=[],
    )
```

- [ ] **Step 4: Run test — verify it passes**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_briefs_endpoint.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add services/client_agent/routes/briefs.py tests/services/client_agent/test_briefs_endpoint.py
git commit -m "feat(client_agent): add POST/GET/LIST/TRACE briefs routes and background runner dispatch"
```

---

## Task 6: Client Agent — SSE stream

**Files:**
- Modify: `services/client_agent/routes/sse.py`
- Create: `tests/services/client_agent/test_sse_stream.py`

- [ ] **Step 1: Write failing test**

Create `tests/services/client_agent/test_sse_stream.py`:

```python
import asyncio
import json

import pytest
import httpx

from services.client_agent.state import ClientTraceEvent


@pytest.mark.asyncio
async def test_client_sse_delivers_published_events(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    from services.client_agent.app import create_app
    app = create_app()

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        async def reader():
            async with client.stream("GET", "/sse/client") as response:
                assert response.status_code == 200
                got = []
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        got.append(json.loads(line[len("data: ") :]))
                    if len(got) >= 2:
                        break
                return got

        task = asyncio.create_task(reader())
        await asyncio.sleep(0.1)

        bus = app.state.trace_bus
        await bus.publish(ClientTraceEvent(brief_id="b1", kind="discovery", summary="first"))
        await bus.publish(ClientTraceEvent(brief_id="b1", kind="decision", summary="second"))

        got = await asyncio.wait_for(task, timeout=2.0)
        assert [e["summary"] for e in got] == ["first", "second"]
```

- [ ] **Step 2: Run test — verify it fails**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_sse_stream.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Implement SSE router**

Replace `services/client_agent/routes/sse.py`:

```python
from __future__ import annotations

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/sse/client")
async def stream_client_trace(request: Request):
    bus = request.app.state.trace_bus

    async def event_generator():
        async with bus.subscribe() as queue:
            while True:
                if await request.is_disconnected():
                    break
                event = await queue.get()
                yield {
                    "event": event.kind,
                    "data": event.model_dump_json(),
                }

    return EventSourceResponse(event_generator())
```

- [ ] **Step 4: Run test**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_sse_stream.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add services/client_agent/routes/sse.py tests/services/client_agent/test_sse_stream.py
git commit -m "feat(client_agent): add /sse/client SSE stream"
```

---

## Task 7: Client Agent — constraint-error envelope tests

**Files:**
- Create: `tests/services/client_agent/test_constraint_errors.py`

- [ ] **Step 1: Write test**

Create `tests/services/client_agent/test_constraint_errors.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CLIENT_AGENT_REPLAY_DIR", "fixtures/llm_recordings/client_landing_page")
    from services.client_agent.app import create_app
    return TestClient(create_app())


def test_brief_not_found_envelope(client):
    resp = client.get("/client/briefs/missing")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] == "brief_not_found"
    assert body["_try_instead"]["href"] == "/client/briefs"


def test_trace_brief_not_found_envelope(client):
    resp = client.get("/client/briefs/missing/trace")
    assert resp.status_code == 404
    assert resp.json()["error"] == "brief_not_found"


def test_empty_brief_is_422(client):
    resp = client.post("/client/briefs", json={"brief": ""})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run test**

Run: `. .venv/bin/activate && pytest tests/services/client_agent/test_constraint_errors.py -v`
Expected: 3 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/services/client_agent/test_constraint_errors.py
git commit -m "test(client_agent): verify 404 / 422 envelope semantics"
```

---

## Task 8: Dashboard — scaffold Next.js project

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/next.config.mjs`
- Create: `dashboard/tailwind.config.ts`
- Create: `dashboard/postcss.config.mjs`
- Create: `dashboard/app/layout.tsx`
- Create: `dashboard/app/globals.css`
- Create: `dashboard/app/page.tsx` (minimal placeholder)

- [ ] **Step 1: Create `package.json`**

Create `dashboard/package.json`:

```json
{
  "name": "agent-first-dashboard",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "14.2.15",
    "react": "18.3.1",
    "react-dom": "18.3.1"
  },
  "devDependencies": {
    "@types/node": "20.11.30",
    "@types/react": "18.3.3",
    "@types/react-dom": "18.3.0",
    "autoprefixer": "10.4.19",
    "postcss": "8.4.38",
    "tailwindcss": "3.4.4",
    "typescript": "5.5.3"
  }
}
```

- [ ] **Step 2: Create `tsconfig.json`**

Create `dashboard/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "baseUrl": ".",
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create `next.config.mjs`**

Create `dashboard/next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
```

- [ ] **Step 4: Create Tailwind config**

Create `dashboard/tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        "trace-thought": "#60a5fa",
        "trace-action": "#f59e0b",
        "trace-observation": "#10b981",
        "trace-final": "#a855f7",
        "trace-error": "#ef4444",
      },
    },
  },
  plugins: [],
};

export default config;
```

Create `dashboard/postcss.config.mjs`:

```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: Create `globals.css`**

Create `dashboard/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  color-scheme: dark;
}

html, body {
  height: 100%;
  background: #0a0a0a;
  color: #e5e5e5;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
```

- [ ] **Step 6: Create `layout.tsx`**

Create `dashboard/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent-First Services — Live Demo",
  description: "Two agents cooperating through a self-describing API.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 7: Create placeholder `page.tsx`**

Create `dashboard/app/page.tsx`:

```tsx
export default function Page() {
  return (
    <main className="p-8">
      <h1 className="text-2xl">Dashboard scaffold — wired up in Task 9.</h1>
    </main>
  );
}
```

- [ ] **Step 8: Install deps and build**

Run:

```bash
cd dashboard && npm install
```

Expected: installation succeeds. Node modules installed.

Then:

```bash
cd dashboard && npm run build
```

Expected: Next.js builds without errors.

- [ ] **Step 9: Commit**

```bash
git add dashboard/
git commit -m "feat(dashboard): scaffold Next.js 14 app with Tailwind"
```

Note: `dashboard/node_modules` should be in `.gitignore` — update the root `.gitignore` to include `dashboard/node_modules` and `dashboard/.next` if not already.

---

## Task 9: Dashboard — types and SSE hooks

**Files:**
- Create: `dashboard/lib/types.ts`
- Create: `dashboard/lib/useTraceStream.ts`
- Create: `dashboard/lib/useServiceSnapshot.ts`

- [ ] **Step 1: Define types**

Create `dashboard/lib/types.ts`:

```typescript
export type TraceKind =
  | "thought"
  | "action"
  | "observation"
  | "final"
  | "error"
  | "discovery"
  | "decision"
  | "invocation"
  | "summary";

export interface TraceEvent {
  brief_id?: string;
  job_id?: string;
  kind: TraceKind;
  summary: string;
  detail: Record<string, unknown>;
  at: string;
}

export interface CapabilityCatalog {
  service: string;
  description: string;
  capabilities: Array<{
    id: string;
    verb: string;
    path: string;
    summary: string;
    hints?: string[];
  }>;
}

export interface Envelope<T> {
  data: T;
  _self: string;
  _related: Array<{ rel: string; href: string; verb: string }>;
  _suggested_next: Array<{ rel: string; href: string; verb: string; example_body?: unknown }>;
  _generated_at: string;
}
```

- [ ] **Step 2: Implement `useTraceStream`**

Create `dashboard/lib/useTraceStream.ts`:

```typescript
"use client";

import { useEffect, useRef, useState } from "react";

import type { TraceEvent } from "./types";

export function useTraceStream(url: string): {
  events: TraceEvent[];
  connected: boolean;
} {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const src = new EventSource(url);
    sourceRef.current = src;

    src.onopen = () => setConnected(true);
    src.onerror = () => setConnected(false);

    const handler = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as TraceEvent;
        setEvents((prev) => [...prev, payload]);
      } catch {
        // ignore malformed payloads
      }
    };

    const kinds = [
      "thought", "action", "observation", "final", "error",
      "discovery", "decision", "invocation", "summary",
    ];
    kinds.forEach((k) => src.addEventListener(k, handler));
    src.addEventListener("message", handler);

    return () => {
      src.close();
    };
  }, [url]);

  return { events, connected };
}
```

- [ ] **Step 3: Implement `useServiceSnapshot`**

Create `dashboard/lib/useServiceSnapshot.ts`:

```typescript
"use client";

import { useEffect, useState } from "react";

import type { CapabilityCatalog, Envelope } from "./types";

export function useServiceSnapshot(url: string, refreshMs = 3000) {
  const [catalog, setCatalog] = useState<CapabilityCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchOnce() {
      try {
        const resp = await fetch(url, { cache: "no-store" });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        const body = (await resp.json()) as Envelope<CapabilityCatalog>;
        if (!cancelled) {
          setCatalog(body.data);
          setError(null);
        }
      } catch (e) {
        if (!cancelled) setError(String(e));
      }
    }

    fetchOnce();
    const id = setInterval(fetchOnce, refreshMs);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [url, refreshMs]);

  return { catalog, error };
}
```

- [ ] **Step 4: Commit**

```bash
git add dashboard/lib/
git commit -m "feat(dashboard): add TraceEvent types and useTraceStream / useServiceSnapshot hooks"
```

---

## Task 10: Dashboard — components and page layout

**Files:**
- Create: `dashboard/components/BriefPanel.tsx`
- Create: `dashboard/components/TraceEvent.tsx`
- Create: `dashboard/components/TracePanel.tsx`
- Create: `dashboard/components/ServiceSnapshot.tsx`
- Modify: `dashboard/app/page.tsx`

- [ ] **Step 1: `TraceEvent.tsx`**

Create `dashboard/components/TraceEvent.tsx`:

```tsx
"use client";

import { useState } from "react";

import type { TraceEvent as TraceEventT } from "@/lib/types";

const KIND_COLOR: Record<string, string> = {
  thought: "text-blue-400 border-blue-400/40",
  action: "text-amber-400 border-amber-400/40",
  observation: "text-emerald-400 border-emerald-400/40",
  final: "text-purple-400 border-purple-400/40",
  error: "text-red-400 border-red-400/40",
  discovery: "text-cyan-400 border-cyan-400/40",
  decision: "text-amber-400 border-amber-400/40",
  invocation: "text-emerald-400 border-emerald-400/40",
  summary: "text-purple-400 border-purple-400/40",
};

export function TraceEventRow({ event }: { event: TraceEventT }) {
  const [expanded, setExpanded] = useState(false);
  const color = KIND_COLOR[event.kind] ?? "text-gray-400 border-gray-500/40";
  const ts = new Date(event.at).toLocaleTimeString();

  return (
    <div className={`border-l-2 pl-3 py-2 mb-1 ${color}`}>
      <button
        className="w-full text-left"
        onClick={() => setExpanded((v) => !v)}
      >
        <div className="flex gap-3 text-xs">
          <span className="uppercase tracking-wider opacity-80 w-24 shrink-0">
            {event.kind}
          </span>
          <span className="opacity-60 shrink-0">{ts}</span>
          <span className="truncate">{event.summary}</span>
        </div>
      </button>
      {expanded && (
        <pre className="mt-2 text-[11px] opacity-75 whitespace-pre-wrap break-all bg-black/30 p-2 rounded">
          {JSON.stringify(event.detail, null, 2)}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 2: `TracePanel.tsx`**

Create `dashboard/components/TracePanel.tsx`:

```tsx
"use client";

import { useTraceStream } from "@/lib/useTraceStream";
import { TraceEventRow } from "./TraceEvent";

export function TracePanel({ title, url }: { title: string; url: string }) {
  const { events, connected } = useTraceStream(url);

  return (
    <div className="flex flex-col h-full border border-gray-800 rounded-lg overflow-hidden">
      <header className="flex items-center justify-between px-4 py-2 border-b border-gray-800 bg-black/40">
        <h2 className="text-sm uppercase tracking-wider">{title}</h2>
        <span
          className={`text-xs px-2 py-1 rounded ${
            connected ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"
          }`}
        >
          {connected ? "live" : "disconnected"}
        </span>
      </header>
      <div className="flex-1 overflow-y-auto p-3 text-sm">
        {events.length === 0 && (
          <p className="opacity-50 text-xs">Waiting for trace events…</p>
        )}
        {events.map((ev, i) => (
          <TraceEventRow event={ev} key={`${ev.at}-${i}`} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: `ServiceSnapshot.tsx`**

Create `dashboard/components/ServiceSnapshot.tsx`:

```tsx
"use client";

import { useServiceSnapshot } from "@/lib/useServiceSnapshot";

export function ServiceSnapshot({ title, url }: { title: string; url: string }) {
  const { catalog, error } = useServiceSnapshot(url);

  return (
    <div className="flex flex-col h-full border border-gray-800 rounded-lg overflow-hidden">
      <header className="px-3 py-2 border-b border-gray-800 bg-black/40">
        <h2 className="text-xs uppercase tracking-wider opacity-80">{title}</h2>
      </header>
      <div className="p-3 text-xs overflow-y-auto">
        {error && <p className="text-red-400">{error}</p>}
        {!catalog && !error && <p className="opacity-50">Loading…</p>}
        {catalog && (
          <>
            <p className="opacity-70 mb-2">{catalog.description}</p>
            <ul className="space-y-1">
              {catalog.capabilities.map((c) => (
                <li key={c.id} className="flex gap-2">
                  <span className="shrink-0 text-amber-400 font-semibold w-14">{c.verb}</span>
                  <code className="shrink-0 opacity-80">{c.path}</code>
                  <span className="opacity-60 truncate">{c.summary}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: `BriefPanel.tsx`**

Create `dashboard/components/BriefPanel.tsx`:

```tsx
"use client";

import { useState } from "react";

const CLIENT_AGENT_URL =
  process.env.NEXT_PUBLIC_CLIENT_AGENT_URL ?? "http://127.0.0.1:8080";

export function BriefPanel() {
  const [brief, setBrief] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setLastResult(null);
    try {
      const resp = await fetch(`${CLIENT_AGENT_URL}/client/briefs`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ brief }),
      });
      const body = await resp.json();
      setLastResult(`brief_id=${body.data.id}  status=${body.data.status}`);
      setBrief("");
    } catch (e) {
      setLastResult(`error: ${String(e)}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="h-full border border-gray-800 rounded-lg flex flex-col overflow-hidden">
      <header className="px-4 py-2 border-b border-gray-800 bg-black/40">
        <h2 className="text-sm uppercase tracking-wider">Presenter input</h2>
      </header>
      <form
        onSubmit={onSubmit}
        className="flex flex-col flex-1 p-4 gap-3"
      >
        <textarea
          className="flex-1 bg-black/40 border border-gray-800 rounded p-3 text-sm resize-none focus:outline-none focus:border-amber-400"
          placeholder="Type a brief like:  Build a marketing landing page for our Q3 launch."
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={4}
          disabled={submitting}
        />
        <div className="flex items-center justify-between">
          <button
            type="submit"
            disabled={submitting || !brief.trim()}
            className="px-4 py-2 bg-amber-500 text-black rounded text-sm font-semibold disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {submitting ? "Sending…" : "Send to client agent"}
          </button>
          {lastResult && (
            <span className="text-xs opacity-60">{lastResult}</span>
          )}
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 5: Replace `page.tsx` with the 5-panel layout**

Replace `dashboard/app/page.tsx`:

```tsx
import { BriefPanel } from "@/components/BriefPanel";
import { ServiceSnapshot } from "@/components/ServiceSnapshot";
import { TracePanel } from "@/components/TracePanel";

const CLIENT_AGENT_URL =
  process.env.NEXT_PUBLIC_CLIENT_AGENT_URL ?? "http://127.0.0.1:8080";
const ORCHESTRATOR_URL =
  process.env.NEXT_PUBLIC_ORCHESTRATOR_URL ?? "http://127.0.0.1:8000";
const PROJECTS_URL = "http://127.0.0.1:8001";
const PEOPLE_URL = "http://127.0.0.1:8002";
const COMMUNICATIONS_URL = "http://127.0.0.1:8003";

export default function Page() {
  return (
    <main className="h-screen grid grid-rows-[auto,1fr] gap-4 p-4">
      <header className="flex items-baseline gap-6">
        <h1 className="text-xl tracking-wide">Agent-First Services — Live Demo</h1>
        <span className="text-xs opacity-60">
          Two agents cooperating through a self-describing API.
        </span>
      </header>

      <div className="grid grid-cols-12 gap-4 min-h-0">
        <div className="col-span-4 min-h-0 grid grid-rows-[auto,1fr] gap-4">
          <div className="h-40">
            <BriefPanel />
          </div>
          <div className="min-h-0">
            <TracePanel title="Client agent — /sse/client" url={`${CLIENT_AGENT_URL}/sse/client`} />
          </div>
        </div>

        <div className="col-span-4 min-h-0">
          <TracePanel title="Orchestrator — /sse/orchestrator" url={`${ORCHESTRATOR_URL}/sse/orchestrator`} />
        </div>

        <div className="col-span-4 min-h-0 grid grid-rows-3 gap-4">
          <ServiceSnapshot title="Projects (:8001)" url={`${PROJECTS_URL}/`} />
          <ServiceSnapshot title="People (:8002)" url={`${PEOPLE_URL}/`} />
          <ServiceSnapshot title="Communications (:8003)" url={`${COMMUNICATIONS_URL}/`} />
        </div>
      </div>
    </main>
  );
}
```

- [ ] **Step 6: Rebuild the dashboard**

Run:

```bash
cd dashboard && npm run build
```

Expected: build completes with no TypeScript errors.

- [ ] **Step 7: Commit**

```bash
git add dashboard/components/ dashboard/app/page.tsx
git commit -m "feat(dashboard): add 5-panel layout (brief input, two trace streams, three service snapshots)"
```

---

## Task 11: Makefile — full demo orchestration

**Files:**
- Modify: `Makefile`
- Modify: `.env.example`
- Modify: `.gitignore`

- [ ] **Step 1: Append to `.env.example`**

Append:

```bash
# Client Agent
CLIENT_AGENT_REPLAY_DIR=fixtures/llm_recordings/client_landing_page
ORCHESTRATOR_BASE_URL=http://127.0.0.1:8000

# Dashboard (Next.js) — public env vars
NEXT_PUBLIC_CLIENT_AGENT_URL=http://127.0.0.1:8080
NEXT_PUBLIC_ORCHESTRATOR_URL=http://127.0.0.1:8000
```

- [ ] **Step 2: Append to `.gitignore`**

Append:

```
dashboard/node_modules/
dashboard/.next/
dashboard/out/
```

- [ ] **Step 3: Append Makefile targets**

Append to `Makefile`:

```makefile
run-client:
	. .venv/bin/activate && CLIENT_AGENT_REPLAY_DIR=fixtures/llm_recordings/client_landing_page python3 -m services.client_agent.main

run-dashboard:
	cd dashboard && npm run dev

test-client-agent:
	. .venv/bin/activate && pytest tests/services/client_agent -v

test-all-python:
	. .venv/bin/activate && pytest tests -v

run-demo:
	@echo "Open six shells and run:"
	@echo "  1)  make run-projects"
	@echo "  2)  make run-people"
	@echo "  3)  make run-communications"
	@echo "  4)  make run-orchestrator"
	@echo "  5)  make run-client"
	@echo "  6)  make run-dashboard"
	@echo ""
	@echo "Then open http://127.0.0.1:3000 in a browser."
```

- [ ] **Step 4: Commit**

```bash
git add Makefile .env.example .gitignore
git commit -m "chore: wire up run-demo Makefile target and dashboard env vars"
```

---

## Task 12: Full stack E2E smoke test (manual)

**Files:** none

- [ ] **Step 1: Start everything**

In six separate shells, run the six `make run-*` targets as listed in `make run-demo`.

- [ ] **Step 2: Verify the dashboard loads**

Open `http://127.0.0.1:3000/` in a browser. You should see:
- Presenter input panel (top-left).
- Client agent trace panel (bottom-left).
- Orchestrator trace panel (center).
- Projects / People / Communications capability snapshots (right column).

All three snapshots should load within a few seconds.

- [ ] **Step 3: Live demo run**

In the dashboard:
1. Type "Build a marketing landing page for our Q3 launch." into the presenter input.
2. Click "Send to client agent".
3. Watch the client agent panel emit `discovery`, `decision`, `invocation`, `summary` events.
4. Watch the orchestrator panel emit `thought`, `action`, `observation`, `final` events as the replayed LLM drives calls to the leaf services.
5. When the run completes, hit the three snapshot panels manually — they refresh every 3s automatically.

- [ ] **Step 4: Verify from the API side**

From a shell:

```bash
curl -s http://127.0.0.1:8080/client/briefs | python3 -m json.tool
```

Expected: list containing your brief with `status: completed`.

```bash
curl -s http://127.0.0.1:8080/client/briefs/<brief_id>/trace | python3 -m json.tool
```

Expected: the four client-agent trace events.

```bash
curl -s http://127.0.0.1:8000/orchestrations | python3 -m json.tool
```

Expected: the orchestration triggered by the client agent.

- [ ] **Step 5: Stop all processes**

Ctrl-C each shell. No commit — manual verification.

---

## Task 13: Documentation roll-up

**Files:**
- Modify: `docs/test_inventory.md`
- Modify: `docs/implementation_status.md`

- [ ] **Step 1: Append to `docs/test_inventory.md`**

Append:

```markdown
## Client Agent (`tests/services/client_agent/`)

| Test file | Covers | Type | Run |
|---|---|---|---|
| `test_state_bus_llm.py` | State, TraceBus, LLM replay factory | Unit / async | `pytest tests/services/client_agent/test_state_bus_llm.py -v` |
| `test_runner_replay.py` | Runner discovers + invokes orchestrator end-to-end | Integration (ASGITransport) | `pytest tests/services/client_agent/test_runner_replay.py -v` |
| `test_capabilities.py` | `GET /` client-agent catalog | Integration | `pytest tests/services/client_agent/test_capabilities.py -v` |
| `test_briefs_endpoint.py` | POST/GET/LIST briefs + background completion | Async integration | `pytest tests/services/client_agent/test_briefs_endpoint.py -v` |
| `test_sse_stream.py` | `/sse/client` streams published events | Async integration | `pytest tests/services/client_agent/test_sse_stream.py -v` |
| `test_constraint_errors.py` | 404 / 422 envelope semantics | Integration | `pytest tests/services/client_agent/test_constraint_errors.py -v` |

External deps: `CLIENT_AGENT_REPLAY_DIR` must point at `fixtures/llm_recordings/client_landing_page` for tests. For live Azure OpenAI, unset replay dir and set `AZURE_OPENAI_*`.

## Dashboard (Next.js, `dashboard/`)

The dashboard is a thin viewer with no unit tests in this plan. Its correctness is verified end-to-end during the manual demo (Task 12). The browser is the test harness:
- `npm run build` enforces TypeScript compilation; broken types fail the build.
- Runtime correctness is evaluated by watching trace events render live during the demo.
```

- [ ] **Step 2: Append to `docs/implementation_status.md`**

Append:

```markdown
## 2026-04-19 — Client Agent + Dashboard increment (Plan 4 complete)

**Plan:** `docs/superpowers/plans/2026-04-19-client-agent-and-dashboard.md`

**Completed:**
- Client Agent service on :8080 — state, trace bus, pluggable LLM (Azure + replay), runner that discovers the orchestrator via its catalog and forwards briefs, FastAPI routes (`POST /client/briefs`, `GET /client/briefs/{id}`, `GET /client/briefs/{id}/trace`, `GET /client/briefs`, `GET /sse/client`), and its own capability catalog at `GET /`.
- LLM recording fixtures for the client-agent landing-page scenario (discover/decide/summarize).
- Next.js dashboard (`dashboard/`) with 5-panel layout: presenter input, client-agent trace, orchestrator trace, and three leaf-service capability snapshots with auto-refresh. Dark-mode Tailwind UI with color-coded trace kinds.
- `run-demo` Makefile target and documented six-shell startup sequence.

**Evidence:**
- `pytest tests -v` runs all Python test suites (Plans 1–4) green. Target ≈ 94 tests.
- Manual Task 12 walked through live on dev machine; dashboard shows both SSE streams fan-out in real time.

**Demo is ready.** `make run-demo` prints the six commands to start; open `http://127.0.0.1:3000/` and type a brief.

**Next:** none — all four plans complete.
```

- [ ] **Step 3: Run full Python regression**

Run: `. .venv/bin/activate && pytest tests -v`
Expected: all Python tests green. Approximate totals across all four plans:
- Plan 1 Projects + agent_protocol: ~29
- Plan 2 leaf services: ~31
- Plan 3 orchestrator: ~18
- Plan 4 client agent: ~14
- **Grand total target: ~92 passed, 0 failed.**

- [ ] **Step 4: Commit**

```bash
git add docs/test_inventory.md docs/implementation_status.md
git commit -m "docs(demo): roll up test inventory and implementation status after Plan 4"
```

---

## Self-review checklist

1. **Spec coverage:**
   - Client Agent exists and is its own service (spec §6.6). ✓
   - Client Agent discovers orchestrator via GET / catalog (spec §6.2, §7). ✓
   - Dashboard shows both agents live on 5 panels (spec §6.7). ✓
   - Two distinct SSE channels: `/sse/client` + `/sse/orchestrator` (spec §6.6, §6.7). ✓
   - Presenter types the request live (spec §3.1 scenario). ✓
   - Client Agent exposes itself using same hypermedia protocol (spec §7). ✓

2. **Placeholder scan:** All code blocks complete. All URLs / env vars resolve. Fixture step names match `invoke(step=...)` calls. ✓

3. **Type consistency:**
   - `TraceEvent` interface in `dashboard/lib/types.ts` has both `job_id` and `brief_id` optional, matching the two agents' event shapes. ✓
   - `ClientBriefState.orchestration_job_id` is optional until the invocation step sets it. ✓
   - `ClientAgentRunner` writes `ClientTraceEvent(kind=…)` values that match the `ClientTraceKind` Literal. ✓
   - Dashboard `TraceEventRow` coloring map covers every kind emitted by both agents. ✓

4. **Ports and bases:**
   - Projects 8001, People 8002, Communications 8003, Orchestrator 8000, Client Agent 8080, Dashboard 3000. All match spec. ✓

5. **CORS:** Client Agent exposes `access-control-allow-origin: *` so the browser at :3000 can POST to :8080. ✓ Dashboard fetches leaf-service snapshots directly — they inherit from `agent_protocol/errors.py` (no CORS middleware there). If browser blocks, curl will still work; for the live demo, verify in Task 12 and add matching CORS to leaf services only if the browser surfaces errors. Leaf CORS is **out of scope** for this plan but acceptable as a follow-up.

---

## Definition of Done

- All client-agent tests pass; full `pytest tests -v` green across all four plans.
- `cd dashboard && npm run build` succeeds with zero TypeScript errors.
- Manual E2E (Task 12) completes: presenter types brief, both trace panels animate live, leaf snapshots stay current, the brief's final status is `completed`, the orchestration's final status is `completed`.
- `make run-demo` prints the six-shell sequence. Running those six commands plus opening `http://127.0.0.1:3000/` brings the full demo up from a clean checkout.
- `docs/test_inventory.md` and `docs/implementation_status.md` reflect the completed Plan 4 increment.

All four plans complete. The demo is stage-ready.
