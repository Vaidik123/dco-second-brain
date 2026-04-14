"""
Slack Events API handler — listens for messages in #research and auto-ingests URLs,
PDFs, and images. Also provides a /wiki slash command for searching from Slack.
"""
import re
from slack_bolt import App
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.ingestion.url import ingest_url
from app.ingestion.slack_history import _ingest_file

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


@slack_app.event("file_shared")
def handle_file_shared(event, client, logger):
    """When a file is uploaded to #research, ingest it (PDF, image, text)."""
    file_id = event.get("file_id") or event.get("file", {}).get("id")
    channel_id = event.get("channel_id")
    if not file_id:
        return

    try:
        # Fetch full file metadata
        file_info = client.files_info(file=file_id)
        file = file_info.get("file", {})
    except Exception as e:
        logger.error(f"Could not fetch file info for {file_id}: {e}")
        return

    db: Session = SessionLocal()
    try:
        result = _ingest_file(db, file)
        status = result.get("status")
        title = result.get("title", file.get("name", "file"))
        if status == "ingested" and channel_id:
            client.chat_postMessage(
                channel=channel_id,
                text=f":brain: Added to Second Brain: *{title}*",
            )
        elif status == "skipped":
            logger.info(f"Skipped file {title}: {result.get('reason')}")
    except Exception as e:
        logger.error(f"Failed to ingest file {file_id}: {e}")
    finally:
        db.close()


def _answer_query(query: str, db: Session) -> str:
    """Search the knowledge base and generate a natural language answer via Claude."""
    from app.services.knowledge import search
    from app.services.llm import chat

    results = search(db, query, limit=6)
    answer = chat(
        messages=[{"role": "user", "content": query}],
        context_chunks=results,
    )
    return answer, results


@slack_app.event("app_mention")
def handle_mention(event, say, logger):
    """Respond to @dco_wiki mentions with a knowledge base answer."""
    from app.services.embeddings import embed_query  # ensure model loaded

    text = event.get("text", "")
    # Strip the @mention prefix (e.g. <@U0ATKAAKBA4> hello)
    query = re.sub(r"<@[^>]+>\s*", "", text).strip()

    if not query:
        say(
            text=":brain: Hi! Ask me anything — e.g. `@dco_wiki what is DeFi?` or use `/wiki <question>` anytime.",
            thread_ts=event.get("ts"),
        )
        return

    # Typing indicator feel — post a placeholder then update
    db: Session = SessionLocal()
    try:
        answer, results = _answer_query(query, db)

        # Build sources footer
        seen = set()
        sources = []
        for r in results[:3]:
            url = r.get("url") or ""
            title = r.get("title") or "Untitled"
            if url and url not in seen and not url.startswith("slack://"):
                seen.add(url)
                sources.append(f"<{url}|{title}>")

        source_line = "\n\n:link: *Sources:* " + " · ".join(sources) if sources else ""

        say(
            text=f":brain: {answer}{source_line}",
            thread_ts=event.get("ts"),
        )
    except Exception as e:
        logger.error(f"Error answering mention: {e}")
        say(
            text=":warning: Something went wrong. Try again in a moment.",
            thread_ts=event.get("ts"),
        )
    finally:
        db.close()


@slack_app.command("/wiki")
def handle_wiki_command(ack, respond, command):
    """Slack slash command: /wiki <query> — search the Second Brain from Slack."""
    ack()
    query = command.get("text", "").strip()
    if not query:
        respond("Usage: `/wiki <your search query>`")
        return

    db: Session = SessionLocal()
    try:
        answer, results = _answer_query(query, db)

        blocks = [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":mag: *{query}*"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": answer}},
            {"type": "divider"},
        ]

        seen = set()
        for r in results[:4]:
            url = r.get("url") or ""
            title = r.get("title") or "Untitled"
            summary = (r.get("summary") or r.get("chunk_text") or "")[:150]
            source = r.get("source") or ""
            if url in seen or url.startswith("slack://"):
                continue
            seen.add(url)
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*<{url}|{title}>* [{source}]\n{summary}"},
            })

        respond(blocks=blocks)
    except Exception as e:
        respond(f":warning: Error: {e}")
    finally:
        db.close()
