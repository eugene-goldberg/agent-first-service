# Agent First Service

Agent-first services demo with Projects, People, Communications, Orchestrator, Client Agent, and Dashboard components.

## Setup

```bash
make install
```

## Make Commands

### Environment and Cleanup

- `make install` - create `.venv`, upgrade pip, install package + dev dependencies
- `make clean` - remove virtualenv, caches, and local `data` artifacts

### Test Commands

- `make test` - run default pytest suite
- `make test-protocol` - run protocol tests
- `make test-projects` - run projects service tests
- `make test-people` - run people service tests
- `make test-communications` - run communications service tests
- `make test-orchestrator` - run orchestrator tests
- `make test-client-agent` - run client agent tests
- `make test-leaf-services` - run tests for service packages under `tests/services`
- `make test-all-services` - run all `tests/services` tests
- `make test-all-python` - run full python test suite (`tests`)
- `make test-full` - run full test suite with verbose output

### Run HTTP Service Commands

- `make run-projects` - run projects HTTP service on `:8001` (reload enabled)
- `make run-people` - run people HTTP service on `:8002` with demo seed
- `make run-communications` - run communications HTTP service on `:8003` with demo seed
- `make run-orchestrator` - run orchestrator on `:8000` in MCP mode using live Azure LLM (no fixtures)
- `make run-client` - run client agent on `:8080` using live Azure LLM (no fixtures)
- `make run-orchestrator-replay` - run orchestrator on `:8000` with replay fixtures (offline mode)
- `make run-client-replay` - run client agent on `:8080` with replay fixtures (offline mode)
- `make run-dashboard` - run stable production dashboard on `:3000` (build + start)
- `make run-dashboard-dev` - run Next.js dashboard dev server on `:3000` (for UI development)
- `make run-people-shared-db` - run People HTTP service on `:8002` against `data/people.db` (used by Projects assignment validation)

### Run MCP Service Commands

- `make run-mcp-projects` - run projects MCP SSE server on `:9001`
- `make run-mcp-people` - run people MCP SSE server on `:9002`
- `make run-mcp-communications` - run communications MCP SSE server on `:9003`

### Workflow Helper Commands

- `make run-all` - print shell instructions for MCP service + orchestrator startup
- `make run-demo` - print shell instructions for full demo startup (MCP + client + dashboard)
- `make check-live-stack` - verify all live endpoints/services are reachable before running a brief

## Demo Startup (MCP Path)

In separate terminals (live path):

```bash
make run-mcp-projects
make run-mcp-people
make run-mcp-communications
make run-people-shared-db
make run-orchestrator
make run-client
make run-dashboard
```

Create a local env file at project root (preferred, no terminal exports needed):

```bash
cat > .env.local <<'EOF'
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_OPENAI_API_VERSION=...
EOF
```

`run-orchestrator`, `run-client`, and `check-live-stack` auto-load `.env.local`
(or `.env`). If you need a custom path, set `AGENT_FIRST_ENV_FILE=/path/to/envfile`.

Then open [http://127.0.0.1:3000](http://127.0.0.1:3000).

Before submitting a brief, run:

```bash
make check-live-stack
```

This validates MCP SSE servers (`:9001/:9002/:9003`), People HTTP (`:8002`), orchestrator (`:8000`), client agent (`:8080`), dashboard (`:3000`), and required `AZURE_OPENAI_*` env vars.
