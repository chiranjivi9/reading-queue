# Reading Queue

A personal tool to paste article URLs during the week and get a ranked digest every Friday.

## What it does

- Paste a URL → app extracts the article, summarises it with Claude AI, and scores it 1–10 for relevance
- See all articles for the current week, sorted by score
- Click any article card to open its detail page — full summary, score breakdown, and a chat interface
- Ask follow-up questions about any article directly in the browser (prompt caching keeps it fast and cheap)
- Every Friday at 6pm, an **AI agent** generates the weekly digest — it reads your articles, searches the web for related context (via Tavily), finds cross-cutting themes through the lens of your interests, and writes a synthesised briefing
- The digest page shows an **agent decision log** — an expandable timeline of every tool call and reasoning step the agent took, so you can see exactly what it did and why

## Tech stack

**Backend**
- **FastAPI** — async Python web framework
- **SQLite** — local database (Postgres-compatible schema for future migration)
- **SQLAlchemy (async)** — ORM for database access
- **Trafilatura** — article content extraction
- **Anthropic Claude API** — summarisation, relevance scoring, article chat (prompt caching), and agentic digest
- **Tavily** — web search API used by the digest agent
- **APScheduler** — Friday digest cron job (triggers the agent)

**Frontend**
- **React** — component-based UI
- **Vite** — fast dev server and build tool
- **React Router** — client-side routing (home list + article detail page)

**Infrastructure**
- **Caddy** — reverse proxy for production (serves React build + proxies API)

## Quick start

**One command (recommended):**
```bash
./start.sh
```
Starts both servers. Stop with Ctrl+C.

- App: http://localhost:5173
- API: http://localhost:8000
- API docs: http://localhost:8000/docs

**Manual setup (first time):**
```bash
# Backend
cd backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
cd ..

# Frontend
cd frontend
npm install
cd ..

# Then run
./start.sh
```

## Run with Docker

```bash
docker-compose up --build
```

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
│       ├── main.py          # FastAPI app, all routes, background task
│       ├── models.py        # SQLAlchemy ORM table definitions
│       ├── database.py      # Async engine, session, init_db()
│       ├── schemas.py       # Pydantic request/response schemas
│       └── services/
│           ├── extractor.py     # Trafilatura article extraction
│           └── summariser.py    # Claude API summarisation + scoring
├── frontend/
│   ├── vite.config.js
│   ├── package.json
│   └── src/
│       ├── main.jsx             # Entry point (BrowserRouter)
│       ├── App.jsx              # Routes + home page state
│       ├── App.css              # All styles
│       ├── utils.js             # Shared helpers (getDomain, scoreBadgeClass)
│       ├── components/
│       │   ├── AddArticle.jsx   # URL input form
│       │   ├── ArticleCard.jsx  # List card (click to open detail)
│       │   └── DigestView.jsx   # Weekly digest display
│       └── pages/
│           └── ArticleDetailPage.jsx  # Summary + chat interface
├── Dockerfile
├── docker-compose.yml
└── Caddyfile
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `TAVILY_API_KEY` | Yes (digest) | Tavily search API key — used by the digest agent |
| `SECRET_KEY` | Prod only | API key for mutating endpoints (`X-API-Key` header) |
| `DATABASE_URL` | No | SQLAlchemy connection string (default: SQLite local file) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: localhost) |
| `INTERESTS` | No | Comma-separated user interests — biases digest framing and article scoring (default: `agentic systems, AI/ML, LLM engineering, software architecture`) |
