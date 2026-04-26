import pytest
import httpx

from services.orchestrator.app import create_app as create_orch_app


@pytest.fixture
def orchestrator_app(tmp_path, monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_REPLAY_DIR", "fixtures/llm_recordings/landing_page")
    app = create_orch_app(sqlite_path=str(tmp_path / "o.db"))

    async def _ready_noop() -> None:
        return None

    app.state.runner.ensure_ready = _ready_noop
    return app


@pytest.fixture
async def orchestrator_transport(orchestrator_app):
    transport = httpx.ASGITransport(app=orchestrator_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        yield client
