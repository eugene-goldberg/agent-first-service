# Foundation & Projects Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared `agent_protocol/` library and a fully-working Projects service (port 8001) that exemplifies the hypermedia agent protocol, with comprehensive test coverage and protocol-conformance guarantees.

**Architecture:** Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2 + SQLite. The `agent_protocol/` library provides a response envelope, semantic errors, and capability catalog helpers used by every service in this project. The Projects service is the first consumer; the patterns it establishes (layout, seed loading, protocol conformance) are reused by Plans 2 and 3.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite (stdlib), pytest, pytest-asyncio, httpx.

**Spec:** `docs/superpowers/specs/2026-04-19-agent-first-services-design.md`

---

## File structure for this plan

New files created by this plan (grouped):

**Root:**
- `pyproject.toml`
- `.gitignore`
- `.env.example`
- `Makefile`

**Shared agent protocol library:**
- `agent_protocol/__init__.py`
- `agent_protocol/envelope.py`
- `agent_protocol/errors.py`
- `agent_protocol/catalog.py`
- `agent_protocol/field_docs.py`

**Projects service:**
- `services/__init__.py`
- `services/projects/__init__.py`
- `services/projects/main.py`
- `services/projects/app.py`
- `services/projects/db.py`
- `services/projects/models.py`
- `services/projects/seed.py`
- `services/projects/routes/__init__.py`
- `services/projects/routes/capabilities.py`
- `services/projects/routes/projects.py`
- `services/projects/routes/tasks.py`

**Fixtures & docs:**
- `fixtures/demo-seed/projects.json`
- `docs/test_inventory.md`
- `docs/implementation_plan.md`
- `docs/implementation_status.md`

**Tests:**
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/protocol/__init__.py`
- `tests/protocol/test_envelope.py`
- `tests/protocol/test_errors.py`
- `tests/protocol/test_catalog.py`
- `tests/protocol/test_field_docs.py`
- `tests/services/__init__.py`
- `tests/services/projects/__init__.py`
- `tests/services/projects/conftest.py`
- `tests/services/projects/test_capabilities.py`
- `tests/services/projects/test_projects_crud.py`
- `tests/services/projects/test_tasks.py`
- `tests/services/projects/test_seed.py`
- `tests/services/projects/test_constraint_errors.py`

---

## Task 1: Bootstrap project structure and tooling

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `Makefile`
- Create: `agent_protocol/__init__.py` (empty)
- Create: `services/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "agent-first-service"
version = "0.0.1"
description = "Agent-first services demo (Projects/People/Communications + Orchestrator)."
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "pydantic>=2.9",
    "sqlalchemy>=2.0",
    "uvicorn[standard]>=0.32",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-asyncio>=0.24",
    "ruff>=0.7",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["agent_protocol*", "services*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
addopts = "-v --tb=short"

[tool.ruff]
line-length = 100
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
venv/
.env
data/
*.db
.pytest_cache/
.ruff_cache/
dist/
build/
*.egg-info/
node_modules/
.next/
```

- [ ] **Step 3: Create `.env.example`**

```
# Azure OpenAI (used in later plans; not required for this plan)
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT_NAME=
AZURE_OPENAI_API_VERSION=2024-10-21
```

- [ ] **Step 4: Create `Makefile`**

```make
VENV := .venv
PY := $(VENV)/bin/python3
PIP := $(VENV)/bin/pip

$(VENV):
	python3 -m venv $(VENV)

.PHONY: install
install: $(VENV)
	$(PIP) install -U pip
	$(PIP) install -e ".[dev]"

.PHONY: test
test:
	$(PY) -m pytest

.PHONY: test-protocol
test-protocol:
	$(PY) -m pytest tests/protocol -v

.PHONY: test-projects
test-projects:
	$(PY) -m pytest tests/services/projects -v

.PHONY: run-projects
run-projects:
	$(PY) -m uvicorn services.projects.main:app --reload --port 8001

.PHONY: clean
clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache data
```

- [ ] **Step 5: Create package markers**

```bash
mkdir -p agent_protocol services tests fixtures/demo-seed docs/superpowers
: > agent_protocol/__init__.py
: > services/__init__.py
: > tests/__init__.py
```

- [ ] **Step 6: Install dev environment**

Run: `make install`
Expected: `.venv/` created, packages installed, final line `Successfully installed ...` without errors.

- [ ] **Step 7: Sanity check**

Run: `.venv/bin/python3 -c "import fastapi, pydantic, sqlalchemy; print('ok')"`
Expected output: `ok`

- [ ] **Step 8: Commit**

```bash
git init 2>/dev/null || true
git add pyproject.toml .gitignore .env.example Makefile agent_protocol/ services/ tests/
git commit -m "chore: bootstrap project structure and tooling"
```

---

## Task 2: Agent protocol — response envelope (TDD)

**Files:**
- Create: `tests/protocol/__init__.py` (empty)
- Create: `tests/protocol/test_envelope.py`
- Create: `agent_protocol/envelope.py`

- [ ] **Step 1: Create empty test package**

```bash
: > tests/protocol/__init__.py
```

- [ ] **Step 2: Write the failing test at `tests/protocol/test_envelope.py`**

```python
from datetime import datetime

from pydantic import BaseModel

from agent_protocol.envelope import AgentResponse


class _Payload(BaseModel):
    id: str
    name: str


def test_envelope_wraps_payload_and_defaults():
    response = AgentResponse[_Payload](
        data=_Payload(id="proj_1", name="Demo"),
        self_link="/projects/proj_1",
    )

    assert response.data.id == "proj_1"
    assert response.self_link == "/projects/proj_1"
    assert response.related == []
    assert response.suggested_next == {}
    assert isinstance(response.generated_at, datetime)
    assert response.generated_at.tzinfo is not None


def test_envelope_serialises_with_underscore_aliases():
    response = AgentResponse[_Payload](
        data=_Payload(id="proj_1", name="Demo"),
        self_link="/projects/proj_1",
        related=["/projects"],
        suggested_next={"add_tasks": "/projects/proj_1/tasks"},
    )

    dumped = response.model_dump(by_alias=True, mode="json")

    assert dumped["_self"] == "/projects/proj_1"
    assert dumped["_related"] == ["/projects"]
    assert dumped["_suggested_next"] == {"add_tasks": "/projects/proj_1/tasks"}
    assert "_generated_at" in dumped
    assert dumped["data"]["id"] == "proj_1"


def test_envelope_accepts_underscore_aliases_as_input():
    response = AgentResponse[_Payload].model_validate(
        {
            "data": {"id": "proj_1", "name": "Demo"},
            "_self": "/projects/proj_1",
            "_related": ["/projects"],
        }
    )
    assert response.self_link == "/projects/proj_1"
    assert response.related == ["/projects"]
```

- [ ] **Step 3: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_envelope.py -v`
Expected: `ModuleNotFoundError: No module named 'agent_protocol.envelope'`.

- [ ] **Step 4: Implement `agent_protocol/envelope.py`**

```python
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AgentResponse(BaseModel, Generic[T]):
    """Envelope wrapping every success response with hypermedia discovery metadata.

    Attribute names are human-friendly; JSON aliases use leading underscores
    (`_self`, `_related`, `_suggested_next`, `_generated_at`) so the wire format
    makes agent-facing fields visually distinct from the business payload.
    """

    model_config = ConfigDict(populate_by_name=True)

    data: T
    self_link: str = Field(alias="_self")
    related: list[str] = Field(default_factory=list, alias="_related")
    suggested_next: dict[str, Any] = Field(
        default_factory=dict, alias="_suggested_next"
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="_generated_at",
    )
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_envelope.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add agent_protocol/envelope.py tests/protocol/__init__.py tests/protocol/test_envelope.py
git commit -m "feat(protocol): add AgentResponse envelope with hypermedia fields"
```

---

## Task 3: Agent protocol — semantic errors (TDD)

**Files:**
- Create: `tests/protocol/test_errors.py`
- Create: `agent_protocol/errors.py`

- [ ] **Step 1: Write the failing test at `tests/protocol/test_errors.py`**

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent_protocol.errors import AgentError, register_error_handler


def _build_app() -> FastAPI:
    app = FastAPI()
    register_error_handler(app)

    @app.get("/raise/validation")
    def raise_validation():
        raise AgentError(
            status_code=400,
            error="missing_required_field",
            message="field 'name' is required",
            why="the 'name' field was not present in the request body",
            try_instead="include a 'name' string in the request body",
            example={"name": "My Project"},
        )

    @app.get("/raise/conflict")
    def raise_conflict():
        raise AgentError(
            status_code=409,
            error="capacity_exceeded",
            message="person is overbooked",
            why="Alice is at 120% capacity for the requested window",
            try_instead="try Bob (65%) or Carol (80%) instead",
            valid_values=["bob", "carol"],
            related=["/people/search"],
        )

    return app


def test_agent_error_renders_full_envelope():
    client = TestClient(_build_app())

    r = client.get("/raise/validation")
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "missing_required_field"
    assert body["message"] == "field 'name' is required"
    assert body["_why"].startswith("the 'name' field")
    assert body["_try_instead"].startswith("include a 'name'")
    assert body["_example"] == {"name": "My Project"}


def test_agent_error_includes_optional_fields_only_when_set():
    client = TestClient(_build_app())

    r = client.get("/raise/conflict")
    assert r.status_code == 409
    body = r.json()
    assert body["_valid_values"] == ["bob", "carol"]
    assert body["_related"] == ["/people/search"]
    assert "_example" not in body
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_errors.py -v`
Expected: `ModuleNotFoundError: No module named 'agent_protocol.errors'`.

- [ ] **Step 3: Implement `agent_protocol/errors.py`**

```python
from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AgentError(Exception):
    """Semantic error that renders as the agent error envelope.

    Fields marked optional are omitted from the response when not supplied,
    keeping responses minimal while still self-documenting.
    """

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
        super().__init__(message)
        self.status_code = status_code
        self.error = error
        self.message = message
        self.why = why
        self.try_instead = try_instead
        self.valid_values = valid_values
        self.example = example
        self.related = related

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


def register_error_handler(app: FastAPI) -> None:
    @app.exception_handler(AgentError)
    async def _handle(request: Request, exc: AgentError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=exc.to_payload())
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_errors.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_protocol/errors.py tests/protocol/test_errors.py
git commit -m "feat(protocol): add AgentError with semantic _why/_try_instead fields"
```

---

## Task 4: Agent protocol — capability catalog (TDD)

**Files:**
- Create: `tests/protocol/test_catalog.py`
- Create: `agent_protocol/catalog.py`

- [ ] **Step 1: Write the failing test at `tests/protocol/test_catalog.py`**

```python
from agent_protocol.catalog import Capability, build_catalog


def test_catalog_contains_capabilities_and_metadata():
    caps = [
        Capability(
            intent="create a new project",
            method="POST",
            path="/projects",
            example_body={"name": "My Project", "description": "..."},
            returns="Project resource",
        ),
        Capability(
            intent="list projects",
            method="GET",
            path="/projects",
            returns="list of Project resources",
        ),
    ]

    doc = build_catalog(
        service="Projects",
        description="Create and manage projects, tasks, and milestones.",
        capabilities=caps,
        related=["/projects", "/tasks"],
    )

    assert doc["service"] == "Projects"
    assert doc["description"].startswith("Create and manage")
    assert len(doc["capabilities"]) == 2
    assert doc["capabilities"][0]["method"] == "POST"
    assert doc["capabilities"][0]["example_body"] == {
        "name": "My Project",
        "description": "...",
    }
    assert "example_body" not in doc["capabilities"][1]  # not supplied
    assert doc["_self"] == "/"
    assert doc["_related"] == ["/projects", "/tasks"]
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_catalog.py -v`
Expected: `ModuleNotFoundError: No module named 'agent_protocol.catalog'`.

- [ ] **Step 3: Implement `agent_protocol/catalog.py`**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Capability:
    intent: str
    method: str
    path: str
    returns: str
    example_body: dict[str, Any] | None = None


def build_catalog(
    *,
    service: str,
    description: str,
    capabilities: list[Capability],
    related: list[str] | None = None,
) -> dict[str, Any]:
    """Build a capabilities catalog document served at `GET /` on every service."""

    cap_payloads: list[dict[str, Any]] = []
    for cap in capabilities:
        payload = {
            "intent": cap.intent,
            "method": cap.method,
            "path": cap.path,
            "returns": cap.returns,
        }
        if cap.example_body is not None:
            payload["example_body"] = cap.example_body
        cap_payloads.append(payload)

    return {
        "service": service,
        "description": description,
        "capabilities": cap_payloads,
        "_self": "/",
        "_related": list(related or []),
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_catalog.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add agent_protocol/catalog.py tests/protocol/test_catalog.py
git commit -m "feat(protocol): add capability catalog builder for GET / endpoints"
```

---

## Task 5: Agent protocol — field documentation helper (TDD)

**Files:**
- Create: `tests/protocol/test_field_docs.py`
- Create: `agent_protocol/field_docs.py`

- [ ] **Step 1: Write the failing test at `tests/protocol/test_field_docs.py`**

```python
import pytest
from pydantic import BaseModel, ValidationError

from agent_protocol.field_docs import DocumentedField


def test_documented_field_requires_description_and_examples():
    with pytest.raises(ValueError, match="description"):
        DocumentedField(description="", examples=["x"])

    with pytest.raises(ValueError, match="examples"):
        DocumentedField(description="a thing", examples=[])


def test_documented_field_exposes_description_and_examples_in_schema():
    class Project(BaseModel):
        name: str = DocumentedField(
            description="The project's short human-readable name.",
            examples=["Q3 Landing Page", "SSO rollout"],
        )

    schema = Project.model_json_schema()
    name_field = schema["properties"]["name"]
    assert name_field["description"].startswith("The project's short")
    assert name_field["examples"] == ["Q3 Landing Page", "SSO rollout"]


def test_documented_field_validates_payloads_normally():
    class Project(BaseModel):
        name: str = DocumentedField(description="x", examples=["y"])

    assert Project(name="hello").name == "hello"
    with pytest.raises(ValidationError):
        Project()
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_field_docs.py -v`
Expected: `ModuleNotFoundError: No module named 'agent_protocol.field_docs'`.

- [ ] **Step 3: Implement `agent_protocol/field_docs.py`**

```python
from __future__ import annotations

from typing import Any

from pydantic import Field
from pydantic.fields import FieldInfo


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

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/protocol/test_field_docs.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run the full protocol suite**

Run: `.venv/bin/python3 -m pytest tests/protocol -v`
Expected: 9 passed (3 envelope + 2 errors + 1 catalog + 3 field_docs).

- [ ] **Step 6: Commit**

```bash
git add agent_protocol/field_docs.py tests/protocol/test_field_docs.py
git commit -m "feat(protocol): add DocumentedField helper enforcing field descriptions"
```

---

## Task 6: Projects service — DB schema and SQLAlchemy setup (TDD)

**Files:**
- Create: `services/projects/__init__.py` (empty)
- Create: `services/projects/db.py`
- Create: `tests/services/__init__.py` (empty)
- Create: `tests/services/projects/__init__.py` (empty)
- Create: `tests/services/projects/conftest.py`
- Create: `tests/services/projects/test_db.py`

- [ ] **Step 1: Create package markers**

```bash
: > services/projects/__init__.py
: > tests/services/__init__.py
: > tests/services/projects/__init__.py
```

- [ ] **Step 2: Write `tests/services/projects/conftest.py`** (shared fixtures)

```python
from __future__ import annotations

import pathlib

import pytest
from sqlalchemy.orm import Session

from services.projects.db import Base, make_engine, make_sessionmaker


@pytest.fixture()
def sqlite_path(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "projects.db"


@pytest.fixture()
def session(sqlite_path: pathlib.Path) -> Session:
    engine = make_engine(sqlite_path)
    Base.metadata.create_all(engine)
    sm = make_sessionmaker(engine)
    with sm() as s:
        yield s
```

- [ ] **Step 3: Write failing test at `tests/services/projects/test_db.py`**

```python
from services.projects.db import ProjectRow, TaskRow, MilestoneRow


def test_can_insert_project_task_milestone(session):
    proj = ProjectRow(id="proj_1", name="Demo", description="seed")
    task = TaskRow(
        id="task_1",
        project_id="proj_1",
        title="copy",
        status="todo",
        assignee_id=None,
    )
    milestone = MilestoneRow(id="ms_1", project_id="proj_1", name="v1 launch")

    session.add_all([proj, task, milestone])
    session.commit()

    assert session.get(ProjectRow, "proj_1").name == "Demo"
    assert session.get(TaskRow, "task_1").title == "copy"
    assert session.get(MilestoneRow, "ms_1").name == "v1 launch"


def test_task_status_defaults_to_todo(session):
    session.add(ProjectRow(id="p", name="n", description="d"))
    session.add(TaskRow(id="t", project_id="p", title="q"))
    session.commit()
    assert session.get(TaskRow, "t").status == "todo"
```

- [ ] **Step 4: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_db.py -v`
Expected: `ModuleNotFoundError: No module named 'services.projects.db'`.

- [ ] **Step 5: Implement `services/projects/db.py`**

```python
from __future__ import annotations

import pathlib

from sqlalchemy import String, ForeignKey, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.orm import sessionmaker


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")

    tasks: Mapped[list["TaskRow"]] = relationship(back_populates="project")
    milestones: Mapped[list["MilestoneRow"]] = relationship(back_populates="project")


class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="todo", nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped[ProjectRow] = relationship(back_populates="tasks")


class MilestoneRow(Base):
    __tablename__ = "milestones"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped[ProjectRow] = relationship(back_populates="milestones")


def make_engine(sqlite_path: pathlib.Path | str) -> Engine:
    url = f"sqlite:///{sqlite_path}"
    return create_engine(url, echo=False, future=True)


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
```

- [ ] **Step 6: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_db.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add services/projects/__init__.py services/projects/db.py \
        tests/services/__init__.py tests/services/projects/__init__.py \
        tests/services/projects/conftest.py tests/services/projects/test_db.py
git commit -m "feat(projects): add SQLAlchemy schema for projects/tasks/milestones"
```

---

## Task 7: Projects service — Pydantic request/response models (TDD)

**Files:**
- Create: `services/projects/models.py`
- Create: `tests/services/projects/test_models.py`

- [ ] **Step 1: Write failing test at `tests/services/projects/test_models.py`**

```python
import pytest
from pydantic import ValidationError

from services.projects.models import (
    CreateProject,
    CreateTask,
    ProjectOut,
    TaskOut,
    UpdateTask,
)


def test_create_project_requires_name():
    with pytest.raises(ValidationError):
        CreateProject(description="no name")


def test_project_out_serialises_all_fields():
    p = ProjectOut(id="proj_1", name="Q3 Launch", description="Landing page")
    dumped = p.model_dump()
    assert dumped == {
        "id": "proj_1",
        "name": "Q3 Launch",
        "description": "Landing page",
    }


def test_task_out_includes_optional_fields():
    t = TaskOut(
        id="task_1",
        project_id="proj_1",
        title="copy",
        status="in_progress",
        assignee_id="alice",
        due_date="2026-05-20",
    )
    assert t.status == "in_progress"
    assert t.assignee_id == "alice"


def test_update_task_allows_partial_payload():
    u = UpdateTask(status="done")
    assert u.status == "done"
    assert u.assignee_id is None
    assert u.due_date is None
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_models.py -v`
Expected: `ModuleNotFoundError: No module named 'services.projects.models'`.

- [ ] **Step 3: Implement `services/projects/models.py`**

```python
from __future__ import annotations

from pydantic import BaseModel

from agent_protocol.field_docs import DocumentedField


class CreateProject(BaseModel):
    name: str = DocumentedField(
        description="Short human-readable name for the project.",
        examples=["Q3 Launch Landing Page", "SSO rollout"],
    )
    description: str = DocumentedField(
        description="One-paragraph description of the project's goal.",
        examples=["Marketing landing page for the Q3 launch campaign."],
        default="",
    )


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str


class CreateTask(BaseModel):
    title: str = DocumentedField(
        description="Short imperative task title.",
        examples=["Write landing page copy", "Implement hero section"],
    )
    assignee_id: str | None = DocumentedField(
        description="ID of the person assigned to this task. Null if unassigned.",
        examples=["alice", None],
        default=None,
    )
    due_date: str | None = DocumentedField(
        description="ISO 8601 date (YYYY-MM-DD) by which the task should be complete.",
        examples=["2026-05-20", None],
        default=None,
    )


class TaskOut(BaseModel):
    id: str
    project_id: str
    title: str
    status: str
    assignee_id: str | None = None
    due_date: str | None = None


class UpdateTask(BaseModel):
    status: str | None = DocumentedField(
        description="New task status.",
        examples=["todo", "in_progress", "done"],
        default=None,
    )
    assignee_id: str | None = DocumentedField(
        description="New assignee ID; set to null to unassign.",
        examples=["alice", None],
        default=None,
    )
    due_date: str | None = DocumentedField(
        description="New due date in ISO 8601 (YYYY-MM-DD).",
        examples=["2026-05-20"],
        default=None,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_models.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add services/projects/models.py tests/services/projects/test_models.py
git commit -m "feat(projects): add Pydantic models for project/task CRUD"
```

---

## Task 8: Projects service — FastAPI app factory + capabilities endpoint (TDD)

**Files:**
- Create: `services/projects/app.py`
- Create: `services/projects/main.py`
- Create: `services/projects/routes/__init__.py` (empty)
- Create: `services/projects/routes/capabilities.py`
- Create: `tests/services/projects/test_capabilities.py`

- [ ] **Step 1: Write failing test at `tests/services/projects/test_capabilities.py`**

```python
from fastapi.testclient import TestClient

from services.projects.app import create_app


def test_capabilities_endpoint_returns_catalog(sqlite_path):
    app = create_app(sqlite_path=sqlite_path)
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200

    body = r.json()
    assert body["service"] == "Projects"
    assert body["_self"] == "/"
    assert body["_related"] == ["/projects", "/tasks"]
    assert isinstance(body["capabilities"], list)
    assert any(cap["path"] == "/projects" and cap["method"] == "POST"
               for cap in body["capabilities"])
    assert any(cap["path"] == "/projects/{id}/tasks" and cap["method"] == "POST"
               for cap in body["capabilities"])
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_capabilities.py -v`
Expected: `ModuleNotFoundError: No module named 'services.projects.app'`.

- [ ] **Step 3: Create empty routes package**

```bash
: > services/projects/routes/__init__.py
```

- [ ] **Step 4: Implement `services/projects/routes/capabilities.py`**

```python
from __future__ import annotations

from fastapi import APIRouter

from agent_protocol.catalog import Capability, build_catalog

router = APIRouter()

_CAPABILITIES = [
    Capability(
        intent="list all projects",
        method="GET",
        path="/projects",
        returns="list of Project resources wrapped in the agent response envelope",
    ),
    Capability(
        intent="create a new project",
        method="POST",
        path="/projects",
        example_body={"name": "Q3 Launch Landing Page", "description": "Marketing launch"},
        returns="Project resource with _suggested_next link to add tasks",
    ),
    Capability(
        intent="get a project by id",
        method="GET",
        path="/projects/{id}",
        returns="Project resource with links to its tasks and milestones",
    ),
    Capability(
        intent="update a project",
        method="PATCH",
        path="/projects/{id}",
        example_body={"name": "Updated Name", "description": "Updated description"},
        returns="Updated Project resource",
    ),
    Capability(
        intent="list tasks belonging to a project",
        method="GET",
        path="/projects/{id}/tasks",
        returns="list of Task resources",
    ),
    Capability(
        intent="create a task under a project",
        method="POST",
        path="/projects/{id}/tasks",
        example_body={"title": "Write copy", "assignee_id": None, "due_date": "2026-05-20"},
        returns="Task resource",
    ),
    Capability(
        intent="update a task",
        method="PATCH",
        path="/tasks/{id}",
        example_body={"status": "in_progress", "assignee_id": "alice"},
        returns="Updated Task resource",
    ),
    Capability(
        intent="query tasks across all projects",
        method="GET",
        path="/tasks?assignee={id}&status={status}&milestone={id}",
        returns="list of Task resources matching filters",
    ),
]


@router.get("/")
def capabilities() -> dict:
    return build_catalog(
        service="Projects",
        description=(
            "Create and manage projects, tasks, and milestones for the business entity. "
            "All responses are wrapped in the agent response envelope; follow "
            "_suggested_next links to perform multi-step workflows."
        ),
        capabilities=_CAPABILITIES,
        related=["/projects", "/tasks"],
    )
```

- [ ] **Step 5: Implement `services/projects/app.py`**

```python
from __future__ import annotations

import pathlib

from fastapi import FastAPI

from agent_protocol.errors import register_error_handler
from services.projects.db import Base, make_engine, make_sessionmaker
from services.projects.routes import capabilities as capabilities_routes


def create_app(*, sqlite_path: pathlib.Path | str) -> FastAPI:
    engine = make_engine(sqlite_path)
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)

    app = FastAPI(title="Projects")
    app.state.session_maker = session_maker

    register_error_handler(app)
    app.include_router(capabilities_routes.router)

    return app
```

- [ ] **Step 6: Implement `services/projects/main.py`**

```python
from __future__ import annotations

import os
import pathlib

from services.projects.app import create_app

_DEFAULT_DB = pathlib.Path(os.getenv("PROJECTS_DB", "data/projects.db"))
_DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)

app = create_app(sqlite_path=_DEFAULT_DB)
```

- [ ] **Step 7: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_capabilities.py -v`
Expected: 1 passed.

- [ ] **Step 8: Commit**

```bash
git add services/projects/app.py services/projects/main.py \
        services/projects/routes/ tests/services/projects/test_capabilities.py
git commit -m "feat(projects): add FastAPI app with capabilities catalog endpoint"
```

---

## Task 9: Projects service — CRUD routes for /projects (TDD)

**Files:**
- Create: `services/projects/routes/projects.py`
- Modify: `services/projects/app.py`
- Create: `tests/services/projects/test_projects_crud.py`

- [ ] **Step 1: Write failing test at `tests/services/projects/test_projects_crud.py`**

```python
from fastapi.testclient import TestClient

from services.projects.app import create_app


def _client(sqlite_path):
    return TestClient(create_app(sqlite_path=sqlite_path))


def test_create_project_returns_envelope_and_suggested_next(sqlite_path):
    client = _client(sqlite_path)

    r = client.post("/projects", json={"name": "Q3 Launch", "description": "Landing page"})
    assert r.status_code == 201

    body = r.json()
    assert body["_self"].startswith("/projects/proj_")
    assert body["data"]["name"] == "Q3 Launch"
    assert "add_tasks" in body["_suggested_next"]
    assert body["_suggested_next"]["add_tasks"].endswith("/tasks")


def test_list_projects_returns_items_wrapped_in_envelope(sqlite_path):
    client = _client(sqlite_path)

    client.post("/projects", json={"name": "One", "description": "a"})
    client.post("/projects", json={"name": "Two", "description": "b"})

    r = client.get("/projects")
    assert r.status_code == 200
    body = r.json()
    assert body["_self"] == "/projects"
    assert len(body["data"]) == 2
    names = {p["name"] for p in body["data"]}
    assert names == {"One", "Two"}


def test_get_project_by_id(sqlite_path):
    client = _client(sqlite_path)
    created = client.post("/projects", json={"name": "Solo", "description": ""}).json()
    pid = created["data"]["id"]

    r = client.get(f"/projects/{pid}")
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["id"] == pid
    assert body["_self"] == f"/projects/{pid}"


def test_patch_project_updates_fields(sqlite_path):
    client = _client(sqlite_path)
    pid = client.post("/projects", json={"name": "Old", "description": "x"}).json()["data"]["id"]

    r = client.patch(f"/projects/{pid}", json={"name": "New"})
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "New"
    assert r.json()["data"]["description"] == "x"
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_projects_crud.py -v`
Expected: 404 or ModuleNotFoundError (routes not yet registered).

- [ ] **Step 3: Implement `services/projects/routes/projects.py`**

```python
from __future__ import annotations

import secrets

from fastapi import APIRouter, Request, Response

from agent_protocol.envelope import AgentResponse
from agent_protocol.errors import AgentError
from services.projects.db import ProjectRow
from services.projects.models import CreateProject, ProjectOut

router = APIRouter()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


def _to_out(row: ProjectRow) -> ProjectOut:
    return ProjectOut(id=row.id, name=row.name, description=row.description)


@router.post("/projects", status_code=201)
def create_project(body: CreateProject, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = ProjectRow(
            id=_new_id("proj"),
            name=body.name,
            description=body.description,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

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


@router.get("/projects")
def list_projects(request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        rows = s.query(ProjectRow).all()
        items = [_to_out(r) for r in rows]

    envelope = AgentResponse[list[ProjectOut]](
        data=items,
        self_link="/projects",
        related=[f"/projects/{p.id}" for p in items],
        suggested_next={"create_project": "/projects"},
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = s.get(ProjectRow, project_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="project_not_found",
                message=f"no project with id {project_id}",
                why=f"the project id {project_id} does not exist in this service",
                try_instead="call GET /projects to list existing project ids",
                related=["/projects"],
            )
        out = _to_out(row)

    envelope = AgentResponse[ProjectOut](
        data=out,
        self_link=f"/projects/{out.id}",
        related=[f"/projects/{out.id}/tasks", "/projects"],
        suggested_next={
            "list_tasks": f"/projects/{out.id}/tasks",
            "update": f"/projects/{out.id}",
        },
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, body: dict, request: Request) -> dict:
    allowed = {"name", "description"}
    bad = set(body.keys()) - allowed
    if bad:
        raise AgentError(
            status_code=400,
            error="unknown_fields",
            message=f"unknown field(s): {sorted(bad)}",
            why=f"the fields {sorted(bad)} are not editable on a project",
            try_instead=f"use only {sorted(allowed)} in the request body",
            valid_values=sorted(allowed),
            example={"name": "New Name"},
        )

    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = s.get(ProjectRow, project_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="project_not_found",
                message=f"no project with id {project_id}",
                why=f"the project id {project_id} does not exist in this service",
                try_instead="call GET /projects to list existing project ids",
                related=["/projects"],
            )
        for k, v in body.items():
            setattr(row, k, v)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[ProjectOut](
        data=out,
        self_link=f"/projects/{out.id}",
        related=[f"/projects/{out.id}/tasks"],
    )
    return envelope.model_dump(by_alias=True, mode="json")
```

- [ ] **Step 4: Modify `services/projects/app.py`** to register the new router

Find this block:

```python
from services.projects.routes import capabilities as capabilities_routes
```

Replace with:

```python
from services.projects.routes import (
    capabilities as capabilities_routes,
    projects as projects_routes,
)
```

Find this line:

```python
    app.include_router(capabilities_routes.router)
```

Replace with:

```python
    app.include_router(capabilities_routes.router)
    app.include_router(projects_routes.router)
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_projects_crud.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add services/projects/routes/projects.py services/projects/app.py \
        tests/services/projects/test_projects_crud.py
git commit -m "feat(projects): add project CRUD routes with hypermedia envelope"
```

---

## Task 10: Projects service — Task routes (TDD)

**Files:**
- Create: `services/projects/routes/tasks.py`
- Modify: `services/projects/app.py`
- Create: `tests/services/projects/test_tasks.py`

- [ ] **Step 1: Write failing test at `tests/services/projects/test_tasks.py`**

```python
from fastapi.testclient import TestClient

from services.projects.app import create_app


def _client(sqlite_path):
    return TestClient(create_app(sqlite_path=sqlite_path))


def _new_project(client) -> str:
    return client.post("/projects", json={"name": "P", "description": ""}).json()["data"]["id"]


def test_create_task_under_project(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)

    r = client.post(f"/projects/{pid}/tasks", json={"title": "write copy"})
    assert r.status_code == 201
    body = r.json()
    assert body["data"]["title"] == "write copy"
    assert body["data"]["status"] == "todo"
    assert body["_self"].startswith("/tasks/task_")
    assert "assign" in body["_suggested_next"]
    assert "update_status" in body["_suggested_next"]


def test_list_tasks_under_project(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)
    client.post(f"/projects/{pid}/tasks", json={"title": "a"})
    client.post(f"/projects/{pid}/tasks", json={"title": "b"})

    r = client.get(f"/projects/{pid}/tasks")
    assert r.status_code == 200
    body = r.json()
    assert len(body["data"]) == 2


def test_patch_task_updates_status_and_assignee(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)
    tid = client.post(f"/projects/{pid}/tasks", json={"title": "x"}).json()["data"]["id"]

    r = client.patch(f"/tasks/{tid}", json={"status": "in_progress", "assignee_id": "alice"})
    assert r.status_code == 200
    body = r.json()
    assert body["data"]["status"] == "in_progress"
    assert body["data"]["assignee_id"] == "alice"


def test_filter_tasks_by_assignee_and_status(sqlite_path):
    client = _client(sqlite_path)
    pid = _new_project(client)
    t1 = client.post(f"/projects/{pid}/tasks", json={"title": "a"}).json()["data"]["id"]
    t2 = client.post(f"/projects/{pid}/tasks", json={"title": "b"}).json()["data"]["id"]
    client.patch(f"/tasks/{t1}", json={"status": "done", "assignee_id": "alice"})
    client.patch(f"/tasks/{t2}", json={"status": "todo", "assignee_id": "alice"})

    r = client.get("/tasks", params={"assignee": "alice", "status": "done"})
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) == 1
    assert items[0]["id"] == t1
```

- [ ] **Step 2: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_tasks.py -v`
Expected: 404 for task endpoints.

- [ ] **Step 3: Implement `services/projects/routes/tasks.py`**

```python
from __future__ import annotations

import secrets

from fastapi import APIRouter, Request

from agent_protocol.envelope import AgentResponse
from agent_protocol.errors import AgentError
from services.projects.db import ProjectRow, TaskRow
from services.projects.models import CreateTask, TaskOut, UpdateTask

router = APIRouter()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


def _to_out(row: TaskRow) -> TaskOut:
    return TaskOut(
        id=row.id,
        project_id=row.project_id,
        title=row.title,
        status=row.status,
        assignee_id=row.assignee_id,
        due_date=row.due_date,
    )


def _task_suggested_next(task_id: str) -> dict:
    return {
        "update_status": {
            "method": "PATCH",
            "path": f"/tasks/{task_id}",
            "body_hint": {"status": "in_progress|done|blocked"},
        },
        "assign": {
            "method": "PATCH",
            "path": f"/tasks/{task_id}",
            "body_hint": {"assignee_id": "<person_id from People service>"},
        },
    }


@router.post("/projects/{project_id}/tasks", status_code=201)
def create_task(project_id: str, body: CreateTask, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        if s.get(ProjectRow, project_id) is None:
            raise AgentError(
                status_code=422,
                error="project_missing",
                message=f"cannot add task: project {project_id} does not exist",
                why=f"the parent project {project_id} was not found",
                try_instead="create the project first via POST /projects, then add tasks under it",
                related=["/projects"],
            )
        row = TaskRow(
            id=_new_id("task"),
            project_id=project_id,
            title=body.title,
            assignee_id=body.assignee_id,
            due_date=body.due_date,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[TaskOut](
        data=out,
        self_link=f"/tasks/{out.id}",
        related=[f"/projects/{project_id}/tasks", f"/projects/{project_id}"],
        suggested_next=_task_suggested_next(out.id),
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/projects/{project_id}/tasks")
def list_tasks_for_project(project_id: str, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        if s.get(ProjectRow, project_id) is None:
            raise AgentError(
                status_code=404,
                error="project_not_found",
                message=f"no project with id {project_id}",
                why="cannot list tasks for a project that does not exist",
                try_instead="call GET /projects to see available projects",
                related=["/projects"],
            )
        rows = s.query(TaskRow).filter(TaskRow.project_id == project_id).all()
        items = [_to_out(r) for r in rows]

    envelope = AgentResponse[list[TaskOut]](
        data=items,
        self_link=f"/projects/{project_id}/tasks",
        related=[f"/projects/{project_id}"],
        suggested_next={"add_task": f"/projects/{project_id}/tasks"},
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.patch("/tasks/{task_id}")
def patch_task(task_id: str, body: UpdateTask, request: Request) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        row = s.get(TaskRow, task_id)
        if row is None:
            raise AgentError(
                status_code=404,
                error="task_not_found",
                message=f"no task with id {task_id}",
                why=f"the task id {task_id} does not exist",
                try_instead="call GET /tasks or GET /projects/{id}/tasks to list task ids",
                related=["/tasks", "/projects"],
            )
        updates = body.model_dump(exclude_none=True)
        for k, v in updates.items():
            setattr(row, k, v)
        s.commit()
        s.refresh(row)
        out = _to_out(row)

    envelope = AgentResponse[TaskOut](
        data=out,
        self_link=f"/tasks/{out.id}",
        related=[f"/projects/{out.project_id}/tasks", f"/projects/{out.project_id}"],
        suggested_next=_task_suggested_next(out.id),
    )
    return envelope.model_dump(by_alias=True, mode="json")


@router.get("/tasks")
def query_tasks(
    request: Request,
    assignee: str | None = None,
    status: str | None = None,
    milestone: str | None = None,
) -> dict:
    session_maker = request.app.state.session_maker
    with session_maker() as s:
        q = s.query(TaskRow)
        if assignee is not None:
            q = q.filter(TaskRow.assignee_id == assignee)
        if status is not None:
            q = q.filter(TaskRow.status == status)
        if milestone is not None:
            # milestone filtering placeholder: tasks have no milestone_id yet in this plan
            q = q.filter(False)
        rows = q.all()
        items = [_to_out(r) for r in rows]

    envelope = AgentResponse[list[TaskOut]](
        data=items,
        self_link="/tasks",
        related=["/projects"],
    )
    return envelope.model_dump(by_alias=True, mode="json")
```

- [ ] **Step 4: Modify `services/projects/app.py`** to register tasks router

Find:

```python
from services.projects.routes import (
    capabilities as capabilities_routes,
    projects as projects_routes,
)
```

Replace with:

```python
from services.projects.routes import (
    capabilities as capabilities_routes,
    projects as projects_routes,
    tasks as tasks_routes,
)
```

Find:

```python
    app.include_router(capabilities_routes.router)
    app.include_router(projects_routes.router)
```

Replace with:

```python
    app.include_router(capabilities_routes.router)
    app.include_router(projects_routes.router)
    app.include_router(tasks_routes.router)
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_tasks.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add services/projects/routes/tasks.py services/projects/app.py \
        tests/services/projects/test_tasks.py
git commit -m "feat(projects): add task routes with suggested_next hypermedia links"
```

---

## Task 11: Projects service — Constraint error coverage (TDD)

**Files:**
- Create: `tests/services/projects/test_constraint_errors.py`

(No code changes expected — validates the error envelope shape already produced by Tasks 9–10.)

- [ ] **Step 1: Write test at `tests/services/projects/test_constraint_errors.py`**

```python
from fastapi.testclient import TestClient

from services.projects.app import create_app


def _client(sqlite_path):
    return TestClient(create_app(sqlite_path=sqlite_path))


def test_project_not_found_returns_semantic_error(sqlite_path):
    client = _client(sqlite_path)
    r = client.get("/projects/proj_nope")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "project_not_found"
    assert "GET /projects" in body["_try_instead"]
    assert body["_related"] == ["/projects"]


def test_task_not_found_returns_semantic_error(sqlite_path):
    client = _client(sqlite_path)
    r = client.patch("/tasks/task_nope", json={"status": "done"})
    assert r.status_code == 404
    assert r.json()["error"] == "task_not_found"


def test_missing_project_when_creating_task_returns_422(sqlite_path):
    client = _client(sqlite_path)
    r = client.post("/projects/proj_nope/tasks", json={"title": "x"})
    assert r.status_code == 422
    body = r.json()
    assert body["error"] == "project_missing"
    assert "POST /projects" in body["_try_instead"]


def test_patch_project_with_unknown_fields_returns_400(sqlite_path):
    client = _client(sqlite_path)
    pid = client.post("/projects", json={"name": "p", "description": ""}).json()["data"]["id"]
    r = client.patch(f"/projects/{pid}", json={"owner": "alice"})
    assert r.status_code == 400
    body = r.json()
    assert body["error"] == "unknown_fields"
    assert "owner" in body["message"]
    assert body["_valid_values"] == ["description", "name"]
```

- [ ] **Step 2: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_constraint_errors.py -v`
Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/services/projects/test_constraint_errors.py
git commit -m "test(projects): verify semantic error envelope across error paths"
```

---

## Task 12: Projects service — Seed loading from JSON fixture (TDD)

**Files:**
- Create: `services/projects/seed.py`
- Create: `fixtures/demo-seed/projects.json`
- Create: `tests/services/projects/test_seed.py`

- [ ] **Step 1: Create `fixtures/demo-seed/projects.json`**

```json
{
  "projects": [
    {
      "id": "proj_seed_alpha",
      "name": "Existing Customer Portal",
      "description": "The customer-facing portal we already operate.",
      "tasks": [
        {"id": "task_seed_a1", "title": "Add CSV export", "status": "in_progress", "assignee_id": "bob", "due_date": "2026-05-10"},
        {"id": "task_seed_a2", "title": "Fix login error on Safari", "status": "todo", "assignee_id": null, "due_date": null}
      ],
      "milestones": [
        {"id": "ms_seed_alpha_v2", "name": "Portal v2", "due_date": "2026-07-01"}
      ]
    }
  ]
}
```

- [ ] **Step 2: Write failing test at `tests/services/projects/test_seed.py`**

```python
import json

from fastapi.testclient import TestClient

from services.projects.app import create_app
from services.projects.seed import load_seed


def test_load_seed_populates_db(tmp_path, sqlite_path):
    fixture = tmp_path / "seed.json"
    fixture.write_text(json.dumps({
        "projects": [
            {"id": "proj_x", "name": "X", "description": "d",
             "tasks": [{"id": "task_x1", "title": "t", "status": "todo", "assignee_id": None, "due_date": None}],
             "milestones": []}
        ]
    }))

    app = create_app(sqlite_path=sqlite_path)
    load_seed(app.state.session_maker, fixture)

    client = TestClient(app)
    r = client.get("/projects/proj_x")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == "X"

    r2 = client.get("/projects/proj_x/tasks")
    assert len(r2.json()["data"]) == 1
    assert r2.json()["data"][0]["id"] == "task_x1"
```

- [ ] **Step 3: Run to see it fail**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_seed.py -v`
Expected: ImportError for `services.projects.seed`.

- [ ] **Step 4: Implement `services/projects/seed.py`**

```python
from __future__ import annotations

import json
import pathlib

from sqlalchemy.orm import sessionmaker

from services.projects.db import MilestoneRow, ProjectRow, TaskRow


def load_seed(session_maker: sessionmaker, fixture_path: pathlib.Path | str) -> None:
    """Load a seed JSON file into the DB. Safe to call on an empty or primed DB:
    pre-existing rows with the same primary key are replaced.
    """

    data = json.loads(pathlib.Path(fixture_path).read_text())
    with session_maker() as s:
        for p in data.get("projects", []):
            project = s.get(ProjectRow, p["id"])
            if project is None:
                project = ProjectRow(id=p["id"], name=p["name"], description=p.get("description", ""))
                s.add(project)
            else:
                project.name = p["name"]
                project.description = p.get("description", "")

            for t in p.get("tasks", []):
                task = s.get(TaskRow, t["id"])
                if task is None:
                    task = TaskRow(
                        id=t["id"],
                        project_id=p["id"],
                        title=t["title"],
                        status=t.get("status", "todo"),
                        assignee_id=t.get("assignee_id"),
                        due_date=t.get("due_date"),
                    )
                    s.add(task)
                else:
                    task.title = t["title"]
                    task.status = t.get("status", "todo")
                    task.assignee_id = t.get("assignee_id")
                    task.due_date = t.get("due_date")

            for m in p.get("milestones", []):
                milestone = s.get(MilestoneRow, m["id"])
                if milestone is None:
                    milestone = MilestoneRow(
                        id=m["id"], project_id=p["id"], name=m["name"], due_date=m.get("due_date")
                    )
                    s.add(milestone)
                else:
                    milestone.name = m["name"]
                    milestone.due_date = m.get("due_date")
        s.commit()
```

- [ ] **Step 5: Run to verify pass**

Run: `.venv/bin/python3 -m pytest tests/services/projects/test_seed.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add services/projects/seed.py fixtures/demo-seed/projects.json \
        tests/services/projects/test_seed.py
git commit -m "feat(projects): add seed loader and demo JSON fixture"
```

---

## Task 13: Projects service — Wire `--seed-from` into `main.py`

**Files:**
- Modify: `services/projects/main.py`

- [ ] **Step 1: Replace `services/projects/main.py` with the seed-aware version**

```python
from __future__ import annotations

import argparse
import os
import pathlib

import uvicorn

from services.projects.app import create_app
from services.projects.seed import load_seed

_DEFAULT_DB = pathlib.Path(os.getenv("PROJECTS_DB", "data/projects.db"))
_DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)

app = create_app(sqlite_path=_DEFAULT_DB)

# If PROJECTS_SEED is set (env var, used when loaded by uvicorn --reload) apply on import.
_SEED_FROM = os.getenv("PROJECTS_SEED")
if _SEED_FROM:
    load_seed(app.state.session_maker, _SEED_FROM)


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed-from", type=pathlib.Path, default=None)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    if args.seed_from:
        load_seed(app.state.session_maker, args.seed_from)

    uvicorn.run(app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    _main()
```

- [ ] **Step 2: Smoke test the service manually**

Run (in one terminal): `.venv/bin/python3 -m services.projects.main --seed-from fixtures/demo-seed/projects.json --port 8001`

In another terminal:
```bash
curl -s http://localhost:8001/ | head
curl -s http://localhost:8001/projects | head
curl -s http://localhost:8001/projects/proj_seed_alpha
```

Expected: each returns a valid envelope JSON containing the seed data. Stop uvicorn with Ctrl+C.

- [ ] **Step 3: Commit**

```bash
git add services/projects/main.py
git commit -m "feat(projects): wire --seed-from flag and env var to main entrypoint"
```

---

## Task 14: Root-level test configuration + full suite verification

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/conftest.py` (root fixtures + import hygiene)**

```python
from __future__ import annotations

import pathlib
import sys

# Ensure the repo root is on sys.path for the `services.*` and `agent_protocol.*` packages
_REPO = pathlib.Path(__file__).resolve().parent.parent
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
```

- [ ] **Step 2: Run the full suite**

Run: `.venv/bin/python3 -m pytest -v`
Expected: all green — 9 protocol tests + 2 db + 4 models + 1 capabilities + 4 projects_crud + 4 tasks + 4 constraint_errors + 1 seed = 29 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "chore(tests): add root conftest ensuring package imports resolve"
```

---

## Task 15: Documentation — test inventory, implementation plan & status

**Files:**
- Create: `docs/test_inventory.md`
- Create: `docs/implementation_plan.md`
- Create: `docs/implementation_status.md`

- [ ] **Step 1: Create `docs/test_inventory.md`**

```markdown
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
```

- [ ] **Step 2: Create `docs/implementation_plan.md`**

```markdown
# Implementation Plan

Phased delivery across four plans (see `docs/superpowers/plans/`).

1. **`2026-04-19-foundation-and-projects-service.md`** — Shared `agent_protocol/` library + Projects service on :8001. (This plan.)
2. **`2026-04-19-leaf-services.md`** — People (:8002) + Communications (:8003).
3. **`2026-04-19-orchestrator-service.md`** — Orchestrator service on :8000 (FastAPI + LangGraph + Azure OpenAI).
4. **`2026-04-19-client-agent-and-dashboard.md`** — Client Agent on :8080 + Next.js dashboard + demo wiring.

Each plan produces working, testable software on its own. Plans must be completed in order.
```

- [ ] **Step 3: Create `docs/implementation_status.md`**

```markdown
# Implementation Status

_Last updated: 2026-04-19_

## Plan 1 — Foundation & Projects Service

- [ ] Task 1: Bootstrap
- [ ] Task 2: `agent_protocol/envelope.py`
- [ ] Task 3: `agent_protocol/errors.py`
- [ ] Task 4: `agent_protocol/catalog.py`
- [ ] Task 5: `agent_protocol/field_docs.py`
- [ ] Task 6: Projects DB schema
- [ ] Task 7: Projects Pydantic models
- [ ] Task 8: Projects capabilities endpoint
- [ ] Task 9: Projects CRUD routes
- [ ] Task 10: Task routes
- [ ] Task 11: Constraint error tests
- [ ] Task 12: Seed loader + fixture
- [ ] Task 13: `--seed-from` in main
- [ ] Task 14: Root test configuration
- [ ] Task 15: Documentation

## Plan 2 — not started
## Plan 3 — not started
## Plan 4 — not started
```

- [ ] **Step 4: Commit**

```bash
git add docs/test_inventory.md docs/implementation_plan.md docs/implementation_status.md
git commit -m "docs: add test inventory, implementation plan and status docs"
```

---

## Definition of done for this plan

- All 15 tasks completed.
- `.venv/bin/python3 -m pytest -v` reports 29+ tests passing.
- `make run-projects` starts the Projects service on :8001 and `curl http://localhost:8001/` returns a valid capability catalog (verified manually).
- `curl http://localhost:8001/projects/proj_seed_alpha` returns the seeded project (after `--seed-from fixtures/demo-seed/projects.json`).
- `docs/test_inventory.md`, `docs/implementation_plan.md`, `docs/implementation_status.md` present and populated.
