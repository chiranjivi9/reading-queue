# Reading Queue

A personal tool to paste article URLs during the week and get a ranked digest every Friday.

## What it does

- Paste a URL → app extracts the article, summarises it with Claude AI, and scores it 1–10 for relevance
- See all articles for the current week, sorted by score
- Click any article card to open its detail page — full summary, score breakdown, and a chat interface
- Ask follow-up questions about any article directly in the browser (prompt caching keeps it fast and cheap)
- Every Friday at 6pm, a digest is automatically generated

## Tech stack

**Backend**
- **FastAPI** — async Python web framework
- **SQLite** — local database (Postgres-compatible schema for future migration)
- **SQLAlchemy (async)** — ORM for database access
- **Trafilatura** — article content extraction
- **Anthropic Claude API** — summarisation, relevance scoring, and article chat (with prompt caching)
- **APScheduler** — Friday digest cron job

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

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `DATABASE_URL` | SQLAlchemy connection string (default: `sqlite+aiosqlite:///./articles.db`) |
