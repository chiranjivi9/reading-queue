"""
services/summariser.py — Article summarisation and relevance scoring.

Calls the Anthropic Claude API with extracted article content and returns
a structured summary and 1-10 relevance score as a Python dict.

Public API:
    summarise(title: str, text: str) -> dict
        Returns { "summary": str, "score": int, "score_reason": str }
        Raises SummariserError on failure.
"""

import json
import os
import re

import anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-20250514"

# Truncate article text sent to Claude to control token usage.
# Most articles are fully represented in their first 4000 chars.
MAX_TEXT_CHARS = 4000

# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class SummariserError(Exception):
    """
    Raised when summarisation fails — API error, bad JSON response, etc.
    Mirrors ExtractorError so the caller in main.py can handle both cleanly.
    """
    pass


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_instruction() -> str:
    """Return the static instruction block sent after the (cached) article content."""
    return (
        'Respond with ONLY a valid JSON object — no markdown fences, no explanation. '
        'Use this exact structure:\n'
        '{\n'
        '  "summary": "2-3 sentence summary of what the article is about and why it matters",\n'
        '  "score": <integer 1-10>,\n'
        '  "score_reason": "one sentence explaining the score"\n'
        '}\n\n'
        'Scoring rubric (1-10) based on relevance to someone interested in:\n'
        '- AI and machine learning\n'
        '- Software engineering and developer tools\n'
        '- Startups and venture capital\n'
        '- Financial markets and investing\n\n'
        '10 = directly and deeply covers one of these topics\n'
        '5  = tangentially related or useful background knowledge\n'
        '1  = unrelated (lifestyle, sports, celebrity news, etc.)'
    )


def _parse_response(raw: str) -> dict:
    """
    Parse Claude's text response into a Python dict.

    Claude occasionally wraps JSON in markdown code fences (```json ... ```)
    even when asked not to. This function strips them before parsing so the
    caller always gets a clean dict regardless of formatting quirks.

    Raises SummariserError if the response cannot be parsed or is missing fields.
    """
    # strip markdown fences if present: ```json ... ``` or ``` ... ```
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise SummariserError(f"Claude returned invalid JSON: {e}\nRaw response: {raw}") from e

    required_fields = {"summary", "score", "score_reason"}
    missing = required_fields - data.keys()
    if missing:
        raise SummariserError(f"Claude response missing fields: {missing}\nRaw response: {raw}")

    # coerce score to int in case Claude returns it as a string
    try:
        data["score"] = int(data["score"])
    except (ValueError, TypeError) as e:
        raise SummariserError(f"Score is not a valid integer: {data['score']}") from e

    if not (1 <= data["score"] <= 10):
        raise SummariserError(f"Score {data['score']} is out of range 1-10")

    return {
        "summary": str(data["summary"]),
        "score": data["score"],
        "score_reason": str(data["score_reason"]),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def summarise(title: str, text: str) -> dict:
    """
    Summarise an article and score its relevance using Claude.

    The article content is sent with cache_control: ephemeral so that if the
    same article is re-processed (e.g. after a failure), the cached text block
    is reused at ~10% of normal input token cost.

    Args:
        title: The article title (from the extractor).
        text:  The clean article body text (from the extractor).

    Returns:
        dict with keys:
            "summary"      (str): 2-3 sentence summary.
            "score"        (int): Relevance score from 1 to 10.
            "score_reason" (str): One sentence explaining the score.

    Raises:
        SummariserError: If the API call fails or the response cannot be parsed.
    """
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    truncated_text = text[:MAX_TEXT_CHARS]

    try:
        message = await client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            # The article content is the expensive part — mark it
                            # cacheable so repeat calls reuse the cached prompt.
                            "type": "text",
                            "text": (
                                "You are a reading assistant that summarises articles "
                                "and scores their relevance.\n\n"
                                f"Article title: {title}\n\n"
                                f"Article text:\n{truncated_text}"
                            ),
                            "cache_control": {"type": "ephemeral"},
                        },
                        {
                            "type": "text",
                            "text": _build_instruction(),
                        },
                    ],
                }
            ],
        )
    except anthropic.APIError as e:
        raise SummariserError(f"Anthropic API error: {e}") from e

    raw_text = message.content[0].text
    return _parse_response(raw_text)
