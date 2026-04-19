# Implementation Plan

Phased delivery across four plans (see `docs/superpowers/plans/`).

1. **`2026-04-19-foundation-and-projects-service.md`** — Shared `agent_protocol/` library + Projects service on :8001. (This plan.)
2. **`2026-04-19-leaf-services.md`** — People (:8002) + Communications (:8003).
3. **`2026-04-19-orchestrator-service.md`** — Orchestrator service on :8000 (FastAPI + LangGraph + Azure OpenAI).
4. **`2026-04-19-client-agent-and-dashboard.md`** — Client Agent on :8080 + Next.js dashboard + demo wiring.

Each plan produces working, testable software on its own. Plans must be completed in order.
