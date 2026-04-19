import pytest

from services.communications.app import create_app
from services.communications.db import Base, make_engine, make_sessionmaker


@pytest.fixture
def communications_app(tmp_path):
    db_path = tmp_path / "communications.db"
    engine = make_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_maker = make_sessionmaker(engine)
    return create_app(session_maker=session_maker)


@pytest.fixture
def communications_client(communications_app):
    from fastapi.testclient import TestClient

    return TestClient(communications_app)
