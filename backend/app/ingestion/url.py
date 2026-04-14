"""
Ingest any single URL into the knowledge base.
Used by Slack handler, manual API endpoint, and article ingestion.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Item, Embedding
from app.services.scraper import scrape_url
from app.services.embeddings import chunk_text, embed_texts
from app.services.llm import generate_summary_and_tags
from app.services.knowledge import boost_confidence


def ingest_url(db: Session, url: str, source: str = "manual", extra: dict | None = None) -> dict:
    # Check if already exists
    existing = db.query(Item).filter_by(url=url).first()
    if existing:
        # Boost confidence score since it's being referenced again
        boost_confidence(db, url)
        return {"status": "already_exists", "id": str(existing.id), "title": existing.title}

    scraped = scrape_url(url)
    content = scraped.get("content", "")
    if not content or len(content) < 50:
        return {"status": "failed", "reason": "Could not extract content", "url": url}

    title = scraped.get("title") or "Untitled"

    # Parse published date if returned as string
    published_at = None
    raw_date = scraped.get("published_at")
    if raw_date:
        try:
            from dateutil import parser as dateparser
            published_at = dateparser.parse(str(raw_date))
        except Exception:
            pass

    meta = generate_summary_and_tags(title, content)

    item = Item(
        url=url,
        title=title,
        content=content,
        summary=meta.get("summary"),
        source=source,
        author=scraped.get("author"),
        published_at=published_at,
        tags=meta.get("tags", []),
        extra=extra or {},
    )
    db.add(item)
    db.flush()

    chunks = chunk_text(content)
    if chunks:
        embeddings = embed_texts(chunks)
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            db.add(Embedding(item_id=item.id, chunk_text=chunk, chunk_index=idx, embedding=emb))

    db.commit()
    return {"status": "ingested", "id": str(item.id), "title": title, "tags": meta.get("tags", [])}
