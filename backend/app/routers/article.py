from fastapi import APIRouter, Depends, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.knowledge import search
from app.services.llm import analyze_article

router = APIRouter()


class ArticleTextRequest(BaseModel):
    text: str
    topic_hint: str | None = None  # optional extra context for search


@router.post("/article/analyze")
def analyze_article_text(req: ArticleTextRequest, db: Session = Depends(get_db)):
    """
    Given a draft article as text, find relevant research from the knowledge base
    and return structured suggestions for how to use each source.
    """
    search_query = req.topic_hint or req.text[:500]
    context = search(db, search_query, limit=12)

    # Also do a second search pass on key phrases in the article
    # Extract first few sentences as additional query
    sentences = req.text.split(". ")[:3]
    second_query = ". ".join(sentences)
    if second_query != search_query:
        extra_context = search(db, second_query, limit=6)
        # Merge, deduplicating by id
        seen_ids = {c["id"] for c in context}
        for c in extra_context:
            if c["id"] not in seen_ids:
                context.append(c)
                seen_ids.add(c["id"])

    analysis = analyze_article(req.text, context[:12])

    return {
        "analysis": analysis,
        "sources_used": [
            {
                "id": c["id"],
                "title": c.get("title"),
                "url": c.get("url"),
                "source": c.get("source"),
                "tags": c.get("tags"),
                "relevance_score": c.get("relevance_score"),
            }
            for c in context[:12]
        ],
    }


@router.post("/article/upload")
async def upload_article_file(
    file: UploadFile = File(...),
    topic_hint: str = Form(""),
    db: Session = Depends(get_db),
):
    """Upload a .txt or .md file and analyze it against the knowledge base."""
    content = await file.read()
    text = content.decode("utf-8", errors="ignore")

    req = ArticleTextRequest(text=text, topic_hint=topic_hint or None)
    return analyze_article_text(req, db)
