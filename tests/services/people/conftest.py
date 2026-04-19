import pytest

from services.people.app import create_app
from services.people.db import Base, make_engine, make_sessionmaker


@pytest.fixture
def people_app(tmp_path):
    db_path = tmp_path / "people.db"
    engine = make_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)
    app = create_app(session_maker=session_maker)
    return app


@pytest.fixture
def people_client(people_app):
    from fastapi.testclient import TestClient

    return TestClient(people_app)
