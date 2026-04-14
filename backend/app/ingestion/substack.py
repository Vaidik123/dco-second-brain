"""
Ingest articles from Dco and Token Dispatch Substack archives.
Uses the Substack archive API (paginated) to get ALL posts, not just the RSS feed.
"""
import time
import requests
from dateutil import parser as dateparser
from sqlalchemy.orm import Session

from app.models import Item, Embedding
from app.services.scraper import scrape_url
from app.services.embeddings import chunk_text, embed_texts
from app.services.llm import generate_summary_and_tags

FEEDS = {
    "substack_dco": "https://www.decentralised.co",
    "substack_td": "https://www.thetokendispatch.com",
}

BATCH_SIZE = 12   # Substack API page size
SCRAPE_DELAY = 1  # seconds between article scrapes (be polite)


def _fetch_archive_page(base_url: str, offset: int) -> list[dict]:
    """Fetch one page of posts from the Substack archive API."""
    try:
        resp = requests.get(
            f"{base_url}/api/v1/archive",
            params={"sort": "new", "limit": BATCH_SIZE, "offset": offset},
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Archive API error at offset {offset}: {e}")
        return []


def ingest_feed(db: Session, source_key: str, max_items: int = 2000) -> dict:
    """Ingest all posts from a Substack publication using the paginated archive API."""
    base_url = FEEDS[source_key]
    ingested = 0
    skipped = 0
    offset = 0

    while ingested + skipped < max_items:
        posts = _fetch_archive_page(base_url, offset)
        if not posts:
            break  # No more posts

        for post in posts:
            url = post.get("canonical_url")
            if not url:
                skipped += 1
                continue

            # Skip already ingested
            existing = db.query(Item).filter_by(url=url).first()
            if existing:
                skipped += 1
                continue

            # Scrape full content from the article page
            scraped = scrape_url(url)
            content = scraped.get("content", "")

            # Fall back to truncated_body_text from API if scrape fails
            if not content or len(content) < 100:
                content = post.get("truncated_body_text") or ""

            if not content or len(content) < 100:
                skipped += 1
                time.sleep(SCRAPE_DELAY)
                continue

            title = (
                scraped.get("title")
                or post.get("title")
                or post.get("social_title")
                or "Untitled"
            )
            author = scraped.get("author") or None

            published_at = None
            raw_date = post.get("post_date") or scraped.get("published_at")
            if raw_date:
                try:
                    published_at = dateparser.parse(str(raw_date))
                except Exception:
                    pass

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
            db.flush()

            chunks = chunk_text(content)
            if chunks:
                embeddings = embed_texts(chunks)
                for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
                    db.add(Embedding(
                        item_id=item.id,
                        chunk_text=chunk,
                        chunk_index=idx,
                        embedding=emb,
                    ))

            db.commit()
            ingested += 1
            print(f"[{source_key}] Ingested ({ingested}): {title[:60]}")
            time.sleep(SCRAPE_DELAY)

        offset += BATCH_SIZE

    return {"source": source_key, "ingested": ingested, "skipped": skipped}


def ingest_all_feeds(db: Session) -> list[dict]:
    results = []
    for key in FEEDS:
        results.append(ingest_feed(db, key))
    return results
