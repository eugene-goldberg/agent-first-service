import json
from pathlib import Path

from services.communications.db import Base, MessageRow, make_engine, make_sessionmaker
from services.communications.seed import load_seed


def test_load_seed_creates_messages(tmp_path):
    fixture = tmp_path / "communications.json"
    fixture.write_text(json.dumps({
        "messages": [
            {
                "id": "msg_seed_001",
                "recipient_id": "person_seed_alice",
                "project_id": "proj_seed_alpha",
                "subject": "Welcome",
                "body": "Welcome to the project.",
                "sent_at": "2026-04-19T10:00:00+00:00",
                "status": "sent",
            }
        ]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/communications.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        rows = session.query(MessageRow).all()
        assert len(rows) == 1
        assert rows[0].subject == "Welcome"


def test_load_seed_is_idempotent(tmp_path):
    fixture = tmp_path / "communications.json"
    fixture.write_text(json.dumps({
        "messages": [{
            "id": "msg_seed_001",
            "recipient_id": "p", "project_id": None, "subject": "s", "body": "b",
            "sent_at": "2026-04-19T10:00:00+00:00", "status": "sent",
        }]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/communications.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))
    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        assert session.query(MessageRow).count() == 1
