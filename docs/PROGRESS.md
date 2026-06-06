# Build Progress — Reading Queue

Track each step as you build. Check off tasks as you complete them.

---

## Setup
- [x] Created project folder structure (`services/`, `static/`)
- [x] Created and activated Python 3.11 virtual environment
- [x] Created `requirements.txt`
- [x] Installed dependencies (`pip install -r requirements.txt`)
- [x] Created documentation (`README.md`, `SPEC.md`, `SDD.md`, `PROGRESS.md`)
- [X] Created `.env` from `.env.example` with real API key

---

## Step 2 — `models.py`
- [X] Defined `Article` model with all columns
- [X] Defined `Digest` model
- [X] Verified: can import models without errors

---

## Step 3 — `database.py`
- [X] Created async SQLAlchemy engine
- [X] Created `get_db()` dependency
- [X] Created `init_db()` function
- [X] Verified: can import database without errors

---

## Step 4 — `services/extractor.py`
- [X] Implemented `extract_article(url)` with Trafilatura
- [X] Handles timeout (10 seconds)
- [X] Raises clear exception if extraction fails
- [X] Manually tested with a real URL

---

## Step 5 — `services/summariser.py`
- [X] Implemented `summarise(title, text)` with Claude API
- [X] Prompt returns JSON: `{ summary, score, score_reason }`
- [X] Parses JSON robustly (strips markdown fences)
- [X] Manually tested with sample article text

---

## Step 6 — `main.py`
- [X] FastAPI app created
- [X] Static files mounted
- [X] `POST /articles` — validates URL, checks duplicate, inserts, kicks off background task
- [X] `GET /articles` — returns current week's articles sorted by score
- [X] `GET /articles/{id}` — returns single article with full_text
- [X] `DELETE /articles/{id}` — hard delete
- [X] `GET /digest/current` — returns current week's digest or null
- [X] `process_article()` background task implemented
- [X] APScheduler Friday cron stub added
- [X] `init_db()` called on startup
- [X] Tested all endpoints with curl or browser

---

## Step 7 — React frontend (`frontend/`)
- [X] Vite + React project scaffolded (`npm create vite@latest`)
- [X] `vite.config.js` proxy set up (routes /articles and /digest to :8000)
- [X] `App.jsx` — fetches articles on load, polls every 5 seconds
- [X] `AddArticle.jsx` — URL input + submit, optimistic "Processing" card
- [X] `ArticleCard.jsx` — title, domain, score badge (green/amber/grey), status pill, delete
- [X] `DigestView.jsx` — renders this week's digest or empty state
- [X] Tested end-to-end in browser (paste URL → processing → ready)

---

## Step 7b — Enhanced UI & chat feature
- [X] `POST /articles/{id}/chat` endpoint added to `main.py`
- [X] Chat schemas added to `schemas.py` (`ChatRequest`, `ChatResponse`)
- [X] Prompt caching added to `summariser.py` (article text block marked `cache_control: ephemeral`)
- [X] `react-router-dom` installed and `BrowserRouter` added to `main.jsx`
- [X] `App.jsx` updated with `<Routes>` — home route and `/articles/:id` route
- [X] `ArticleCard.jsx` updated — card click navigates to detail page
- [X] `pages/ArticleDetailPage.jsx` created — summary view + chat interface
- [X] `utils.js` created — shared `getDomain` and `scoreBadgeClass` helpers
- [X] `App.css` updated — fluid, modern, mobile-first design with hover effects and chat bubbles
- [ ] Tested: article detail page loads, chat responds

---

## Step 8 — Docker & deployment files
- [X] `Dockerfile` created — multi-stage build (Node builds frontend → Python runs everything)
- [X] `.dockerignore` created — excludes venv, node_modules, .env, .db from image
- [X] `docker-compose.yml` created — single `app` service with SQLite volume; Caddy section commented out for optional HTTPS
- [X] `Caddyfile` created — TLS reverse proxy config (uncomment Caddy in compose to use)
- [X] `start.sh` created — one command starts both backend and frontend dev servers
- [X] `start.sh` fixed — exports `VIRTUAL_ENV` and uses `python -m uvicorn` so `--reload` subprocesses inherit the venv Python instead of Anaconda's
- [X] `main.py` updated — serves built frontend static files in production (catch-all route after all API routes)
- [ ] `docker-compose up --build` tested successfully

---

## Step 9 — Rate limiting
Add `slowapi` to cap how many times AI endpoints can be called per IP.
Prevents unexpected Anthropic bill spikes if the app URL is discovered.

- [X] `slowapi` installed and added to `requirements.txt`
- [X] `Limiter` configured in `main.py` with in-memory store (resets on restart)
- [X] `POST /articles` limited to 20/hour per IP
- [X] `POST /articles/{id}/chat` limited to 30/hour per IP
- [X] Returns HTTP 429 automatically when limit is exceeded
- [ ] Test: verify 429 is returned after limit is hit

---

## Step 10 — Authentication (Option B: API key)
- [X] `SECRET_KEY` added to `backend/.env.example`
- [X] `verify_api_key()` dependency added to `main.py` — checks `X-API-Key` header
- [X] Applied to `POST /articles`, `DELETE /articles/{id}`, `POST /articles/{id}/chat`
- [X] GET routes left open (read-only, no AI cost)
- [X] Frontend sends `X-API-Key` header on all mutating requests
- [X] `VITE_API_KEY` read from `frontend/.env.local` (gitignored)
- [X] Auth skipped in dev if `SECRET_KEY` is not set — no friction during development
- [ ] Test: unauthenticated request returns 401
- [ ] Test: authenticated request works normally

---

## Done!
- [ ] Full end-to-end test: paste URL → processing → ready → digest stub
- [ ] Rate limiting verified (429 after limit)
- [ ] Authentication verified (401 without credentials)
- [ ] README instructions verified accurate
