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
