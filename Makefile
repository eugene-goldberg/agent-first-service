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

.PHONY: run-orchestrator
run-orchestrator:
	. .venv/bin/activate && ORCHESTRATOR_REPLAY_DIR=fixtures/llm_recordings/landing_page python3 -m services.orchestrator.main

.PHONY: test-orchestrator
test-orchestrator:
	. .venv/bin/activate && pytest tests/services/orchestrator -v

.PHONY: run-all
run-all:
	@echo "Open four shells and run:"
	@echo "  make run-projects"
	@echo "  make run-people"
	@echo "  make run-communications"
	@echo "  make run-orchestrator"

.PHONY: test-all-services
test-all-services:
	. .venv/bin/activate && pytest tests/services -v

.PHONY: test-full
test-full:
	. .venv/bin/activate && pytest tests -v

.PHONY: run-client
run-client:
	. .venv/bin/activate && CLIENT_AGENT_REPLAY_DIR=fixtures/llm_recordings/client_landing_page python3 -m services.client_agent.main

.PHONY: run-dashboard
run-dashboard:
	cd dashboard && npm run dev

.PHONY: test-client-agent
test-client-agent:
	. .venv/bin/activate && pytest tests/services/client_agent -v

.PHONY: test-all-python
test-all-python:
	. .venv/bin/activate && pytest tests -v

.PHONY: run-demo
run-demo:
	@echo "Open six shells and run:"
	@echo "  1)  make run-projects"
	@echo "  2)  make run-people"
	@echo "  3)  make run-communications"
	@echo "  4)  make run-orchestrator"
	@echo "  5)  make run-client"
	@echo "  6)  make run-dashboard"
	@echo ""
	@echo "Then open http://127.0.0.1:3000 in a browser."

.PHONY: clean
clean:
	rm -rf $(VENV) .pytest_cache .ruff_cache data
