from __future__ import annotations

import json
from datetime import datetime

from services.communications.db import MessageRow


def load_seed(session_maker, fixture_path: str) -> None:
    with open(fixture_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    with session_maker() as session:
        for item in payload.get("messages", []):
            sent_at = datetime.fromisoformat(item["sent_at"])
            existing = session.get(MessageRow, item["id"])
            if existing is None:
                session.add(
                    MessageRow(
                        id=item["id"],
                        recipient_id=item["recipient_id"],
                        project_id=item.get("project_id"),
                        subject=item["subject"],
                        body=item["body"],
                        sent_at=sent_at,
                        status=item.get("status", "sent"),
                    )
                )
            else:
                existing.recipient_id = item["recipient_id"]
                existing.project_id = item.get("project_id")
                existing.subject = item["subject"]
                existing.body = item["body"]
                existing.sent_at = sent_at
                existing.status = item.get("status", "sent")
        session.commit()
