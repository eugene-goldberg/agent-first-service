import pytest
from pydantic import ValidationError

from services.communications.models import CreateMessage, MessageOut


def test_create_message_requires_recipient_subject_and_body():
    msg = CreateMessage(
        recipient_id="person_alice",
        subject="Assignment",
        body="You've been assigned to milestone #2.",
    )
    assert msg.recipient_id == "person_alice"
    assert msg.project_id is None


def test_create_message_rejects_blank_subject():
    with pytest.raises(ValidationError):
        CreateMessage(recipient_id="person_alice", subject="", body="hello")


def test_message_out_serializes_datetime_iso():
    from datetime import datetime, timezone

    out = MessageOut(
        id="msg_001",
        recipient_id="person_alice",
        project_id=None,
        subject="Hi",
        body="Hello.",
        sent_at=datetime(2026, 4, 19, 10, 0, tzinfo=timezone.utc),
        status="sent",
    )
    dumped = out.model_dump(mode="json")
    assert dumped["sent_at"].startswith("2026-04-19T10:00:00")
