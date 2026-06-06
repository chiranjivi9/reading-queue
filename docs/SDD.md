# Software Design Document — Reading Queue

## 1. Architecture Overview

```
React app (Vite dev server :5173 / built files in prod)
       │  HTTP (REST JSON)
       ▼
FastAPI app (main.py :8000)
  ├── Routes         → validate input, return responses
  ├── BackgroundTask → process_article() pipeline
  ├── database.py    → async SQLAlchemy session
  ├── models.py      → ORM table definitions
  └── services/
        ├── extractor.py   → Trafilatura
        └── summariser.py  → Anthropic Claude API
```

**Local dev flow:**
- React dev server runs on :5173, proxies `/api/*` requests to FastAPI on :8000
- FastAPI has CORS enabled for localhost:5173
- Two terminals: one for `uvicorn`, one for `npm run dev`

**Production flow:**
- React is built to `frontend/dist/`
- Caddy serves `frontend/dist/` as static files
- Caddy proxies `/api/*` to FastAPI container on :8000

**Key design decisions:**
- Everything async on the backend — FastAPI, SQLAlchemy, and the Anthropic client all use `async/await`
- Services are plain async functions, not classes — keeps them simple and testable
- Background tasks run inside the FastAPI process (no separate worker/queue needed at this scale)
- SQLite for local dev; DATABASE_URL env var allows swapping to Postgres without code changes
- React + Vite chosen for frontend: component model, React Router for detail pages
- Prompt caching: article text sent with `cache_control: ephemeral` so follow-up chat questions reuse the cached context at ~10% cost

---

## 2. Database Design

### Table: `articles`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | Primary key, auto-increment |
| `url` | TEXT | Unique constraint |
| `title` | TEXT | Extracted from article |
| `summary` | TEXT | 2–3 sentence summary from Claude |
| `score` | INTEGER | 1–10 relevance score |
| `score_reason` | TEXT | One sentence explaining the score |
| `full_text` | TEXT | Raw extracted article content |
| `status` | TEXT | Enum: `pending` / `processing` / `ready` / `failed` |
| `created_at` | DATETIME | UTC, set on insert |
| `week_number` | INTEGER | ISO week number (for weekly grouping) |

### Table: `digests`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | Primary key, auto-increment |
| `week_number` | INTEGER | ISO week number |
| `content` | TEXT | Markdown-formatted digest |
| `created_at` | DATETIME | UTC, set on insert |

---

## 3. API Design

### POST /articles
Add a new article URL.

**Request body:**
```json
{ "url": "https://example.com/article" }
```

**Response (201 or 200 if duplicate):**
```json
{ "id": 1, "url": "https://...", "status": "pending" }
```

**Errors:**
- `422` — invalid URL format

---

### GET /articles
List all articles for the current ISO week.

**Response:**
```json
[
  {
    "id": 1,
    "url": "https://...",
    "title": "Article title",
    "summary": "2-3 sentence summary...",
    "score": 9,
    "score_reason": "Directly covers LLM fine-tuning techniques.",
    "status": "ready",
    "created_at": "2025-06-04T10:00:00"
  }
]
```

Ordered by `score DESC` (nulls last).

---

### GET /articles/{id}
Get a single article including `full_text`.

**Errors:**
- `404` — article not found

---

### DELETE /articles/{id}
Hard delete an article.

**Response:** `204 No Content`

**Errors:**
- `404` — article not found

---

### POST /articles/{id}/chat
Chat with an article using Claude.

**Request body:**
```json
{
  "messages": [
    { "role": "user", "content": "What is the main argument?" },
    { "role": "assistant", "content": "The article argues..." },
    { "role": "user", "content": "Can you give an example?" }
  ]
}
```

**Response:**
```json
{ "reply": "Sure, one example given is..." }
```

**Errors:**
- `404` — article not found
- `400` — article not yet processed (status ≠ ready)

**Model:** `claude-sonnet-4-6`

**How caching works:** The article's `full_text` is placed in the system prompt with `cache_control: ephemeral`. Each request in the same session reuses the cached system prompt — only the new user message is billed at full price.

---

### GET /digest/current
Get this week's digest.

**Response:**
```json
{ "id": 1, "week_number": 23, "content": "# Week 23 Digest\n...", "created_at": "..." }
```
or `null` if no digest generated yet.

---

## 4. Component Design

### `models.py`
Defines SQLAlchemy ORM models (`Article`, `Digest`). Maps Python classes to database tables. Uses `DeclarativeBase` from SQLAlchemy 2.0.

### `database.py`
- Creates the async SQLAlchemy engine from `DATABASE_URL`
- Provides `get_db()` — an async generator used as a FastAPI dependency to inject a database session into route handlers
- `init_db()` — creates all tables on startup

### `services/extractor.py`

```
extract_article(url: str) -> dict
  └── trafilatura.fetch_url(url)       # download page
  └── trafilatura.extract(downloaded)  # extract clean text
  └── return { "title": ..., "text": ... }
  └── raises ExtractorError if failed
```

Timeout: 10 seconds.

### `services/summariser.py`

```
summarise(title: str, text: str) -> dict
  └── build two content blocks:
        block 1 — article title + first ~4000 chars of text (cache_control: ephemeral)
        block 2 — static scoring instruction (not cached)
  └── call anthropic client (claude-sonnet-4-20250514)
  └── parse JSON from response (strip markdown fences if present)
  └── return { "summary": ..., "score": ..., "score_reason": ... }
```

Prompt caching: the article content block is marked `cache_control: {type: "ephemeral"}`. If the same article is summarised more than once (e.g. retry after failure), the cached text is reused at ~10% input token cost.

### `main.py`

Route handlers (thin — delegate to services):
```
POST /articles
  └── validate URL
  └── check duplicate → return existing if found
  └── insert article (status=pending)
  └── add background task: process_article(id)
  └── return { id, url, status }

process_article(id)
  └── status → "processing"
  └── extractor.extract_article(url)
  └── summariser.summarise(title, text)
  └── update article fields + status → "ready"
  └── on exception → status → "failed", log error
```

APScheduler: Friday 6pm cron job — logs "digest would run here" (stub).

### `frontend/` — React + Vite + React Router

**Routing:**
- `/` — home (article list + add form)
- `/articles/:id` — article detail page (summary + chat)

**Shared utilities:**
- `utils.js` — `getDomain(url)` and `scoreBadgeClass(score)` used by both `ArticleCard` and `ArticleDetailPage`

**Components:**
- `main.jsx` — entry point, wraps app in `<BrowserRouter>`
- `App.jsx` — defines routes, home page state (articles, digest, toast), polling
- `AddArticle.jsx` — URL input + submit button, calls POST /articles
- `ArticleCard.jsx` — displays one article (title, domain, score badge, status pill, delete); clicking the card navigates to the detail page
- `DigestView.jsx` — displays current week's digest if available
- `pages/ArticleDetailPage.jsx` — fetches GET /articles/{id}, shows full summary, hosts chat interface; sends POST /articles/{id}/chat with full conversation history on each message

**Data flow:**
- `App.jsx` fetches GET /articles on load and every 5 seconds
- On submit, `AddArticle` calls POST /articles; `App` adds an optimistic "Processing" card immediately
- Score badge colour: green (≥8), amber (5–7), grey (≤4)
- Chat history is kept in local component state — each POST /chat sends the full `messages` array so Claude has full context

**Vite proxy (dev only):**
```js
// vite.config.js — /articles covers /articles/{id}/chat automatically
server: {
  proxy: {
    '/articles': 'http://localhost:8000',
    '/digest': 'http://localhost:8000',
  }
}
```

---

## 5. Background Task Flow

```
POST /articles received
        │
        ▼
Insert article (status = "pending")
        │
        ▼
Return { id, url, status } to client   ← client is not blocked
        │
        ▼ (async, in background)
update status → "processing"
        │
        ▼
extractor.extract_article(url)
        │
   ┌────┴────┐
  OK       FAIL
   │          └─ status → "failed", log
   ▼
summariser.summarise(title, text)
   │
   ├────┐
  OK  FAIL
   │     └─ status → "failed", log
   ▼
update article: title, summary, score,
                score_reason, full_text,
                status → "ready"
```

---

## 6. Security (planned)

### Rate limiting — Step 9

Library: [`slowapi`](https://github.com/laurentS/slowapi) (FastAPI-compatible wrapper around `limits`).

```
pip install slowapi
```

Implementation sketch (`main.py`):
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/articles")
@limiter.limit("20/hour")
async def create_article(request: Request, ...):
    ...

@app.post("/articles/{article_id}/chat")
@limiter.limit("30/hour")
async def chat_with_article(request: Request, ...):
    ...
```

Limits are per IP address, stored in memory (resets on restart). Can be upgraded to Redis for persistence across restarts.

---

### Authentication — Step 10

**Option A: Caddy HTTP Basic Auth** (requires Docker/Caddy from Step 8)

Add to `Caddyfile`:
```
queue.yourdomain.com {
    basic_auth {
        # generate hash with: caddy hash-password
        username $2a$14$...hashed_password...
    }
    reverse_proxy app:8000
}
```

Zero backend code changes. The browser will show a native login prompt.

**Option B: FastAPI API key** (works standalone, no Docker required)

Add to `.env`:
```
SECRET_KEY=some-long-random-string
```

Add to `main.py`:
```python
from fastapi.security.api_key import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_key(key: str = Depends(api_key_header)):
    if key != os.getenv("SECRET_KEY"):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# Apply to sensitive routes:
@app.post("/articles", dependencies=[Depends(verify_key)])
@app.delete("/articles/{article_id}", dependencies=[Depends(verify_key)])
@app.post("/articles/{article_id}/chat", dependencies=[Depends(verify_key)])
```

Frontend sends the header on every mutating request:
```js
headers: { 'X-API-Key': import.meta.env.VITE_API_KEY }
```

Add `VITE_API_KEY` to `frontend/.env.local` (gitignored by `*.local`).

---

## 7. Deployment

### Local dev
```bash
uvicorn main:app --reload
```

### Docker
- `Dockerfile`: Python 3.12 slim, install deps, run uvicorn on port 8000
- `docker-compose.yml`: single `app` service, SQLite db file mounted as volume
- `Caddyfile`: reverse proxy `queue.yourdomain.com` → `app:8000`
