# Functional Specification — Reading Queue

## Overview

A personal reading-queue web app. The user pastes article URLs during the week; the app extracts, summarises, and scores each article. On Fridays, a ranked digest is generated.

## Users

Single-user personal tool. No authentication required.

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

### FR-6: Chat with an article

- On the detail page, the user can ask questions about the article
- Questions are answered by Claude using the article's full text as context
- `POST /articles/{id}/chat` accepts a list of messages (conversation history) and returns the assistant reply
- Prompt caching is used so the article text is only billed once per cache window — subsequent questions in the same conversation are cheaper

### FR-4: Delete an article

- Hard delete — removed from database permanently

### FR-5: Weekly digest

- Every Friday at 6pm, a digest is generated (stubbed for now — logs a message)
- Digest is stored in the `digests` table for the current week
- GET /digest/current returns this week's digest or null

---

## Non-Functional Requirements

### NFR-1: Performance
- Article processing happens in a background task — the POST endpoint must return immediately (< 200ms)

### NFR-2: Reliability
- If extraction or summarisation fails, article status is set to `failed` (visible in UI)
- Errors are logged

### NFR-3: Portability
- Database schema must be compatible with Postgres for future migration
- App must run locally with SQLite and in Docker

### NFR-4: Simplicity
- React + Vite for frontend (component model, no complex state management)
- No authentication
- No separate worker process — background tasks run inside FastAPI

---

## Scoring Criteria (Claude prompt)

Claude scores articles 1–10 for relevance to someone interested in:
- AI and machine learning
- Software engineering
- Startups
- Financial markets

Score bands:
- **8–10**: Green — highly relevant
- **5–7**: Amber — moderately relevant
- **1–4**: Grey — low relevance

---

### NFR-5: Security (planned — Steps 9 & 10)
- All endpoints that trigger AI calls (`POST /articles`, `POST /articles/{id}/chat`) must be rate-limited to prevent unexpected API cost spikes
- The app must require authentication before any data can be read or written
- Authentication approach: either HTTP Basic Auth at the Caddy proxy level (requires Docker deployment), or an API key header validated by a FastAPI dependency

### NFR-6: Rate limiting (planned — Step 9)
- `POST /articles` — max 20 requests/hour per IP
- `POST /articles/{id}/chat` — max 30 requests/hour per IP
- Exceeding the limit returns HTTP 429 with a clear error message

---

## Out of Scope

- User accounts / authentication
- Multiple users
- Email delivery of digest
- Mobile app
- Article archiving beyond current week display
