from sqlalchemy import select

from services.orchestrator.db import Base, JobRow, TraceEventRow, make_engine, make_sessionmaker
from services.orchestrator.state import OrchestrationState, TraceEvent


def test_orchestration_state_defaults():
    state = OrchestrationState(
        job_id="job_1",
        brief="Build a landing page.",
        transcript=[],
        trace=[],
        completed=False,
    )
    assert state.job_id == "job_1"
    assert state.completed is False
    assert state.trace == []


def test_trace_event_has_required_fields():
    ev = TraceEvent(
        job_id="job_1",
        kind="action",
        summary="GET /people?skill=design",
        detail={"method": "GET", "url": "http://127.0.0.1:8002/people?skill=design"},
    )
    assert ev.kind == "action"
    assert ev.summary.startswith("GET")


def test_job_and_trace_row_persistence(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/orchestrator.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    with SessionMaker() as session:
        session.add(JobRow(id="job_1", brief="Hello", status="running"))
        session.add(TraceEventRow(
            id="ev_1", job_id="job_1", kind="thought",
            summary="thinking...", detail_json="{}",
        ))
        session.commit()

    with SessionMaker() as session:
        job = session.execute(select(JobRow)).scalar_one()
        assert job.status == "running"
        events = session.execute(select(TraceEventRow)).scalars().all()
        assert len(events) == 1
        assert events[0].kind == "thought"
