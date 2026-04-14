"""
Ingest tweets and threads from @Decentralisedco via Twitter API v2.
Requires TWITTER_BEARER_TOKEN in .env.
"""
import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Item, Embedding
from app.services.embeddings import chunk_text, embed_texts
from app.services.llm import generate_summary_and_tags

TWITTER_USER_ID = None  # Resolved on first call
TWITTER_HANDLE = "Decentralisedco"
API_BASE = "https://api.twitter.com/2"


def _headers():
    return {"Authorization": f"Bearer {settings.twitter_bearer_token}"}


def _get_user_id() -> str | None:
    global TWITTER_USER_ID
    if TWITTER_USER_ID:
        return TWITTER_USER_ID
    if not settings.twitter_bearer_token:
        return None
    resp = httpx.get(f"{API_BASE}/users/by/username/{TWITTER_HANDLE}", headers=_headers())
    if resp.status_code == 200:
        TWITTER_USER_ID = resp.json()["data"]["id"]
        return TWITTER_USER_ID
    return None


def ingest_tweets(db: Session, max_results: int = 100) -> dict:
    if not settings.twitter_bearer_token:
        return {"status": "skipped", "reason": "No TWITTER_BEARER_TOKEN configured"}

    user_id = _get_user_id()
    if not user_id:
        return {"status": "failed", "reason": "Could not resolve Twitter user ID"}

    params = {
        "max_results": min(max_results, 100),
        "tweet.fields": "created_at,author_id,conversation_id,text",
        "exclude": "retweets,replies",
    }
    resp = httpx.get(f"{API_BASE}/users/{user_id}/tweets", headers=_headers(), params=params)
    if resp.status_code != 200:
        return {"status": "failed", "reason": resp.text}

    tweets = resp.json().get("data", [])
    ingested = 0
    skipped = 0

    for tweet in tweets:
        tweet_id = tweet["id"]
        url = f"https://twitter.com/{TWITTER_HANDLE}/status/{tweet_id}"

        existing = db.query(Item).filter_by(url=url).first()
        if existing:
            skipped += 1
            continue

        content = tweet["text"]
        if len(content) < 30:
            skipped += 1
            continue

        meta = generate_summary_and_tags(f"Tweet by @{TWITTER_HANDLE}", content)

        item = Item(
            url=url,
            title=f"Tweet: {content[:80]}...",
            content=content,
            summary=meta.get("summary"),
            source="twitter",
            author=TWITTER_HANDLE,
            tags=meta.get("tags", []),
        )
        db.add(item)
        db.flush()

        chunks = chunk_text(content)
        embeddings = embed_texts(chunks)
        for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            db.add(Embedding(item_id=item.id, chunk_text=chunk, chunk_index=idx, embedding=emb))

        db.commit()
        ingested += 1

    return {"source": "twitter", "ingested": ingested, "skipped": skipped}
