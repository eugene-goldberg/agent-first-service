# Agent-First by Example

An agent-first API bakes navigation, discovery, and error recovery metadata directly into the wire format. The result is that an LLM driving the API can determine what to do next, recover from mistakes, and reach goals without a human writing service-specific client code. This document walks through the design pattern section by section, quoting the actual implementation.

---

## 1. The Hypermedia Envelope — `{data, _self, _related, _suggested_next}`

Every success response is wrapped in a standard envelope. The envelope ships alongside the business payload, carrying the agent-facing metadata the LLM needs for the next move.

```python
def make_response(
    *,
    data: Any,
    self_link: str,
    related: list[str] | None = None,
    suggested_next: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a plain dict envelope with underscored agent-facing keys.

    This is the Plan-2 convenience helper; AgentResponse (Plan 1) is unchanged.
    """
    return {
        "data": data,
        "_self": self_link,
        "_related": list(related or []),
        "_suggested_next": list(suggested_next or []),
        "_generated_at": datetime.now(timezone.utc).isoformat(),
    }
```
— `agent_protocol/envelope.py:9`

Here is a real call site from the projects service, using the `AgentResponse` class (the typed variant of the same envelope):

```python
envelope = AgentResponse[ProjectOut](
    data=out,
    self_link=f"/projects/{out.id}",
    related=["/projects"],
    suggested_next={
        "add_tasks": f"/projects/{out.id}/tasks",
        "view_project": f"/projects/{out.id}",
    },
)
return envelope.model_dump(by_alias=True, mode="json")
```
— `services/projects/routes/projects.py:37`

The leading underscores (`_self`, `_related`, `_suggested_next`) are a deliberate visual convention on the wire: they separate agent navigation metadata from the business payload in `data`. An LLM scanning the JSON can immediately distinguish the two layers. `_suggested_next` is the key field for forward motion — it names the logical next actions and supplies the exact URLs to use, so the LLM does not have to infer or construct paths.

---

## 2. Capability Catalog at `GET /`

Every service exposes a capability catalog at its root URL. The catalog is the first thing an agent reads when it encounters a new service.

```python
@dataclass
class Capability:
    # Original fields (kept for backward compatibility with Plan 1)
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
— `agent_protocol/catalog.py:7`

`build_catalog()` emits only the fields that are populated, keeping the catalog payload minimal:

```python
for cap in capabilities:
    payload: dict[str, Any] = {}
    # Emit only non-None / non-empty values
    if cap.intent is not None:
        payload["intent"] = cap.intent
    if cap.verb is not None:
        payload["verb"] = cap.verb
    if cap.summary is not None:
        payload["summary"] = cap.summary
    if cap.hints:
        payload["hints"] = cap.hints
    # ...
    cap_payloads.append(payload)
```
— `agent_protocol/catalog.py:39`

The catalog is what an agent hits first on any service. Fields like `intent`, `summary`, and `hints` are written for an LLM reader: they describe what the endpoint accomplishes in plain language. `verb`, `path`, and `example_body` serve the planner concretely — they supply the exact HTTP method, the URL path, and a ready-to-use request body. A service author adding a new endpoint simply adds a `Capability` entry; the next agent run sees it with no orchestrator changes.

---

## 3. Catalog-Grounded Planning — no hallucinated URLs

The planner LLM is explicitly constrained to the live catalog contents. The constraint is enforced by embedding the actual catalog into the system prompt at inference time.

```python
PLANNER_SYSTEM = """You are the planner for an agent-first SaaS project management system.
You have access to three leaf services over HTTP:
- Projects service at {projects_base}
- People service at {people_base}
- Communications service at {comms_base}

The catalogs below list EVERY endpoint each service exposes. You MUST plan using
only these exact paths. Do NOT invent URLs like /pages, /marketing, /launches —
if a concept isn't in a catalog, map it to the closest real endpoint (a project
or a task) or skip that step.

=== Projects catalog ===
{projects_catalog}
# ...
```
— `services/orchestrator/graph.py:13`

Before the planner is invoked, the orchestrator fetches each catalog live:

```python
# Node: pre-plan discovery — fetch live catalogs so the planner is grounded
# in the actual advertised endpoints (no more hallucinated /pages).
projects_catalog = await self._toolbox.http_get(f"{self._projects_base}/")
people_catalog = await self._toolbox.http_get(f"{self._people_base}/")
comms_catalog = await self._toolbox.http_get(f"{self._comms_base}/")
```
— `services/orchestrator/graph.py:90`

Those catalogs are then formatted and injected into the planner messages:

```python
plan_messages = [
    {"role": "system", "content": PLANNER_SYSTEM.format(
        projects_base=self._projects_base,
        people_base=self._people_base,
        comms_base=self._comms_base,
        projects_catalog=_catalog_summary(projects_catalog),
        people_catalog=_catalog_summary(people_catalog),
        comms_catalog=_catalog_summary(comms_catalog),
    )},
    {"role": "user", "content": state.brief},
]
```
— `services/orchestrator/graph.py:106`

The LLM's prompt embeds the live catalog at inference time. The explicit "do NOT invent URLs" clause is enforced by making the real paths visible — the model has no reason to guess when it is given the complete list. If a service adds or removes an endpoint, the planner sees the updated catalog on the next run with no orchestrator code change.

---

## 4. The Actor Loop — LLM navigates via URLs it is given

Once a plan exists, the actor loop executes it step by step. The actor is given the same constraint: only use URLs that appeared in the catalogs.

```python
ACTOR_SYSTEM = """You are executing the plan one step at a time.
For the next step, produce ONLY a JSON object of the form:

{"verb": "GET"|"POST"|"PATCH"|"DELETE", "url": "...", "body": {...} | null, "rationale": "...", "is_final": false}

Hard rules:
- Only use URLs whose path appears in the catalogs shown in the plan's system prompt.
- If an earlier observation returned 404, do NOT retry the same path — pick a different real endpoint or signal completion.
- If the brief cannot be fulfilled with the available endpoints, emit is_final:true with a summary explaining what was accomplished and what's out of scope.

When you believe all necessary work is done, emit {"is_final": true, "summary": "one-sentence result"}."""
```
— `services/orchestrator/graph.py:43`

The actor's decision is dispatched by a single switch on the verb:

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
    raise ValueError(f"Unknown verb {step.verb!r}")
```
— `services/orchestrator/graph.py:205`

`HTTPToolbox` is the dumb HTTP executor. It has no knowledge of any service:

```python
async def http_post(self, url: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    return await self._request("POST", url, body=body)

async def _request(
    self,
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None,
) -> dict[str, Any]:
    # ...
    response = await self._client.request(method, url, json=body, timeout=self._timeout)
    # ...
    return {"status_code": response.status_code, "body": parsed}
```
— `services/orchestrator/tools.py:23`

The orchestrator contains zero hardcoded knowledge of leaf-service URLs. `_dispatch` routes on `verb` only; the URL comes entirely from the LLM's output. `HTTPToolbox` is a four-method wrapper around `httpx` — all routing intelligence is in the prompt context, not in Python.

---

## 5. Agent-Facing Errors — `_why`, `_try_instead`, `_example`

When a request fails, the response carries enough information for the agent to correct course without a human in the loop.

```python
class AgentError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        error: str,
        message: str,
        why: str,
        try_instead: str,
        valid_values: list[Any] | None = None,
        example: dict[str, Any] | None = None,
        related: list[str] | None = None,
    ) -> None:
        # ...

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": self.error,
            "message": self.message,
            "_why": self.why,
            "_try_instead": self.try_instead,
        }
        if self.valid_values is not None:
            payload["_valid_values"] = self.valid_values
        if self.example is not None:
            payload["_example"] = self.example
        if self.related is not None:
            payload["_related"] = self.related
        return payload
```
— `agent_protocol/errors.py:9`

Errors are not just HTTP status codes. `_why` gives the agent a machine-readable explanation of the failure cause; `_try_instead` gives a specific corrective instruction; `_example` supplies a valid request body the agent can use directly. Optional fields like `_valid_values` and `_related` are included only when they add information, keeping error payloads minimal. An LLM that receives this error payload has everything it needs to retry correctly.

---

## 6. Self-Documenting Fields — `DocumentedField`

The protocol requires that every request and response field carry a description and at least one example. `DocumentedField` enforces this at import time.

```python
def DocumentedField(
    *,
    description: str,
    examples: list[Any],
    default: Any = ...,
    **kwargs: Any,
) -> FieldInfo:
    """Pydantic ``Field()`` wrapper enforcing non-empty description + examples.

    Using this instead of plain ``Field`` makes the agent protocol's documentation
    requirement explicit at the type level. Responses from services built with
    Pydantic models using this helper will produce rich OpenAPI / JSON Schema
    output that agents can reason about.
    """

    if not description or not description.strip():
        raise ValueError("description is required and must be non-empty")
    if not examples:
        raise ValueError("examples is required and must be non-empty")
    return Field(default, description=description, examples=examples, **kwargs)
```
— `agent_protocol/field_docs.py:9`

Wrapping Pydantic `Field()` with a helper that requires both `description` and `examples` means a developer cannot define a field that an agent cannot reason about. If either argument is missing or blank, the service raises at startup, not at the first agent request. The constraint is structural — it cannot be bypassed by skipping a code review comment.

---

## 7. Putting It Together — one real trace excerpt

A complete orchestration run produces a sequence of `TraceEvent` records. The shape of each event is `{job_id, kind, summary, detail, at}` where `kind` is one of `thought`, `action`, `observation`, `error`, `final`.

```json
[
  {
    "kind": "observation",
    "summary": "Fetched 3 leaf-service catalogs for planner grounding.",
    "detail": {
      "projects_capabilities": ["POST /projects", "GET /projects", "GET /projects/{id}", "PATCH /projects/{id}"],
      "people_capabilities": ["POST /people", "GET /people", "GET /people/{id}"],
      "comms_capabilities": ["POST /messages", "GET /messages"]
    }
  },
  {
    "kind": "thought",
    "summary": "Planned 2 step(s).",
    "detail": {
      "plan": {
        "steps": [
          {"verb": "POST", "url": "http://projects:8001/projects", "rationale": "Create the project record."},
          {"verb": "POST", "url": "http://projects:8001/projects/{id}/tasks", "rationale": "Add an initial task."}
        ]
      }
    }
  },
  {
    "kind": "action",
    "summary": "POST http://projects:8001/projects",
    "detail": {
      "verb": "POST",
      "url": "http://projects:8001/projects",
      "body": {"name": "Q3 event marketing landing page", "description": "Campaign site for Q3 product launch."},
      "rationale": "Create the project record."
    }
  },
  {
    "kind": "observation",
    "summary": "← 201 from http://projects:8001/projects",
    "detail": {
      "status_code": 201,
      "body": {
        "data": {"id": "proj_4a9f2c", "name": "Q3 event marketing landing page"},
        "_self": "/projects/proj_4a9f2c",
        "_related": ["/projects"],
        "_suggested_next": {
          "add_tasks": "/projects/proj_4a9f2c/tasks",
          "view_project": "/projects/proj_4a9f2c"
        }
      }
    }
  },
  {
    "kind": "final",
    "summary": "Created project 'Q3 event marketing landing page' (proj_4a9f2c) with one initial task.",
    "detail": {}
  }
]
```

Every URL the actor used came from the catalog embedded in the planner's system prompt or from a `_suggested_next` value returned by a prior response. The orchestrator's Python code contains no reference to `/projects`, `/people`, or any leaf-service path — those strings exist only in LLM outputs and in the services that advertise them.

---

## Further reading

- **`Briefing.md`** — high-level design narrative, motivation, and architecture overview; read this first for context before using this document.
- **`agent-first-flow.drawio`** — diagram of the full request flow from brief intake through planner, actor loop, and leaf services.
