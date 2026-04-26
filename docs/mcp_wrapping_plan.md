# MCP Wrapping Plan — Leaf Services as MCP Servers

Cross-references: `docs/implementation_plan.md`, `docs/implementation_status.md`,
`docs/test_inventory.md`, `Briefing.md`, `AgentFirstByExample.md`, `agent-first-flow.drawio`.

---

## 1. Goal & Non-Goals

**Goal.** Expose the three leaf services — Projects (`services/projects/`), People
(`services/people/`), Communications (`services/communications/`) — as MCP (Model Context
Protocol) servers so that any MCP-compatible client (Claude Desktop, an MCP-aware orchestrator,
or a third-party agent framework) can discover and invoke their capabilities without knowing
anything about HTTP paths.

**Explicit non-goals.**

- (a) Do NOT remove or deprecate the HTTP surface. The Next.js dashboard at `dashboard/` calls
  `GET /projects`, `GET /sse/...`, and other HTTP routes directly from the browser. Those routes
  must remain fully functional and unchanged.
- (b) Do not redesign the hypermedia envelope. The `{data, _self, _related, _suggested_next,
  _generated_at}` structure produced by `agent_protocol/envelope.py::make_response()` and
  `AgentResponse` is the canonical wire format and must be preserved as-is — MCP clients receive
  the same envelope bytes that `curl` would receive.
- (c) Do not change any leaf-service domain logic (routes, models, DB schema, seed data,
  error handling).

---

## 2. Architecture Decision — Dual-Mode, Thin Wrapper

**Chosen approach.** Each leaf service keeps its existing FastAPI application unmodified. A
separate MCP server process (or optional in-process mount) is layered alongside it. That MCP
server re-exports every `Capability` from `GET /` as an MCP `tool`. Tool implementations satisfy
calls by invoking the existing FastAPI app in-process via `httpx.AsyncClient` with
`httpx.ASGITransport`, avoiding a second network hop and keeping the test surface contained to
a single process.

### Decision table

| Option | Description | Verdict |
|---|---|---|
| 1. Replace HTTP with MCP | Remove FastAPI routes; implement everything in MCP handlers. | **Rejected.** Breaks the dashboard, breaks all existing HTTP integration tests, and discards the working envelope infrastructure. |
| 2. MCP alongside, sharing handlers in-process (ASGITransport) | Keep FastAPI app intact; MCP server calls it via `httpx.AsyncClient(transport=ASGITransport(app=app))`. No extra network hop. | **Chosen.** Zero duplication of business logic, no port dependency between MCP and HTTP layers, testable in a single process. |
| 3. MCP as external subprocess talking HTTP to the running service | MCP server process calls `http://localhost:8001/projects` etc. | **Viable fallback.** Simpler to implement but requires the HTTP server to be running, adds latency, and complicates test setup. Adopt only if in-process transport proves incompatible with a future MCP SDK version. |

---

## 3. Capability → MCP Tool Mapping

### 3.1 Tool name derivation

Tool `name` is derived as follows, in priority order:

1. If `Capability.id` is set (non-None, non-empty), use it verbatim.
2. Otherwise, build the name from `f"{verb.lower()}_{path}"` where every character that is not
   `[a-z0-9]` is replaced by `_`, and runs of multiple underscores are collapsed to one.
   Path parameters such as `{id}` become `_id_` in the intermediate string before collapsing.

Tool names must be unique within a service. Because the People and Communications services
already use the `id` field on every `Capability`, uniqueness is guaranteed there. The Projects
service uses the legacy format (no `id`); the derivation rule produces unique names from the
verb+path combination.

### 3.2 Worked examples — Projects service (legacy `Capability` format)

| `Capability` fields | Derived tool name |
|---|---|
| `method="POST"`, `path="/projects"` | `post_projects` |
| `method="GET"`, `path="/projects/{id}/tasks"` | `get_projects_id_tasks` |
| `method="PATCH"`, `path="/tasks/{id}"` | `patch_tasks_id` |

### 3.3 Worked examples — People service (`id`-based format)

| `Capability.id` | Tool name (identity) |
|---|---|
| `list_people` | `list_people` |
| `create_person` | `create_person` |
| `filter_by_skill` | `filter_by_skill` |

### 3.4 Worked examples — Communications service (`id`-based format)

| `Capability.id` | Tool name (identity) |
|---|---|
| `send_message` | `send_message` |
| `find_message` | `find_message` |
| `filter_by_project` | `filter_by_project` |

### 3.5 Tool description

Concatenate `summary` (or fall back to `intent`) and each entry in `hints` (joined with a
space). Example for `create_person`:

```
"Add a new team member. Body fields: name, role, skills."
```

### 3.6 Tool `inputSchema`

Derived in two layers:

**Body layer.** When the route handler accepts a Pydantic `BaseModel` (e.g. `CreateProject`,
`CreateTask`), call `model.model_json_schema()` as the base schema. This carries all field
descriptions, types, and examples already present in the model.

**Path/query parameter layer.** Path parameters (e.g. `project_id` in
`POST /projects/{project_id}/tasks`) and query parameters (e.g. `assignee` in `GET /tasks`)
are **hoisted to the top level** alongside body fields. Path params are typed `"type":
"string"` and added to `required`; query params are optional. Justification: `tools/call`
delivers a single flat `arguments` dict — a nested `_parameters` key forces callers to split
arguments unnecessarily.

Example `required` + `properties` keys for `post_projects_id_tasks`:
`project_id` (path, required), `title` (body, required), `assignee_id` (body, optional),
`due_date` (body, optional). The adapter extracts path params from `arguments`, builds the
URL, and forwards the remainder as the JSON body.

### 3.7 Tool result content

The result of every `tools/call` is:

```json
[{"type": "text", "text": "<json-serialised envelope>", "annotations": {"contentType": "application/json"}}]
```

where `<json-serialised envelope>` is `json.dumps(envelope_dict)` — the exact same dict that
the HTTP endpoint returns, including all `_self`, `_related`, `_suggested_next`, and
`_generated_at` keys. MCP clients that need to re-parse the data call `json.loads(content[0].text)`.

---

## 4. MCP SDK & Transport Choice

### 4.1 Dependency

Add to `pyproject.toml` dependencies:

```toml
"mcp>=1.6,<2.0",
```

Pin to `<2.0` because the SDK server API is still evolving and minor-version breaks have
occurred. The `mcp` package ships both server and client libraries; no second package is needed.

### 4.2 Transports

Two transports are supported per service:

- **stdio** — required for Claude Desktop integration. The MCP server reads JSON-RPC frames from
  stdin and writes responses to stdout. Launch command:
  `python -m services.projects.mcp_main` (no flags).
- **SSE** — required for orchestrator integration. The MCP server runs as an HTTP server
  streaming JSON-RPC frames over Server-Sent Events. Launch command:
  `python -m services.projects.mcp_main --sse --port 9001`.

Justification: SSE gives the orchestrator a stable URL without managing subprocess lifecycles;
stdio gives free integration with Claude Desktop without requiring a network port.

### 4.3 File layout per service (new files to be created)

| Service | Server module | Entrypoint |
|---|---|---|
| Projects | `services/projects/mcp_server.py` — builds `Server("projects")`, registers tools from `_CAPABILITIES`, wires `tools/list` + `tools/call` via `ASGITransport` | `services/projects/mcp_main.py` — parses `--sse`/`--port`; instantiates app via `create_app(sqlite_path="./projects.db")` |
| People | `services/people/mcp_server.py` | `services/people/mcp_main.py` |
| Communications | `services/communications/mcp_server.py` | `services/communications/mcp_main.py` |

### 4.4 Port assignments (SSE mode)

| Service | HTTP port | MCP SSE port |
|---|---|---|
| Projects | 8001 | 9001 |
| People | 8002 | 9002 |
| Communications | 8003 | 9003 |

---

## 5. Shared Adapter in `agent_protocol/`

New file: `agent_protocol/mcp_adapter.py`. Contains all logic shared across the three MCP
servers. Operates on `Capability` objects and FastAPI `app` instances; has no knowledge of any
specific service.

**`capability_to_tool(cap, request_model, path_params, query_params) -> dict`**

Produces an MCP tool spec dict with keys `name`, `description`, `inputSchema`. Arguments:
`cap` is the `Capability` entry; `request_model` is the Pydantic body model or `None`;
`path_params` is a list of path parameter names parsed from `cap.path`
(e.g. `["project_id"]` for `"/projects/{project_id}/tasks"`); `query_params` is a list of
optional query parameter names.

**`class CatalogBackedMCPServer`**

Constructor takes `(app: FastAPI, server_name: str, tool_registry: dict)` where
`tool_registry` maps `tool_name -> (route_path_template, http_verb, request_model | None,
path_params, query_params)`. Wires up:

- `list_tools` handler: returns the full tool list via `capability_to_tool()`.
- `call_tool` handler: extracts path params from `arguments`, builds the URL, dispatches via
  `httpx.AsyncClient(transport=ASGITransport(app=app))`, returns
  `[{type: "text", text: json.dumps(envelope), annotations: {contentType: "application/json"}}]`.

The adapter does not parse, filter, or augment the dict returned by the FastAPI route.
`json.dumps` uses `default=str` to handle `datetime` in `_generated_at`.

---

## 6. Orchestrator Integration (behind a flag)

### 6.1 Environment variable

Add `ORCHESTRATOR_TOOL_MODE` to the orchestrator's config. Valid values: `http` (default) and
`mcp`. Default is `http` so the existing demo is unchanged.

### 6.2 New file: `services/orchestrator/mcp_tools.py` (new file to be created)

`MCPToolbox` mirrors `HTTPToolbox`'s role. Public interface:

```python
async def call_tool(self, server: str, tool: str, arguments: dict) -> dict: ...
```

`server` is one of `"projects"`, `"people"`, `"communications"`. Resolves the SSE URL from
a config dict `{"projects": "http://localhost:9001", ...}`, connects via the `mcp` client's
SSE transport, calls `tools/call`, and returns
`{"status": "ok", "content": <parsed envelope dict>}` or `{"status": "error", "message": "..."}`.

### 6.3 Changes to `services/orchestrator/graph.py`

All changes are gated by `ORCHESTRATOR_TOOL_MODE`; HTTP-mode paths are byte-for-byte unchanged.

- **Pre-plan discovery:** replace `http_get(f"{base}/")` with `mcp_client.list_tools(server)`;
  inject tool name + description lists into the planner prompt in place of `_catalog_summary`.
- **`PLANNER_SYSTEM` MCP variant:** instructs the LLM to emit
  `{"steps": [{"server": "projects", "tool": "post_projects", "rationale": "..."}, ...]}`;
  forbids inventing tool names not present in the listed tools.
- **`ACTOR_SYSTEM` MCP variant:** actor emits
  `{"server": "...", "tool": "...", "arguments": {...}, "rationale": "...", "is_final": false}`.
- **`_dispatch`:** polymorphic — delegates to `MCPToolbox.call_tool(step.server, step.tool,
  step.arguments)` in MCP mode, `HTTPToolbox` in HTTP mode.
- **`OrchestrationStep`** in `services/orchestrator/state.py`: add
  `server: str | None = None` and `tool: str | None = None`.

---

## 7. Dashboard Impact

None. The dashboard at `dashboard/` continues to call HTTP endpoints (`GET /projects`,
`GET /sse/...`). No dashboard code changes are required as part of this plan.

Optional future (deferred): add a trace-panel rendering raw MCP `tools/call` frames in MCP
mode. Note as deferred in `dashboard/README.md`.

---

## 8. Testing Strategy (no mocks)

All tests are real-integration tests per project rules. No mocks. No hardcoded magic values.
Every test uses a real SQLite database created in a `tmp_path` pytest fixture.

### 8.1 `tests/mcp/test_mcp_adapter_capability_mapping.py`

Imports all three capability lists directly. Feeds each `Capability` through
`capability_to_tool()`. Asserts: tool name matches derivation rule; `inputSchema` is a valid
JSON Schema object; required path params appear in `required`; the dict passes
`mcp.types.Tool.model_validate()`. No network, no DB.

### 8.2 `tests/mcp/test_mcp_server_projects.py`

Creates a real SQLite DB in `tmp_path`. Instantiates `CatalogBackedMCPServer` with the
Projects app. Calls `list_tools` in-process; asserts all tools from `_CAPABILITIES` are
present. Calls `call_tool` for `post_projects`, `get_projects`, `post_projects_id_tasks`,
`get_projects_id_tasks`. For each call asserts: returned text parses to a dict with
`data`, `_self`, `_related`, `_suggested_next`, `_generated_at`; envelope is structurally
identical to what `TestClient` returns for the same input.

### 8.3 `tests/mcp/test_mcp_server_people.py`

Equivalent of 8.2 for People. Exercises: `create_person`, `list_people`, `find_person`,
`update_person`, `filter_by_skill`, `filter_by_availability`.

### 8.4 `tests/mcp/test_mcp_server_communications.py`

Equivalent of 8.2 for Communications. Exercises: `send_message`, `list_messages`,
`find_message`, `filter_by_recipient`, `filter_by_project`.

### 8.5 `tests/mcp/test_mcp_stdio_transport_projects.py`

Launches `python -m services.projects.mcp_main` via `asyncio.create_subprocess_exec`. Uses
the `mcp` stdio client to call `tools/list` and `tools/call post_projects`. Asserts a valid
envelope is returned. Terminates the subprocess cleanly.

### 8.6 `tests/mcp/test_mcp_sse_transport_projects.py`

Launches `python -m services.projects.mcp_main --sse --port 9091`. Uses the `mcp` SSE client
to repeat the `tools/list` + `tools/call` assertions from 8.5. Uses port 9091 to avoid
clashing with the HTTP service on 8001.

### 8.7 Equivalent stdio + SSE tests for People and Communications

- `tests/mcp/test_mcp_stdio_transport_people.py`
- `tests/mcp/test_mcp_sse_transport_people.py` (port 9092)
- `tests/mcp/test_mcp_stdio_transport_communications.py`
- `tests/mcp/test_mcp_sse_transport_communications.py` (port 9093)

### 8.8 `tests/mcp/test_orchestrator_mcp_mode_end_to_end.py`

Reads all `AZURE_OPENAI_*` vars from `.env`; fails fast if missing. Starts all three MCP
servers in SSE mode as subprocesses (ports 9091, 9092, 9093). Submits the brief
`"Set up a Q3 landing page project with three tasks and notify Alice."` to the orchestrator
with `ORCHESTRATOR_TOOL_MODE=mcp`. Asserts: at least one project exists (`GET /projects`),
at least one task exists under it, a message was sent (`GET /messages`), orchestrator returns
`completed: true`. Uses the live Azure OpenAI LLM (same config as existing live tests).
Terminates MCP subprocesses in teardown.

### 8.9 Regression gate

All pre-existing HTTP-mode tests must pass unmodified after every increment.
`pytest tests/` with `ORCHESTRATOR_TOOL_MODE` unset is the gate; no increment is complete
until it exits green.

---

## 9. Rollout Increments (ordered)

Each increment ends with: targeted tests pass, `pytest tests/` (full suite) green,
`docs/implementation_status.md` updated, commit created (do not push).

| # | Work | Verification |
|---|---|---|
| 1 | Add `"mcp>=1.6,<2.0"` to `pyproject.toml`; `pip install -e .` | `python -c "import mcp; print(mcp.__version__)"` succeeds; `pytest tests/` green |
| 2 | Create `agent_protocol/mcp_adapter.py::capability_to_tool()`; create `tests/mcp/__init__.py` + `tests/mcp/test_mcp_adapter_capability_mapping.py` | `pytest tests/mcp/test_mcp_adapter_capability_mapping.py -v` passes |
| 3 | Add `CatalogBackedMCPServer` to `agent_protocol/mcp_adapter.py`; create `tests/mcp/test_mcp_server_projects.py` | `pytest tests/mcp/test_mcp_server_projects.py -v` passes |
| 4 | Create `services/projects/mcp_server.py` + `mcp_main.py` (stdio); create `tests/mcp/test_mcp_stdio_transport_projects.py` | stdio transport test passes |
| 5 | Add `--sse --port` to `services/projects/mcp_main.py`; create `tests/mcp/test_mcp_sse_transport_projects.py` | SSE transport test passes |
| 6 | Create `services/people/mcp_server.py` + `mcp_main.py`; create `tests/mcp/test_mcp_server_people.py`, `test_mcp_stdio_transport_people.py`, `test_mcp_sse_transport_people.py` | All three pass |
| 7 | Create `services/communications/mcp_server.py` + `mcp_main.py`; create `tests/mcp/test_mcp_server_communications.py`, `test_mcp_stdio_transport_communications.py`, `test_mcp_sse_transport_communications.py` | All three pass |
| 8 | Create `services/orchestrator/mcp_tools.py::MCPToolbox`; create `tests/mcp/test_orchestrator_mcp_toolbox.py` (starts People MCP server in SSE mode, calls `list_people`) | Toolbox test passes |
| 9 | Add `server`/`tool` fields to `OrchestrationStep` in `services/orchestrator/state.py`; add MCP-mode `PLANNER_SYSTEM`, `ACTOR_SYSTEM`, conditional `_dispatch` in `graph.py`; create `tests/mcp/test_orchestrator_mcp_graph_replay.py` (replay LLM, three MCP subprocesses) | Replay test passes; all pre-existing orchestrator tests still pass with `ORCHESTRATOR_TOOL_MODE` unset |
| 10 | Create `tests/mcp/test_orchestrator_mcp_mode_end_to_end.py` (see §8.8) | Test passes against live Azure OpenAI |
| 11 | Update `docs/implementation_status.md`, `docs/test_inventory.md` (add `tests/mcp/` section), `Briefing.md` (MCP Mode section), `AgentFirstByExample.md` (Claude Desktop worked example), `agent-first-flow.drawio` (MCP-mode overlay) | All docs consistent and cross-linked |
| 12 | Add Claude Desktop config block to `Briefing.md` under "Connecting Claude Desktop": | Reviewer can copy-paste config and connect |

```json
{
  "mcpServers": {
    "projects": {
      "command": "python",
      "args": ["-m", "services.projects.mcp_main"],
      "cwd": "/path/to/agent-first-service"
    },
    "people": {
      "command": "python",
      "args": ["-m", "services.people.mcp_main"],
      "cwd": "/path/to/agent-first-service"
    },
    "communications": {
      "command": "python",
      "args": ["-m", "services.communications.mcp_main"],
      "cwd": "/path/to/agent-first-service"
    }
  }
}
```

Use the venv Python binary for `"command"` in production configs.

---

## 10. Risks & Open Questions

**MCP SDK version stability.** The `Server` API and transport helpers (`stdio_server`,
`SseServerTransport`) may change between `1.x` minor versions. Mitigation: pin `>=1.6,<2.0`;
run the full suite against any version bump before merging.

**Tool name collisions across services.** If the orchestrator ever flattens all tools into a
single namespace, propose prefixing in the planner prompt: `projects.post_projects`,
`people.create_person`. Per-server `tools/list` names remain unprefixed.

**SSE transport and `sse-starlette` conflict.** The codebase already uses `sse-starlette>=2.1`.
Before Increment 1, confirm that adding `mcp` does not downgrade `sse-starlette`. The two SSE
layers already run on distinct port ranges (8001–8003 HTTP, 9001–9003 MCP SSE), so port
conflict is not a concern.

**Authentication.** MCP servers in this plan are unauthenticated — acceptable for a local demo.
Before any production deployment, add per-server API keys (`Authorization` header in SSE mode;
handshake token in stdio mode).

**Path parameter hoisting correctness.** The `call_tool` handler distinguishes path params
from body fields via the `path_params` list. Verify explicitly in `test_mcp_server_projects.py`
for `patch_tasks_id`, where `task_id` is a path param and `status`/`assignee_id`/`due_date`
are body fields from `UpdateTask`.

---

## 11. Done Criteria

The MCP wrapping feature is complete when all of the following are true:

1. `pytest tests/` passes in full with `ORCHESTRATOR_TOOL_MODE` unset (HTTP mode), confirming
   zero regression.
2. `pytest tests/` passes in full with `ORCHESTRATOR_TOOL_MODE=mcp` and all `AZURE_OPENAI_*`
   vars set, including `test_orchestrator_mcp_mode_end_to_end.py`.
3. Claude Desktop, configured with the sample JSON from Increment 12, can connect to each of
   the three MCP servers via stdio, call `tools/list`, and invoke at least one tool per server
   without error.
4. The Next.js dashboard demo (`npm run dev` + browser) behaves identically to today — no
   visual or functional change.
5. `docs/test_inventory.md` includes a `tests/mcp/` section covering all 12 new test files.
6. `agent-first-flow.drawio` contains an MCP-mode variant or overlay showing the new call path.
