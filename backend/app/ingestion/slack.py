"""
Slack Events API handler — listens for messages in #research and auto-ingests URLs.
Also provides a /wiki slash command for searching from Slack.
"""
import re
from slack_bolt import App
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.ingestion.url import ingest_url

# URLs in Slack messages look like <https://...> or plain https://...
URL_RE = re.compile(r"https?://[^\s>|]+")

slack_app = App(
    token=settings.slack_bot_token,
    signing_secret=settings.slack_signing_secret,
)


@slack_app.event("message")
def handle_message(event, say, logger):
    """When a message is posted in #research, extract and ingest any URLs."""
    text = event.get("text", "")
    channel = event.get("channel_type")

    urls = URL_RE.findall(text)
    if not urls:
        return

    db: Session = SessionLocal()
    try:
        for url in urls[:3]:  # max 3 per message
            try:
                result = ingest_url(db, url, source="slack", extra={"slack_channel": event.get("channel")})
                if result.get("status") == "ingested":
                    say(
                        text=f":brain: Added to Second Brain: *{result.get('title', url)}*",
                        thread_ts=event.get("ts"),
                    )
            except Exception as e:
                logger.error(f"Failed to ingest {url}: {e}")
    finally:
        db.close()


@slack_app.command("/wiki")
def handle_wiki_command(ack, respond, command):
    """Slack slash command: /wiki <query> — search the Second Brain from Slack."""
    from app.services.knowledge import search

    ack()
    query = command.get("text", "").strip()
    if not query:
        respond("Usage: `/wiki <your search query>`")
        return

    db: Session = SessionLocal()
    try:
        results = search(db, query, limit=5)
        if not results:
            respond(f"No results found for: *{query}*")
            return

        blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": f":mag: *Results for:* {query}"}}]
        for r in results:
            title = r.get("title") or "Untitled"
            url = r.get("url") or ""
            summary = (r.get("summary") or r.get("chunk_text") or "")[:200]
            source = r.get("source") or ""
            tags = ", ".join(r.get("tags") or [])
            text = f"*<{url}|{title}>* [{source}]\n{summary}"
            if tags:
                text += f"\n_Tags: {tags}_"
            blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": text}})
            blocks.append({"type": "divider"})

        respond(blocks=blocks)
    finally:
        db.close()
