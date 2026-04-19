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
