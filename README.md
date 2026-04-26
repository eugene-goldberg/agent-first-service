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
- `make run-orchestrator` - run orchestrator on `:8000` in MCP mode with replay fixtures
- `make run-client` - run client agent on `:8080` with replay fixtures
- `make run-dashboard` - run Next.js dashboard on `:3000`

### Run MCP Service Commands

- `make run-mcp-projects` - run projects MCP SSE server on `:9001`
- `make run-mcp-people` - run people MCP SSE server on `:9002`
- `make run-mcp-communications` - run communications MCP SSE server on `:9003`

### Workflow Helper Commands

- `make run-all` - print shell instructions for MCP service + orchestrator startup
- `make run-demo` - print shell instructions for full demo startup (MCP + client + dashboard)

## Demo Startup (MCP Path)

In separate terminals:

```bash
make run-mcp-projects
make run-mcp-people
make run-mcp-communications
make run-orchestrator
make run-client
make run-dashboard
```

Then open [http://127.0.0.1:3000](http://127.0.0.1:3000).
