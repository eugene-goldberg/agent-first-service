# LLM recordings

Recorded LLM responses used by tests and offline demos. Each scenario is a
directory; each file is named `<step>.json` where `<step>` is `plan`,
`act_1..act_N`, or `finalize` — matching the `step` argument passed to
`LLMClient.invoke(...)`.

## Format

```json
{
  "messages": [...the input messages, for provenance...],
  "response": {"content": "...the LLM output..."}
}
```

Only the `response` field is consumed by `ReplayLLMClient`. The `messages`
field is kept for humans so we can see what prompt was sent when this
fixture was captured.

## Provenance

These fixtures are hand-authored to exercise the orchestration graph
deterministically. They intentionally match the capability catalogs and
route shapes defined in Plans 1 and 2. If a leaf service changes URL
shapes, the matching fixture URLs must be updated here.

## Redaction

No secrets should appear in recordings. No PII. Demo data only.
