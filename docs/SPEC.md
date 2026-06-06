# Functional Specification — Reading Queue

## Overview

A personal reading-queue web app. The user pastes article URLs during the week; the app extracts, summarises, and scores each article. Every Friday, a two-agent AI system generates a synthesised digest — the Discovery Agent finds new articles from the web, the Digest Agent synthesises everything and writes the final digest — recording every decision so the user can see exactly what each agent decided and why.

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
- Star button to mark an article as a favourite (persists to database)

### FR-3: View a single article

- Clicking an article card opens a detail page (`/articles/:id`)
- Detail page shows: title, domain, score badge, score reason, full summary, status
- Full article text is accessible via `GET /articles/{id}`

### FR-4: Delete an article

- Hard delete — removed from database permanently

### FR-5: Chat with an article

- On the detail page, the user can ask questions about the article
- Questions are answered by Claude using the article's full text as context
- `POST /articles/{id}/chat` accepts a list of messages (conversation history) and returns the assistant reply
- Prompt caching is used so the article text is only billed once per cache window

### FR-6: Weekly digest — Multi-agent

Every Friday at 6pm (or on-demand via `POST /digest/generate`), a two-agent system generates the digest:

**Agent 1 — Discovery Agent**
1. Receives this week's article list and user interests
2. Calls `web_search` (Tavily) to find new, related articles not already in the queue
3. Calls `report_findings` when done — returns a curated list of suggested articles

**Agent 2 — Digest Agent**
1. Receives the saved articles + Discovery Agent's findings
2. Reasons about themes through the lens of the user's standing interests (`INTERESTS` env var)
3. Optionally calls `web_search` for additional context
4. Calls `save_digest` — writes the final markdown digest and ends the loop

Both agents receive memory of the past 4 weeks' themes so the digest evolves over time rather than repeating the same angles.

### FR-7: Agent decision log

- Every step both agents take is recorded: reasoning text, which tool was called, what was searched, what was decided, which agent ran it
- The trace is stored as JSON alongside the digest
- `GET /digest/current` returns the digest content and full trace
- The digest detail page (`/digest`) shows:
  - Full markdown content
  - Token usage (input / output / cached tokens for the full agent run)
  - Timestamp of generation
  - "Also worth reading" — Discovery Agent's suggested articles with reasons
  - Clickable Mermaid flowchart of the agent tool call sequence
  - Expandable step-by-step trace timeline
  - Popup modal on node click — shows query, result, and which agent ran the step

### FR-8: Manual digest trigger

- `POST /digest/generate` starts the agent in the background immediately
- Returns 202 — the UI polls `GET /digest/current` until the new digest appears
- "Generate / Regenerate" button available on both the home page and the digest detail page

### FR-9: Configurable user interests

- `INTERESTS` env var — comma-separated list of topics the user cares about
- Default: `agentic systems, AI/ML, LLM engineering, software architecture`
- Passed to both agents' system prompts to bias theme detection, web search queries, and article scoring

### FR-10: Digest history (planned)

- `/history` page lists all past digests by week — week number, timestamp, content preview
- Clicking a past digest opens the full digest detail page for that week
- Favourited articles shown at the top of the history page

### FR-11: Favourite articles (planned)

- Star button on each article card toggles favourite status
- Favourites persist to the database (`is_favorite` column on Article)
- Favourite articles are surfaced in the history page

---

## Non-Functional Requirements

### NFR-1: Performance
- Article processing happens in a background task — the POST endpoint must return immediately (< 200ms)
- Digest generation runs in the background — the trigger endpoint returns 202 immediately
- UI polls every 3 seconds after triggering digest until new digest appears

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
- Mutating endpoints require `X-API-Key` header — includes `POST /digest/generate`
- Auth is skipped in local dev when `SECRET_KEY` is not set — no friction during development
- AI-triggering endpoints are rate-limited to prevent unexpected Anthropic/Tavily bill spikes
- Static file serving is path-traversal safe (resolved paths checked against dist root)

### NFR-6: Rate limiting
- `POST /articles` — max 20 requests/hour per IP
- `POST /articles/{id}/chat` — max 30 requests/hour per IP
- Exceeding the limit returns HTTP 429

---

## Scoring Criteria (Claude prompt)

Claude scores articles 1–10 for relevance to the user's interests (configurable via `INTERESTS` env var).

Score bands:
- **8–10**: Green — highly relevant
- **5–7**: Amber — moderately relevant
- **1–4**: Grey — low relevance

---

## Out of Scope

- Multiple users
- Email delivery of digest
- Mobile app
