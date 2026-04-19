---

# Agent-First Services Demo — Design Spec

**Date:** 2026-04-19
**Status:** Approved for implementation planning
**Project root:** `/Users/eugene/dev/ai-projects/agent-first-service`

---

## 1. Overview

An example application modeling a single fictional business entity ("Acme Digital") as four FastAPI services plus a standalone agent process. Every service is designed from the ground up to be consumed by AI agents rather than humans.

The demo showcases **self-describing endpoints** as the defining agent-first pattern: each service publishes a natural-language capabilities catalog at `GET /`, every successful response embeds `_related` and `_suggested_next` discovery links, and every error carries `_why` and `_try_instead` semantic fields. Agents discover, learn, and recover without pre-registered tool schemas.

On top of this protocol, the demo shows **agent-to-agent composition**: a **Client Agent** represents the user to the business entity; the business entity exposes an **Orchestrator** that *looks like* an agent-first service but is itself powered by a LangGraph agent; the Orchestrator in turn drives three downstream agent-first services.

## 2. Purpose and audience

- **Purpose:** Live, on-stage demo. The presenter types a natural-language brief ("Build a marketing landing page for our Q3 launch") and the audience watches the agents cooperate through the services to produce a structured plan and stakeholder communications.
- **Audience:** Developers / architects evaluating agent-first API design patterns.
- **Success criterion:** The audience can see, in real time, (a) agents discovering endpoints they were not pre-trained on, (b) agents following `_suggested_next` links, and (c) agents recovering from constraint errors using `_try_instead` guidance.

## 3. Scope

### In scope

- Three agent-first FastAPI services: **Projects**, **People**, **Communications**.
- A fourth FastAPI service, **Orchestrator**, internally powered by a LangGraph agent, exposing the same hypermedia protocol.
- A standalone **Client Agent** process (LangGraph) that discovers and calls the Orchestrator.
- A **Next.js dashboard** visualizing both agent traces and all four services' live state.
- **SQLite** per service, seeded from JSON fixtures.
- **Azure OpenAI** (`AzureChatOpenAI`) as the LLM for both agents.
- End-to-end test coverage: protocol conformance, service unit/integration, cross-service integration, LLM-replay, live smoke.
- Local `make demo` orchestration (no Docker requirement).

### Out of scope

- Authentication / authorization (single-tenant local demo).
- Real email / Slack integration (Communications simulates channels).
- Distributed tracing (OpenTelemetry, Jaeger) — SSE traces suffice for the demo.
- Load / performance testing.
- Production deployment, horizontal scaling.
- Idempotency keys on POSTs (flagged as follow-up).

## 4. Stack

- Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy (or `sqlite3` stdlib) over SQLite files on disk.
- LangGraph + `langchain-openai` `AzureChatOpenAI`.
- Next.js (App Router) + Tailwind + `EventSource` for the dashboard.
- `make` for multi-process orchestration.

## 5. Architecture

### 5.1 System diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                         Demo Dashboard                           │
│           Next.js + SSE (audience-facing storyboard)             │
└────────▲────────────────▲──────────────────▲────────────────────┘
         │ input          │ client-agent     │ orchestrator
         │                │ trace            │ trace
         │                │                  │
┌────────┴────────────────┴──────────┐      │
│           Client Agent             │      │
│     LangGraph + Azure OpenAI       │      │
│     Port :8080 (thin HTTP shim)    │      │
│  Role: interpret human intent,     │      │
│  talk to the business entity.      │      │
│  Tools: http_get/post/patch/del    │      │
└──────────────┬─────────────────────┘      │
               │ HTTP (hypermedia agent protocol)
               ▼                             │
┌──────────────────────────────────────┐    │
│          Orchestrator Service        ├────┘
│   FastAPI facade wrapping LangGraph  │
│   Port :8000                         │
│   Endpoints: GET /, POST /requests,  │
│   GET /requests/{id}, .../result,    │
│   POST /requests/{id}/cancel         │
│   Same hypermedia protocol as below  │
│   LLM: Azure OpenAI (separate graph) │
└───┬──────────────┬───────────────┬───┘
    │ HTTP         │ HTTP          │ HTTP
┌───▼────────┐ ┌───▼────────┐ ┌────▼──────────────┐
│ Projects   │ │ People     │ │ Communications    │
│ :8001      │ │ :8002      │ │ :8003             │
│ SQLite     │ │ SQLite     │ │ SQLite            │
└────────────┘ └────────────┘ └───────────────────┘
```

### 5.2 Key design choices

1. **Five independent processes** — the four FastAPI services (Projects, People, Communications, Orchestrator) plus the Client Agent each run as their own `uvicorn` process with their own SQLite file (services) or no DB (Client Agent). Makes "multiple services serving one business entity" real rather than cosmetic.
2. **Generic HTTP tools only** — both agents' tool set is `http_get`, `http_post`, `http_patch`, `http_delete`. No per-endpoint tools. Forces the agents to rely on the hypermedia protocol for discovery.
3. **Protocol recursion** — the Orchestrator exposes itself using the same hypermedia protocol as the leaf services. The Client Agent treats it identically to any other agent-first service. This makes the pattern **compositional**: agent-first services can themselves be powered by agents, with no protocol change.
4. **Two SSE streams** — dashboard subscribes to `/sse/client` and `/sse/orchestrator` independently, so the audience sees two reasoning loops side by side.
5. **Zero cross-service coupling in the services** — Projects/People/Communications know nothing about each other. Only the agents cross service boundaries. Coordination is visibly an agent responsibility.

## 6. Components

### 6.1 Shared `agent_protocol/` library

Used by all four FastAPI services to enforce the hypermedia pattern consistently.

- `envelope.py` — `AgentResponse[T]` Pydantic model wrapping any payload with `_self`, `_related`, `_suggested_next`, `_generated_at`.
- `errors.py` — `AgentError` exception + FastAPI exception handler producing `{error, message, _why, _try_instead, _valid_values?, _example?, _related?}`.
- `catalog.py` — helpers for building the `GET /` capabilities document (endpoint list + natural-language when-to-use descriptions + example bodies).
- `field_docs.py` — Pydantic field helpers enforcing a `description` + `examples` on every field.

### 6.2 Projects service — `services/projects/`, port 8001

**Entities:** `Project`, `Task`, `Milestone`.

**Endpoints:**
- `GET /` — capabilities catalog.
- `GET /projects`, `POST /projects`.
- `GET /projects/{id}`, `PATCH /projects/{id}`.
- `GET /projects/{id}/tasks`, `POST /projects/{id}/tasks`.
- `PATCH /tasks/{id}` (status, assignee, due date).
- `GET /tasks?filter=...` (by assignee, status, milestone).

**SQLite file:** `data/projects.db`, seeded from `fixtures/demo-seed/projects.json`.

### 6.3 People service — `services/people/`, port 8002

**Entities:** `Person`, `Skill`, `CapacityWindow`.

**Endpoints:**
- `GET /` — capabilities catalog.
- `GET /people`, `GET /people/{id}`.
- `GET /people/search?skills=...&available_before=...`.
- `GET /people/{id}/workload`.
- `POST /people/{id}/capacity` (record booked time).

**SQLite file:** `data/people.db`, seeded with 8–12 realistic team members, skills, and current workloads.

### 6.4 Communications service — `services/communications/`, port 8003

**Entities:** `Stakeholder`, `Message`, `Channel` (email / slack / status-page, all simulated).

**Endpoints:**
- `GET /` — capabilities catalog.
- `GET /stakeholders`, `POST /stakeholders`.
- `GET /messages`, `POST /messages` (recorded, not actually sent).
- `GET /messages?project_id=...`.

**SQLite file:** `data/communications.db`.

### 6.5 Orchestrator service — `services/orchestrator/`, port 8000

A FastAPI service that *looks like* an agent-first service but is internally powered by a LangGraph agent.

**Entities:** `Request` (a brief the business entity accepts), `RequestStep` (a narrated progress entry).

**Endpoints:**
- `GET /` — capabilities catalog; describes that this service accepts natural-language project briefs and returns structured plans.
- `POST /requests` — body `{brief: string, context?: {...}}`; returns a `Request` with `status: "planning"` and `_suggested_next` link to poll.
- `GET /requests/{id}` — current state + streamed `steps[]` for narration.
- `GET /requests/{id}/result` — final plan + cross-service links into Projects/People/Communications for the artifacts created.
- `POST /requests/{id}/cancel` — idempotent cancel.

**Internals:** On `POST /requests`, the endpoint spawns an `asyncio.create_task(...)` that runs the LangGraph `StateGraph` to completion and returns immediately with the new `Request` resource. The graph has `http_get`/`http_post`/`http_patch` tools pointed at the three downstream services. Every node transition writes a `RequestStep` row (visible via `GET /requests/{id}`) and publishes to the orchestrator's SSE channel.

**SQLite file:** `data/orchestrator.db` (request history + step log).

**LLM:** `AzureChatOpenAI` (separate client instance from the Client Agent).

### 6.6 Client Agent — `agent/client/`, port 8080

Runs as its own `uvicorn` process with a thin FastAPI shim — just enough HTTP to integrate with the dashboard.

- **Runtime:** LangGraph `StateGraph` with a "reason + act" loop; `AzureChatOpenAI`.
- **Tools:** `http_get`, `http_post`, `http_patch`, `http_delete` only. No pre-registered knowledge of the Orchestrator's endpoints.
- **System prompt:** instructs the agent to start with `GET http://localhost:8000/` for discovery, follow `_suggested_next` links, and narrate progress back to the user in plain language.
- **HTTP surface:**
  - `POST /prompt` — accepts `{prompt: string}` from the dashboard; spawns an `asyncio` task running the reason-act loop.
  - `GET /sse/client` — Server-Sent Events stream of the current loop's events.
  - `POST /cancel` — aborts the in-flight loop (idempotent).
- **SSE events:** `thought`, `tool_call`, `tool_result`, `narration`.
- **Headless mode:** also supports stdin input for test runs without the dashboard.

### 6.7 Demo dashboard — `dashboard/`

Next.js (App Router) + Tailwind; subscribes to two SSE channels — one hosted by the Client Agent (`:8080/sse/client`) and one by the Orchestrator service (`:8000/sse/orchestrator`).

**Layout:**
1. **Top bar:** user types request.
2. **Left column — Client Agent trace:** thoughts, discovery, requests sent, polling results.
3. **Middle column — Orchestrator trace:** reasoning, calls to downstream services, steps written.
4. **Right column — Service state:** four mini-panels (Orchestrator requests, Projects, People, Communications) showing live DB contents.
5. **Bottom strip — Stakeholder feed:** messages "sent" by Communications.

### 6.8 Orchestration / launch

Top-level `Makefile`. `make demo` starts:
- 4 uvicorn processes for the services on ports 8000–8003.
- Client Agent uvicorn process on port 8080.
- Next.js dev server (default port 3000).

All local. Optional `docker-compose.yml` as a convenience; not required.

## 7. Hypermedia agent protocol

### 7.1 Success envelope

Every successful response wraps its payload in:
```json
{
  "data": { ... payload ... },
  "_self": "/path/to/this/resource",
  "_related": ["/related/a", "/related/b"],
  "_suggested_next": {
    "intent_name": "/path/to/follow",
    "another_intent": {"service": "projects", "path": "/tasks/{id}", "body_hint": {...}}
  },
  "_generated_at": "2026-04-19T12:34:56Z"
}
```

### 7.2 Error envelope

Every error (4xx / 5xx) conforms to:
```json
{
  "error": "short-machine-readable-code",
  "message": "human-readable summary",
  "_why": "natural-language explanation of what went wrong",
  "_try_instead": "natural-language suggestion of what to do next",
  "_valid_values": ["..."],
  "_example": { ... },
  "_related": ["/search", "/..."]
}
```

### 7.3 Capabilities catalog (`GET /`)

Each service's root returns a hand-crafted document:
```json
{
  "service": "Projects",
  "description": "Plain-language description of what this service is for.",
  "capabilities": [
    {
      "intent": "create a new project",
      "method": "POST",
      "path": "/projects",
      "example_body": { ... },
      "returns": "Project resource"
    },
    { ... }
  ],
  "_self": "/",
  "_related": ["/projects", "/tasks"]
}
```

## 8. Data flow — end-to-end walkthrough

Example: user types **"Build a marketing landing page for our Q3 launch"**.

1. **Client Agent discovers the business entity.** `GET http://localhost:8000/`. Reads the capabilities catalog.
2. **Client Agent submits the brief.** `POST http://localhost:8000/requests` with `{"brief": "Build a marketing landing page for our Q3 launch"}`. Receives `{"id": "req_7f3a", "status": "planning", "_suggested_next": {"poll_progress": "/requests/req_7f3a"}}`.
3. **Orchestrator discovers downstream services.** Its background LangGraph task calls `GET :8001/`, `:8002/`, `:8003/`. Writes `RequestStep` rows.
4. **Orchestrator decomposes the brief.** Identifies 4 tasks (copywriting, design, frontend build, QA). Calls `POST :8001/projects`, then follows `_suggested_next` to `POST :8001/projects/{id}/tasks` four times.
5. **Orchestrator assigns based on capacity.** `GET :8002/people/search?skills=copywriting&available_before=...`. For each matched person, follows `_suggested_next` to check workload, book capacity, then `PATCH :8001/tasks/{id}` to set assignee.
6. **Orchestrator notifies stakeholders.** `GET :8003/` → `/stakeholders` → `POST :8003/messages` with a summary.
7. **Orchestrator completes the request.** Updates `req_7f3a` to `status: "complete"`; writes final plan to `/requests/req_7f3a/result` with cross-service links.
8. **Client Agent narrates.** Has been polling `/requests/req_7f3a` every few seconds; reads new `steps[]`, generates natural-language narration, streams to dashboard. On completion, fetches `/result` and summarizes.

### 8.1 SSE trace channels

- `http://localhost:8080/sse/client` — served by the Client Agent process. Events: `thought`, `tool_call`, `tool_result`, `narration`.
- `http://localhost:8000/sse/orchestrator` — served by the Orchestrator service. Events: `thought`, `tool_call`, `tool_result`, `step_written`.
- Each leaf service optionally exposes `/sse/events` on its own port for DB change notifications to update the dashboard's state panels.

## 9. Error handling

### 9.1 Error categories

| Category | HTTP | Example | `_try_instead` content |
|---|---|---|---|
| Validation | 400 | Missing required field, wrong type | Shows a valid example body; lists accepted values |
| Not found | 404 | `GET /people/{bad-id}` | Points to `/people/search` or `/people` listing |
| Conflict / constraint | 409 | Assigning a task to someone at 120% capacity | "Alice is overbooked; consider Bob (65%) or Carol (80%)" — inline alternatives from a live query |
| Dependency missing | 422 | Creating a task referencing a non-existent project | Link to `POST /projects` |
| Rate / size limit | 413 / 429 | Batch too large | Suggests splitting, shows max size |
| Upstream unavailable | 503 | Orchestrator can't reach People service | Names the unreachable service; suggests retry delay |

The **409 constraint error** is the key demo moment: the agent recovers by reading `_try_instead` and calling the suggested alternative without human guidance.

### 9.2 Service-to-service propagation

- The Orchestrator's LangGraph tool wrapper inspects downstream error envelopes and returns a tool-result the LLM can reason about. It does not rethrow blindly.
- Orchestrator-level errors use the same envelope so the Client Agent recovers symmetrically.

### 9.3 Agent safety rails

- **Max tool calls per request:** Client Agent capped at 20, Orchestrator at 40. On hit: write a terminal step `"max iterations reached"`; return 503 with `_why`.
- **Per-call HTTP timeout:** 10 seconds. On timeout, a synthetic tool-result informs the agent; it may retry or try another endpoint.
- **Schema drift guard:** tool wrapper logs responses missing expected envelope fields but passes them through — don't mask protocol bugs.
- **Hallucinated endpoints:** 404s include `_try_instead: "Call GET / on this service to see available endpoints"`.
- **Infinite loop detection:** if the same tool call signature appears 3 times consecutively, LangGraph `before_model_callback` injects a synthetic `"you just did this; reconsider"` system message.

### 9.4 Demo-specific failures

- **Nonsense user request** ("make me a sandwich"): Client Agent discovers no matching capability in the business entity's catalog; responds "This business entity handles project briefs; try something like ...". No service call made.
- **One service down during demo:** Orchestrator gets 503 on discovery, writes a visible `RequestStep` explaining the problem, surfaces partial completion on the dashboard.
- **Azure OpenAI rate limit:** `AzureChatOpenAI` retries with exponential backoff (3 attempts). On final failure, current node returns an error surfaced as a terminal step.

## 10. Testing strategy

### 10.1 Test layers

| Layer | What it covers | Real or fixture | Location |
|---|---|---|---|
| Protocol conformance | Every service response carries a valid envelope; errors match the error envelope; `GET /` returns a well-formed catalog | Real services (FastAPI TestClient) | `tests/protocol/` |
| Service unit / integration | Each service's CRUD + queries + constraint logic | Real SQLite (tmpdir per test) + FastAPI TestClient; no mocks | `tests/services/{projects,people,communications,orchestrator}/` |
| Cross-service integration | Orchestrator actually calls the three downstream services over HTTP; links resolve end-to-end | Real services in subprocesses on ephemeral ports | `tests/integration/` |
| Agent behavior (replay) | Client Agent and Orchestrator reason correctly over recorded LLM responses | Fixtures in `tests/fixtures/llm_recordings/` | `tests/agent/` |
| Agent behavior (live smoke) | End-to-end demo scenario with a real Azure OpenAI call | Real LLM; gated on `AZURE_OPENAI_API_KEY`; skipped otherwise | `tests/smoke/` |

### 10.2 LLM fixture policy

- Capture via a recording wrapper around `AzureChatOpenAI` writing `{prompt, response, model, temperature, timestamp}` to `tests/fixtures/llm_recordings/<scenario>/<step>.json`.
- Replay wrapper reads the same files; if a prompt doesn't match a recording, test fails loudly — never silently falls back to live.
- Each fixture folder has a `README.md` documenting capture method and redactions.
- Stored verbatim.

### 10.3 Seed data and SQLite

- Each service exposes `--seed-from <json>` for startup and tests.
- Tests use tmpdir SQLite so no state bleeds between tests or into the demo.
- Demo uses `fixtures/demo-seed/*.json` — curated team members, existing projects, stakeholders — rich enough to absorb an arbitrary live-typed brief.

### 10.4 Test inventory

Maintained at `docs/test_inventory.md`. For every test module, records: what it covers, location, how to run it, external dependencies, and whether it is unit vs integration vs replay vs live.

### 10.5 Increment verification gate

Each implementation increment is "done" only when:
1. Targeted tests added and passing (visible pytest output).
2. Protocol conformance suite still green.
3. Integration suite still green.
4. `docs/test_inventory.md` updated.
5. Live smoke test run at least once if LLM behavior was touched.

### 10.6 Demo dry-run test

`tests/demo/test_rehearsal.py` replays a handful of realistic briefs through the full stack using recorded LLM responses, asserting the dashboard receives the expected trace events in order. Run before any live demo session.

### 10.7 Not in scope for tests

- Load / performance testing.
- Security / auth testing.
- Browser-level UI testing of the dashboard (Playwright) unless SSE rendering proves flaky in practice.

## 11. Repository layout (proposed)

```
agent-first-service/
├── Makefile
├── README.md
├── pyproject.toml
├── agent_protocol/            # shared library
│   ├── envelope.py
│   ├── errors.py
│   ├── catalog.py
│   └── field_docs.py
├── services/
│   ├── projects/
│   ├── people/
│   ├── communications/
│   └── orchestrator/
├── agent/
│   └── client/
├── dashboard/                 # Next.js app
├── fixtures/
│   └── demo-seed/
├── data/                      # SQLite files at runtime (gitignored)
├── tests/
│   ├── protocol/
│   ├── services/
│   ├── integration/
│   ├── agent/
│   ├── smoke/
│   ├── demo/
│   └── fixtures/llm_recordings/
└── docs/
    ├── superpowers/specs/
    ├── implementation_plan.md
    ├── implementation_status.md
    └── test_inventory.md
```

## 12. Open questions / follow-ups

- Azure OpenAI deployment name and API version to pin (needs env config).
- Whether to record a dry-run demo video as a fallback for stage connectivity issues.
- Whether the Communications service should simulate send *delays* to make the dashboard feel more alive.
- Idempotency keys on POST endpoints — out of scope now, flagged for a future iteration.

## 13. Glossary

- **Agent-first service** — an API whose design prioritizes consumption by AI agents over human developers.
- **Hypermedia agent protocol** — the response envelope convention defined in §7: `_self`, `_related`, `_suggested_next`, error `_why` / `_try_instead`.
- **Client Agent** — the agent representing the human user to the business entity; discovers the Orchestrator via `GET /`.
- **Orchestrator** — a service that looks agent-first from the outside but is internally powered by a LangGraph agent driving the three leaf services.
- **Business entity** — the collective of the four services presented as a single addressable system to the Client Agent.
