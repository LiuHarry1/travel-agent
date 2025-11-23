"""Tool execution logic for chat service."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List

from ..mcp_tools import ToolCall

logger = logging.getLogger(__name__)


class ToolExecutionService:
    """Service for executing tool calls."""

    def __init__(self, mcp_registry, tool_result_formatter):
        """Initialize tool execution service."""
        self.mcp_registry = mcp_registry
        self._format_tool_result = tool_result_formatter

    async def execute_single_tool(
        self,
        tool_call_data: Dict[str, Any],
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute a single tool call and yield events.
        
        Args:
            tool_call_data: Tool call data from LLM
            messages: Conversation messages (will be updated with tool result)
            
        Yields:
            Tool call events (start, end, or error)
        """
        tool_call_id = tool_call_data.get("id", "")
        tool_name = tool_call_data.get("function", {}).get("name", "")
        tool_args_str = tool_call_data.get("function", {}).get("arguments", "{}")
        
        # Parse arguments
        try:
            tool_args = json.loads(tool_args_str)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tool arguments: {tool_args_str}")
            tool_args = {}
        
        # Yield tool call start event
        logger.info(f"Yielding tool_call_start event for tool: {tool_name}, id: {tool_call_id}")
        yield {
            "type": "tool_call_start",
            "tool": tool_name,
            "tool_call_id": tool_call_id,
            "input": tool_args
        }
        
        # Execute tool
        tool_call = ToolCall(
            name=tool_name,
            arguments=tool_args,
            id=tool_call_id
        )
        
        try:
            exec_start = time.time()
            tool_result = await self.mcp_registry.call_tool(tool_call)
            exec_time = time.time() - exec_start
            logger.info(f"[PERF] Tool '{tool_name}' execution (async) took {exec_time:.3f}s")
            
            if tool_result.success:
                # Yield tool call end event
                yield {
                    "type": "tool_call_end",
                    "tool": tool_name,
                    "tool_call_id": tool_call_id,
                    "result": tool_result.result
                }
                
                # Format tool result content for LLM
                format_start = time.time()
                tool_content = self._format_tool_result(tool_result.result, tool_name)
                format_time = time.time() - format_start
                logger.info(
                    f"[PERF] Tool '{tool_name}' result formatting took {format_time:.3f}s, "
                    f"content length: {len(tool_content)} chars"
                )
                
                # Add tool result to messages
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": tool_content
                }
                messages.append(tool_message)
            else:
                # Yield tool call error event
                error_msg = tool_result.error or "Unknown error"
                yield {
                    "type": "tool_call_error",
                    "tool": tool_name,
                    "tool_call_id": tool_call_id,
                    "error": error_msg
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": f"Error: {error_msg}"
                })
        except Exception as e:
            logger.error(f"[PERF] Tool '{tool_name}' failed: {e}", exc_info=True)
            yield {
                "type": "tool_call_error",
                "tool": tool_name,
                "tool_call_id": tool_call_id,
                "error": str(e)
            }
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": f"Error: {str(e)}"
            })

    async def execute_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        content: str,
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute multiple tool calls and yield events.
        
        If multiple tools are detected, they will be executed in parallel for better performance.
        
        Args:
            tool_calls: List of tool call data from LLM
            content: Assistant message content
            messages: Conversation messages (will be updated with tool results)
            
        Yields:
            Tool call events for each tool
        """
        # Add assistant message with tool calls to history
        messages.append({
            "role": "assistant",
            "content": content,
            "tool_calls": tool_calls
        })
        
        # If multiple tools, execute in parallel for better performance
        if len(tool_calls) > 1:
            logger.info(f"[PERF] Executing {len(tool_calls)} tools in parallel (async)")
            # Execute tools in parallel using async
            async for event in self.execute_tools_parallel(tool_calls, messages):
                yield event
        else:
            # Single tool, execute asynchronously
            async for event in self.execute_single_tool(tool_calls[0], messages):
                yield event

    async def execute_tools_parallel(
        self,
        tool_calls: List[Dict[str, Any]],
        messages: List[Dict[str, str]]
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Execute multiple tool calls in parallel and yield events.
        
        Args:
            tool_calls: List of tool call data from LLM
            messages: Conversation messages (will be updated with tool results)
            
        Yields:
            Tool call events for each tool (in the order they complete)
        """
        # Yield start events for all tools first
        for tool_call_data in tool_calls:
            tool_call_id = tool_call_data.get("id", "")
            tool_name = tool_call_data.get("function", {}).get("name", "")
            tool_args_str = tool_call_data.get("function", {}).get("arguments", "{}")
            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_args = {}
            
            yield {
                "type": "tool_call_start",
                "tool": tool_name,
                "tool_call_id": tool_call_id,
                "input": tool_args
            }
        
        # Execute all tools in parallel
        async def execute_tool_async(tool_call_data: Dict[str, Any]) -> Dict[str, Any]:
            """Execute a single tool asynchronously and return result."""
            tool_call_id = tool_call_data.get("id", "")
            tool_name = tool_call_data.get("function", {}).get("name", "")
            tool_args_str = tool_call_data.get("function", {}).get("arguments", "{}")
            try:
                tool_args = json.loads(tool_args_str)
            except json.JSONDecodeError:
                tool_args = {}
            
            tool_call = ToolCall(name=tool_name, arguments=tool_args, id=tool_call_id)
            try:
                tool_result = await self.mcp_registry.call_tool(tool_call)
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": True,
                    "result": tool_result
                }
            except Exception as e:
                return {
                    "tool_call_id": tool_call_id,
                    "tool_name": tool_name,
                    "success": False,
                    "error": str(e)
                }
        
        # Execute all tools concurrently
        tasks = [execute_tool_async(tc) for tc in tool_calls]
        results = await asyncio.gather(*tasks)
        
        # Yield end/error events for each tool
        for result in results:
            tool_call_id = result["tool_call_id"]
            tool_name = result["tool_name"]
            
            if result["success"]:
                tool_result = result["result"]
                if tool_result.success:
                    yield {
                        "type": "tool_call_end",
                        "tool": tool_name,
                        "tool_call_id": tool_call_id,
                        "result": tool_result.result
                    }
                    tool_content = self._format_tool_result(tool_result.result, tool_name)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": tool_content
                    })
                else:
                    yield {
                        "type": "tool_call_error",
                        "tool": tool_name,
                        "tool_call_id": tool_call_id,
                        "error": tool_result.error or "Unknown error"
                    }
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": tool_name,
                        "content": f"Error: {tool_result.error or 'Unknown error'}"
                    })
            else:
                yield {
                    "type": "tool_call_error",
                    "tool": tool_name,
                    "tool_call_id": tool_call_id,
                    "error": result["error"]
                }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "name": tool_name,
                    "content": f"Error: {result['error']}"
                })

