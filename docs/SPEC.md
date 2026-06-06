# Functional Specification — Reading Queue

## Overview

A personal reading-queue web app. The user pastes article URLs during the week; the app extracts, summarises, and scores each article. Every Friday, an AI agent generates a synthesised digest — finding themes, making connections, and searching the web for related context — then saves its reasoning so the user can see exactly what the agent decided and why.

## Users

Single-user personal tool. API key authentication on mutating endpoints.

---

## Functional Requirements

### FR-1: Add an article

- User pastes a URL into the input field and clicks Add (or presses Enter)
- The app validates it is a real URL
- If the URL already exists, return the existing record (no duplicate)
- Insert the article with status `pending`
- In the background: extract content → summarise → score → update to `ready` or `failed`
- The UI shows the card immediately with a "Processing" pill, then refreshes automatically

### FR-2: View this week's articles

- Show all articles added in the current ISO week
- Sorted by score descending (unscored articles appear last)
- Each card shows: title, domain, score badge, status pill, score reason

### FR-3: View a single article

- Clicking an article card opens a detail page (`/articles/:id`)
- Detail page shows: title, domain, score badge, score reason, full summary, status
- Full article text is accessible via `GET /articles/{id}`

### FR-4: Delete an article

- Hard delete — removed from database permanently

### FR-6: Chat with an article

- On the detail page, the user can ask questions about the article
- Questions are answered by Claude using the article's full text as context
- `POST /articles/{id}/chat` accepts a list of messages (conversation history) and returns the assistant reply
- Prompt caching is used so the article text is only billed once per cache window — subsequent questions in the same conversation are cheaper

### FR-5: Weekly digest — Agentic

Every Friday at 6pm, an AI agent generates the digest. The agent:

1. Calls `list_articles` to read all articles saved this week
2. Reasons about themes — including through the lens of the user's standing interests (see `INTERESTS` env var)
3. Optionally calls `web_search` (Tavily) one or more times to pull in related context on topics it finds interesting
4. Calls `save_digest` when ready — this writes the final digest and ends the agent loop

The digest is markdown-formatted. Unlike a simple summary loop, the agent synthesises across articles — it finds connections, frames diverse reads through the user's interests, and decides how much web research is warranted.

### FR-7: Agent decision log

- Every step the agent takes is recorded: its reasoning text, which tool it called, what it searched for, and what it decided
- The trace is stored as JSON alongside the digest in the `digests` table
- `GET /digest/current` returns both the digest content and the full trace
- The UI displays the digest and, below it, an expandable **"How the agent thought"** panel showing each step as a timeline

This serves two purposes: transparency (user sees why the digest was shaped as it was) and learning (the trace makes the agent loop observable and concrete).

### FR-8: Configurable user interests

- `INTERESTS` env var — comma-separated list of topics the user cares about
- Default: `agentic systems, AI/ML, LLM engineering, software architecture`
- Passed to the agent's system prompt to bias theme detection and web search queries
- Also used by the article scoring prompt to define relevance

---

## Non-Functional Requirements

### NFR-1: Performance
- Article processing happens in a background task — the POST endpoint must return immediately (< 200ms)
- Digest generation is a background cron job — latency does not affect the user

### NFR-2: Reliability
- If extraction or summarisation fails, article status is set to `failed` (visible in UI)
- If the digest agent fails, the error is logged and the trace records the failure step
- Errors are logged

### NFR-3: Portability
- Database schema must be compatible with Postgres for future migration
- App must run locally with SQLite and in Docker

### NFR-4: Simplicity
- React + Vite for frontend (component model, no complex state management)
- No separate worker process — background tasks and the agent loop run inside FastAPI
- API key auth (header-based) — no session management

### NFR-5: Security
- Mutating endpoints (`POST /articles`, `DELETE /articles/{id}`, `POST /articles/{id}/chat`) require `X-API-Key` header
- Auth is skipped in local dev when `SECRET_KEY` is not set — no friction during development
- AI-triggering endpoints are rate-limited to prevent unexpected Anthropic bill spikes
- Static file serving is path-traversal safe (resolved paths checked against dist root)

### NFR-6: Rate limiting
- `POST /articles` — max 20 requests/hour per IP
- `POST /articles/{id}/chat` — max 30 requests/hour per IP
- Exceeding the limit returns HTTP 429

---

## Scoring Criteria (Claude prompt)

Claude scores articles 1–10 for relevance to the user's interests (configurable via `INTERESTS` env var; default topics below).

Score bands:
- **8–10**: Green — highly relevant
- **5–7**: Amber — moderately relevant
- **1–4**: Grey — low relevance

---

## Out of Scope

- Multiple users
- Email delivery of digest
- Mobile app
- Article archiving beyond current week display
