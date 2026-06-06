"""
models.py — SQLAlchemy ORM table definitions.

Each class maps to one database table. SQLAlchemy reads these definitions
and creates the actual SQL tables via init_db() in database.py.

ORM (Object Relational Mapper) means we define tables as Python classes
instead of writing raw SQL — SQLAlchemy handles the translation.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """
    Base class that every ORM model must inherit from.

    SQLAlchemy uses this to keep track of all table definitions in one place.
    When init_db() runs, it asks Base to create every table it knows about.
    You never instantiate Base directly — it's just a shared parent.
    """
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ArticleStatus(str, Enum):
    """
    The allowed lifecycle states for an article.

    Inheriting from both `str` and `Enum` means each value IS a plain string,
    so it serialises cleanly to JSON and stores as plain text in SQLite/Postgres.
    Defining these here prevents status typos scattered across the codebase —
    use ArticleStatus.PENDING instead of the raw string "pending" everywhere.

    Lifecycle:
        pending → processing → ready
                             → failed
    """
    PENDING    = "pending"     # just inserted, not yet processed
    PROCESSING = "processing"  # background task is actively running
    READY      = "ready"       # extraction + summarisation complete
    FAILED     = "failed"      # something went wrong; error was logged


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Article(Base):
    """
    Represents a single article added to the reading queue.

    Columns that are Optional[...] are NULL in the database until the
    background processing task completes successfully. This allows us to
    return the article immediately after a POST request (status=pending)
    without blocking the client while extraction runs.
    """

    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    url: Mapped[str] = mapped_column(
        String(2048),  # capped length so this column can be indexed
        unique=True,   # database-level duplicate prevention
        nullable=False,
        index=True,    # fast lookup when checking for existing URLs on POST
    )

    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=ArticleStatus.PENDING.value,
        index=True,  # GET /articles filters by week_number and orders by score;
                     # indexing status helps when filtering for "ready" articles
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        # server_default lets the database set this timestamp, not Python.
        # This is safer: the DB clock is always consistent, Python's datetime
        # can drift depending on where the code runs (local vs container).
        server_default=func.now(),
    )

    week_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,  # GET /articles filters by current week — must be fast
    )


class Digest(Base):
    """
    Stores the auto-generated weekly digest for each ISO week.

    One row per week. Generated every Friday at 6pm by the APScheduler job.
    The content field holds a markdown-formatted ranking of that week's articles.
    """

    __tablename__ = "digests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    week_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,  # one digest per week, enforced at the database level
        index=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )
