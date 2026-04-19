from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class Base(DeclarativeBase):
    pass


class MessageRow(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    subject: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued")


def make_engine(url: str):
    return create_engine(url, future=True)


def make_sessionmaker(engine):
    return sessionmaker(bind=engine, expire_on_commit=False, future=True)
