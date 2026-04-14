from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.ingestion.url import ingest_url
from app.ingestion.substack import ingest_all_feeds, ingest_feed
from app.ingestion.twitter import ingest_tweets

router = APIRouter()


class IngestURLRequest(BaseModel):
    url: str
    source: str = "manual"


@router.post("/ingest/url")
def ingest_single_url(req: IngestURLRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Manually ingest any URL into the knowledge base."""
    result = ingest_url(db, req.url, source=req.source)
    return result


@router.post("/ingest/substack")
def trigger_substack(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger ingestion of all Substack feeds (runs in background)."""
    def run():
        ingest_all_feeds(db)

    background_tasks.add_task(run)
    return {"status": "started", "message": "Substack ingestion running in background"}


@router.post("/ingest/substack/{source}")
def trigger_substack_source(source: str, db: Session = Depends(get_db)):
    if source not in ("substack_dco", "substack_td"):
        raise HTTPException(400, "source must be substack_dco or substack_td")
    result = ingest_feed(db, source)
    return result


@router.post("/ingest/twitter")
def trigger_twitter(db: Session = Depends(get_db)):
    result = ingest_tweets(db)
    return result


@router.post("/ingest/slack-event")
async def slack_event(request_data: dict):
    """Slack Events API webhook endpoint."""
    # Handle URL verification challenge
    if request_data.get("type") == "url_verification":
        return {"challenge": request_data.get("challenge")}

    from app.config import settings
    from slack_bolt.adapter.fastapi import SlackRequestHandler
    from app.ingestion.slack import slack_app

    handler = SlackRequestHandler(slack_app)
    # The actual processing happens via slack_bolt's handler
    return {"ok": True}
