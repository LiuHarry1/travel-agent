"""Chatbot API routes."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ..llm import DashScopeError
from ..models import ChatRequest
from ..utils.exceptions import format_error_message

if TYPE_CHECKING:
    from ..service.chat import ChatService
else:
    ChatService = Any

router = APIRouter()

# Global service instance (will be set by setup_chat_routes)
_chat_service: ChatService | None = None


def get_chat_service() -> ChatService:
    """Dependency to get chat service."""
    if _chat_service is None:
        raise RuntimeError("Chat service not initialized. Call setup_chat_routes first.")
    return _chat_service


def setup_chat_routes(chat_service: ChatService) -> None:
    """
    Setup chat route handlers with service dependencies.
    
    Args:
        chat_service: Chat service instance
    """
    global _chat_service
    _chat_service = chat_service


@router.post("/agent/message/stream")
def agent_message_stream(
    request: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    """Handle chat request with streaming response and tool calling events."""
    
    def generate():
        try:
            for event in chat_service.chat_stream(request):
                # Event is already a dictionary with type and data
                # Format as SSE
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"
            # Send done signal
            yield "data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n"
        except DashScopeError as exc:
            error_msg = format_error_message(exc, "Error processing request")
            error_data = json.dumps({"type": "error", "content": error_msg}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
        except Exception as exc:
            error_msg = format_error_message(exc, "An error occurred while processing your request")
            error_data = json.dumps({"type": "error", "content": error_msg}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

