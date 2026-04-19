import json

from sqlalchemy import select

from services.people.db import Base, PersonRow, make_engine, make_sessionmaker


def test_create_person_row(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/people.db")
    Base.metadata.create_all(engine)
    SessionMaker = make_sessionmaker(engine)

    with SessionMaker() as session:
        session.add(
            PersonRow(
                id="person_alice",
                name="Alice Chen",
                role="senior engineer",
                skills_json=json.dumps(["python", "langgraph"]),
                available=True,
                current_load=2,
            )
        )
        session.commit()

    with SessionMaker() as session:
        row = session.execute(
            select(PersonRow).where(PersonRow.id == "person_alice")
        ).scalar_one()
        assert row.name == "Alice Chen"
        assert json.loads(row.skills_json) == ["python", "langgraph"]
        assert row.available is True
        assert row.current_load == 2
