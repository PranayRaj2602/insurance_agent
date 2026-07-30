import json
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from src.tools.document_store import DocumentStore
from src.agents.chat import ChatAgent

router = APIRouter()
_store = DocumentStore()
_summaries_cache: dict = {}
_chat_agent = ChatAgent(_store, _summaries_cache)


class ChatRequest(BaseModel):
    message: str
    history: list = []
    claim_id: Optional[str] = None


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    """Stream chat response as SSE."""
    def generate():
        for chunk in _chat_agent.stream_response(
            req.message, req.history, req.claim_id
        ):
            yield f"data: {json.dumps({'text': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
