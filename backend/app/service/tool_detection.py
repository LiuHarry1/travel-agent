"""Tool detection logic for chat service."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ToolDetectionService:
    """Service for detecting tool calls from LLM responses."""

    def __init__(self, llm_client):
        """Initialize tool detection service."""
        self.llm_client = llm_client

    def normalize_tool_calls(self, assistant_message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Normalize tool calls from different LLM formats (function_call vs tool_calls).
        
        Args:
            assistant_message: Assistant message from LLM response
            
        Returns:
            List of normalized tool call dictionaries
        """
        # DashScope/Qwen uses "function_call" (singular) instead of "tool_calls" (plural)
        # OpenAI format uses "tool_calls" (plural)
        function_call = assistant_message.get("function_call")
        tool_calls = assistant_message.get("tool_calls", [])
        
        # Convert function_call to tool_calls format for consistency
        if function_call and not tool_calls:
            # DashScope format: single function_call
            tool_calls = [{
                "id": function_call.get("id", f"call_{int(time.time() * 1000)}"),
                "function": {
                    "name": function_call.get("name", ""),
                    "arguments": function_call.get("arguments", "{}")
                },
                "type": "function"
            }]
            logger.info(f"Converted function_call to tool_calls format: {function_call.get('name', 'unknown')}")
        
        return tool_calls or []

    def extract_tool_name(self, tool_call: Any) -> str:
        """Extract tool name from tool call data structure."""
        if isinstance(tool_call, dict):
            func_info = tool_call.get("function", {})
            if isinstance(func_info, dict):
                return func_info.get("name", "unknown")
            return str(func_info)
        return str(tool_call)

    async def detect_tool_calls(
        self,
        messages: List[Dict[str, str]],
        system_prompt: str,
        functions: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Detect tool calls by making a non-streaming LLM request.
        
        Args:
            messages: Conversation messages
            system_prompt: System prompt for the LLM
            functions: Available function definitions
            
        Returns:
            Dict with 'content' and 'tool_calls' keys, or None if error
        """
        start_time = time.time()
        try:
            client = self.llm_client._get_client()
            system_msg = {"role": "system", "content": system_prompt}
            all_messages = [system_msg] + messages
            
            payload_start = time.time()
            payload = client._normalize_payload(all_messages, model=client.model)
            payload["functions"] = functions
            payload["function_call"] = "auto"
            payload["max_tokens"] = 300  # Reduced from 500 to 300 for faster tool detection
            payload_time = time.time() - payload_start
            logger.info(f"[PERF] Tool detection payload preparation took {payload_time:.3f}s")
            
            logger.info(f"Making tool detection request (async) with {len(functions)} functions")
            logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}")
            
            request_start = time.time()
            response_data = await client._make_request("chat/completions", payload)
            request_time = time.time() - request_start
            logger.info(f"[PERF] Tool detection LLM request (async) took {request_time:.3f}s")
            logger.info(f"Received response, keys: {list(response_data.keys())}")
            
            parse_start = time.time()
            if "choices" not in response_data or not response_data["choices"]:
                logger.error(f"Invalid response format: {response_data}")
                return None
            
            assistant_message = response_data.get("choices", [{}])[0].get("message", {})
            logger.info(f"Assistant message keys: {list(assistant_message.keys())}")
            
            content = assistant_message.get("content") or assistant_message.get("text", "")
            tool_calls = self.normalize_tool_calls(assistant_message)
            parse_time = time.time() - parse_start
            logger.info(f"[PERF] Tool detection response parsing took {parse_time:.3f}s")
            
            logger.info(f"Content: {content[:100] if content else 'None'}, Tool calls: {len(tool_calls)}")
            
            if tool_calls:
                tool_names = [self.extract_tool_name(tc) for tc in tool_calls]
                logger.info(f"Tool calls detected: {tool_names}")
            
            total_time = time.time() - start_time
            logger.info(
                f"[PERF] Total tool detection (async) took {total_time:.3f}s "
                f"(payload: {payload_time:.3f}s, request: {request_time:.3f}s, parse: {parse_time:.3f}s)"
            )
            
            return {
                "content": content,
                "tool_calls": tool_calls
            }
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"[PERF] Tool detection failed after {total_time:.3f}s: {e}", exc_info=True)
            return None

