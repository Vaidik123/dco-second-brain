import anthropic
from app.config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are the Dco Second Brain — a knowledge assistant for the Dco team.
You have access to a curated corpus of research articles, Dco's own writing (Decentralised.co substack),
Token Dispatch articles, and links shared in Dco's Slack #research channel.

When answering:
- Ground every claim in the retrieved sources. Cite them inline as [Source: title].
- If you're not sure, say so — don't hallucinate.
- Be concise but thorough. Lead with the key insight.
- When relevant, connect ideas across sources.
"""


def chat(messages: list[dict], context_chunks: list[dict]) -> str:
    """Non-streaming chat with retrieved context injected."""
    context_text = _format_context(context_chunks)

    system = SYSTEM_PROMPT
    if context_text:
        system += f"\n\n## Relevant Knowledge Base Excerpts\n{context_text}"

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system,
        messages=messages,
    )
    return response.content[0].text


def stream_chat(messages: list[dict], context_chunks: list[dict]):
    """Streaming chat — yields text chunks."""
    context_text = _format_context(context_chunks)
    system = SYSTEM_PROMPT
    if context_text:
        system += f"\n\n## Relevant Knowledge Base Excerpts\n{context_text}"

    with _client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system,
        messages=messages,
    ) as stream:
        for text in stream.text_stream:
            yield text


def analyze_article(article_text: str, context_chunks: list[dict]) -> str:
    """Given a draft article + relevant research, return structured suggestions."""
    context_text = _format_context(context_chunks)

    prompt = f"""You are reviewing a draft article for the Dco team.
Below is the draft and relevant research from our knowledge base.

## Draft Article
{article_text[:8000]}

## Relevant Knowledge Base Research
{context_text}

Provide a structured analysis:

### 1. Key Research to Include
For each relevant source, explain:
- What specific insight/data point from it to use
- Exactly WHERE in the article to include it (which section/paragraph)
- HOW to frame it (quote, paraphrase, supporting data, counterpoint, etc.)

### 2. Missing Perspectives
What important angles does the research cover that the draft doesn't address?

### 3. Potential Contradictions
Any sources that present a different view from what the draft argues?

### 4. Suggested Citations
Format any key stats or claims as proper inline citations.

Be specific and actionable."""

    response = _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def generate_summary_and_tags(title: str, content: str) -> dict:
    """Auto-generate a summary and topic tags for a new item."""
    response = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=500,
        messages=[
            {
                "role": "user",
                "content": f"""Summarize this article in 2-3 sentences and generate 3-6 topic tags.
Title: {title or 'Untitled'}
Content (first 3000 chars): {content[:3000]}

Reply in this exact JSON format:
{{"summary": "...", "tags": ["tag1", "tag2", "tag3"]}}""",
            }
        ],
    )
    import json
    try:
        text = response.content[0].text
        # Extract JSON if wrapped in markdown code block
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text.strip())
    except Exception:
        return {"summary": content[:200], "tags": []}


def _format_context(chunks: list[dict]) -> str:
    if not chunks:
        return ""
    parts = []
    for i, c in enumerate(chunks[:8], 1):
        title = c.get("title") or "Untitled"
        url = c.get("url") or ""
        source = c.get("source") or ""
        chunk_text = c.get("chunk_text") or c.get("summary") or ""
        parts.append(f"[{i}] **{title}** ({source})\nURL: {url}\n{chunk_text[:600]}")
    return "\n\n---\n\n".join(parts)
