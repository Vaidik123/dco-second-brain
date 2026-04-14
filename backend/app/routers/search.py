from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.database import get_db
from app.models import Item
from app.services.knowledge import search as hybrid_search

router = APIRouter()


@router.get("/search")
def search_endpoint(
    q: str = Query(..., description="Search query"),
    source: str | None = Query(None),
    limit: int = Query(10, le=50),
    db: Session = Depends(get_db),
):
    import traceback
    from fastapi import HTTPException
    try:
        results = hybrid_search(db, q, limit=limit, source_filter=source)
        return {"query": q, "results": results, "count": len(results)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}")


@router.get("/items")
def list_items(
    source: str | None = Query(None),
    tag: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db),
):
    q = db.query(Item)
    if source:
        q = q.filter(Item.source == source)
    if tag:
        q = q.filter(Item.tags.contains([tag]))
    total = q.count()
    items = q.order_by(Item.ingested_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": str(i.id),
                "title": i.title,
                "url": i.url,
                "source": i.source,
                "author": i.author,
                "summary": i.summary,
                "tags": i.tags or [],
                "published_at": str(i.published_at) if i.published_at else None,
                "ingested_at": str(i.ingested_at),
                "confidence_score": i.confidence_score,
                "access_count": i.access_count,
            }
            for i in items
        ],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/items/{item_id}")
def get_item(item_id: str, db: Session = Depends(get_db)):
    item = db.query(Item).filter_by(id=item_id).first()
    if not item:
        from fastapi import HTTPException
        raise HTTPException(404, "Item not found")
    return {
        "id": str(item.id),
        "title": item.title,
        "url": item.url,
        "source": item.source,
        "author": item.author,
        "content": item.content,
        "summary": item.summary,
        "tags": item.tags or [],
        "published_at": str(item.published_at) if item.published_at else None,
        "ingested_at": str(item.ingested_at),
        "confidence_score": item.confidence_score,
        "access_count": item.access_count,
    }


@router.get("/tags")
def get_all_tags(db: Session = Depends(get_db)):
    rows = db.execute(text("SELECT UNNEST(tags) AS tag, COUNT(*) AS count FROM items GROUP BY tag ORDER BY count DESC")).fetchall()
    return [{"tag": r.tag, "count": r.count} for r in rows]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total = db.query(Item).count()
    by_source = db.execute(text("SELECT source, COUNT(*) as count FROM items GROUP BY source")).fetchall()
    return {
        "total_items": total,
        "by_source": {r.source: r.count for r in by_source},
    }
