"""
Hybrid search: vector similarity (pgvector) + BM25 keyword, fused via Reciprocal Rank Fusion.
Inspired by LLM Wiki v2 weighted knowledge architecture.
"""
from __future__ import annotations
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text, func
from rank_bm25 import BM25Okapi

from app.models import Item, Embedding
from app.services.embeddings import embed_query


def search(db: Session, query: str, limit: int = 8, source_filter: str | None = None) -> list[dict]:
    query_vec = embed_query(query)

    # --- Vector search ---
    vec_str = "[" + ",".join(str(v) for v in query_vec) + "]"
    source_clause = "AND i.source = :source" if source_filter else ""
    vector_sql = text(f"""
        SELECT i.id, i.title, i.url, i.source, i.author, i.summary, i.tags,
               i.published_at, i.confidence_score, i.access_count,
               e.chunk_text,
               1 - (e.embedding <=> CAST(:vec AS vector)) AS similarity
        FROM embeddings e
        JOIN items i ON e.item_id = i.id
        WHERE 1=1 {source_clause}
        ORDER BY e.embedding <=> CAST(:vec AS vector)
        LIMIT :limit
    """)
    params = {"vec": vec_str, "limit": limit * 3}
    if source_filter:
        params["source"] = source_filter
    vec_results = db.execute(vector_sql, params).fetchall()

    # --- BM25 keyword search ---
    all_items = db.query(Item).all()
    corpus = [((i.title or "") + " " + (i.summary or "") + " " + i.content[:2000]).split() for i in all_items]
    if corpus:
        bm25 = BM25Okapi(corpus)
        scores = bm25.get_scores(query.split())
        bm25_ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[: limit * 3]
        bm25_item_ids = {str(all_items[i].id): rank for rank, (i, _) in enumerate(bm25_ranked)}
    else:
        bm25_item_ids = {}

    # --- Reciprocal Rank Fusion ---
    vec_item_ids = {str(r.id): rank for rank, r in enumerate(vec_results)}
    all_ids = set(vec_item_ids) | set(bm25_item_ids)

    K = 60
    rrf_scores: dict[str, float] = {}
    for item_id in all_ids:
        vec_rank = vec_item_ids.get(item_id, len(vec_item_ids) + 100)
        bm25_rank = bm25_item_ids.get(item_id, len(bm25_item_ids) + 100)
        rrf_scores[item_id] = 1 / (K + vec_rank) + 1 / (K + bm25_rank)

    top_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)[:limit]

    # --- Assemble results ---
    results = []
    vec_map = {str(r.id): r for r in vec_results}
    item_map = {str(i.id): i for i in all_items}

    for item_id in top_ids:
        if item_id in vec_map:
            r = vec_map[item_id]
            results.append({
                "id": item_id,
                "title": r.title,
                "url": r.url,
                "source": r.source,
                "author": r.author,
                "summary": r.summary,
                "tags": r.tags,
                "published_at": str(r.published_at) if r.published_at else None,
                "confidence_score": r.confidence_score,
                "chunk_text": r.chunk_text,
                "relevance_score": rrf_scores[item_id],
            })
        elif item_id in item_map:
            i = item_map[item_id]
            results.append({
                "id": item_id,
                "title": i.title,
                "url": i.url,
                "source": i.source,
                "author": i.author,
                "summary": i.summary,
                "tags": i.tags or [],
                "published_at": str(i.published_at) if i.published_at else None,
                "confidence_score": i.confidence_score,
                "chunk_text": (i.summary or i.content[:500]),
                "relevance_score": rrf_scores[item_id],
            })

    # Bump access counts
    ids_to_update = [uuid.UUID(r["id"]) for r in results]
    if ids_to_update:
        db.execute(
            text("UPDATE items SET access_count = access_count + 1, last_accessed = NOW() WHERE id = ANY(:ids)"),
            {"ids": ids_to_update},
        )
        db.commit()

    return results


def boost_confidence(db: Session, url: str):
    """When a URL is referenced multiple times, boost its confidence score."""
    db.execute(
        text("UPDATE items SET confidence_score = LEAST(confidence_score + 0.1, 2.0) WHERE url = :url"),
        {"url": url},
    )
    db.commit()
