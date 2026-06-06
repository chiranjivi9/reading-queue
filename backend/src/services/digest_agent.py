"""
digest_agent.py — Agentic weekly digest generator.

Claude is given three tools and decides what to call, in what order:
  1. list_articles  — read this week's saved articles
  2. web_search     — search Tavily for related context (0-3 calls)
  3. save_digest    — write the final digest and end the loop

Every reasoning step and tool call is captured in a trace list stored
alongside the digest, so the user can see exactly what the agent decided
and why. This is the "tool-use agentic loop" pattern — the simplest and
most common form of an AI agent.

Key concepts visible here:
  - Tool definitions: JSON schema describing what Claude can call
  - Agent loop: call API → check stop_reason → execute tools → repeat
  - Trace capture: reasoning text blocks + tool call summaries
  - Loop termination: save_digest signals "I'm done"
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
MAX_ITERATIONS = 10  # safety guard — prevents runaway loops
DEFAULT_INTERESTS = "agentic systems, AI/ML, LLM engineering, software architecture"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------
# These JSON schemas tell Claude what tools exist, what they do, and
# what arguments they expect. Claude decides when and how to call them.

TOOLS: list[anthropic.types.ToolParam] = [
    {
        "name": "list_articles",
        "description": (
            "Get all articles saved to the reading queue this week. "
            "Always call this first before doing anything else."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "web_search",
        "description": (
            "Search the web for context on a topic. Use when an article touches "
            "on something that deserves more background, or when you want to find "
            "related recent developments. Keep searches focused. "
            "Call this 0–3 times — only when a search would genuinely enrich the digest."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A specific, targeted search query.",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "save_digest",
        "description": (
            "Write the final weekly digest and end the loop. Call this once you "
            "have enough information. The content must be a markdown-formatted "
            "synthesised briefing — find themes, make connections, don't just list "
            "article summaries one by one. Lead with the main story of the week."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The complete markdown digest.",
                }
            },
            "required": ["content"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def _exec_list_articles(db: AsyncSession, week_number: int) -> tuple[str, dict]:
    result = await db.execute(
        select(Article).where(
            Article.week_number == week_number,
            Article.status == ArticleStatus.READY.value,
        )
    )
    articles = result.scalars().all()

    if not articles:
        text = "No articles found for this week yet."
    else:
        lines = []
        for a in articles:
            lines.append(
                f"- **{a.title}** (score {a.score}/10)\n"
                f"  URL: {a.url}\n"
                f"  Summary: {a.summary}\n"
                f"  Score reason: {a.score_reason}"
            )
        text = f"Found {len(articles)} article(s) this week:\n\n" + "\n\n".join(lines)

    trace_entry = {
        "type": "tool_call",
        "tool": "list_articles",
        "input": {},
        "summary": f"Found {len(articles)} article(s) this week",
    }
    return text, trace_entry


async def _exec_web_search(query: str) -> tuple[str, dict]:
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        text = "Web search unavailable: TAVILY_API_KEY not configured."
        summary = f"Search skipped (no API key) for '{query}'"
        return text, {"type": "tool_call", "tool": "web_search", "input": {"query": query}, "summary": summary}

    try:
        client = AsyncTavilyClient(api_key=api_key)
        response = await client.search(query, max_results=3)
        results = response.get("results", [])
        if not results:
            text = "No results found."
        else:
            items = []
            for r in results:
                snippet = (r.get("content") or "")[:300]
                items.append(f"- **{r['title']}**\n  {r['url']}\n  {snippet}")
            text = "\n\n".join(items)
        summary = f"{len(results)} result(s) for '{query}'"
    except Exception as exc:
        text = f"Search failed: {exc}"
        summary = f"Search failed for '{query}'"
        logger.warning("Tavily search error: %s", exc)

    trace_entry = {
        "type": "tool_call",
        "tool": "web_search",
        "input": {"query": query},
        "summary": summary,
    }
    return text, trace_entry


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def _system_prompt() -> str:
    interests = os.getenv("INTERESTS", "").strip() or DEFAULT_INTERESTS
    return (
        f"You are writing a weekly reading digest for someone interested in: {interests}.\n\n"
        "Your job is to synthesise — not just list. Find cross-cutting themes, "
        "surface unexpected connections, and frame the reading through the lens of "
        "the user's interests. If one article seems unrelated, find the angle that "
        "ties it to the bigger picture.\n\n"
        "Steps:\n"
        "1. Call list_articles to see what was read this week.\n"
        "2. Think about themes. If a topic deserves more context, call web_search "
        "   (0–3 times maximum — only when it would genuinely improve the digest).\n"
        "3. When you have enough, call save_digest with a polished markdown briefing.\n\n"
        "The digest should feel like a thoughtful human wrote it, not a summary bot. "
        "Lead with the main theme or story of the week, weave in the articles as "
        "evidence, and close with what's worth watching next."
    )


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

async def run_digest_agent(db: AsyncSession) -> None:
    """
    Run the agentic digest for the current ISO week.

    Skips silently if a digest already exists for the week.
    Saves both the digest content and the agent trace to the digests table.
    """
    week_number = datetime.now(timezone.utc).isocalendar().week

    existing = await db.scalar(select(Digest).where(Digest.week_number == week_number))
    if existing:
        logger.info("Digest for week %d already exists — skipping.", week_number)
        return

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    # messages accumulates the full conversation the model sees each turn.
    # We start with a single user message to kick off the agent.
    messages: list[anthropic.types.MessageParam] = [
        {"role": "user", "content": "Please generate this week's reading digest."}
    ]
    trace: list[dict] = []

    logger.info("Digest agent starting for week %d", week_number)

    for iteration in range(MAX_ITERATIONS):
        logger.debug("Agent iteration %d", iteration)

        response = await client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=_system_prompt(),
            tools=TOOLS,
            messages=messages,
        )

        # Capture any reasoning text the model emitted before/between tool calls.
        for block in response.content:
            if block.type == "text" and block.text.strip():
                trace.append({"type": "reasoning", "content": block.text.strip()})
                logger.debug("Agent: %s", block.text[:120])

        # end_turn means the model finished without calling a tool.
        # This shouldn't happen given our prompt, but handle it gracefully.
        if response.stop_reason == "end_turn":
            logger.warning("Agent finished with end_turn but never called save_digest.")
            break

        if response.stop_reason != "tool_use":
            logger.warning("Unexpected stop_reason: %s", response.stop_reason)
            break

        # Execute each tool the model requested this turn.
        tool_results: list[anthropic.types.ToolResultBlockParam] = []
        digest_content: str | None = None

        for block in response.content:
            if block.type != "tool_use":
                continue

            if block.name == "list_articles":
                result_text, trace_entry = await _exec_list_articles(db, week_number)

            elif block.name == "web_search":
                result_text, trace_entry = await _exec_web_search(block.input["query"])

            elif block.name == "save_digest":
                digest_content = block.input["content"]
                trace_entry = {
                    "type": "tool_call",
                    "tool": "save_digest",
                    "input": {},
                    "summary": "Digest written",
                }
                result_text = "Digest saved."

            else:
                result_text = f"Unknown tool: {block.name}"
                trace_entry = {
                    "type": "tool_call",
                    "tool": block.name,
                    "input": block.input,
                    "summary": "Unknown tool called",
                }

            trace.append(trace_entry)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result_text,
            })

        # Append the assistant turn and the tool results so the model has
        # the full conversation history on the next iteration.
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        # save_digest signals the agent is done — persist and exit.
        if digest_content is not None:
            digest = Digest(
                week_number=week_number,
                content=digest_content,
                trace=json.dumps(trace),
            )
            db.add(digest)
            await db.commit()
            logger.info("Digest for week %d saved (%d trace steps).", week_number, len(trace))
            return

    logger.warning("Digest agent loop exhausted without saving — week %d.", week_number)
