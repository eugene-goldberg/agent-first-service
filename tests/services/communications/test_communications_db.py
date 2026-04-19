from datetime import datetime, timezone

from sqlalchemy import select

from services.communications.db import (
    Base,
    MessageRow,
    make_engine,
    make_sessionmaker,
)


def test_create_message_row(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/communications.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    with SessionMaker() as session:
        session.add(
            MessageRow(
                id="msg_001",
                recipient_id="person_alice",
                project_id="proj_alpha",
                subject="Assignment",
                body="You've been assigned to milestone #2.",
                sent_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
                status="sent",
            )
        )
        session.commit()

    with SessionMaker() as session:
        row = session.execute(select(MessageRow).where(MessageRow.id == "msg_001")).scalar_one()
        assert row.recipient_id == "person_alice"
        assert row.project_id == "proj_alpha"
        assert row.status == "sent"
