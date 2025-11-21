"""Chat service for conversational travel agent with MCP tool calling."""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Generator, List, Optional, Tuple

from ..config import get_config
from ..llm import LLMClient, LLMError
from ..mcp import MCPToolRegistry, ToolCall, ToolResult
from ..models import ChatRequest
from ..utils.constants import MAX_CONVERSATION_TURNS
from ..utils.exceptions import format_error_message
from .chat_file_handler import format_files_for_message

logger = logging.getLogger(__name__)


class ChatService:
    """Service for conversational travel agent with MCP tool calling."""

    def __init__(self, llm_client: Optional[LLMClient] = None, mcp_registry: Optional[MCPToolRegistry] = None):
        """Initialize chat service."""
        self.llm_client = llm_client or LLMClient()
        self.mcp_registry = mcp_registry or MCPToolRegistry()
        self.max_tool_iterations = 5

    def _build_agent_system_prompt(self) -> str:
        """Build unified system prompt for travel agent."""
        # Get tool descriptions
        tools = self.mcp_registry.list_tools()
        tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}" for tool in tools
        ])
        
        return f"""You are a helpful travel agent assistant. Your goal is to help users with travel-related questions and planning.

Available Tools:
{tool_descriptions}

IMPORTANT: You MUST use the available tools when users ask travel-related questions that require specific information. Always use tools for:
- Questions about travel requirements (visas, passports, vaccinations)
- Questions about travel destinations, guides, or recommendations
- Questions that need factual travel information from knowledge bases
- Any travel-related query where you need to search for specific information

Guidelines:
1. For travel-related questions that need specific information, ALWAYS use the available tools (faq or retriever) to get accurate information
2. For non-travel questions (like general conversation, math, coding), answer directly without using tools
3. For simple travel greetings or general travel advice that doesn't need specific data, you can answer directly
4. When using tools, explain what information you're retrieving
5. Combine information from multiple tools when needed to provide comprehensive answers
6. Use the 'faq' tool for common travel questions (visas, passports, insurance, etc.)
7. Use the 'retriever' tool for destination guides, travel tips, and detailed travel information

Examples of when to use tools:
- "我需要签证吗？" → Use faq tool
- "日本旅游有什么推荐？" → Use retriever tool
- "去欧洲旅行需要注意什么？" → Use retriever tool
- "护照有效期要求是什么？" → Use faq tool

Examples of when NOT to use tools:
- "你好" → Answer directly
- "1+1等于多少？" → Answer directly (not travel-related)
- "今天天气怎么样？" → Answer directly (not travel-related)

Answer user questions about travel planning, destinations, visas, accommodations, and other travel-related topics."""

    def _trim_history(self, messages: List[Dict[str, str]], max_turns: int = MAX_CONVERSATION_TURNS) -> List[Dict[str, str]]:
        """
        Trim conversation history to keep only recent messages.
        
        Args:
            messages: Full conversation history
            max_turns: Maximum number of message turns to keep
            
        Returns:
            Trimmed conversation history
        """
        if len(messages) <= max_turns:
            return messages

        # Keep system message if exists, then recent messages
        if messages and messages[0].get("role") == "system":
            return [messages[0]] + messages[-(max_turns - 1):]
        return messages[-max_turns:]

    def chat_stream(self, request: ChatRequest) -> Generator[Dict[str, Any], None, None]:
        """
        Handle chat request with streaming response and tool calling support.
        
        Yields dictionaries with event information:
        - {"type": "chunk", "content": "..."} for text chunks
        - {"type": "tool_call_start", "tool": "...", "input": "..."} for tool call start
        - {"type": "tool_call_end", "tool": "...", "result": "..."} for tool call end
        - {"type": "tool_call_error", "tool": "...", "error": "..."} for tool call errors
        """
        try:
            # Handle file uploads - format as part of user message
            file_content = format_files_for_message(request.files)
            
            # Build user message
            user_message = request.message or ""
            if file_content:
                if user_message:
                    user_message = f"{user_message}\n\n{file_content}"
                else:
                    user_message = file_content

            # Get conversation history from request
            messages = request.messages or []
            
            # Add current user message to history
            if user_message:
                messages.append({"role": "user", "content": user_message})

            # Trim history to keep it manageable
            messages = self._trim_history(messages)

            # Build system prompt
            system_prompt = self._build_agent_system_prompt()

            if not messages:
                # No messages yet, return welcome message
                yield {"type": "chunk", "content": "你好！我是您的旅行助手。我可以帮助您规划旅行、回答旅行相关问题、查找目的地信息等。请告诉我您需要什么帮助？"}
                return

            # Get function definitions for tool calling
            functions = self.mcp_registry.get_tool_function_definitions()
            
            # Tool calling loop (max 5 iterations)
            iteration = 0
            while iteration < self.max_tool_iterations:
                iteration += 1
                logger.info(f"Tool calling iteration {iteration}/{self.max_tool_iterations}")
                
                # For tool calling, we need to make a non-streaming request first to detect tool calls
                # Then stream the final response after tool execution
                accumulated_content = ""
                tool_calls_detected = []
                
                try:
                    if functions and iteration == 1:
                        # First iteration: check if tools are needed using a non-streaming call
                        # This is a simplified approach - in production, tool calls would be detected in stream
                        client = self.llm_client._get_client()
                        system_msg = {"role": "system", "content": system_prompt}
                        all_messages = [system_msg] + messages
                        
                        payload = client._normalize_payload(all_messages, model=client.model)
                        payload["functions"] = functions
                        payload["function_call"] = "auto"
                        payload["max_tokens"] = 1000  # Limit tokens to encourage tool use if needed
                        
                        # Make non-streaming request to detect tool calls
                        try:
                            logger.info(f"Making tool detection request with {len(functions)} functions")
                            logger.debug(f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:500]}")
                            
                            response_data = client._make_request("chat/completions", payload)
                            logger.info(f"Received response, keys: {list(response_data.keys())}")
                            
                            if "choices" not in response_data or not response_data["choices"]:
                                logger.error(f"Invalid response format: {response_data}")
                                raise ValueError("Invalid response format: no choices")
                            
                            assistant_message = response_data.get("choices", [{}])[0].get("message", {})
                            logger.info(f"Assistant message keys: {list(assistant_message.keys())}")
                            
                            content = assistant_message.get("content") or assistant_message.get("text", "")
                            
                            # DashScope/Qwen uses "function_call" (singular) instead of "tool_calls" (plural)
                            # OpenAI format uses "tool_calls" (plural)
                            function_call = assistant_message.get("function_call")
                            tool_calls = assistant_message.get("tool_calls", [])
                            
                            # Convert function_call to tool_calls format for consistency
                            if function_call and not tool_calls:
                                # DashScope format: single function_call
                                tool_calls = [{
                                    "id": function_call.get("id", "call_" + str(int(time.time() * 1000))),
                                    "function": {
                                        "name": function_call.get("name", ""),
                                        "arguments": function_call.get("arguments", "{}")
                                    },
                                    "type": "function"
                                }]
                                logger.info(f"Converted function_call to tool_calls format: {function_call.get('name', 'unknown')}")
                            
                            logger.info(f"Content: {content[:100] if content else 'None'}, Tool calls: {len(tool_calls) if tool_calls else 0}")
                            
                            if tool_calls:
                                tool_names = []
                                for tc in tool_calls:
                                    if isinstance(tc, dict):
                                        func_info = tc.get("function", {})
                                        if isinstance(func_info, dict):
                                            tool_names.append(func_info.get("name", "unknown"))
                                        else:
                                            tool_names.append(str(func_info))
                                    else:
                                        tool_names.append(str(tc))
                                logger.info(f"Tool calls detected: {tool_names}")
                                # Tool calls detected - execute them
                                messages.append({
                                    "role": "assistant",
                                    "content": content,
                                    "tool_calls": tool_calls
                                })
                                
                                # Execute each tool call
                                for tool_call_data in tool_calls:
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
                                    logger.info(f"Tool call start event yielded for: {tool_name}")
                                    
                                    # Execute tool
                                    tool_call = ToolCall(
                                        name=tool_name,
                                        arguments=tool_args,
                                        id=tool_call_id
                                    )
                                    
                                    try:
                                        import asyncio
                                        try:
                                            loop = asyncio.get_event_loop()
                                        except RuntimeError:
                                            loop = asyncio.new_event_loop()
                                            asyncio.set_event_loop(loop)
                                        
                                        tool_result = loop.run_until_complete(
                                            self.mcp_registry.call_tool(tool_call)
                                        )
                                        
                                        if tool_result.success:
                                            # Yield tool call end event
                                            yield {
                                                "type": "tool_call_end",
                                                "tool": tool_name,
                                                "tool_call_id": tool_call_id,
                                                "result": tool_result.result
                                            }
                                            
                                            # Add tool result to messages
                                            messages.append({
                                                "role": "tool",
                                                "tool_call_id": tool_call_id,
                                                "name": tool_name,
                                                "content": json.dumps(tool_result.result, ensure_ascii=False)
                                            })
                                        else:
                                            # Yield tool call error event
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
                                                "content": f"Error: {tool_result.error}"
                                            })
                                    except Exception as e:
                                        logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
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
                                
                                # Continue loop to get final response with tool results
                                # Don't break, continue to next iteration to get final response
                                # Reset accumulated_content since we'll stream the final response
                                accumulated_content = ""
                                continue
                            else:
                                # No tool calls, stream the content from the response
                                logger.info("No tool calls detected, streaming content directly")
                                if content:
                                    accumulated_content = content
                                    yield {"type": "chunk", "content": content}
                                else:
                                    logger.warning("No content in response, falling back to streaming")
                                    # Fall through to regular streaming
                                # Break out of loop since we got a response without tool calls
                                break
                        except Exception as e:
                            logger.error(f"Error in tool detection call: {e}", exc_info=True)
                            # Fall through to regular streaming
                    
                    # Regular streaming (no tools or after tool execution in previous iterations)
                    # Stream the final response after tool execution
                    # If iteration > 1, we've executed tools and need final response
                    # If iteration == 1 and no functions, just stream normally
                    should_stream = False
                    if iteration > 1:
                        # After tool execution, get final response with tool results
                        logger.info(f"Streaming final response after tool execution (iteration {iteration})")
                        should_stream = True
                    elif iteration == 1 and not functions:
                        # No functions available, stream normally
                        logger.info("No functions available, streaming normally")
                        should_stream = True
                    elif iteration == 1 and functions:
                        # First iteration with functions but no tool calls detected or error occurred
                        # Stream normally as fallback
                        logger.info("First iteration with functions but no tool calls, streaming as fallback")
                        should_stream = True
                    
                    if should_stream:
                        logger.info(f"Starting stream with {len(messages)} messages")
                        chunk_count = 0
                        for chunk in self.llm_client.chat_stream(messages, system_prompt=system_prompt):
                            chunk_count += 1
                            accumulated_content += chunk
                            yield {"type": "chunk", "content": chunk}
                        logger.info(f"Stream completed, received {chunk_count} chunks, total content length: {len(accumulated_content)}")
                    
                    # If we have content, we're done
                    if accumulated_content:
                        logger.info(f"Completed with content (length: {len(accumulated_content)})")
                        break
                    elif iteration >= self.max_tool_iterations:
                        logger.warning(f"Reached max iterations ({self.max_tool_iterations}) without content")
                        yield {"type": "chunk", "content": "抱歉，处理请求时遇到问题，请重试。"}
                        break
                        
                except LLMError as exc:
                    error_msg = format_error_message(exc, "Error processing request")
                    yield {"type": "chunk", "content": error_msg}
                    break
                except Exception as exc:
                    logger.error(f"Unexpected error during LLM streaming: {exc}", exc_info=True)
                    yield {"type": "chunk", "content": f"An unexpected error occurred: {str(exc)}"}
                    break
            
            if iteration >= self.max_tool_iterations:
                logger.warning(f"Reached maximum tool calling iterations ({self.max_tool_iterations})")

        except Exception as exc:
            logger.error(f"Error in chat_stream: {exc}", exc_info=True)
            yield {"type": "chunk", "content": f"An error occurred while processing your request: {str(exc)}"}
