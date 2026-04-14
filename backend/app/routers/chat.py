from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.knowledge import search
from app.services.llm import stream_chat

router = APIRouter()


class Message(BaseModel):
    role: str  # user | assistant
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    source_filter: str | None = None  # optionally restrict to one source
    model: str = "claude-haiku-4-5-20251001"


@router.post("/chat")
def chat_endpoint(req: ChatRequest, db: Session = Depends(get_db)):
    """Streaming chat with the Second Brain."""
    # Use the last user message as the search query
    last_user = next((m for m in reversed(req.messages) if m.role == "user"), None)
    query = last_user.content if last_user else ""

    context = search(db, query, limit=8, source_filter=req.source_filter) if query else []

    messages = [{"role": m.role, "content": m.content} for m in req.messages]

    def generate():
        for chunk in stream_chat(messages, context, model=req.model):
            yield f"data: {chunk}\n\n"
        # Send sources at the end as a special event
        import json
        sources = [
            {"id": c["id"], "title": c.get("title"), "url": c.get("url"), "source": c.get("source")}
            for c in context
        ]
        yield f"event: sources\ndata: {json.dumps(sources)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
