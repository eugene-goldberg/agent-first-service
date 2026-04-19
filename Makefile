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

.PHONY: run-people
run-people:
	. .venv/bin/activate && PEOPLE_SEED=fixtures/demo-seed/people.json python3 -m services.people.main

.PHONY: run-communications
run-communications:
	. .venv/bin/activate && COMMUNICATIONS_SEED=fixtures/demo-seed/communications.json python3 -m services.communications.main

.PHONY: test-people
test-people:
	. .venv/bin/activate && pytest tests/services/people -v

.PHONY: test-communications
test-communications:
	. .venv/bin/activate && pytest tests/services/communications -v

.PHONY: test-leaf-services
test-leaf-services:
	. .venv/bin/activate && pytest tests/services -v

.PHONY: clean
clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache data
