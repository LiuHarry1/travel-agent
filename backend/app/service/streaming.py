"""Streaming response logic for chat service."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StreamingService:
    """Service for streaming LLM responses with real-time tool call detection."""

    def __init__(self, llm_client):
        """Initialize streaming service."""
        self.llm_client = llm_client

    async def stream_with_tool_detection(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        functions: List[Dict[str, Any]]
    ) -> AsyncGenerator[Tuple[str, Optional[List[Dict[str, Any]]]], None]:
        """
        Stream LLM response with real-time tool call detection.
        
        This is TRUE streaming - we stream from the start and detect tool calls
        in real-time as chunks arrive.
        
        Args:
            messages: Conversation messages
            system_prompt: System prompt for the LLM
            functions: Available function definitions
            
        Yields:
            Tuples of (content_chunk, tool_calls):
            - content_chunk: Text content chunk (can be empty)
            - tool_calls: List of tool calls if detected, None otherwise
        """
        stream_start_time = time.time()
        logger.info(f"Starting TRUE streaming with {len(messages)} messages, {len(functions)} functions")
        
        try:
            client = self.llm_client._get_client()
            system_msg = {"role": "system", "content": system_prompt or ""}
            all_messages = [system_msg] + messages
            
            payload = client._normalize_payload(all_messages, model=client.model)
            
            # Add functions for tool calling
            if functions:
                payload["functions"] = functions
                payload["function_call"] = "auto"
            
            # Track tool calls across chunks
            tool_calls_by_id: Dict[str, Dict[str, Any]] = {}
            accumulated_content = ""
            chunk_count = 0
            first_chunk_time = None
            
            # Stream and parse in real-time
            # We need to get raw JSON chunks, not just text content
            # Access the underlying HTTP client to get raw chunks
            request_start = time.time()
            
            # Get raw stream chunks directly from the HTTP client
            from ..llm.base import BaseLLMClient
            
            if isinstance(client, BaseLLMClient):
                # Use the async client directly to get raw chunks
                async_client = client._get_async_client()
                url = client._get_base_url() + "/chat/completions"
                # Get headers - construct based on provider type
                headers = {"Content-Type": "application/json"}
                if hasattr(client, 'api_key') and client.api_key:
                    # Check provider type by class name
                    client_type = type(client).__name__
                    if 'Qwen' in client_type or 'DashScope' in client_type:
                        headers["Authorization"] = f"Bearer {client.api_key}"
                    elif 'Azure' in client_type:
                        headers["api-key"] = client.api_key
                    else:
                        # Default to Bearer token
                        headers["Authorization"] = f"Bearer {client.api_key}"
                
                async with async_client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line or not line.strip():
                            continue
                        
                        if line.startswith("data: "):
                            data_str = line[6:].strip()  # Remove "data: " prefix
                            if data_str == "[DONE]":
                                break
                            
                            if not data_str:
                                continue
                            
                            try:
                                chunk_data = json.loads(data_str)
                                chunk_count += 1
                                
                                if first_chunk_time is None:
                                    first_chunk_time = time.time() - request_start
                                    logger.info(f"[PERF] First chunk received after {first_chunk_time:.3f}s (TTFB)")
                                
                                # Debug: log chunk structure for first few chunks
                                if chunk_count <= 3:
                                    logger.debug(f"Chunk {chunk_count} structure: {list(chunk_data.keys())}, "
                                               f"has choices: {'choices' in chunk_data}")
                                
                                # Parse chunk to extract content and tool call info
                                content_chunk, tool_call_updates = self._parse_stream_chunk_from_json(
                                    chunk_data, tool_calls_by_id
                                )
                                
                                if content_chunk:
                                    accumulated_content += content_chunk
                                    yield (content_chunk, None)
                                elif chunk_count <= 3:
                                    # Log why we didn't get content
                                    if "choices" in chunk_data and chunk_data["choices"]:
                                        delta = chunk_data["choices"][0].get("delta", {})
                                        logger.debug(f"Chunk {chunk_count} has delta keys: {list(delta.keys())}, "
                                                   f"delta: {delta}")
                                
                                # If we detected complete tool calls, yield them
                                if tool_call_updates:
                                    # Check if any tool calls are complete
                                    complete_tool_calls = self._get_complete_tool_calls(tool_calls_by_id)
                                    if complete_tool_calls:
                                        logger.info(f"Detected {len(complete_tool_calls)} complete tool calls during streaming")
                                        yield ("", complete_tool_calls)
                                        # Clear accumulated tool calls after yielding
                                        tool_calls_by_id.clear()
                                        break  # Stop streaming, tool calls detected
                            except json.JSONDecodeError as e:
                                logger.debug(f"JSON decode error for line: {line[:100]}, error: {e}")
                                continue
                            except Exception as e:
                                logger.warning(f"Error parsing stream chunk: {e}", exc_info=True)
                                continue
            else:
                # Fallback: use normal streaming (won't detect tool calls in real-time)
                logger.warning("Client is not BaseLLMClient, falling back to normal streaming")
                async for chunk in client._make_stream_request("chat/completions", payload):
                    if first_chunk_time is None:
                        first_chunk_time = time.time() - request_start
                        logger.info(f"[PERF] First chunk received after {first_chunk_time:.3f}s (TTFB)")
                    chunk_count += 1
                    accumulated_content += chunk
                    yield (chunk, None)
                
                if content_chunk:
                    accumulated_content += content_chunk
                    yield (content_chunk, None)
                
                # If we detected complete tool calls, yield them
                if tool_call_updates:
                    # Check if any tool calls are complete
                    complete_tool_calls = self._get_complete_tool_calls(tool_calls_by_id)
                    if complete_tool_calls:
                        yield ("", complete_tool_calls)
                        # Clear accumulated tool calls after yielding
                        tool_calls_by_id.clear()
            
            request_time = time.time() - request_start
            total_time = time.time() - stream_start_time
            logger.info(
                f"[PERF] TRUE streaming took {total_time:.3f}s, "
                f"received {chunk_count} chunks, "
                f"content length: {len(accumulated_content)}"
            )
            
        except Exception as e:
            logger.error(f"Error in TRUE streaming: {e}", exc_info=True)
            raise

    def _parse_stream_chunk_from_json(self, chunk_data: Dict[str, Any], tool_calls_by_id: Dict[str, Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parse a JSON chunk to extract content and tool call updates.
        
        Args:
            chunk_data: Parsed JSON chunk data
            tool_calls_by_id: Dictionary to accumulate tool call data
            
        Returns:
            Tuple of (content_chunk, tool_call_updates)
        """
        if "choices" not in chunk_data or not chunk_data["choices"]:
            logger.debug(f"No choices in chunk_data: {chunk_data.keys()}")
            return ("", [])
        
        delta = chunk_data["choices"][0].get("delta", {})
        content = delta.get("content") or delta.get("text", "")  # Support both "content" and "text" fields
        
        # Log if we're getting chunks but no content (for debugging)
        if not content and delta:
            logger.debug(f"Chunk has delta but no content: {delta.keys()}")
        
        # Extract tool call information from delta
        tool_call_updates = []
        
        # Check for function_call (Qwen/DashScope format)
        if "function_call" in delta:
            func_call = delta["function_call"]
            call_id = func_call.get("id") or func_call.get("index", "default")
            
            if call_id not in tool_calls_by_id:
                tool_calls_by_id[call_id] = {
                    "id": call_id,
                    "function": {"name": "", "arguments": ""}
                }
            
            if "name" in func_call:
                tool_calls_by_id[call_id]["function"]["name"] = func_call["name"]
            if "arguments" in func_call:
                tool_calls_by_id[call_id]["function"]["arguments"] += func_call["arguments"]
            
            tool_call_updates.append(tool_calls_by_id[call_id])
        
        # Check for tool_calls (OpenAI format)
        if "tool_calls" in delta:
            for tool_call_delta in delta["tool_calls"]:
                call_id = tool_call_delta.get("id", "unknown")
                index = tool_call_delta.get("index", 0)
                
                if call_id not in tool_calls_by_id:
                    tool_calls_by_id[call_id] = {
                        "id": call_id,
                        "type": "function",
                        "function": {"name": "", "arguments": ""},
                        "index": index
                    }
                
                if "function" in tool_call_delta:
                    func_delta = tool_call_delta["function"]
                    if "name" in func_delta:
                        tool_calls_by_id[call_id]["function"]["name"] = func_delta["name"]
                    if "arguments" in func_delta:
                        tool_calls_by_id[call_id]["function"]["arguments"] += func_delta["arguments"]
                
                tool_call_updates.append(tool_calls_by_id[call_id])
        
        return (content, tool_call_updates)

    def _parse_stream_chunk(self, chunk: str, tool_calls_by_id: Dict[str, Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Parse a stream chunk to extract content and tool call updates.
        
        Args:
            chunk: Raw chunk string (may be JSON or plain text)
            tool_calls_by_id: Dictionary to accumulate tool call data
            
        Returns:
            Tuple of (content_chunk, tool_call_updates)
        """
        # Try to parse as JSON (SSE format)
        try:
            if chunk.startswith("data: "):
                chunk = chunk[6:]  # Remove "data: " prefix
            if chunk == "[DONE]":
                return ("", [])
            
            chunk_data = json.loads(chunk)
            
            if "choices" not in chunk_data or not chunk_data["choices"]:
                return ("", [])
            
            delta = chunk_data["choices"][0].get("delta", {})
            content = delta.get("content", "")
            
            # Extract tool call information from delta
            tool_call_updates = []
            
            # Check for function_call (Qwen/DashScope format)
            if "function_call" in delta:
                func_call = delta["function_call"]
                call_id = func_call.get("id") or func_call.get("index", "default")
                
                if call_id not in tool_calls_by_id:
                    tool_calls_by_id[call_id] = {
                        "id": call_id,
                        "function": {"name": "", "arguments": ""}
                    }
                
                if "name" in func_call:
                    tool_calls_by_id[call_id]["function"]["name"] = func_call["name"]
                if "arguments" in func_call:
                    tool_calls_by_id[call_id]["function"]["arguments"] += func_call["arguments"]
                
                tool_call_updates.append(tool_calls_by_id[call_id])
            
            # Check for tool_calls (OpenAI format)
            if "tool_calls" in delta:
                for tool_call_delta in delta["tool_calls"]:
                    call_id = tool_call_delta.get("id", "unknown")
                    index = tool_call_delta.get("index", 0)
                    
                    if call_id not in tool_calls_by_id:
                        tool_calls_by_id[call_id] = {
                            "id": call_id,
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                            "index": index
                        }
                    
                    if "function" in tool_call_delta:
                        func_delta = tool_call_delta["function"]
                        if "name" in func_delta:
                            tool_calls_by_id[call_id]["function"]["name"] = func_delta["name"]
                        if "arguments" in func_delta:
                            tool_calls_by_id[call_id]["function"]["arguments"] += func_delta["arguments"]
                    
                    tool_call_updates.append(tool_calls_by_id[call_id])
            
            return (content, tool_call_updates)
            
        except json.JSONDecodeError:
            # Not JSON, treat as plain text content
            return (chunk, [])
        except Exception as e:
            logger.warning(f"Error parsing stream chunk: {e}")
            return ("", [])

    def _get_complete_tool_calls(self, tool_calls_by_id: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Get complete tool calls (those with both name and arguments).
        
        Args:
            tool_calls_by_id: Dictionary of tool calls being accumulated
            
        Returns:
            List of complete tool calls
        """
        complete_calls = []
        for call_id, call_data in tool_calls_by_id.items():
            func_info = call_data.get("function", {})
            name = func_info.get("name", "")
            arguments = func_info.get("arguments", "")
            
            # Consider a tool call complete if it has a name
            # Arguments might be empty for some providers
            if name:
                complete_calls.append(call_data)
        
        return complete_calls if complete_calls else []

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
        Stream LLM response chunks (without tool detection).
        
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
