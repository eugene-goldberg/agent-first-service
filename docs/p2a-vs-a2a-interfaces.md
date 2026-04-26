# P2A vs A2A Interfaces

Purpose: clarify how person-to-agent (P2A) interfaces differ from agent-to-agent (A2A) interfaces so teams can place boundaries, contracts, and controls correctly.

## Technical Definitions

- **P2A (Person-to-Agent):** An interface where a human expresses intent (usually natural language plus optional metadata) and an agent runtime interprets, plans, and executes actions.
- **A2A (Agent-to-Agent):** An interface where one software agent/system invokes another agent or capability through machine-oriented, explicit contracts (tool schemas, protocol envelopes, typed parameters).

## Protocol/Interface Characteristics

### P2A

- **Transport:** Commonly HTTP(S), WebSocket, or chat transports; optimized for interactive UX.
- **Schema strictness:** Loose at ingress (free-form text), then normalized internally into structured intent/state.
- **Discovery:** Human-visible capabilities (UI hints, help text, prompt/tool descriptions), not always protocol-native discovery.
- **Error handling:** User-oriented, ambiguity-tolerant; often includes clarification loops and recoverable retries.
- **State model:** Conversational/session-centric; partial, implicit state across turns is common.
- **Security:** End-user authN/authZ, session controls, rate limits, prompt/data safety filtering.

### A2A

- **Transport:** Protocol endpoints (for example JSON-RPC over stdio/HTTP, gRPC, message bus) with deterministic request/response behavior.
- **Schema strictness:** Strict typed schemas (JSON Schema/protobuf/etc.); invalid payloads should fail fast.
- **Discovery:** Protocol-level capability discovery (for example MCP `tools/list`) and machine-readable metadata.
- **Error handling:** Structured error envelopes with stable codes, retriable/non-retriable classification, and correlation IDs.
- **State model:** Explicit and scoped (request-local, transaction, or durable resource IDs); minimal implicit conversation semantics.
- **Security:** Service identity (mTLS, token exchange), least-privilege scopes, auditable action logs, policy enforcement per tool/action.

## Side-by-Side Comparison

| Dimension | P2A (Person-to-Agent) | A2A (Agent-to-Agent) |
|---|---|---|
| Primary caller | Human user | Software agent/service |
| Input shape | Natural language + optional context | Typed structured payloads |
| Contract style | Intent-level, probabilistic interpretation | Deterministic API/protocol contract |
| Validation point | Post-parse and guardrails | Pre-execution schema validation |
| Discovery method | UI/help/prompt docs | Protocol-native discovery endpoints |
| Error surface | Human-readable and corrective | Machine-readable with stable codes |
| State | Conversation/session memory | Explicit IDs, resources, or stateless calls |
| Change management | Prompt/version + UX updates | Versioned schemas and compatibility policy |
| Security emphasis | User trust/safety and data handling | Service identity, authorization scopes, auditability |

## Technical Examples

### 1) P2A HTTP Request (Natural Language Brief + Optional Context)

```json
POST /v1/agent/run
Content-Type: application/json
Authorization: Bearer <user_jwt>

{
  "brief": "Summarize incidents from last 24h and draft a status note for engineering leadership.",
  "context": {
    "workspace_id": "ws_42",
    "time_window": "24h",
    "preferred_tone": "concise-professional",
    "attachments": [
      {"type": "url", "value": "https://ops.example.com/incidents?window=24h"}
    ]
  }
}
```

### 2) A2A MCP `tools/list` Response Example

```json
{
  "jsonrpc": "2.0",
  "id": "req-1001",
  "result": {
    "tools": [
      {
        "name": "incidents.search",
        "description": "Search incidents by time window, severity, and service.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "from": {"type": "string", "format": "date-time"},
            "to": {"type": "string", "format": "date-time"},
            "severity": {"type": "string", "enum": ["low", "medium", "high", "critical"]}
          },
          "required": ["from", "to"]
        }
      },
      {
        "name": "reports.create_status_note",
        "description": "Create a leadership-facing status note from structured incident data.",
        "inputSchema": {
          "type": "object",
          "properties": {
            "audience": {"type": "string"},
            "highlights": {"type": "array", "items": {"type": "string"}}
          },
          "required": ["audience", "highlights"]
        }
      }
    ]
  }
}
```

### 3) A2A MCP `tools/call` Request + Success/Error Envelopes

```json
{
  "jsonrpc": "2.0",
  "id": "req-1002",
  "method": "tools/call",
  "params": {
    "name": "incidents.search",
    "arguments": {
      "from": "2026-04-25T12:00:00Z",
      "to": "2026-04-26T12:00:00Z",
      "severity": "high"
    }
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": "req-1002",
  "result": {
    "content": [
      {
        "type": "json",
        "json": {
          "count": 3,
          "incidents": [
            {"id": "inc_901", "service": "payments", "status": "mitigated"},
            {"id": "inc_902", "service": "gateway", "status": "resolved"},
            {"id": "inc_903", "service": "auth", "status": "monitoring"}
          ]
        }
      }
    ]
  }
}
```

```json
{
  "jsonrpc": "2.0",
  "id": "req-1002",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "field": "from",
      "reason": "must be RFC3339 date-time"
    }
  }
}
```

### 4) Translation Layer Pseudocode (P2A Intent -> A2A Tool Calls)

```text
function handleP2ARequest(p2aRequest):
  intent = nlu.parse(p2aRequest.brief, p2aRequest.context)
  plan = planner.toToolPlan(intent)

  tools = mcp.call("tools/list")
  validatedPlan = planner.validateAgainstSchemas(plan, tools.result.tools)

  outputs = []
  for step in validatedPlan.steps:
    resp = mcp.call("tools/call", { name: step.tool, arguments: step.args })
    if resp.error:
      if policy.isRetriable(resp.error.code):
        resp = retryWithBackoff(step)
      else:
        return userSafeError(intent, resp.error)
    outputs.append(resp.result)

  return responseComposer.toUserAnswer(intent, outputs)
```

## Practical Architecture Guidance

- **Boundary placement:** Keep P2A at the product edge (UI/API gateway), then convert to explicit internal intents before any A2A orchestration. Treat this translation boundary as a trust and contract boundary.
- **Observability:** Emit correlated traces across both layers (`request_id`, `session_id`, `tool_call_id`), log tool schema versions, capture latency per tool call, and classify failures into parse, validation, authorization, dependency, and policy classes.
- **Versioning strategy:** Version A2A contracts explicitly (schema semver, additive-first changes, deprecation windows). For P2A, version prompt/runtime policies separately from API payload shape, and monitor intent regression with golden interaction tests.

## Executive Summary

P2A and A2A solve different interface problems: P2A accepts ambiguous human intent and optimizes for usability, while A2A enforces strict machine contracts for deterministic interoperability. Robust systems place a deliberate translation layer between them, where intent is normalized, policies are enforced, and execution is expressed as validated tool calls with strong observability and versioned schemas.

**Slide-ready one-liner:** P2A interprets intent; A2A executes contracts.
