"""
digest_agent.py — Multi-agent weekly digest pipeline.

Two agents run in sequence:

  1. Discovery Agent
     - Reads this week's articles + user interests + past-week memory
     - Searches the web for related articles you didn't post
     - Reports its findings (ends loop by calling report_findings)

  2. Digest Agent
     - Receives your articles + discovery findings + memory
     - Optionally does extra web searches for context
     - Writes the final synthesised digest (ends loop by calling save_digest)

The orchestrator (run_digest_agent) is plain Python code — it calls each
agent in order and passes results between them. This is the most common
multi-agent pattern: code-orchestrated specialised agents.

Key concepts:
  - Tool-use agentic loop: call API → execute tools → feed results back → repeat
  - Agent handoff: output of Agent 1 becomes input to Agent 2
  - Memory: past week themes injected into both agents' system prompts
  - Trace: every reasoning step and tool call is recorded for display
"""

import json
import logging
import os
from datetime import datetime, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tavily import AsyncTavilyClient

from src.models import Article, ArticleStatus, Digest

logger = logging.getLogger(__name__)

MODEL = "claude-opus-4-7"
MAX_ITERATIONS = 10
DEFAULT_INTERESTS = "agentic systems, AI/ML, LLM engineering, software architecture"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _interests() -> str:
    return os.getenv("INTERESTS", "").strip() or DEFAULT_INTERESTS


async def _web_search(query: str) -> tuple[str, dict]:
    """Execute a Tavily search and return (result_text, trace_entry)."""
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return (
            "Web search unavailable: TAVILY_API_KEY not configured.",
            {"type": "tool_call", "tool": "web_search",
             "input": {"query": query}, "summary": "Skipped (no API key)"},
        )
    try:
        client = AsyncTavilyClient(api_key=api_key)
        response = await client.search(query, max_results=3)
        results = response.get("results", [])
        text = "\n\n".join(
            f"- **{r['title']}**\n  {r['url']}\n  {(r.get('content') or '')[:300]}"
            for r in results
        ) or "No results found."
        summary = f"{len(results)} result(s) for '{query}'"
    except Exception as exc:
        text = f"Search failed: {exc}"
        summary = f"Search failed for '{query}'"
        logger.warning("Tavily error: %s", exc)

    return text, {
        "type": "tool_call", "tool": "web_search",
        "input": {"query": query}, "summary": summary,
    }


async def _fetch_memory(db: AsyncSession, current_week: int, limit: int = 4) -> str:
    """Return a short summary of the last `limit` weeks' themes for the system prompt."""
    result = await db.execute(
        select(Digest)
        .where(Digest.week_number < current_week, Digest.themes.isnot(None))
        .order_by(Digest.week_number.desc())
        .limit(limit)
    )
    past = result.scalars().all()
    if not past:
        return "No previous weeks recorded yet."

    lines = []
    for d in reversed(past):
        themes = json.loads(d.themes or "[]")
        theme_str = ", ".join(themes) if themes else "no themes recorded"
        lines.append(f"  Week {d.week_number}: {theme_str}")
    return "Past reading patterns:\n" + "\n".join(lines)


async def _extract_and_save_themes(digest_content: str, digest: Digest) -> None:
    """
    Ask Claude to extract 2-4 theme keywords from the digest text.
    Saves them to digest.themes so next week's agents have memory.
    This is a simple single call — not an agent loop.
    """
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=128,
            messages=[{
                "role": "user",
                "content": (
                    "Extract 2–4 short theme keywords from this digest. "
                    "Respond with ONLY a JSON array of strings, e.g. "
                    '["agentic systems", "LLM fine-tuning"]\n\n'
                    f"{digest_content[:2000]}"
                ),
            }],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        themes = json.loads(raw.strip())
        digest.themes = json.dumps(themes)
        logger.info("Themes extracted: %s", themes)
    except Exception as exc:
        logger.warning("Theme extraction failed: %s", exc)


# ---------------------------------------------------------------------------
# Agent 1: Discovery
# ---------------------------------------------------------------------------

_DISCOVERY_TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "web_search",
        "description": (
            "Search the web for articles related to the user's interests and "
            "this week's reading themes. Call this 2–4 times with different "
            "queries to find a variety of relevant content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A specific search query."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "report_findings",
        "description": (
            "Submit the articles you discovered. Call this once when you have "
            "found enough interesting content (aim for 3–5 articles). "
            "Only include articles that are genuinely relevant and high quality."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "articles": {
                    "type": "array",
                    "description": "List of discovered articles.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title":   {"type": "string"},
                            "url":     {"type": "string"},
                            "snippet": {"type": "string", "description": "1-2 sentence description."},
                            "reason":  {"type": "string", "description": "Why this fits the user's interests."},
                        },
                        "required": ["title", "url", "snippet", "reason"],
                    },
                }
            },
            "required": ["articles"],
        },
    },
]


def _discovery_system(articles_text: str, memory: str) -> str:
    return (
        f"You are a research assistant finding articles for someone interested in: {_interests()}.\n\n"
        f"{memory}\n\n"
        "This week's reading queue:\n"
        f"{articles_text}\n\n"
        "Your job: search the web to find 3–5 high-quality articles the user "
        "DIDN'T post but would benefit from reading. They should complement or "
        "extend what's already in the queue.\n\n"
        "Use web_search 2–4 times with varied queries based on the themes you "
        "see in this week's articles and the user's standing interests. "
        "Then call report_findings with your best picks."
    )


async def run_discovery_agent(
    db: AsyncSession,
    articles_text: str,
    memory: str,
    trace: list,
) -> list[dict]:
    """
    Agent 1: searches the web and returns a list of suggested articles.
    Results are appended to `trace` for display in the UI.
    """
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages: list[anthropic.types.MessageParam] = [
        {"role": "user", "content": "Please find related articles for this week's reading queue."}
    ]

    trace.append({"type": "agent_start", "agent": "discovery",
                  "summary": "Discovery agent started"})

    for iteration in range(MAX_ITERATIONS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=_discovery_system(articles_text, memory),
            tools=_DISCOVERY_TOOLS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text" and block.text.strip():
                trace.append({"type": "reasoning", "agent": "discovery",
                               "content": block.text.strip()})

        if response.stop_reason == "end_turn":
            logger.warning("Discovery agent ended without report_findings.")
            return []

        tool_results = []
        findings = None

        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "web_search":
                result_text, entry = await _web_search(block.input["query"])
                entry["agent"] = "discovery"
                trace.append(entry)

            elif block.name == "report_findings":
                findings = block.input.get("articles", [])
                result_text = f"Reported {len(findings)} article(s)."
                trace.append({
                    "type": "tool_call", "agent": "discovery",
                    "tool": "report_findings",
                    "input": {},
                    "summary": f"Found {len(findings)} article(s) to suggest",
                })
            else:
                result_text = f"Unknown tool: {block.name}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        if findings is not None:
            return findings

    logger.warning("Discovery agent loop exhausted.")
    return []


# ---------------------------------------------------------------------------
# Agent 2: Digest
# ---------------------------------------------------------------------------

_DIGEST_TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "web_search",
        "description": (
            "Search the web for additional context on a specific topic. "
            "Use sparingly — only when it would meaningfully improve the digest."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_digest",
        "description": (
            "Write the final weekly digest and end the loop. "
            "Synthesise — don't list. Find the story of the week."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "The complete markdown digest."}
            },
            "required": ["content"],
        },
    },
]


def _digest_system(memory: str, suggested: list[dict]) -> str:
    suggested_text = ""
    if suggested:
        items = "\n".join(
            f"- **{a['title']}** ({a['url']})\n  {a['snippet']}\n  Why relevant: {a['reason']}"
            for a in suggested
        )
        suggested_text = f"\n\nThe Discovery agent also found these related articles:\n{items}"

    return (
        f"You are writing a weekly reading digest for someone interested in: {_interests()}.\n\n"
        f"{memory}"
        f"{suggested_text}\n\n"
        "Synthesise everything — the user's articles and the discovered ones — "
        "into a cohesive narrative. Don't just list. Find cross-cutting themes, "
        "reference past weeks where relevant, and close with what's worth watching next.\n\n"
        "Use web_search only if you need a specific piece of context you don't already have. "
        "When ready, call save_digest."
    )


async def run_digest_agent_step(
    articles_text: str,
    memory: str,
    suggested: list[dict],
    trace: list,
) -> str | None:
    """
    Agent 2: synthesises articles + discovery findings into the weekly digest.
    Returns the digest content string, or None if the loop exhausted.
    """
    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    messages: list[anthropic.types.MessageParam] = [
        {"role": "user", "content": (
            f"Here are this week's articles:\n\n{articles_text}\n\n"
            "Please write the weekly digest."
        )}
    ]

    trace.append({"type": "agent_start", "agent": "digest",
                  "summary": "Digest agent started"})

    for iteration in range(MAX_ITERATIONS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_digest_system(memory, suggested),
            tools=_DIGEST_TOOLS,
            messages=messages,
        )

        for block in response.content:
            if block.type == "text" and block.text.strip():
                trace.append({"type": "reasoning", "agent": "digest",
                               "content": block.text.strip()})

        if response.stop_reason == "end_turn":
            logger.warning("Digest agent ended without save_digest.")
            return None

        tool_results = []
        digest_content = None

        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "web_search":
                result_text, entry = await _web_search(block.input["query"])
                entry["agent"] = "digest"
                trace.append(entry)

            elif block.name == "save_digest":
                digest_content = block.input["content"]
                result_text = "Digest saved."
                trace.append({
                    "type": "tool_call", "agent": "digest",
                    "tool": "save_digest", "input": {}, "summary": "Digest written",
                })
            else:
                result_text = f"Unknown tool: {block.name}"

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        if digest_content is not None:
            return digest_content

    return None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_digest_agent(db: AsyncSession) -> None:
    """
    Orchestrate the multi-agent digest pipeline for the current week.

    1. Fetch articles + memory
    2. Run Discovery Agent → suggested articles
    3. Run Digest Agent   → final digest content
    4. Save digest + trace + themes + suggested articles
    """
    week_number = datetime.now(timezone.utc).isocalendar().week

    existing = await db.scalar(select(Digest).where(Digest.week_number == week_number))
    if existing:
        logger.info("Digest for week %d already exists — skipping.", week_number)
        return

    # --- Fetch this week's articles ---
    result = await db.execute(
        select(Article).where(
            Article.week_number == week_number,
            Article.status == ArticleStatus.READY.value,
        )
    )
    articles = result.scalars().all()

    if not articles:
        logger.info("No ready articles for week %d — skipping digest.", week_number)
        return

    articles_text = "\n\n".join(
        f"- **{a.title}** (score {a.score}/10)\n"
        f"  URL: {a.url}\n"
        f"  Summary: {a.summary}\n"
        f"  Score reason: {a.score_reason}"
        for a in articles
    )

    # --- Load memory ---
    memory = await _fetch_memory(db, week_number)
    logger.info("Memory: %s", memory[:100])

    trace: list[dict] = []

    # --- Agent 1: Discovery ---
    logger.info("Starting Discovery agent for week %d", week_number)
    suggested = await run_discovery_agent(db, articles_text, memory, trace)
    logger.info("Discovery found %d suggested article(s).", len(suggested))

    # --- Agent 2: Digest ---
    logger.info("Starting Digest agent for week %d", week_number)
    digest_content = await run_digest_agent_step(articles_text, memory, suggested, trace)

    if not digest_content:
        logger.warning("Digest agent produced no content for week %d.", week_number)
        return

    # --- Save everything ---
    digest = Digest(
        week_number=week_number,
        content=digest_content,
        trace=json.dumps(trace),
        suggested_articles=json.dumps(suggested),
    )
    db.add(digest)
    await db.commit()

    await _extract_and_save_themes(digest_content, digest)
    await db.commit()

    logger.info(
        "Week %d digest saved — %d trace steps, %d suggested articles.",
        week_number, len(trace), len(suggested),
    )
