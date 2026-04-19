from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class PersonRow(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    skills_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


def make_engine(url: str):
    return create_engine(url, future=True)


def make_sessionmaker(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
