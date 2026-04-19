from __future__ import annotations

import pathlib

import pytest
from sqlalchemy.orm import Session

from services.projects.db import Base, make_engine, make_sessionmaker


@pytest.fixture()
def sqlite_path(tmp_path: pathlib.Path) -> pathlib.Path:
    return tmp_path / "projects.db"


@pytest.fixture()
def session(sqlite_path: pathlib.Path) -> Session:
    engine = make_engine(sqlite_path)
    Base.metadata.create_all(engine)
    sm = make_sessionmaker(engine)
    with sm() as s:
        yield s
