"""
schemas.py — Pydantic models for API request and response validation.

Pydantic is FastAPI's validation layer. Every route that receives a request
body or returns JSON uses one of these schemas. FastAPI automatically:
  - Parses and validates incoming JSON against the schema
  - Returns HTTP 422 if validation fails (e.g. bad URL, missing field)
  - Serialises Python objects to JSON on the way out

Keeping schemas in their own file prevents main.py from growing too large.
"""

from datetime import datetime
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Request schemas  (what the client sends to us)
# ---------------------------------------------------------------------------

class ArticleCreate(BaseModel):
    """
    Body for POST /articles.

    AnyHttpUrl validates that the value is a properly formatted http/https URL.
    FastAPI returns 422 automatically if the value fails validation.
    """
    url: AnyHttpUrl


# ---------------------------------------------------------------------------
# Response schemas  (what we send back to the client)
# ---------------------------------------------------------------------------

class ArticleBasicResponse(BaseModel):
    """
    Returned immediately by POST /articles.

    Intentionally minimal — the article has only just been inserted.
    Full details (title, summary, score) arrive later via GET /articles
    once the background task completes.
    """
    model_config = ConfigDict(from_attributes=True)
    # from_attributes=True tells Pydantic to read values from SQLAlchemy
    # ORM object attributes, not just plain dicts. Required whenever we
    # pass a model instance directly to a response schema.

    id: int
    url: str
    status: str


class ArticleResponse(BaseModel):
    """
    One article as returned by GET /articles (list view).
    Excludes full_text to keep list responses lightweight.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: Optional[str]
    summary: Optional[str]
    score: Optional[int]
    score_reason: Optional[str]
    status: str
    created_at: Optional[datetime]
    week_number: int


class ArticleDetailResponse(ArticleResponse):
    """
    Single article as returned by GET /articles/{id}.
    Extends ArticleResponse with the full extracted text.
    """
    full_text: Optional[str]


class DigestResponse(BaseModel):
    """Returned by GET /digest/current."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    week_number: int
    content: str
    trace: Optional[list] = None
    created_at: Optional[datetime]

    @field_validator("trace", mode="before")
    @classmethod
    def _parse_trace(cls, v):
        """Deserialise the JSON string stored in the DB into a Python list."""
        if isinstance(v, str):
            try:
                return __import__("json").loads(v)
            except (ValueError, TypeError):
                return []
        return v or []


# ---------------------------------------------------------------------------
# Chat schemas  (POST /articles/{id}/chat)
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """One message in a conversation — either user or assistant."""
    role: str     # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """
    Body for POST /articles/{id}/chat.

    The frontend sends the full conversation history so Claude has context
    for follow-up questions. The article text is supplied by the backend
    (from the DB) and cached in the system prompt — not sent by the client.
    """
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    """Single reply returned by POST /articles/{id}/chat."""
    reply: str
