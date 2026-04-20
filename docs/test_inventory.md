# Test Inventory

Canonical list of all test modules in this project.

## tests/protocol/

| File | Covers | How to run | Deps |
|---|---|---|---|
| `test_envelope.py` | `AgentResponse` generic envelope (defaults, aliases, inbound parsing). Unit. | `pytest tests/protocol/test_envelope.py -v` | — |
| `test_errors.py` | `AgentError` exception + FastAPI handler render the full error envelope. Unit. | `pytest tests/protocol/test_errors.py -v` | — |
| `test_catalog.py` | `build_catalog()` shape, optional `example_body` handling. Unit. | `pytest tests/protocol/test_catalog.py -v` | — |
| `test_field_docs.py` | `DocumentedField` description/examples enforcement + schema output. Unit. | `pytest tests/protocol/test_field_docs.py -v` | — |

## tests/services/projects/

| File | Covers | How to run | Deps |
|---|---|---|---|
| `test_db.py` | SQLAlchemy schema + default column values. Unit (real SQLite in tmpdir). | `pytest tests/services/projects/test_db.py -v` | — |
| `test_models.py` | Pydantic request/response models for projects and tasks. Unit. | `pytest tests/services/projects/test_models.py -v` | — |
| `test_capabilities.py` | `GET /` capability catalog structure. Integration (TestClient + real SQLite). | `pytest tests/services/projects/test_capabilities.py -v` | — |
| `test_projects_crud.py` | POST / GET / PATCH /projects. Integration. | `pytest tests/services/projects/test_projects_crud.py -v` | — |
| `test_tasks.py` | POST / GET / PATCH / filter of task routes. Integration. | `pytest tests/services/projects/test_tasks.py -v` | — |
| `test_constraint_errors.py` | Semantic error envelope on 404/422/400 paths. Integration. | `pytest tests/services/projects/test_constraint_errors.py -v` | — |
| `test_seed.py` | Seed loader populates DB from JSON fixture. Integration. | `pytest tests/services/projects/test_seed.py -v` | — |

## External dependencies / credentials

None for this plan. Plans 3+ require Azure OpenAI credentials (`AZURE_OPENAI_*`).

## People service (`tests/services/people/`)

| Test file | Covers | Type | Run |
|---|---|---|---|
| `test_people_db.py` | SQLAlchemy PersonRow create/read | Integration (sqlite) | `pytest tests/services/people/test_people_db.py -v` |
| `test_models.py` | Pydantic model validation | Unit | `pytest tests/services/people/test_models.py -v` |
| `test_capabilities.py` | `GET /` capability catalog | Integration (TestClient) | `pytest tests/services/people/test_capabilities.py -v` |
| `test_people_crud.py` | Create/get/patch/list with envelope | Integration | `pytest tests/services/people/test_people_crud.py -v` |
| `test_people_filters.py` | `skill` and `available` query filters | Integration | `pytest tests/services/people/test_people_filters.py -v` |
| `test_constraint_errors.py` | 404 / 422 envelope semantics | Integration | `pytest tests/services/people/test_constraint_errors.py -v` |
| `test_seed.py` | JSON seed loader idempotence | Integration | `pytest tests/services/people/test_seed.py -v` |

External deps: none (sqlite is stdlib).

## Communications service (`tests/services/communications/`)

| Test file | Covers | Type | Run |
|---|---|---|---|
| `test_communications_db.py` | SQLAlchemy MessageRow create/read | Integration (sqlite) | `pytest tests/services/communications/test_communications_db.py -v` |
| `test_models.py` | Pydantic model validation | Unit | `pytest tests/services/communications/test_models.py -v` |
| `test_capabilities.py` | `GET /` capability catalog | Integration | `pytest tests/services/communications/test_capabilities.py -v` |
| `test_messages_crud.py` | Send/get/list with envelope | Integration | `pytest tests/services/communications/test_messages_crud.py -v` |
| `test_messages_filters.py` | `recipient_id` and `project_id` filters | Integration | `pytest tests/services/communications/test_messages_filters.py -v` |
| `test_constraint_errors.py` | 404 / 422 envelope semantics | Integration | `pytest tests/services/communications/test_constraint_errors.py -v` |
| `test_seed.py` | JSON seed loader idempotence | Integration | `pytest tests/services/communications/test_seed.py -v` |

External deps: none.

## Orchestrator service (`tests/services/orchestrator/`)

| Test file | Covers | Type | Run |
|---|---|---|---|
| `test_state_and_db.py` | OrchestrationState + JobRow/TraceEventRow | Unit + integration | `pytest tests/services/orchestrator/test_state_and_db.py -v` |
| `test_trace_bus.py` | TraceBus pub/sub fan-out | Async unit | `pytest tests/services/orchestrator/test_trace_bus.py -v` |
| `test_fake_llm.py` | ReplayLLMClient + LLMClient.from_env | Unit | `pytest tests/services/orchestrator/test_fake_llm.py -v` |
| `test_tools.py` | HTTPToolbox verbs | Integration (MockTransport) | `pytest tests/services/orchestrator/test_tools.py -v` |
| `test_capabilities.py` | `GET /` orchestrator catalog | Integration | `pytest tests/services/orchestrator/test_capabilities.py -v` |
| `test_graph_replay.py` | End-to-end graph replay against live leaf apps | Integration (ASGITransport) | `pytest tests/services/orchestrator/test_graph_replay.py -v` |
| `test_orchestrations_endpoint.py` | POST/GET/LIST/TRACE orchestration routes | Integration | `pytest tests/services/orchestrator/test_orchestrations_endpoint.py -v` |
| `test_sse_stream.py` | `/sse/orchestrator` live streaming | Async integration | `pytest tests/services/orchestrator/test_sse_stream.py -v` |
| `test_constraint_errors.py` | 404 / 422 envelope semantics | Integration | `pytest tests/services/orchestrator/test_constraint_errors.py -v` |
| `test_hybrid_llm.py` | HybridLLMClient live/fallback/both-fail + factory `ORCHESTRATOR_LLM_MODE=hybrid` | Unit | `pytest tests/services/orchestrator/test_hybrid_llm.py -v` |
| `test_graph_hybrid_trace.py` | Graph surfaces `llm_path` into trace events via `_with_llm_path` | Integration (ASGITransport) | `pytest tests/services/orchestrator/test_graph_hybrid_trace.py -v` |

External deps:
- `ORCHESTRATOR_REPLAY_DIR` must be set for tests. Default in tests: `fixtures/llm_recordings/landing_page`.
- For live runs against Azure OpenAI: set `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION`, and leave `ORCHESTRATOR_REPLAY_DIR` unset.
- For hybrid fallback mode: set `ORCHESTRATOR_LLM_MODE=hybrid` with BOTH Azure config and `ORCHESTRATOR_REPLAY_DIR` populated.

## Client Agent (`tests/services/client_agent/`)

| Test file | Covers | Type | Run |
|---|---|---|---|
| `test_state_bus_llm.py` | State, TraceBus, LLM replay factory | Unit / async | `pytest tests/services/client_agent/test_state_bus_llm.py -v` |
| `test_runner_replay.py` | Runner discovers + invokes orchestrator end-to-end | Integration (ASGITransport) | `pytest tests/services/client_agent/test_runner_replay.py -v` |
| `test_capabilities.py` | `GET /` client-agent catalog | Integration | `pytest tests/services/client_agent/test_capabilities.py -v` |
| `test_briefs_endpoint.py` | POST/GET/LIST briefs + background completion | Async integration | `pytest tests/services/client_agent/test_briefs_endpoint.py -v` |
| `test_sse_stream.py` | `/sse/client` streams published events | Async integration | `pytest tests/services/client_agent/test_sse_stream.py -v` |
| `test_constraint_errors.py` | 404 / 422 envelope semantics | Integration | `pytest tests/services/client_agent/test_constraint_errors.py -v` |
| `test_hybrid_llm.py` | ClientHybridLLM live/fallback/both-fail + factory `CLIENT_AGENT_LLM_MODE=hybrid` | Unit | `pytest tests/services/client_agent/test_hybrid_llm.py -v` |
| `test_runner_hybrid_trace.py` | Runner surfaces `llm_path` into trace events via `_with_llm_path` | Integration (ASGITransport) | `pytest tests/services/client_agent/test_runner_hybrid_trace.py -v` |

External deps: `CLIENT_AGENT_REPLAY_DIR` must point at `fixtures/llm_recordings/client_landing_page` for tests. For live Azure OpenAI, unset replay dir and set `AZURE_OPENAI_*`. For hybrid fallback: set `CLIENT_AGENT_LLM_MODE=hybrid` with BOTH Azure config and `CLIENT_AGENT_REPLAY_DIR` populated.

## Dashboard (Next.js, `dashboard/`)

The dashboard is a thin viewer with no unit tests in this plan. Its correctness is verified end-to-end during the manual demo (Task 12). The browser is the test harness:
- `npm run build` enforces TypeScript compilation; broken types fail the build.
- Runtime correctness is evaluated by watching trace events render live during the demo.
