# Reading Queue

A personal tool to paste article URLs during the week and get a ranked AI digest every Friday.

**Live:** https://sunlit-grove-996.fly.dev

---

## What it does

- **Paste a URL** → app extracts the article, summarises it with Claude, and scores it 1–10 for relevance
- **Resilient extraction** — tries Trafilatura first; falls back to Jina Reader for sites that block bots (Medium, etc.); retries up to 3× with backoff before marking failed
- **Article detail page** — full summary, score breakdown, and a chat interface powered by Claude with prompt caching
- **Weekly digest** — a two-agent system runs every Friday at 6pm (or on-demand):
  - **Discovery Agent** searches the web for new articles related to your interests
  - **Digest Agent** synthesises your saved articles + discoveries into a ranked briefing
  - Both agents share **memory** of past weeks' themes to avoid repetition
- **Agent decision log** — the digest page shows a Mermaid flowchart of every tool call, an expandable trace timeline, and a popup for each step — so you can see exactly what the agents did and why
- **Token usage** — input / output / cached tokens displayed per digest
- **History & Favorites** — star articles, browse all past digests, delete anything you don't need

---

## Tech stack

**Backend**
- **FastAPI** — async Python web framework
- **SQLite** — local database (Postgres-compatible schema)
- **SQLAlchemy (async)** — ORM
- **Trafilatura** + **Jina Reader** — article extraction with fallback
- **Anthropic Claude API** — summarisation, scoring, chat (prompt caching), multi-agent digest
- **Tavily** — web search for the Discovery Agent
- **APScheduler** — Friday 6pm digest cron job
- **slowapi** — per-IP rate limiting
- **API key auth** — `X-API-Key` header on all mutating endpoints

**Frontend**
- **React + Vite** — component UI and build tool
- **React Router** — client-side routing
- **Mermaid.js** — clickable agent flowchart

**Infrastructure**
- **Docker** — multi-stage build (Node → Python), single container
- **Fly.io** — cloud deploy, auto-suspend on idle, SQLite volume persistence
- **Caddy** — optional TLS reverse proxy for self-hosted deploys

---

## Quick start (local dev)

```bash
# First time setup
cd backend && python3.11 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY + TAVILY_API_KEY

cd ../frontend && npm install
cp .env.local.example .env.local  # add VITE_API_KEY (same as SECRET_KEY)
cd ..

# Run both servers
./start.sh
```

- App: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

---

## Run with Docker

```bash
VITE_API_KEY=your-key docker-compose up --build
```

App available at http://localhost:8000

---

## Deploy to Fly.io

```bash
fly auth login
fly apps create --generate-name
fly volumes create sqlite_data --size 1 --region sin
fly secrets set ANTHROPIC_API_KEY=... TAVILY_API_KEY=... SECRET_KEY=... CORS_ORIGINS=https://your-app.fly.dev
fly deploy --build-arg VITE_API_KEY=...   # must match SECRET_KEY
```

---

## Project structure

```
reading-queue/
├── docs/
│   ├── SPEC.md          # Functional specification
│   ├── SDD.md           # Software design document
│   └── PROGRESS.md      # Build checklist
├── backend/
│   ├── .env.example     # Environment variable template
│   ├── requirements.txt
│   └── src/
│       ├── main.py          # FastAPI routes, background tasks, retry logic
│       ├── models.py        # SQLAlchemy ORM (Article, Digest)
│       ├── database.py      # Async engine, session, migrations
│       ├── schemas.py       # Pydantic request/response schemas
│       └── services/
│           ├── extractor.py     # Trafilatura + Jina Reader fallback
│           ├── summariser.py    # Claude summarisation + scoring
│           └── digest_agent.py  # Discovery + Digest agents, memory, token tracking
├── frontend/
│   ├── vite.config.js
│   └── src/
│       ├── App.jsx              # Routes + home page state
│       ├── App.css              # All styles (indigo theme, CSS custom properties)
│       ├── components/
│       │   ├── AddArticle.jsx
│       │   ├── ArticleCard.jsx  # Score badge, star button, delete
│       │   ├── DigestView.jsx   # Collapsed preview on home page
│       │   ├── AgentGraph.jsx   # Clickable Mermaid flowchart
│       │   ├── AgentTrace.jsx   # Expandable step timeline
│       │   └── StepModal.jsx    # Popup for tool call details
│       └── pages/
│           ├── ArticleDetailPage.jsx  # Summary + chat
│           ├── DigestPage.jsx         # Full digest, graph, trace
│           └── HistoryPage.jsx        # Past digests + starred articles
├── fly.toml
├── Dockerfile
├── docker-compose.yml
└── Caddyfile
```

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `TAVILY_API_KEY` | Yes (digest) | Tavily search API key |
| `SECRET_KEY` | Prod only | API key for mutating endpoints |
| `VITE_API_KEY` | Prod only | Must match `SECRET_KEY` — passed as Docker build arg |
| `DATABASE_URL` | No | SQLAlchemy URL (default: SQLite local file) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: localhost) |
| `INTERESTS` | No | User interests for digest framing (default: `agentic systems, AI/ML, LLM engineering, software architecture`) |

---

## API endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/articles` | ✓ | Add article URL |
| `GET` | `/articles` | — | Current week's articles |
| `GET` | `/articles/favorites` | — | All starred articles |
| `GET` | `/articles/{id}` | — | Single article + full text |
| `DELETE` | `/articles/{id}` | ✓ | Delete article |
| `PATCH` | `/articles/{id}/favorite` | ✓ | Toggle star |
| `POST` | `/articles/{id}/chat` | ✓ | Chat with article |
| `GET` | `/digest/current` | — | This week's digest + trace |
| `GET` | `/digest/all` | — | All past digests |
| `GET` | `/digest/{id}` | — | Specific digest by id |
| `POST` | `/digest/generate` | ✓ | Trigger agents now |
| `DELETE` | `/digest/{id}` | ✓ | Delete a digest |
