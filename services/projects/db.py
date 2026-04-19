from __future__ import annotations

import pathlib

from sqlalchemy import String, ForeignKey, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.orm import sessionmaker


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = "projects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False, default="")

    tasks: Mapped[list["TaskRow"]] = relationship(back_populates="project")
    milestones: Mapped[list["MilestoneRow"]] = relationship(back_populates="project")


class TaskRow(Base):
    __tablename__ = "tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="todo", nullable=False)
    assignee_id: Mapped[str | None] = mapped_column(String, nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped[ProjectRow] = relationship(back_populates="tasks")


class MilestoneRow(Base):
    __tablename__ = "milestones"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(String, nullable=False)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)

    project: Mapped[ProjectRow] = relationship(back_populates="milestones")


def make_engine(sqlite_path: pathlib.Path | str) -> Engine:
    url = f"sqlite:///{sqlite_path}"
    return create_engine(url, echo=False, future=True)


def make_sessionmaker(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, expire_on_commit=False)
