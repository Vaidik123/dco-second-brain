from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slack_bolt.adapter.fastapi import SlackRequestHandler

from app.config import settings
from app.database import init_db
from app.routers import chat, ingest, search, article

app = FastAPI(title="Dco Second Brain API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router, prefix="/api")
app.include_router(ingest.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(article.router, prefix="/api")


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


# Slack Events API — mount at /slack/events
if settings.slack_bot_token and settings.slack_signing_secret:
    from app.ingestion.slack import slack_app

    slack_handler = SlackRequestHandler(slack_app)

    @app.post("/slack/events")
    async def slack_events(req: Request):
        return await slack_handler.handle(req)
