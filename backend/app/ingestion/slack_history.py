"""
Slack channel history ingestion — backfills all past messages from a channel.
Extracts URLs and downloads file attachments (PDFs, text files).
"""
import io
import re
import time
import requests
from sqlalchemy.orm import Session

from app.config import settings
from app.ingestion.url import ingest_url
from app.models import Item
from app.services.embeddings import chunk_text, embed_texts
from app.services.llm import generate_summary_and_tags

URL_RE = re.compile(r"https?://[^\s<>|\"']+")

# File types we can ingest
PDF_MIME = {"application/pdf"}
TEXT_MIME = {"text/plain", "text/markdown", "text/html"}
IMAGE_MIME = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
IMAGE_FILETYPES = {"png", "jpg", "jpeg", "gif", "webp"}


def _slack_get(endpoint: str, params: dict) -> dict:
    """Make an authenticated Slack API call."""
    resp = requests.get(
        f"https://slack.com/api/{endpoint}",
        headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            pages = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n\n".join(pages)
    except Exception:
        return ""


def _extract_text_from_image(content: bytes, mimetype: str, filename: str) -> str:
    """Use Claude vision to extract text and describe an image."""
    import base64
    import anthropic
    from app.config import settings

    # Map mimetype to what Claude expects
    media_map = {
        "image/png": "image/png",
        "image/jpeg": "image/jpeg",
        "image/jpg": "image/jpeg",
        "image/gif": "image/gif",
        "image/webp": "image/webp",
    }
    media_type = media_map.get(mimetype, "image/png")

    b64 = base64.standard_b64encode(content).decode("utf-8")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {"type": "base64", "media_type": media_type, "data": b64},
                        },
                        {
                            "type": "text",
                            "text": (
                                f"This image is from the Dco research Slack channel (filename: {filename}).\n"
                                "Please:\n"
                                "1. Extract ALL text visible in the image verbatim\n"
                                "2. Describe what the image shows (chart, screenshot, diagram, photo, etc.)\n"
                                "3. If it's a chart or graph, describe the key data points and trends\n"
                                "4. Summarize the key insight or information conveyed\n\n"
                                "Be thorough — this will be used for semantic search."
                            ),
                        },
                    ],
                }
            ],
        )
        return response.content[0].text
    except Exception as e:
        return ""


def _ingest_file(db: Session, file: dict) -> dict:
    """Download and ingest a Slack file attachment."""
    name = file.get("name", "Untitled")
    mimetype = file.get("mimetype", "")
    url_private = file.get("url_private_download") or file.get("url_private")
    filetype = file.get("filetype", "")
    slack_file_id = file.get("id", "")

    # Use a pseudo-URL so deduplication works
    pseudo_url = f"slack://file/{slack_file_id}"

    existing = db.query(Item).filter_by(url=pseudo_url).first()
    if existing:
        return {"status": "already_exists", "title": name}

    # Only ingest supported types
    is_pdf = mimetype in PDF_MIME or filetype == "pdf"
    is_text = mimetype in TEXT_MIME or filetype in ("text", "markdown", "md")
    is_image = mimetype in IMAGE_MIME or filetype in IMAGE_FILETYPES
    if not (is_pdf or is_text or is_image):
        return {"status": "skipped", "reason": f"unsupported type: {mimetype}"}

    if not url_private:
        return {"status": "skipped", "reason": "no download URL"}

    # Download with auth
    try:
        resp = requests.get(
            url_private,
            headers={"Authorization": f"Bearer {settings.slack_bot_token}"},
            timeout=60,
        )
        resp.raise_for_status()
        file_bytes = resp.content
    except Exception as e:
        return {"status": "failed", "reason": f"download error: {e}"}

    # Extract text
    if is_pdf:
        content = _extract_text_from_pdf(file_bytes)
    elif is_image:
        content = _extract_text_from_image(file_bytes, mimetype, name)
    else:
        try:
            content = file_bytes.decode("utf-8", errors="replace")
        except Exception:
            content = ""

    if not content or len(content.strip()) < 50:
        return {"status": "failed", "reason": "could not extract text"}

    # Generate summary/tags and store
    meta = generate_summary_and_tags(name, content)

    item = Item(
        url=pseudo_url,
        title=name,
        content=content,
        summary=meta.get("summary"),
        source="slack",
        tags=meta.get("tags", []),
        extra={"slack_file_id": slack_file_id, "original_mimetype": mimetype},
    )
    db.add(item)
    db.flush()

    chunks = chunk_text(content)
    if chunks:
        embeddings = embed_texts(chunks)
        from app.models import Embedding
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            db.add(Embedding(item_id=item.id, chunk_text=chunk, chunk_index=idx, embedding=emb))

    db.commit()
    return {"status": "ingested", "title": name}


def ingest_channel_history(db: Session, channel_id: str) -> dict:
    """
    Backfill all messages from a Slack channel.
    Extracts URLs and ingests file attachments.
    Returns a summary of what was processed.
    """
    stats = {"urls_found": 0, "urls_ingested": 0, "files_found": 0, "files_ingested": 0, "errors": []}

    cursor = None
    page = 0

    while True:
        params = {"channel": channel_id, "limit": 200}
        if cursor:
            params["cursor"] = cursor

        try:
            data = _slack_get("conversations.history", params)
        except Exception as e:
            stats["errors"].append(f"API error on page {page}: {e}")
            break

        if not data.get("ok"):
            error = data.get("error", "unknown")
            stats["errors"].append(f"Slack API error: {error}")
            break

        messages = data.get("messages", [])
        page += 1

        for msg in messages:
            # Skip bot messages (avoid re-ingesting our own confirmations)
            if msg.get("bot_id"):
                continue

            text = msg.get("text", "")

            # Extract and ingest URLs
            urls = URL_RE.findall(text)
            # Also check unfurl/attachments for URLs
            for att in msg.get("attachments", []):
                att_url = att.get("original_url") or att.get("title_link")
                if att_url:
                    urls.append(att_url)

            seen_urls = set()
            for url in urls[:5]:  # max 5 per message
                url = url.rstrip(".,;)")
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                # Skip internal Slack URLs
                if "slack.com" in url or url.startswith("slack://"):
                    continue
                stats["urls_found"] += 1
                try:
                    result = ingest_url(db, url, source="slack", extra={"slack_channel": channel_id, "backfill": True})
                    if result.get("status") == "ingested":
                        stats["urls_ingested"] += 1
                    # Rate limit courtesy pause
                    time.sleep(1)
                except Exception as e:
                    stats["errors"].append(f"URL ingest error ({url}): {e}")

            # Process file attachments
            for file in msg.get("files", []):
                stats["files_found"] += 1
                try:
                    result = _ingest_file(db, file)
                    if result.get("status") == "ingested":
                        stats["files_ingested"] += 1
                except Exception as e:
                    stats["errors"].append(f"File ingest error ({file.get('name')}): {e}")

        # Pagination
        next_cursor = data.get("response_metadata", {}).get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor

    return stats
