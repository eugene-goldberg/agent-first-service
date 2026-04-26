# Agent-First Services: Technical Briefing

A greenfield demo of an API design pattern in which the wire format is the contract —
not a separately maintained SDK, not a hand-written OpenAPI spec — so that an LLM
planner can discover, reason about, and navigate the API from first principles.

---

## 1. What "Agent-First" Means Here

A conventional REST API is designed for human-written client code. The contract lives
in documentation or an SDK that a developer reads, then hard-codes into a client. The
HTTP response carries the business payload; the developer's prior knowledge supplies
the navigation.

An agent-first API shifts that knowledge into the response itself. Every response
carries:

- a self-link so the agent always knows where it is,
- related links to adjacent resources,
- suggested-next actions with example bodies,
- a generated-at timestamp for cache reasoning.

Every service also serves its complete capability catalog at `GET /`, formatted so an
LLM can read it, select the right endpoint, and produce a well-formed request — with no
prior knowledge of this specific codebase.

The motivation is concrete: in the demo an orchestrator LLM receives a natural-language
brief such as "Build a marketing landing page for our Q3 launch." It must turn that into
a sequence of real HTTP calls. If the wire format does not tell it what endpoints exist,
the LLM will invent plausible-sounding ones (`/pages`, `/marketing`, `/launches`). The
catalog-injection pattern described in section 6 is the primary defence against that.

---

## 2. System Shape

```
Human brief (browser)
        |
        v
+-------------------+  :8080
|   client_agent    |  POST /client/briefs
|  (ClientAgent     |  GET  /sse/client          (SSE)
|   Runner)         |
+-------------------+
        |  POST /orchestrations
        v
+-------------------+  :8000
|   orchestrator    |  GET  /sse/orchestrator     (SSE)
|  (Orchestration   |  GET  /orchestrations/{id}
|   Graph: plan →   |
|   act → observe)  |
+-------------------+
     |        |        |
     v        v        v
:8001      :8002     :8003
projects   people  communications
(SQLite)  (SQLite)  (SQLite)

                            ^
                            |  EventSource x2  +  fetch /projects
+---------------------------+
|  Next.js dashboard :3000  |
|  3-column observer UI     |
+---------------------------+
```

All five Python services are FastAPI apps. The dashboard is a Next.js 14 app.
Inter-service calls are plain HTTP (`httpx.AsyncClient`). There is no message broker,
no service mesh, and no shared database.

---

## 3. The Hypermedia Envelope

Every success response from a leaf service or the orchestrator's own catalog uses one
of two shapes that share the same underscore-prefixed metadata keys.

The Pydantic model (`agent_protocol/envelope.py`):

```python
class AgentResponse(BaseModel, Generic[T]):
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
```

The plain-dict helper used by Plan-2 routes:

```python
def make_response(*, data, self_link, related=None, suggested_next=None):
    return {
        "data": data,
        "_self": self_link,
        "_related": list(related or []),
        "_suggested_next": list(suggested_next or []),
        "_generated_at": datetime.now(timezone.utc).isoformat(),
    }
```

A real response from `POST /projects` looks like:

```json
{
  "data": {
    "id": "proj_68c0de",
    "name": "Q3 Launch Landing Page",
    "description": "Marketing launch",
    "status": "active"
  },
  "_self": "/projects/proj_68c0de",
  "_related": ["/projects/proj_68c0de/tasks"],
  "_suggested_next": [
    {"rel": "add_task", "href": "/projects/proj_68c0de/tasks", "verb": "POST",
     "example_body": {"title": "Write copy"}}
  ],
  "_generated_at": "2026-04-20T14:22:05.123456+00:00"
}
```

The leading underscores are a deliberate visual signal. An LLM scanning this JSON can
immediately distinguish `data` (the business payload it should act on or return to the
user) from `_self`, `_related`, `_suggested_next`, `_generated_at` (protocol metadata
it should use for navigation decisions). No naming convention document is needed; the
punctuation is the convention.

---

## 4. The Capability Catalog at `GET /`

Every service — including the orchestrator — serves a capability catalog at `GET /`.
The catalog is built by `build_catalog()` in `agent_protocol/catalog.py` and uses the
`Capability` dataclass:

```python
@dataclass
class Capability:
    # Original fields (Plan 1)
    intent: str | None = None
    method: str | None = None
    path: str | None = None
    returns: str | None = None
    example_body: dict[str, Any] | None = None
    # New agent-facing fields (Plan 2)
    id: str | None = None
    verb: str | None = None
    summary: str | None = None
    hints: list[str] = field(default_factory=list)
```

The Projects service (`services/projects/routes/capabilities.py`) uses the Plan-1 shape
(`intent`, `method`, `path`, `returns`, `example_body`). The Orchestrator
(`services/orchestrator/routes/capabilities.py`) uses the Plan-2 shape
(`id`, `verb`, `summary`, `hints`) and wraps the result in `make_response()`.

Both shapes are intentionally supported. `build_catalog()` emits only non-None fields,
so a Plan-1 catalog and a Plan-2 catalog are structurally compatible — any consumer
that checks `verb or method` and `path` will work against either. The coexistence
documents the natural evolution of the protocol: new services gain the richer shape;
existing services are not broken.

A real `GET /` response from the orchestrator:

```json
{
  "data": {
    "service": "orchestrator",
    "description": "Agent-first orchestrator. Accepts natural-language briefs ...",
    "capabilities": [
      {
        "id": "start_orchestration",
        "verb": "POST",
        "path": "/orchestrations",
        "summary": "Start a new multi-step orchestration from a natural-language brief.",
        "hints": ["Returns a job id; poll /orchestrations/{id} or subscribe to /sse/orchestrator."]
      },
      {
        "id": "stream_trace",
        "verb": "GET",
        "path": "/sse/orchestrator",
        "summary": "Server-Sent Events stream of every orchestration's trace events.",
        "hints": ["EventSource-compatible; each event is a JSON-encoded TraceEvent."]
      }
    ],
    "_self": "/",
    "_related": [...]
  },
  "_self": "http://127.0.0.1:8000/",
  "_related": [...],
  "_suggested_next": [
    {"rel": "start_orchestration", "href": "/orchestrations", "verb": "POST",
     "example_body": {"brief": "Build a marketing landing page for our Q3 launch."}}
  ],
  "_generated_at": "2026-04-20T14:22:00.000000+00:00"
}
```

---

## 5. The Two-Agent Loop

When a human submits a brief through the dashboard, the following sequence runs:

**Client Agent** (`services/client_agent/runner.py`, `ClientAgentRunner.run()`):

1. `GET http://127.0.0.1:8000/` — reads the orchestrator's capability catalog.
2. LLM call (DISCOVERY_SYSTEM): reasons about which capability matches the brief.
3. LLM call (DECISION_SYSTEM): emits a JSON action object pointing at `POST /orchestrations`.
4. `POST /orchestrations {"brief": "<user text>"}` — creates a job, captures `job_id`.
5. LLM call (SUMMARY_SYSTEM): generates a user-facing summary paragraph.

Every step emits a `ClientTraceEvent` to the `ClientTraceBus` for SSE fan-out.

**Orchestrator** (`services/orchestrator/graph.py`, `OrchestrationGraph.run()`):

1. Pre-plan discovery: `GET /` on all three leaf services to fetch live catalogs.
2. Planner node: LLM call with PLANNER_SYSTEM (catalog-injected; see section 6).
   Returns `{"steps": [{"verb": ..., "url": ..., "rationale": ...}, ...]}`.
3. Actor/observe loop (up to `max_steps=8`):
   - Actor LLM call with ACTOR_SYSTEM: emits one step JSON including `is_final`.
   - If `is_final: true` → emit `final` trace event, mark job `completed`, return.
   - Otherwise `_dispatch(step)` → one HTTP call via `HTTPToolbox`.
   - Result appended to transcript; `observation` trace event emitted.
4. Fallback finalize node: if max_steps reached without `is_final`, a final LLM call
   summarises what happened.

`_dispatch` (`graph.py:205`) is four lines:

```python
async def _dispatch(self, step: OrchestrationStep) -> dict[str, Any]:
    if step.verb == "GET":
        return await self._toolbox.http_get(step.url)
    if step.verb == "POST":
        return await self._toolbox.http_post(step.url, body=step.body)
    if step.verb == "PATCH":
        return await self._toolbox.http_patch(step.url, body=step.body)
    if step.verb == "DELETE":
        return await self._toolbox.http_delete(step.url)
```

The `HTTPToolbox` (`services/orchestrator/tools.py`) exposes exactly four methods —
GET, POST, PATCH, DELETE — with no service-specific knowledge. As its docstring states:
"The LLM discovers URLs via the hypermedia protocol ... No service-specific tools are
pre-registered — this is the whole point of the agent-first design."

---

## 6. Grounding the Planner

The most consequential design decision is how the planner's system prompt is
constructed. At the start of every orchestration run, the graph fetches the live
catalogs from all three leaf services and injects them verbatim into the prompt:

```python
PLANNER_SYSTEM = """You are the planner for an agent-first SaaS project management system.
...
The catalogs below list EVERY endpoint each service exposes. You MUST plan using
only these exact paths. Do NOT invent URLs like /pages, /marketing, /launches —
if a concept isn't in a catalog, map it to the closest real endpoint (a project
or a task) or skip that step.

=== Projects catalog ===
{projects_catalog}

=== People catalog ===
{people_catalog}

=== Communications catalog ===
{comms_catalog}
...
"""
```

The `_catalog_summary()` function (`graph.py:245`) formats each capability as a single
line — `VERB /path — summary` — so the injected text is dense but scannable:

```python
def _catalog_summary(observation: dict[str, Any]) -> str:
    body = _catalog_body(observation)
    caps = body.get("capabilities", []) or []
    lines = []
    for c in caps:
        verb = c.get("verb") or c.get("method") or "?"
        path = c.get("path") or "?"
        summary = c.get("summary") or c.get("intent") or c.get("returns") or ""
        lines.append(f"{verb} {path} — {summary}")
    return "\n".join(lines) if lines else "(no capabilities reported)"
```

The prohibition against invented URLs is explicit in both PLANNER_SYSTEM and
ACTOR_SYSTEM. ACTOR_SYSTEM adds a 404 recovery rule:

```
- If an earlier observation returned 404, do NOT retry the same path —
  pick a different real endpoint or signal completion.
```

This grounding approach means the planner is always working from the actual deployed
state of the system, not from a stale OpenAPI snapshot embedded at build time.

---

## 7. Live Tracing via SSE

Both agents maintain an in-memory pub/sub bus:

```python
class TraceBus:
    """Async pub/sub fan-out for trace events. One bus per orchestrator process."""
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[TraceEvent]] = set()
        self._lock = asyncio.Lock()

    async def publish(self, event: TraceEvent) -> None:
        async with self._lock:
            targets = list(self._subscribers)
        for q in targets:
            await q.put(event)
```

`subscribe()` is an async context manager that adds an `asyncio.Queue` to the set on
entry and discards it on exit. The SSE endpoint subscribes once per browser connection
and yields events as they arrive:

```python
@router.get("/sse/orchestrator")
async def stream_trace(request: Request):
    bus = request.app.state.trace_bus

    async def event_generator():
        async with bus.subscribe() as queue:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=_IDLE_TIMEOUT)
                except asyncio.TimeoutError:
                    continue          # heartbeat pause; keep the connection open
                yield {"event": event.kind, "data": event.model_dump_json()}

    return EventSourceResponse(event_generator(), ping=15)
```

The `continue` on `TimeoutError` (rather than `break` or `yield` a keepalive string)
is a deliberate fix. Earlier versions broke out of the loop on idle timeout, causing
SSE subscribers to drop and reconnect between events. `_IDLE_TIMEOUT = 0.3` seconds is
the poll interval; the `ping=15` argument to `EventSourceResponse` sends an SSE comment
line every 15 seconds to keep proxies alive.

`TraceEvent.kind` is typed as a `Literal` over nine values:
`thought`, `action`, `observation`, `final`, `error` (orchestrator);
`discovery`, `decision`, `invocation`, `summary` (client agent).

The client agent uses an identical structure (`ClientTraceBus`, `ClientTraceEvent`,
`GET /sse/client`) in a separate module so the two services remain independent.

---

## 8. The Observer Dashboard

The Next.js dashboard at `http://127.0.0.1:3000` is a single page with a 12-column
grid (`dashboard/app/page.tsx`):

- **Left column (4 cols):** `BriefPanel` (text input + submit button) stacked above a
  `TracePanel` consuming `http://127.0.0.1:8080/sse/client`.
- **Centre column (4 cols):** `TracePanel` consuming
  `http://127.0.0.1:8000/sse/orchestrator`.
- **Right column (4 cols):** `CreatedProjectPanel` (polls `/projects` every 2 s, shows
  the latest project and its tasks) stacked above three `ServiceSnapshot` components
  that call `GET /` on each leaf service to display their capability catalogs.

`useTraceStream` (`dashboard/lib/useTraceStream.ts`) opens an `EventSource` and
registers listeners for all nine event kinds. The disconnect-flicker fix uses a 1500 ms
debounce timer: the `onerror` handler starts a timeout to set `connected = false`; any
subsequent `onopen` or incoming message cancels the timer. This prevents a brief
"disconnected" flash on the UI when the EventSource performs its normal reconnect cycle
between events.

```typescript
src.onerror = () => {
  clearPendingDisconnect();
  disconnectTimerRef.current = setTimeout(() => setConnected(false), 1500);
};
```

`CreatedProjectPanel` polls `GET /projects` on a 2-second interval, selects the last
item in the list, then fetches `GET /projects/{id}/tasks`. The result renders as a live
task list with status badges.

---

## 9. CORS and Browser-Callability

Every FastAPI service registers `CORSMiddleware` with `allow_origins=["*"]`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

This is present in all five services (`services/projects/app.py`,
`services/people/app.py`, `services/communications/app.py`,
`services/orchestrator/app.py`, `services/client_agent/app.py`).

The dashboard running on `:3000` directly calls the backend services (no Next.js API
route proxy). For a demo this is the correct choice: the audience can open DevTools and
see the real requests, real SSE streams, and real response envelopes without a
reverse-proxy layer obscuring the protocol.

---

## 10. Error Protocol and Field Docs

`AgentError` (`agent_protocol/errors.py`) is a structured exception class. Its
`to_payload()` method produces:

```json
{
  "error": "validation_error",
  "message": "Field 'name' is required.",
  "_why": "The request body was missing a required field.",
  "_try_instead": "Include 'name' in the request body.",
  "_valid_values": ["..."],
  "_example": {"name": "Q3 Launch"}
}
```

The `_why` and `_try_instead` fields follow the same underscore convention as the
success envelope. An agent receiving a 4xx response can parse `_why` to understand what
went wrong and `_try_instead` to decide on the next action — without needing a separate
error-code registry or human-readable documentation.

`DocumentedField` (`agent_protocol/field_docs.py`) is a Pydantic `Field()` wrapper that
enforces non-empty `description` and non-empty `examples` at construction time:

```python
def DocumentedField(*, description: str, examples: list[Any], ...) -> FieldInfo:
    if not description or not description.strip():
        raise ValueError("description is required and must be non-empty")
    if not examples:
        raise ValueError("examples is required and must be non-empty")
    return Field(default, description=description, examples=examples, **kwargs)
```

Pydantic models built with this helper produce OpenAPI/JSON Schema output that agents
can reason about: every field has a description and at least one example. This makes the
requirement explicit at the type level rather than relying on a documentation convention.

---

## 11. What Makes This Different

| Dimension | Conventional REST | Agent-First (this project) |
|---|---|---|
| **Contract** | OpenAPI spec or SDK, maintained separately from runtime | Wire format is the contract; catalog served live at `GET /` |
| **Discovery** | Developer reads docs before writing code | Agent calls `GET /` at runtime; plan is grounded in live state |
| **Navigation** | Hard-coded URLs in client code | `_suggested_next` and `_related` in every response |
| **Error semantics** | HTTP status + optional message string | `_why` + `_try_instead` in every error; agent-parseable |
| **Grounding** | LLM must be told about the API via system prompt or RAG | Catalog injected into planner prompt from live `GET /` responses |
| **Tooling** | Service-specific SDK or MCP tools per service | Four generic HTTP verbs; LLM discovers URLs from catalog |

---

## 12. Running the Demo

There is no single `make up` command. The demo requires six concurrent processes. The
`make run-demo` target prints the instructions:

```
1)  make run-projects       # :8001  — SQLite-backed Projects service
2)  make run-people         # :8002  — People service (seeded from fixtures)
3)  make run-communications # :8003  — Communications service (seeded from fixtures)
4)  make run-orchestrator   # :8000  — Orchestrator (uses LLM replay fixtures by default)
5)  make run-client         # :8080  — Client Agent (uses LLM replay fixtures by default)
6)  make run-dashboard      # :3000  — Next.js dashboard (cd dashboard && npm run dev)
```

Each `run-*` target activates `.venv` before starting. The orchestrator and client agent
accept `ORCHESTRATOR_REPLAY_DIR` and `CLIENT_AGENT_REPLAY_DIR` environment variables to
point at pre-recorded LLM fixture directories; if these are unset and Azure credentials
are present in `.env`, the services hit the live Azure OpenAI endpoint.

Once all six processes are running, open `http://127.0.0.1:3000` in a browser, type a
brief in the input panel, and click submit. The two trace panels will populate in real
time as the agents think and act.

---

## 13. Known Limitations / Non-Goals

- **In-memory trace bus.** `TraceBus` and `ClientTraceBus` are `asyncio.Queue`-based
  sets held in process memory. A second orchestrator process would have a separate bus;
  no events would cross the boundary. Horizontal scaling requires an external broker
  (Redis Pub/Sub, etc.).

- **No authentication.** All endpoints and SSE streams are open. `allow_origins=["*"]`
  is intentional for demo observability; it is not a starting point for production.

- **SQLite only.** Each leaf service and the orchestrator use their own SQLite file.
  Concurrent write throughput is limited by SQLite's single-writer lock. No migration
  tooling is provided.

- **Demo scope.** The three leaf services cover projects, tasks, people, and messages —
  enough to demonstrate the pattern with real HTTP side-effects. There is no
  authentication, no multi-tenancy, no pagination beyond basic query filters, and no
  background job queue beyond `asyncio.create_task`.

- **LLM replay fixtures are scenario-specific.** The shipped fixtures were recorded for
  the "landing page" brief. A different brief will diverge from the fixture at the first
  LLM call and either fall back to Azure (hybrid mode) or fail with a `ReplayMissError`.
