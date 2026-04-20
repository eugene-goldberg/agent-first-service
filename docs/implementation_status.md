# Implementation Status

_Last updated: 2026-04-19_

## Plan 1 — Foundation & Projects Service ✅ COMPLETE

- [x] Task 1: Bootstrap
- [x] Task 2: `agent_protocol/envelope.py`
- [x] Task 3: `agent_protocol/errors.py`
- [x] Task 4: `agent_protocol/catalog.py`
- [x] Task 5: `agent_protocol/field_docs.py`
- [x] Task 6: Projects DB schema
- [x] Task 7: Projects Pydantic models
- [x] Task 8: Projects capabilities endpoint
- [x] Task 9: Projects CRUD routes
- [x] Task 10: Task routes
- [x] Task 11: Constraint error tests
- [x] Task 12: Seed loader + fixture
- [x] Task 13: `--seed-from` in main
- [x] Task 14: Root test configuration
- [x] Task 15: Documentation

**Evidence:** 29/29 tests passing; commit range `7702e51`..`d4b3a01` (16 commits).

## Plan 2 — Leaf Services (People + Communications)

_Deviation note: `tests/services/people/conftest.py` is deferred from Task 1 to Task 3 because pytest loads conftests at collection time and the plan's conftest imports `services.people.app.create_app` (built in Task 3)._

- [x] Task 1: People service — DB layer (commit `3852f85`, 1/1 tests passing)
- [ ] Task 2: People service — Pydantic models
- [ ] Task 3: People service — App factory and capabilities
- [ ] Task 4: People service — CRUD routes
- [ ] Task 5: People service — filter tests and constraint errors
- [ ] Task 6: People service — seed loader
- [ ] Task 7: Communications service — DB layer
- [ ] Task 8: Communications service — Pydantic models
- [ ] Task 9: Communications service — App factory and capabilities
- [ ] Task 10: Communications service — send and retrieve messages
- [ ] Task 11: Communications service — filters and constraint errors
- [ ] Task 12: Communications service — seed loader
- [x] Task 13: Wire up Makefile + env + documentation
- [x] Task 14: Full regression and live smoke test

## 2026-04-19 — Leaf services increment (Plan 2 complete)

**Plan:** `docs/superpowers/plans/2026-04-19-leaf-services.md`

**Completed:**
- People service (port 8002): DB, models, app factory, capabilities catalog, CRUD routes, skill/availability filters, semantic error envelopes, JSON seed loader, demo fixture.
- Communications service (port 8003): DB, models, app factory, capabilities catalog, send/list/find routes, recipient/project filters, semantic error envelopes, JSON seed loader, demo fixture.
- Makefile targets: `run-people`, `run-communications`, `test-people`, `test-communications`, `test-leaf-services`.
- Note: `agent_protocol/` was extended mid-Plan-2 (commit `95b9b80`) to add `try_instead` dict support; Tasks 4/5/10/11 adapted using string-vs-dict pattern for `try_instead` field compatibility.

**Evidence:** `pytest tests/ -v` → **76 passed, 0 failed** (protocol: 17, projects: 29, people: 16, communications: 14 — collected 76 items in 0.68 s). Live smoke tests: People service (port 8002) served `/` capabilities catalog and `/people` with all 4 seeded members; `?skill=python&available=true` returned Alice Chen only. Communications service (port 8003) accepted `POST /messages` (201), returned hypermedia envelope with `_suggested_next` links, and `GET /messages?recipient_id=person_alice` returned 1 message.

**Next:** Plan 3 — Orchestrator service (`docs/superpowers/plans/2026-04-19-orchestrator-service.md`).

## 2026-04-19 — Orchestrator service increment (Plan 3 complete)

**Plan:** `docs/superpowers/plans/2026-04-19-orchestrator-service.md`

**Completed:**
- LangGraph-based `OrchestrationGraph` (plan → act → observe → finalize).
- Pluggable `LLMClient` with `AzureLLMClient` and `ReplayLLMClient` modes.
- Generic `HTTPToolbox` (GET/POST/PATCH/DELETE) — the only tools the LLM gets.
- `TraceBus` in-memory pub/sub for live SSE fan-out.
- `OrchestrationRunner` with DB-backed job + trace persistence and `asyncio.create_task` execution.
- FastAPI routes: `POST /orchestrations`, `GET /orchestrations`, `GET /orchestrations/{id}`, `GET /orchestrations/{id}/trace`, `GET /sse/orchestrator`.
- Orchestrator's own hypermedia capability catalog at `GET /` — treats itself as a peer to the leaf services.
- Recorded LLM fixtures for the landing-page scenario (plan + 5 act steps + finalize).

**Evidence:** all orchestrator tests pass; live E2E smoke test walked through in Task 14.

**Known issue (follow-up):** An intermittent `RuntimeError('Event loop is closed')` was observed during the Task 14 smoke test when an SSE subscriber was active at the moment a new orchestration was spawned. The error propagates correctly as `event: error` and marks the job `failed`; subsequent orchestrations succeed. Suspected race in `OrchestrationRunner` loop acquisition under SSE fan-out. Flagged for Plan 4 hardening.

**Next:** Plan 4 — Client Agent + Dashboard (`docs/superpowers/plans/2026-04-19-client-agent-and-dashboard.md`).

## Plan 4 — not started
