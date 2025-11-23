"""Streaming response logic for chat service."""
from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)


class StreamingService:
    """Service for streaming LLM responses."""

    def __init__(self, llm_client):
        """Initialize streaming service."""
        self.llm_client = llm_client

    def should_stream_response(
        self,
        iteration: int,
        functions: List[Dict[str, Any]],
        has_tool_calls: bool
    ) -> bool:
        """
        Determine if we should stream the final response.
        
        Args:
            iteration: Current iteration number
            functions: Available function definitions
            has_tool_calls: Whether tool calls were detected in this iteration
            
        Returns:
            True if should stream, False otherwise
        """
        if iteration > 1:
            # After tool execution, get final response with tool results
            logger.info(f"Streaming final response after tool execution (iteration {iteration})")
            return True
        elif iteration == 1 and not functions:
            # No functions available, stream normally
            logger.info("No functions available, streaming normally")
            return True
        elif iteration == 1 and functions and not has_tool_calls:
            # First iteration with functions but no tool calls detected or error occurred
            # Stream normally as fallback
            logger.info("First iteration with functions but no tool calls, streaming as fallback")
            return True
        return False

    async def stream_llm_response(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        disable_tools: bool = True
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response chunks.
        
        Args:
            messages: Conversation messages
            system_prompt: System prompt for the LLM
            disable_tools: If True, explicitly disable tool calling (for final response after tool execution)
            
        Yields:
            Text chunks from LLM
        """
        stream_start_time = time.time()
        logger.info(f"Starting async stream with {len(messages)} messages, disable_tools={disable_tools}")
        chunk_count = 0
        first_chunk_time = None
        
        # If we need to disable tools, we need to modify the payload
        if disable_tools:
            # Use the client directly to modify payload
            try:
                payload_start = time.time()
                client = self.llm_client._get_client()
                system_msg = {"role": "system", "content": system_prompt or ""}
                all_messages = [system_msg] + messages
                
                payload = client._normalize_payload(all_messages, model=client.model)
                # Explicitly disable function calling
                payload["function_call"] = "none"
                # Remove functions if present
                if "functions" in payload:
                    del payload["functions"]
                payload_time = time.time() - payload_start
                logger.info(f"[PERF] Stream payload preparation took {payload_time:.3f}s")
                
                # Make async streaming request directly
                request_start = time.time()
                async for chunk in client._make_stream_request("chat/completions", payload):
                    if first_chunk_time is None:
                        first_chunk_time = time.time() - request_start
                        logger.info(f"[PERF] First chunk received after {first_chunk_time:.3f}s (TTFB)")
                    chunk_count += 1
                    yield chunk
                request_time = time.time() - request_start
                logger.info(f"[PERF] Stream request (async) took {request_time:.3f}s, received {chunk_count} chunks")
            except Exception as e:
                logger.error(f"Error in async streaming with disabled tools: {e}", exc_info=True)
                # Fallback to normal streaming
                request_start = time.time()
                async for chunk in self._stream_llm_client(messages, system_prompt=system_prompt):
                    if first_chunk_time is None:
                        first_chunk_time = time.time() - request_start
                    chunk_count += 1
                    yield chunk
                request_time = time.time() - request_start
                logger.info(f"[PERF] Stream request (async fallback) took {request_time:.3f}s, received {chunk_count} chunks")
        else:
            # Normal async streaming
            request_start = time.time()
            async for chunk in self._stream_llm_client(messages, system_prompt=system_prompt):
                if first_chunk_time is None:
                    first_chunk_time = time.time() - request_start
                    logger.info(f"[PERF] First chunk received after {first_chunk_time:.3f}s (TTFB)")
                chunk_count += 1
                yield chunk
            request_time = time.time() - request_start
            logger.info(f"[PERF] Stream request (async) took {request_time:.3f}s, received {chunk_count} chunks")
        
        total_time = time.time() - stream_start_time
        logger.info(f"[PERF] Total async stream took {total_time:.3f}s, received {chunk_count} chunks")

    async def _stream_llm_client(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream from LLM client.
        Uses async HTTP client for true async streaming.
        """
        client = self.llm_client._get_client()
        system_msg = {"role": "system", "content": system_prompt or ""} if system_prompt else None
        all_messages = ([system_msg] + messages) if system_msg else messages
        
        payload = client._normalize_payload(all_messages, model=client.model)
        
        async for chunk in client._make_stream_request("chat/completions", payload):
            yield chunk

