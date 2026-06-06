# Software Design Document — Reading Queue

## 1. Architecture Overview

```
React app (Vite dev server :5173 / built files in prod)
       │  HTTP (REST JSON)
       ▼
FastAPI app (main.py :8000)
  ├── Routes         → validate input, return responses
  ├── BackgroundTask → process_article() pipeline
  ├── APScheduler    → Friday 6pm: run_digest_agent()
  ├── database.py    → async SQLAlchemy session
  ├── models.py      → ORM table definitions
  └── services/
        ├── extractor.py     → Trafilatura article extraction
        ├── summariser.py    → Claude API: summarise + score
        └── digest_agent.py  → Agentic digest: tool loop + Tavily
```

**Local dev flow:**
- React dev server on :5173, proxies `/articles` and `/digest` to FastAPI on :8000
- FastAPI has CORS enabled for localhost:5173
- `./start.sh` starts both servers with one command

**Production flow:**
- React is built to `frontend/dist/` at Docker build time
- FastAPI serves `frontend/dist/` as static files (catch-all route after all API routes)
- Caddy (optional) terminates TLS and proxies to the container on :8000

**Key design decisions:**
- Everything async on the backend — FastAPI, SQLAlchemy, and the Anthropic client all use `async/await`
- Services are plain async functions, not classes — keeps them simple and testable
- Background tasks run inside the FastAPI process (no separate worker/queue needed at this scale)
- SQLite for local dev; DATABASE_URL env var allows swapping to Postgres without code changes
- React + Vite chosen for frontend: component model, React Router for detail pages
- Prompt caching: article text sent with `cache_control: ephemeral` so follow-up chat questions reuse the cached context at ~10% cost
- Agent decision log stored as JSON in the `digests.trace` column — makes the agent loop observable without a separate tracing system

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
| `trace` | TEXT | JSON array of agent steps (see §8) |
| `created_at` | DATETIME | UTC, set on insert |

---

## 3. API Design

### POST /articles
Add a new article URL.

**Auth:** `X-API-Key` header required (skipped in dev when `SECRET_KEY` not set)
**Rate limit:** 20/hour per IP

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
- `401` — missing or invalid API key
- `429` — rate limit exceeded

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

**Auth:** `X-API-Key` header required

**Response:** `204 No Content`

**Errors:**
- `404` — article not found

---

### POST /articles/{id}/chat
Chat with an article using Claude.

**Auth:** `X-API-Key` header required
**Rate limit:** 30/hour per IP

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
Get this week's digest including the agent trace.

**Response:**
```json
{
  "id": 1,
  "week_number": 23,
  "content": "# Week 23 Digest\n...",
  "trace": [
    { "type": "reasoning", "content": "Let me look at this week's articles first." },
    { "type": "tool_call", "tool": "list_articles", "input": {}, "summary": "Found 5 articles" },
    { "type": "reasoning", "content": "I see a theme around agentic systems. I'll search for more context." },
    { "type": "tool_call", "tool": "web_search", "input": { "query": "agentic AI 2025" }, "summary": "3 results found" },
    { "type": "tool_call", "tool": "save_digest", "input": { "content": "..." }, "summary": "Digest saved" }
  ],
  "created_at": "..."
}
```
or `null` if no digest generated yet this week.

---

## 4. Component Design

### `models.py`
Defines SQLAlchemy ORM models (`Article`, `Digest`). `Digest` includes a `trace` TEXT column storing JSON.

### `database.py`
- Creates the async SQLAlchemy engine from `DATABASE_URL`
- Provides `get_db()` — async generator injecting a session into route handlers
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
  └── call anthropic client (claude-sonnet-4-6)
  └── parse JSON from response (strip markdown fences if present)
  └── return { "summary": ..., "score": ..., "score_reason": ... }
```

### `services/digest_agent.py` ← new

See §8 for full design. Public interface:

```
run_digest_agent(db: AsyncSession) -> None
  └── fetch this week's articles from DB
  └── run agentic loop (Claude + tools)
  └── save digest + trace to digests table
```

### `main.py`

Route handlers (thin — delegate to services).

APScheduler: Friday 6pm cron job calls `run_digest_agent`.

Rate limiting: `slowapi`, per IP, in-memory store.

Auth: `verify_api_key` FastAPI dependency on mutating routes.

Static files: `frontend/dist/` served by FastAPI in production. Catch-all `/{full_path:path}` route returns `index.html` for React Router paths. Paths are resolved and checked against dist root before serving (path traversal safe).

### `frontend/` — React + Vite + React Router

**Routing:**
- `/` — home (article list + add form + digest)
- `/articles/:id` — article detail page (summary + chat)

**Shared utilities:**
- `utils.js` — `getDomain(url)` and `scoreBadgeClass(score)`

**Components:**
- `main.jsx` — entry point, wraps app in `<BrowserRouter>`
- `App.jsx` — defines routes, home page state (articles, digest, toast), polling every 5s
- `AddArticle.jsx` — URL input + submit, sends `X-API-Key` header
- `ArticleCard.jsx` — title, domain, score badge, status pill, delete; clicking navigates to detail
- `DigestView.jsx` — renders this week's digest markdown; below digest, renders `<AgentTrace>`
- `AgentTrace.jsx` — expandable panel showing each agent step as a timeline ← new
- `pages/ArticleDetailPage.jsx` — full summary, score reason, chat interface

**Data flow:**
- `App.jsx` fetches `GET /articles` on load and every 5 seconds
- `App.jsx` fetches `GET /digest/current` and passes both `content` and `trace` to `DigestView`
- Chat history kept in local state — each POST /chat sends the full `messages` array

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

## 6. Security

### Authentication
`APIKeyHeader` FastAPI dependency checks `X-API-Key` against `SECRET_KEY` env var.
Skipped entirely when `SECRET_KEY` is not set — no friction in local dev.
Applied to: `POST /articles`, `DELETE /articles/{id}`, `POST /articles/{id}/chat`.
GET routes are open (read-only, no AI cost).

### Rate limiting
`slowapi` — per IP, in-memory. `POST /articles`: 20/hour. `POST /articles/{id}/chat`: 30/hour.

### Path traversal
`serve_spa` resolves `(dist_root / full_path).resolve()` and checks `is_relative_to(dist_root)` before serving. Falls back to `index.html` if the resolved path escapes the dist directory.

### CORS
Controlled by `CORS_ORIGINS` env var. Defaults to localhost origins in dev; set to production domain before deploying.

---

## 7. Deployment

### Local dev
```bash
./start.sh   # starts backend (:8000) + frontend (:5173) with one command
```

### Docker
- Multi-stage Dockerfile: Node 20 Alpine builds React → Python 3.11 slim runs everything
- `VITE_API_KEY` passed as build arg so Vite embeds it in the JS bundle
- `docker-compose.yml`: single `app` service, SQLite persisted at `/app/data/articles.db` on a named volume
- `Caddyfile`: optional TLS reverse proxy — uncomment Caddy service in compose when deploying with a real domain

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `TAVILY_API_KEY` | Yes (for digest) | — | Tavily search API key |
| `SECRET_KEY` | Prod only | — | API key for mutating endpoints |
| `DATABASE_URL` | No | SQLite local file | SQLAlchemy connection string |
| `CORS_ORIGINS` | No | localhost origins | Comma-separated allowed origins |
| `INTERESTS` | No | `agentic systems, AI/ML, LLM engineering, software architecture` | User interests — biases scoring and digest framing |

---

## 8. Agentic Digest — Design

### Overview

The digest is generated by an agent loop: Claude is given tools and decides what to call, in what order, until it is ready to write the final digest.

```
System prompt: user interests + instructions
      │
      ▼
Claude reasons → calls list_articles
      │
      ▼
Claude reads articles, spots themes
      │
      ├── (optional) calls web_search one or more times
      │
      ▼
Claude calls save_digest → loop ends
```

This is a "tool-use agentic loop" — the fundamental agent pattern. Claude drives the sequence; our code executes whatever tool it asks for.

### Tools

**`list_articles`**
- No input
- Returns: array of `{ title, url, summary, score, score_reason }` for all ready articles this week
- The agent always calls this first

**`web_search`**
- Input: `{ "query": string }`
- Calls Tavily API, returns top 3 results as `{ title, url, snippet }`
- Agent decides if and when to call it, and what to search for
- Typically called 0–3 times per digest

**`save_digest`**
- Input: `{ "content": string }` — markdown-formatted digest
- Saves to `digests` table and signals end of loop (no further tool calls after this)

### Decision log (trace)

Every step of the agent loop is recorded as a list of trace entries:

```json
[
  { "type": "reasoning", "content": "Let me look at this week's articles." },
  { "type": "tool_call", "tool": "list_articles", "input": {}, "summary": "5 articles found" },
  { "type": "reasoning", "content": "Themes: AI agents, Python tooling. I'll search for agent context." },
  { "type": "tool_call", "tool": "web_search", "input": { "query": "..." }, "summary": "3 results" },
  { "type": "tool_call", "tool": "save_digest", "input": { "content": "..." }, "summary": "Digest saved" }
]
```

Reasoning entries come from Claude's text blocks returned before tool calls. Tool call entries are built from the `tool_use` content blocks. The trace is serialised to JSON and stored in `digests.trace`.

### Agent loop implementation sketch

```python
# services/digest_agent.py

tools = [list_articles_tool, web_search_tool, save_digest_tool]
messages = []
trace = []

while True:
    response = await client.messages.create(
        model="claude-opus-4-7",
        system=build_system_prompt(),   # includes INTERESTS
        tools=tools,
        messages=messages,
    )

    # Capture reasoning text the model emitted before tool calls
    for block in response.content:
        if block.type == "text" and block.text.strip():
            trace.append({"type": "reasoning", "content": block.text})

    if response.stop_reason == "end_turn":
        break   # model finished without calling a tool — shouldn't happen but safe

    # Execute each tool the model requested
    tool_results = []
    for block in response.content:
        if block.type == "tool_use":
            result, trace_entry = await execute_tool(block.name, block.input)
            trace.append(trace_entry)
            tool_results.append(build_tool_result(block.id, result))
            if block.name == "save_digest":
                return  # digest saved, done

    # Append assistant turn + tool results and loop
    messages.append({"role": "assistant", "content": response.content})
    messages.append({"role": "user", "content": tool_results})
```

### Frontend: AgentTrace component

Displayed below the digest content in `DigestView.jsx`.

```
┌─ How the agent thought ─────────────────────── [expand ▼] ┐
│                                                             │
│  💭 "Let me look at this week's articles first."           │
│  🔧 list_articles → Found 5 articles                       │
│  💭 "Strong theme around agentic systems. I'll search..."  │
│  🔧 web_search("agentic AI 2025") → 3 results              │
│  💭 "I have enough context. Writing digest now."           │
│  ✅ save_digest → Done                                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Collapsed by default. Each step shows icon, action, and brief summary.
