"""
database.py — Async SQLAlchemy engine and session management.

Provides:
  - engine:     the single database connection for the whole app
  - get_db():   FastAPI dependency — yields one session per HTTP request
  - init_db():  creates all tables on app startup (called once in main.py)

Why async?
  A normal (synchronous) database call blocks the entire server while it
  waits for the DB to respond. With async, the server can handle other
  requests while waiting — important for an app that processes articles
  in the background while still serving the UI.
"""

import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.models import Base

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

load_dotenv()  # reads .env file and loads variables into os.environ

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./articles.db")
# The URL format tells SQLAlchemy two things:
#   - WHICH database to use  (sqlite / postgresql)
#   - WHICH async driver     (aiosqlite / asyncpg)
# Swapping to Postgres later only requires changing this env variable.


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

engine = create_async_engine(
    DATABASE_URL,
    # echo=True logs every SQL query to stdout — useful for debugging,
    # but too noisy for production. Controlled by an env variable later.
    echo=False,
)
# The engine is created once at module load time and shared across all
# requests. Creating a new engine per request would be expensive.


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # expire_on_commit=False means ORM objects remain usable after a
    # commit without issuing another SELECT. Avoids surprising lazy-load
    # errors in async code where implicit I/O is not allowed.
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db():
    """
    Yield an async database session for the duration of one HTTP request.

    Usage in a route handler:
        async def my_route(db: AsyncSession = Depends(get_db)):
            ...

    FastAPI calls this function before the route handler runs, injects the
    session, and then resumes here after the handler returns — executing the
    finally block to close the session cleanly whether or not an error occurred.

    This is a Python *generator* (note `yield` instead of `return`).
    The code before yield = setup. The code after yield (in finally) = teardown.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# ---------------------------------------------------------------------------
# Table creation
# ---------------------------------------------------------------------------

async def init_db():
    """
    Create all database tables defined in models.py.

    Called once on application startup (see lifespan in main.py).
    Safe to call on every startup — SQLAlchemy skips tables that already exist.
    """
    async with engine.begin() as conn:
        # run_sync is needed because create_all is a synchronous method.
        # engine.begin() gives us an async connection; run_sync bridges the gap.
        await conn.run_sync(Base.metadata.create_all)

        # One-time migration: add trace column to existing digests tables.
        # create_all skips tables that already exist, so we handle new columns here.
        # Silently ignored if the column is already present.
        try:
            await conn.execute(text("ALTER TABLE digests ADD COLUMN trace TEXT"))
        except Exception:
            pass
