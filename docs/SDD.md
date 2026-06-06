# Software Design Document — Reading Queue

## 1. Architecture Overview

```
React app (Vite dev server :5173 / built files in prod)
       │  HTTP (REST JSON)
       ▼
FastAPI app (main.py :8000)
  ├── Routes         → validate input, return responses
  ├── BackgroundTask → process_article() pipeline + digest generation
  ├── APScheduler    → Friday 6pm: run_digest_agent()
  ├── database.py    → async SQLAlchemy session
  ├── models.py      → ORM table definitions
  └── services/
        ├── extractor.py     → Trafilatura article extraction
        ├── summariser.py    → Claude API: summarise + score
        └── digest_agent.py  → Multi-agent digest: Discovery + Digest agents
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
- Multi-agent pattern: two specialised agents (Discovery + Digest) run sequentially, each with their own system prompt and tool set
- Token usage accumulated across all agent API calls and stored alongside the digest

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
| `is_favorite` | BOOLEAN | Default false — user-starred articles *(planned)* |
| `created_at` | DATETIME | UTC, set on insert |
| `week_number` | INTEGER | ISO week number (for weekly grouping) |

### Table: `digests`

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER | Primary key, auto-increment |
| `week_number` | INTEGER | ISO week number |
| `content` | TEXT | Markdown-formatted digest |
| `trace` | TEXT | JSON array of agent steps (see §8) |
| `themes` | TEXT | JSON array of 2–4 keyword themes extracted from digest |
| `suggested_articles` | TEXT | JSON array of `{ title, url, reason }` from Discovery Agent |
| `token_usage` | TEXT | JSON: `{ input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens }` |
| `created_at` | DATETIME | UTC, set on insert |

**Schema migrations:** New columns added via `ALTER TABLE ... ADD COLUMN` in `init_db()` (try/except loop) — SQLite-compatible, idempotent, runs on every startup.

---

## 3. API Design

### POST /articles
Add a new article URL.

**Auth:** `X-API-Key` header required  
**Rate limit:** 20/hour per IP

**Request body:**
```json
{ "url": "https://example.com/article" }
```

**Response (201 or 200 if duplicate):**
```json
{ "id": 1, "url": "https://...", "status": "pending" }
```

**Errors:** `422` invalid URL, `401` bad key, `429` rate limit

---

### GET /articles
List all articles for the current ISO week, ordered by score DESC.

---

### GET /articles/{id}
Get a single article including `full_text`.

**Errors:** `404` not found

---

### DELETE /articles/{id}
Hard delete an article.

**Auth:** `X-API-Key` required  
**Response:** `204 No Content`

---

### PATCH /articles/{id}/favorite *(planned)*
Toggle `is_favorite` on an article.

**Auth:** `X-API-Key` required  
**Response:** updated article object

---

### POST /articles/{id}/chat
Chat with an article using Claude.

**Auth:** `X-API-Key` required  
**Rate limit:** 30/hour per IP

**Request body:**
```json
{
  "messages": [
    { "role": "user", "content": "What is the main argument?" }
  ]
}
```

**Response:**
```json
{ "reply": "The article argues..." }
```

**Model:** `claude-sonnet-4-6` with prompt caching on article text.

---

### POST /digest/generate
Trigger the digest agent in the background immediately.

**Auth:** `X-API-Key` required  
**Response:** `202 Accepted`

The UI polls `GET /digest/current` every 3 seconds until a new digest appears. Timeout: 120 seconds.

---

### GET /digest/current
Get this week's digest including the full agent trace and token usage.

**Response:**
```json
{
  "id": 1,
  "week_number": 23,
  "content": "# Week 23 Digest\n...",
  "trace": [
    { "type": "agent_start", "agent": "discovery", "summary": "Discovery Agent starting" },
    { "type": "reasoning", "agent": "discovery", "content": "Let me search for related articles." },
    { "type": "tool_call", "agent": "discovery", "tool": "web_search", "input": { "query": "agentic AI 2025" }, "summary": "3 results found" },
    { "type": "tool_call", "agent": "discovery", "tool": "report_findings", "summary": "2 articles suggested" },
    { "type": "agent_start", "agent": "digest", "summary": "Digest Agent starting" },
    { "type": "tool_call", "agent": "digest", "tool": "save_digest", "summary": "Digest saved" }
  ],
  "suggested_articles": [
    { "title": "...", "url": "https://...", "reason": "Directly relevant to agentic systems theme" }
  ],
  "token_usage": {
    "input_tokens": 12400,
    "output_tokens": 1850,
    "cache_read_tokens": 4200,
    "cache_creation_tokens": 800
  },
  "created_at": "2025-06-06T18:00:00"
}
```

or `null` if no digest generated yet this week.

---

### GET /digest/all *(planned)*
List all digests, ordered by week DESC.

**Response:**
```json
[
  { "id": 3, "week_number": 23, "content": "# Week 23...", "created_at": "..." },
  { "id": 2, "week_number": 22, "content": "# Week 22...", "created_at": "..." }
]
```

---

## 4. Component Design

### `models.py`
Defines SQLAlchemy ORM models (`Article`, `Digest`). `Digest` has `trace`, `themes`, `suggested_articles`, and `token_usage` TEXT columns storing JSON.

### `database.py`
- Creates the async SQLAlchemy engine from `DATABASE_URL`
- Provides `get_db()` — async generator injecting a session into route handlers
- `init_db()` — creates all tables + runs idempotent `ALTER TABLE` migrations for new columns

### `services/extractor.py`
```
extract_article(url: str) -> dict
  └── _fetch_and_extract(url)          # Trafilatura (fast, local)
        └── if fails →
  └── _extract_via_jina(url)           # Jina Reader fallback (r.jina.ai)
        └── GET https://r.jina.ai/<url>
        └── validates response (length + error keywords)
        └── parses "Title: ..." from response header line
  └── raises ExtractorError if both fail

Retry logic (in process_article background task):
  attempt 1: immediate
  attempt 2: after 5s
  attempt 3: after 15s
  → marks article "failed" only after all 3 attempts exhausted
```

### `services/summariser.py`
```
summarise(title: str, text: str) -> dict
  └── article text block with cache_control: ephemeral
  └── call claude-sonnet-4-6
  └── parse JSON: { summary, score, score_reason }
```

### `services/digest_agent.py`

Public interface:
```
run_digest_agent(db: AsyncSession) -> None
  └── fetch this week's articles from DB
  └── fetch agent memory (past 4 weeks' themes)
  └── run Discovery Agent → list of suggested articles
  └── run Digest Agent   → final digest content
  └── extract themes from digest (single Claude call)
  └── save digest, trace, themes, suggested_articles, token_usage to DB
```

**`_TokenUsage` class** — accumulates input/output/cache tokens across every API call in both agents. Stored as JSON in `digests.token_usage`.

**Discovery Agent** (`run_discovery_agent`)
- Tools: `web_search`, `report_findings`
- System prompt includes user interests + past themes
- Returns list of `{ title, url, reason }` suggested articles

**Digest Agent** (`run_digest_agent_step`)
- Tools: `web_search`, `save_digest`
- System prompt includes user interests + past themes + Discovery findings
- Returns final digest markdown string

**Agent memory** (`_fetch_memory`)
- Loads last 4 weeks' themes from DB
- Formatted as bullet list in both agents' system prompts
- Prevents the digest from repeating the same angles week over week

**Theme extraction** (`_extract_and_save_themes`)
- Single Claude call after digest is written
- Extracts 2–4 keyword themes from the digest content
- Stored in `digests.themes` for future memory retrieval

### `main.py`

Route handlers (thin — delegate to services).

APScheduler: Friday 6pm cron calls `run_digest_agent`.

`POST /digest/generate`: triggers `run_digest_agent` via `BackgroundTasks`, auth-protected.

Rate limiting: `slowapi`, per IP, in-memory store.

Auth: `verify_api_key` FastAPI dependency on mutating routes.

Static files: `frontend/dist/` served in production. Catch-all `/{full_path:path}` resolves and validates paths against dist root before serving (path traversal safe). **This route must be last — otherwise it intercepts API POST routes.**

### `frontend/` — React + Vite + React Router

**Routing:**
- `/` — home (article list + add form + digest preview)
- `/articles/:id` — article detail page (summary + chat)
- `/digest` — current week's full digest page
- `/digest/:id` — past digest by id *(planned)*
- `/history` — all past digests + favourited articles *(planned)*

**Shared utilities:**
- `utils.js` — `getDomain(url)` and `scoreBadgeClass(score)`

**Components:**
- `main.jsx` — entry point, wraps app in `<BrowserRouter>`
- `App.jsx` — defines routes, home page state (articles, digest, toast), polling every 5s
- `AddArticle.jsx` — URL input + submit
- `ArticleCard.jsx` — title, domain, score badge, status pill, delete, star button *(star planned)*
- `DigestView.jsx` — collapsed 180-char preview on home page; clicking navigates to `/digest`
- `AgentGraph.jsx` — Mermaid flowchart of agent tool call sequence; `securityLevel: 'loose'` enables click callbacks; `window.__agGraphClick` wired to `onNodeClick` prop
- `AgentTrace.jsx` — expandable timeline of all agent steps with agent badges
- `StepModal.jsx` — overlay popup showing step details (query, result, agent badge)
- `pages/ArticleDetailPage.jsx` — full summary + chat interface
- `pages/DigestPage.jsx` — full digest view: content, token usage, timestamp, regenerate button, discovery picks, clickable agent graph, expandable trace, step modal
- `pages/HistoryPage.jsx` *(planned)* — past digests list + favourited articles

**Data flow:**
- `App.jsx` fetches `GET /articles` on load and every 5 seconds
- `App.jsx` fetches `GET /digest/current` on load
- `DigestPage.jsx` fetches `GET /digest/current` independently on mount
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
Applied to: `POST /articles`, `DELETE /articles/{id}`, `POST /articles/{id}/chat`, `POST /digest/generate`.  
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

### Docker (next step — not yet verified)
- Multi-stage Dockerfile: Node 20 Alpine builds React → Python 3.11 slim runs everything
- `VITE_API_KEY` passed as build arg so Vite embeds it in the JS bundle at build time
- `docker-compose.yml`: single `app` service, SQLite persisted at `/app/data/articles.db` on a named volume
- `Caddyfile`: optional TLS reverse proxy — uncomment Caddy service in compose when deploying with a real domain

```bash
# Build and run locally
VITE_API_KEY=your-key docker-compose up --build

# With Caddy TLS (needs a real domain in Caddyfile)
docker-compose --profile caddy up --build
```

### Cloud deploy options

| Platform | Effort | Cost | Notes |
|---|---|---|---|
| **Fly.io** | Low | ~$5/mo (shared-cpu-1x) | `fly launch` reads Dockerfile; volumes for SQLite |
| **Railway** | Low | ~$5/mo | Connect GitHub repo; auto-deploys on push |
| **VPS + Caddy** | Medium | ~$5/mo (Hetzner CX11) | Full control; Caddy handles HTTPS automatically |

**Recommended: Fly.io** — single command deploy, volume support for SQLite, free tier for low traffic.

```bash
# Fly.io deploy (after fly auth login)
fly launch          # detects Dockerfile, prompts for region
fly volumes create data --size 1   # SQLite persistence
fly secrets set ANTHROPIC_API_KEY=... TAVILY_API_KEY=... SECRET_KEY=...
fly deploy --build-arg VITE_API_KEY=...
```

**Key production checklist:**
- Set `CORS_ORIGINS` to your actual domain (removes localhost from allowed origins)
- `SECRET_KEY` must be set — without it auth is skipped entirely
- `VITE_API_KEY` must be provided at Docker build time (Vite embeds it; runtime env vars have no effect)
- SQLite volume must be mounted — without it the DB resets on every deploy

### Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | — | Anthropic API key |
| `TAVILY_API_KEY` | Yes (for digest) | — | Tavily search API key |
| `SECRET_KEY` | Yes (prod) | — | API key for mutating endpoints; auth skipped if unset |
| `VITE_API_KEY` | Yes (prod) | — | Must match `SECRET_KEY`; passed as Docker build arg |
| `DATABASE_URL` | No | SQLite local file | SQLAlchemy connection string |
| `CORS_ORIGINS` | No | localhost origins | Comma-separated allowed origins |
| `INTERESTS` | No | `agentic systems, AI/ML, LLM engineering, software architecture` | User interests — biases scoring and digest framing |

---

## 8. Multi-Agent Digest — Design

### Overview

The digest is generated by two specialised agents run sequentially. Each agent has its own system prompt, tool set, and responsibility.

```
fetch this week's articles + past themes (memory)
      │
      ▼
Discovery Agent
  ├── web_search × N   (finds new articles not in queue)
  └── report_findings  (returns curated list → exits)
      │
      ▼
Digest Agent
  ├── web_search × N   (optional additional context)
  └── save_digest      (writes final digest → exits)
      │
      ▼
Theme extraction (single Claude call)
      │
      ▼
Save to DB: content, trace, themes, suggested_articles, token_usage
```

### Agent memory

After each digest, `_extract_and_save_themes` extracts 2–4 keyword themes.  
`_fetch_memory` loads the last 4 weeks' themes and formats them into both agents' system prompts.  
This ensures the digest finds new angles each week rather than repeating itself.

### Token tracking

`_TokenUsage` accumulates `input_tokens`, `output_tokens`, `cache_read_input_tokens`, and `cache_creation_input_tokens` from every `response.usage` object across both agents. The final totals are stored as JSON in `digests.token_usage` and displayed in the UI.

### Tools

**`list_articles`** (Digest Agent only)
- Returns all ready articles this week: `{ title, url, summary, score, score_reason }`

**`web_search`** (both agents)
- Input: `{ "query": string }`
- Calls Tavily AsyncTavilyClient, returns top 3 results as `{ title, url, snippet }`

**`report_findings`** (Discovery Agent)
- Input: `{ "articles": [{ title, url, reason }] }`
- Ends the Discovery Agent loop and passes findings to the Digest Agent

**`save_digest`** (Digest Agent)
- Input: `{ "content": string }` — markdown-formatted digest
- Saves to DB and signals end of Digest Agent loop

### Trace format

Every step from both agents is recorded in a single flat trace array:

```json
[
  { "type": "agent_start", "agent": "discovery", "summary": "Discovery Agent starting" },
  { "type": "reasoning",   "agent": "discovery", "content": "I'll search for agentic AI articles." },
  { "type": "tool_call",   "agent": "discovery", "tool": "web_search", "input": { "query": "..." }, "summary": "3 results" },
  { "type": "tool_call",   "agent": "discovery", "tool": "report_findings", "summary": "2 articles found" },
  { "type": "agent_start", "agent": "digest",    "summary": "Digest Agent starting" },
  { "type": "reasoning",   "agent": "digest",    "content": "Strong theme around multi-agent systems." },
  { "type": "tool_call",   "agent": "digest",    "tool": "save_digest", "summary": "Digest saved" }
]
```

### Frontend: DigestPage

```
┌─ ← Back                                   [Regenerate] ─┐
│                                                           │
│  Week 23 Digest                                          │
│  Fri, Jun 6, 6:00 PM  ·  14,250 tokens  ·  1,850 out   │
│                                                           │
│  [Full markdown digest content]                           │
│                                                           │
│  Also worth reading (Discovery Agent picks)              │
│  ──────────────────────────────────────                  │
│  • Article title — reason it was picked                  │
│                                                           │
│  Agent flow (clickable Mermaid graph)                    │
│  ──────────────────────────────────────                  │
│  [Discovery Agent] → [web_search] → [report_findings]   │
│  → [Digest Agent] → [save_digest]                       │
│                                                           │
│  ▼ Agent trace (expandable timeline)                     │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

Clicking any graph node opens `StepModal` — a popup showing: tool name, agent badge, query input, and result summary.
