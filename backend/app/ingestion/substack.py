"""
Ingest articles from Dco and Token Dispatch Substack RSS feeds.
Can be run as a standalone script or triggered via API.
"""
import feedparser
from datetime import datetime
from dateutil import parser as dateparser
from sqlalchemy.orm import Session

from app.models import Item, Embedding
from app.services.scraper import scrape_url
from app.services.embeddings import chunk_text, embed_texts
from app.services.llm import generate_summary_and_tags

FEEDS = {
    "substack_dco": "https://www.decentralised.co/feed",
    "substack_td": "https://www.thetokendispatch.com/feed",
}


def ingest_feed(db: Session, source_key: str, max_items: int = 50) -> dict:
    feed_url = FEEDS[source_key]
    feed = feedparser.parse(feed_url)
    ingested = 0
    skipped = 0

    for entry in feed.entries[:max_items]:
        url = entry.get("link")
        if not url:
            continue

        # Skip if already exists
        existing = db.query(Item).filter_by(url=url).first()
        if existing:
            skipped += 1
            continue

        # Scrape full content
        scraped = scrape_url(url)
        content = scraped.get("content", "")
        if not content or len(content) < 100:
            skipped += 1
            continue

        title = scraped.get("title") or entry.get("title") or "Untitled"
        author = scraped.get("author") or entry.get("author") or None

        published_at = None
        if entry.get("published"):
            try:
                published_at = dateparser.parse(entry["published"])
            except Exception:
                pass

        # Generate summary + tags using Claude Haiku (cheap)
        meta = generate_summary_and_tags(title, content)

        item = Item(
            url=url,
            title=title,
            content=content,
            summary=meta.get("summary"),
            source=source_key,
            author=author,
            published_at=published_at,
            tags=meta.get("tags", []),
        )
        db.add(item)
        db.flush()  # Get the ID

        # Chunk + embed
        chunks = chunk_text(content)
        embeddings = embed_texts(chunks)
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            db.add(Embedding(item_id=item.id, chunk_text=chunk, chunk_index=idx, embedding=emb))

        db.commit()
        ingested += 1

    return {"source": source_key, "ingested": ingested, "skipped": skipped}


def ingest_all_feeds(db: Session) -> list[dict]:
    results = []
    for key in FEEDS:
        results.append(ingest_feed(db, key))
    return results
