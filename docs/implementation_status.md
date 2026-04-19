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
- [ ] Task 13: Wire up Makefile + env + documentation
- [ ] Task 14: Full regression and live smoke test

## Plan 3 — not started
## Plan 4 — not started
