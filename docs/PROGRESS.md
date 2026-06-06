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
- [ ] `Dockerfile` created
- [ ] `docker-compose.yml` created
- [ ] `.env.example` created
- [ ] `Caddyfile` created
- [ ] `docker-compose up --build` runs successfully

---

## Step 9 — Rate limiting (~30 min)
Add `slowapi` to cap how many times AI endpoints can be called per IP.
Prevents unexpected Anthropic bill spikes if the app URL is discovered.

- [ ] `pip install slowapi` and add to `requirements.txt`
- [ ] Configure `Limiter` in `main.py` with a default in-memory store
- [ ] Apply limit to `POST /articles` — e.g. 20/hour per IP
- [ ] Apply limit to `POST /articles/{id}/chat` — e.g. 30/hour per IP
- [ ] Test: verify 429 is returned after limit is hit

---

## Step 10 — Authentication (~1 hour, two options — pick one)

**Option A: Caddy HTTP Basic Auth** (simplest, requires Step 8 done first)
- Zero backend code changes — Caddy handles it at the proxy level
- Add `basic_auth` block to `Caddyfile` with a hashed password
- All routes are protected automatically
- Estimated time: ~10 min once Docker is running

**Option B: FastAPI API key middleware** (works without Docker, ~30 min)
- Add `SECRET_KEY` env var to `.env` and `.env.example`
- Add a FastAPI dependency `verify_api_key()` that checks the `X-API-Key` header
- Apply the dependency to all routes that mutate data (POST, DELETE, chat)
- Update frontend to send the header on every API call
- Estimated time: ~30–45 min

Tasks (fill in once you've chosen):
- [ ] Choose approach (A or B)
- [ ] Implement chosen approach
- [ ] Test: unauthenticated request returns 401/403
- [ ] Test: authenticated request works normally

---

## Done!
- [ ] Full end-to-end test: paste URL → processing → ready → digest stub
- [ ] Rate limiting verified (429 after limit)
- [ ] Authentication verified (401 without credentials)
- [ ] README instructions verified accurate
