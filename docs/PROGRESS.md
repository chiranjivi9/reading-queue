# Build Progress — Reading Queue

Track each step as you build. Check off tasks as you complete them.

---

## Setup
- [x] Created project folder structure (`services/`, `static/`)
- [x] Created and activated Python 3.11 virtual environment
- [x] Created `requirements.txt`
- [x] Installed dependencies (`pip install -r requirements.txt`)
- [x] Created documentation (`README.md`, `SPEC.md`, `SDD.md`, `PROGRESS.md`)
- [x] Created `.env` from `.env.example` with real API key

---

## Step 2 — `models.py`
- [x] Defined `Article` model with all columns
- [x] Defined `Digest` model
- [x] Verified: can import models without errors

---

## Step 3 — `database.py`
- [x] Created async SQLAlchemy engine
- [x] Created `get_db()` dependency
- [x] Created `init_db()` function
- [x] Verified: can import database without errors

---

## Step 4 — `services/extractor.py`
- [x] Implemented `extract_article(url)` with Trafilatura
- [x] Handles timeout (10 seconds)
- [x] Raises clear exception if extraction fails
- [x] Manually tested with a real URL

---

## Step 5 — `services/summariser.py`
- [x] Implemented `summarise(title, text)` with Claude API
- [x] Prompt returns JSON: `{ summary, score, score_reason }`
- [x] Parses JSON robustly (strips markdown fences)
- [x] Manually tested with sample article text

---

## Step 6 — `main.py`
- [x] FastAPI app created
- [x] Static files mounted
- [x] `POST /articles` — validates URL, checks duplicate, inserts, kicks off background task
- [x] `GET /articles` — returns current week's articles sorted by score
- [x] `GET /articles/{id}` — returns single article with full_text
- [x] `DELETE /articles/{id}` — hard delete
- [x] `GET /digest/current` — returns current week's digest or null
- [x] `process_article()` background task implemented
- [x] APScheduler Friday cron stub added
- [x] `init_db()` called on startup
- [x] Tested all endpoints with curl or browser

---

## Step 7 — React frontend (`frontend/`)
- [x] Vite + React project scaffolded (`npm create vite@latest`)
- [x] `vite.config.js` proxy set up (routes /articles and /digest to :8000)
- [x] `App.jsx` — fetches articles on load, polls every 5 seconds
- [x] `AddArticle.jsx` — URL input + submit, optimistic "Processing" card
- [x] `ArticleCard.jsx` — title, domain, score badge (green/amber/grey), status pill, delete
- [x] `DigestView.jsx` — renders this week's digest or empty state
- [x] Tested end-to-end in browser (paste URL → processing → ready)

---

## Step 7b — Enhanced UI & chat feature
- [x] `POST /articles/{id}/chat` endpoint added to `main.py`
- [x] Chat schemas added to `schemas.py` (`ChatRequest`, `ChatResponse`)
- [x] Prompt caching added to `summariser.py` (article text block marked `cache_control: ephemeral`)
- [x] `react-router-dom` installed and `BrowserRouter` added to `main.jsx`
- [x] `App.jsx` updated with `<Routes>` — home route and `/articles/:id` route
- [x] `ArticleCard.jsx` updated — card click navigates to detail page
- [x] `pages/ArticleDetailPage.jsx` created — summary view + chat interface
- [x] `utils.js` created — shared `getDomain` and `scoreBadgeClass` helpers
- [x] `App.css` updated — fluid, modern, mobile-first design with hover effects and chat bubbles
- [ ] Tested: article detail page loads, chat responds

---

## Step 8 — Docker & deployment files
- [x] `Dockerfile` created — multi-stage build (Node builds frontend → Python runs everything)
- [x] `VITE_API_KEY` build arg wired in Dockerfile + docker-compose so key is embedded at build time
- [x] `.dockerignore` created — excludes venv, node_modules, .env, .db from image
- [x] `docker-compose.yml` created — single `app` service with SQLite volume; Caddy section commented out for optional HTTPS
- [x] `Caddyfile` created — TLS reverse proxy config (uncomment Caddy in compose to use)
- [x] `start.sh` created — one command starts both backend and frontend dev servers
- [x] `start.sh` fixed — exports `VIRTUAL_ENV` and uses `python -m uvicorn` so `--reload` subprocesses inherit the venv Python instead of Anaconda's
- [x] `main.py` updated — serves built frontend static files in production (catch-all route after all API routes)
- [ ] `docker-compose up --build` tested successfully

---

## Step 9 — Rate limiting
- [x] `slowapi` installed and added to `requirements.txt`
- [x] `Limiter` configured in `main.py` with in-memory store (resets on restart)
- [x] `POST /articles` limited to 20/hour per IP
- [x] `POST /articles/{id}/chat` limited to 30/hour per IP
- [x] Returns HTTP 429 automatically when limit is exceeded
- [ ] Test: verify 429 is returned after limit is hit

---

## Step 10 — Authentication (Option B: API key)
- [x] `SECRET_KEY` added to `backend/.env.example`
- [x] `verify_api_key()` dependency added to `main.py` — checks `X-API-Key` header
- [x] Applied to `POST /articles`, `DELETE /articles/{id}`, `POST /articles/{id}/chat`
- [x] GET routes left open (read-only, no AI cost)
- [x] Frontend sends `X-API-Key` header on all mutating requests
- [x] `VITE_API_KEY` read from `frontend/.env.local` (gitignored)
- [x] Auth skipped in dev if `SECRET_KEY` is not set — no friction during development
- [ ] Test: unauthenticated request returns 401
- [ ] Test: authenticated request works normally

---

## Step 11 — Agentic digest with decision log

Replace the Friday cron stub with a real agent that synthesises articles, searches the web, and records every decision it makes.

### Backend

- [ ] `TAVILY_API_KEY` and `INTERESTS` added to `.env.example`
- [ ] `tavily-python` added to `requirements.txt`
- [ ] `trace` column (TEXT / JSON) added to `Digest` model in `models.py`
- [ ] `DigestResponse` schema updated to include `trace` field
- [ ] `services/digest_agent.py` created:
  - [ ] Tool definitions: `list_articles`, `web_search`, `save_digest`
  - [ ] Agent loop: call Claude → execute tool → append result → repeat
  - [ ] Trace captured: reasoning text blocks + tool call entries
  - [ ] `save_digest` tool writes digest + trace to DB and ends loop
- [ ] Friday cron in `main.py` replaced: calls `run_digest_agent(db)` instead of logging stub

### Frontend

- [ ] `GET /digest/current` now returns `trace` — no backend route change needed (schema update handles it)
- [ ] `DigestView.jsx` updated — passes `trace` to `AgentTrace`
- [ ] `AgentTrace.jsx` created — expandable timeline panel (collapsed by default)
  - [ ] Reasoning steps shown with 💭 icon
  - [ ] Tool calls shown with 🔧 icon + tool name + brief result summary
  - [ ] Final `save_digest` shown with ✅ icon

### Config

- [ ] `TAVILY_API_KEY` set in `backend/.env`
- [ ] `INTERESTS` optionally set in `backend/.env` (default used if not set)

---

## Done!
- [ ] Full end-to-end test: paste URL → processing → ready → digest generated
- [ ] Agent trace visible in UI below digest
- [ ] Rate limiting verified (429 after limit)
- [ ] Authentication verified (401 without credentials)
- [ ] README instructions verified accurate
