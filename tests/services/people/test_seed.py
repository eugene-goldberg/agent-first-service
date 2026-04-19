import json
from pathlib import Path

from services.people.db import Base, PersonRow, make_engine, make_sessionmaker
from services.people.seed import load_seed


def test_load_seed_creates_people(tmp_path):
    fixture = tmp_path / "people.json"
    fixture.write_text(json.dumps({
        "people": [
            {
                "id": "person_seed_alice",
                "name": "Alice Seed",
                "role": "senior engineer",
                "skills": ["python", "langgraph"],
                "available": True,
                "current_load": 0,
            },
            {
                "id": "person_seed_bob",
                "name": "Bob Seed",
                "role": "product manager",
                "skills": ["roadmaps"],
                "available": True,
                "current_load": 1,
            },
        ]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/people.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        rows = session.query(PersonRow).order_by(PersonRow.id).all()
        assert [r.id for r in rows] == ["person_seed_alice", "person_seed_bob"]
        assert rows[0].name == "Alice Seed"


def test_load_seed_is_idempotent(tmp_path):
    fixture = tmp_path / "people.json"
    fixture.write_text(json.dumps({
        "people": [{
            "id": "person_seed_alice", "name": "Alice", "role": "eng",
            "skills": ["python"], "available": True, "current_load": 0,
        }]
    }))

    engine = make_engine(f"sqlite:///{tmp_path}/people.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    load_seed(SessionMaker, str(fixture))
    load_seed(SessionMaker, str(fixture))

    with SessionMaker() as session:
        assert session.query(PersonRow).count() == 1
