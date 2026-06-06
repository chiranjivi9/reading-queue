"""
main.py — FastAPI application entry point.

Defines all API routes and the background task pipeline.
Delegates all business logic to services/ to stay under 150 lines.

Security:
  - API key auth: mutating routes (POST, DELETE) require X-API-Key header.
    Set SECRET_KEY in .env. If SECRET_KEY is not set, auth is skipped
    (useful in local dev so you don't need the header for every curl command).
  - Rate limiting: AI-triggering endpoints are capped per IP to prevent
    unexpected cost spikes. Limit is kept in memory (resets on restart).
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import anthropic
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security.api_key import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import AsyncSessionLocal, get_db, init_db
from src.models import Article, ArticleStatus, Digest
from src.schemas import (
    ArticleBasicResponse,
    ArticleCreate,
    ArticleDetailResponse,
    ArticleResponse,
    ChatRequest,
    ChatResponse,
    DigestListItem,
    DigestResponse,
)
from src.services.digest_agent import run_digest_agent
from src.services.extractor import ExtractorError, extract_article
from src.services.summariser import SummariserError, summarise

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rate limiter  (in-memory, per IP)
# ---------------------------------------------------------------------------

limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# API key authentication
# ---------------------------------------------------------------------------

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(key: str = Security(_api_key_header)) -> None:
    """
    FastAPI dependency that enforces API key authentication.

    Reads SECRET_KEY from the environment. If SECRET_KEY is not set, auth
    is skipped entirely — handy in local dev where you don't want to set
    headers for every request. In production, always set SECRET_KEY.
    """
    secret = os.getenv("SECRET_KEY")
    if not secret:
        return  # dev mode — no key configured, allow all
    if key != secret:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

scheduler = AsyncIOScheduler()


async def _generate_digest_job():
    """Friday 6pm cron: run the agentic digest generator."""
    logger.info("Digest job triggered — starting agent.")
    async with AsyncSessionLocal() as db:
        await run_digest_agent(db)


# ---------------------------------------------------------------------------
# Lifespan  (startup + shutdown)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Code before `yield` runs on startup; code after runs on shutdown.
    This is FastAPI's recommended way to manage app-level resources.
    """
    await init_db()

    scheduler.add_job(_generate_digest_job, "cron", day_of_week="fri", hour=18)
    scheduler.start()
    logger.info("Scheduler started.")

    yield  # app runs here

    scheduler.shutdown()
    logger.info("Scheduler stopped.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Reading Queue", lifespan=lifespan)

# Attach limiter to app state and register the 429 handler.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS_ORIGINS is a comma-separated list of allowed frontend origins.
# Default covers localhost dev servers. In production set this env var
# to your actual domain: CORS_ORIGINS=https://queue.yourdomain.com
_cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

async def process_article(article_id: int) -> None:
    """
    Extract and summarise an article after it has been inserted.

    Retries extraction up to 3 times with exponential backoff before
    giving up and marking the article as failed.
    """
    MAX_ATTEMPTS = 3
    BACKOFF = [0, 5, 15]  # seconds to wait before each attempt

    async with AsyncSessionLocal() as db:
        article = await db.get(Article, article_id)
        if not article:
            return

        article.status = ArticleStatus.PROCESSING.value
        await db.commit()

        last_error = None
        for attempt in range(MAX_ATTEMPTS):
            if BACKOFF[attempt]:
                await asyncio.sleep(BACKOFF[attempt])
            try:
                extracted = await extract_article(str(article.url))
                summarised = await summarise(extracted["title"], extracted["text"])

                article.title = extracted["title"]
                article.full_text = extracted["text"]
                article.summary = summarised["summary"]
                article.score = summarised["score"]
                article.score_reason = summarised["score_reason"]
                article.status = ArticleStatus.READY.value
                await db.commit()
                return

            except (ExtractorError, SummariserError) as e:
                last_error = e
                logger.warning("Article %d attempt %d/%d failed: %s",
                               article_id, attempt + 1, MAX_ATTEMPTS, e)

        logger.error("Article %d permanently failed after %d attempts: %s",
                     article_id, MAX_ATTEMPTS, last_error)
        article.status = ArticleStatus.FAILED.value
        await db.commit()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/articles", response_model=ArticleBasicResponse, status_code=201,
          dependencies=[Depends(verify_api_key)])
@limiter.limit("20/hour")
async def create_article(
    request: Request,
    body: ArticleCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Add a new article URL to the reading queue."""
    url_str = str(body.url)

    existing = await db.scalar(select(Article).where(Article.url == url_str))
    if existing:
        return existing

    week_number = datetime.now(timezone.utc).isocalendar().week
    article = Article(url=url_str, week_number=week_number)
    db.add(article)
    await db.commit()
    await db.refresh(article)

    background_tasks.add_task(process_article, article.id)
    return article


@app.get("/articles", response_model=list[ArticleResponse])
async def list_articles(db: AsyncSession = Depends(get_db)):
    """Return all articles for the current ISO week, sorted by score descending."""
    week_number = datetime.now(timezone.utc).isocalendar().week
    result = await db.execute(
        select(Article)
        .where(Article.week_number == week_number)
        .order_by(Article.score.desc().nulls_last())
    )
    return result.scalars().all()


@app.get("/articles/favorites", response_model=list[ArticleResponse])
async def list_favorites(db: AsyncSession = Depends(get_db)):
    """Return all favorited articles across all weeks, sorted by score descending."""
    result = await db.execute(
        select(Article)
        .where(Article.is_favorite == True)  # noqa: E712
        .order_by(Article.score.desc().nulls_last())
    )
    return result.scalars().all()


@app.get("/articles/{article_id}", response_model=ArticleDetailResponse)
async def get_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Return a single article including its full extracted text."""
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article


@app.delete("/articles/{article_id}", status_code=204,
            dependencies=[Depends(verify_api_key)])
async def delete_article(article_id: int, db: AsyncSession = Depends(get_db)):
    """Hard delete an article."""
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    await db.delete(article)
    await db.commit()


@app.post("/articles/{article_id}/chat", response_model=ChatResponse,
          dependencies=[Depends(verify_api_key)])
@limiter.limit("30/hour")
async def chat_with_article(
    request: Request,
    article_id: int,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Answer a question about an article using Claude.

    The article's full_text is placed in the system prompt with
    cache_control: ephemeral so follow-up questions in the same session
    reuse the cached context at ~10% of normal input token cost.
    """
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    if article.status != ArticleStatus.READY.value or not article.full_text:
        raise HTTPException(status_code=400, detail="Article is not yet processed")

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": (
                        "You are a helpful reading assistant. Answer questions about "
                        "the following article concisely and accurately.\n\n"
                        f"Title: {article.title}\n\n"
                        f"Content:\n{article.full_text}"
                    ),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": m.role, "content": m.content} for m in body.messages],
        )
    except anthropic.APIError as e:
        raise HTTPException(status_code=502, detail=f"AI service error: {e}")

    return ChatResponse(reply=response.content[0].text)


@app.get("/digest/current", response_model=Optional[DigestResponse])
async def get_current_digest(db: AsyncSession = Depends(get_db)):
    """Return this week's digest, or null if it hasn't been generated yet."""
    week_number = datetime.now(timezone.utc).isocalendar().week
    digest = await db.scalar(select(Digest).where(Digest.week_number == week_number))
    return digest


@app.post("/digest/generate", status_code=202, dependencies=[Depends(verify_api_key)])
async def trigger_digest(background_tasks: BackgroundTasks):
    """
    Manually trigger the digest agent for the current week.

    Returns 202 immediately — the agent runs in the background.
    Poll GET /digest/current until it returns a result.
    Auth-protected so this can stay in production without risk.
    """
    async def _run():
        async with AsyncSessionLocal() as db:
            await run_digest_agent(db)

    background_tasks.add_task(_run)
    return {"status": "started", "message": "Digest agent running — poll GET /digest/current for the result."}


@app.get("/digest/all", response_model=list[DigestListItem])
async def list_digests(db: AsyncSession = Depends(get_db)):
    """Return all digests ordered by week descending."""
    result = await db.scalars(select(Digest).order_by(Digest.week_number.desc()))
    return result.all()


@app.get("/digest/{digest_id}", response_model=DigestResponse)
async def get_digest(digest_id: int, db: AsyncSession = Depends(get_db)):
    """Return a specific digest by id."""
    digest = await db.get(Digest, digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    return digest


@app.delete("/digest/{digest_id}", status_code=204, dependencies=[Depends(verify_api_key)])
async def delete_digest(digest_id: int, db: AsyncSession = Depends(get_db)):
    """Hard delete a digest by id."""
    digest = await db.get(Digest, digest_id)
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    await db.delete(digest)
    await db.commit()


@app.patch("/articles/{article_id}/favorite", response_model=ArticleResponse,
           dependencies=[Depends(verify_api_key)])
async def toggle_favorite(article_id: int, db: AsyncSession = Depends(get_db)):
    """Toggle is_favorite on an article."""
    article = await db.get(Article, article_id)
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.is_favorite = not article.is_favorite
    await db.commit()
    return article


# ---------------------------------------------------------------------------
# Frontend static file serving (production only)
#
# In development, Vite's dev server handles the frontend on port 5173.
# In Docker, the React app is built and placed at frontend/dist/ relative
# to the project root. FastAPI serves those files here so a single container
# handles both the API and the UI.
#
# The catch-all route MUST be defined after all API routes so it doesn't
# intercept API requests.
# ---------------------------------------------------------------------------

_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

if _FRONTEND_DIST.exists():
    # Serve compiled JS/CSS bundles
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="frontend-assets",
    )

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """
        Catch-all: serve specific static files from the dist root (favicon,
        icons, etc.) or fall back to index.html so React Router handles the path.

        Resolves and checks the path is still inside dist/ before serving,
        preventing path traversal attacks (e.g. GET /../../etc/passwd).
        """
        dist_root = _FRONTEND_DIST.resolve()
        file = (dist_root / full_path).resolve()
        if file.is_file() and file.is_relative_to(dist_root):
            return FileResponse(file)
        return FileResponse(dist_root / "index.html")
