from __future__ import annotations

import json

from services.people.db import PersonRow


def load_seed(session_maker, fixture_path: str) -> None:
    with open(fixture_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    with session_maker() as session:
        for item in payload.get("people", []):
            existing = session.get(PersonRow, item["id"])
            if existing is None:
                session.add(
                    PersonRow(
                        id=item["id"],
                        name=item["name"],
                        role=item["role"],
                        skills_json=json.dumps(item.get("skills", [])),
                        available=bool(item.get("available", True)),
                        current_load=int(item.get("current_load", 0)),
                    )
                )
            else:
                existing.name = item["name"]
                existing.role = item["role"]
                existing.skills_json = json.dumps(item.get("skills", []))
                existing.available = bool(item.get("available", True))
                existing.current_load = int(item.get("current_load", 0))
        session.commit()
