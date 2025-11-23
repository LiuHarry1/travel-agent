"""Chatbot API routes."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..llm import LLMError
from ..models import ChatRequest
from ..utils.exceptions import format_error_message
from .dependencies import get_chat_service

router = APIRouter()


@router.post("/agent/message/stream")
async def agent_message_stream(
    request: ChatRequest,
    chat_service = Depends(get_chat_service),
) -> StreamingResponse:
    """Handle chat request with streaming response and tool calling events (async implementation)."""
    
    async def generate():
        """Async generator for streaming SSE events with full async implementation."""
        try:
            # Use async generator directly - no threads needed!
            # This provides true async concurrency with minimal overhead
            async for event in chat_service.chat_stream(request):
                # Format as SSE
                data = json.dumps(event, ensure_ascii=False)
                yield f"data: {data}\n\n"
            
            # Send done signal
            yield "data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n"
            
        except LLMError as exc:
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

