from datetime import datetime

from sqlalchemy import Date, DateTime, Enum, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.config import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    owner_id: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(
        Enum("high", "medium", "low"), default="medium"
    )
    status: Mapped[str] = mapped_column(
        Enum("todo", "in_progress", "done"), default="todo"
    )
    due_date: Mapped[datetime | None] = mapped_column(Date)
    tag: Mapped[str | None] = mapped_column(String(50))
    task_type: Mapped[str] = mapped_column(
        Enum("short_term", "long_term", "daily"), default="short_term"
    )
    deadline_precision: Mapped[str | None] = mapped_column(
        Enum("day", "month", "year"), nullable=True
    )
    timer_preset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timer_total_seconds: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    wikilinks: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    domain: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_pinned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class RawSource(Base):
    __tablename__ = "raw_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(Enum("pending", "ingested"), default="pending")
    ingested_to_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
