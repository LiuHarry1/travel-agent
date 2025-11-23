"""Chat service for conversational travel agent with MCP tool calling."""
from __future__ import annotations

import logging
import time
from typing import Any, AsyncGenerator, Dict, Optional

from ..config import get_config
from ..llm import LLMClient, LLMError
from ..mcp_tools import MCPToolRegistry
from ..models import ChatRequest
from ..utils.exceptions import format_error_message
from .message_processing import MessageProcessingService
from .streaming import StreamingService
from .tool_detection import ToolDetectionService
from .tool_execution import ToolExecutionService
from .tool_result_formatter import (
    check_tools_used_but_no_info,
    format_tool_result_for_llm,
    response_suggests_contact_harry,
)

logger = logging.getLogger(__name__)


class ChatService:
    """Service for conversational travel agent with MCP tool calling."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        mcp_registry: Optional[MCPToolRegistry] = None,
    ):
        """Initialize chat service."""
        self.llm_client = llm_client or LLMClient()
        self.mcp_registry = mcp_registry or MCPToolRegistry()
        self.max_tool_iterations = 4

        # Initialize sub-services
        self.message_processor = MessageProcessingService(get_config)
        self.message_processor.set_mcp_registry(self.mcp_registry)
        self.tool_detector = ToolDetectionService(self.llm_client)
        self.tool_executor = ToolExecutionService(
            self.mcp_registry, format_tool_result_for_llm
        )
        self.streaming_service = StreamingService(self.llm_client)

    async def chat_stream(
        self, request: ChatRequest
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Handle chat request with streaming response and tool calling support.

        Yields dictionaries with event information:
        - {"type": "chunk", "content": "..."} for text chunks
        - {"type": "tool_call_start", "tool": "...", "input": "..."} for tool call start
        - {"type": "tool_call_end", "tool": "...", "result": "..."} for tool call end
        - {"type": "tool_call_error", "tool": "...", "error": "..."} for tool call errors
        """
        chat_start_time = time.time()
        try:
            # Prepare messages from request
            prep_start = time.time()
            messages = self.message_processor.prepare_messages(request)
            prep_time = time.time() - prep_start
            logger.info(f"[PERF] Message preparation took {prep_time:.3f}s")

            # Build system prompt
            prompt_start = time.time()
            system_prompt = self.message_processor.build_agent_system_prompt()
            prompt_time = time.time() - prompt_start
            logger.info(f"[PERF] System prompt building took {prompt_time:.3f}s")

            # Handle empty conversation
            if not messages:
                yield {
                    "type": "chunk",
                    "content": "你好！我是您的旅行助手。我可以帮助您规划旅行、回答旅行相关问题、查找目的地信息等。请告诉我您需要什么帮助？",
                }
                return

            # Get function definitions for tool calling (async)
            func_start = time.time()
            functions = await self.mcp_registry.get_tool_function_definitions()
            func_time = time.time() - func_start
            logger.info(
                f"[PERF] Function definitions loading took {func_time:.3f}s, "
                f"found {len(functions)} functions"
            )

            # Tool calling loop (max iterations)
            iteration = 0
            accumulated_content = ""

            while iteration < self.max_tool_iterations:
                iteration += 1
                iter_start_time = time.time()
                logger.info(
                    f"[PERF] Starting iteration {iteration}/{self.max_tool_iterations}"
                )

                try:
                    # Let LLM decide if tools are needed based on all tool results in messages
                    has_tool_calls = False
                    tool_count = len([m for m in messages if m.get("role") == "tool"])

                    # Always let LLM decide if more tools are needed
                    if functions and iteration <= self.max_tool_iterations:
                        logger.info(
                            f"Iteration {iteration}: Letting LLM decide if tools are needed "
                            f"(can see {tool_count} tool results from previous iterations)"
                        )
                        detection_result = await self.tool_detector.detect_tool_calls(
                            messages, system_prompt, functions
                        )

                        if detection_result:
                            content = detection_result["content"]
                            tool_calls = detection_result["tool_calls"]

                            logger.info(
                                f"Iteration {iteration}: Detection result - "
                                f"content length: {len(content) if content else 0}, "
                                f"tool_calls count: {len(tool_calls) if tool_calls else 0}"
                            )

                            if tool_calls:
                                # Execute tool calls and yield events
                                logger.info(
                                    f"Iteration {iteration}: Executing {len(tool_calls)} tool calls"
                                )
                                async for event in self.tool_executor.execute_tool_calls(
                                    tool_calls, content, messages
                                ):
                                    yield event
                                has_tool_calls = True
                                # Continue to next iteration to let LLM decide again
                                continue
                            elif content and iteration == 1:
                                # First iteration with content but no tool calls - yield it directly
                                accumulated_content = content
                                yield {"type": "chunk", "content": content}
                                break
                            else:
                                # Later iterations: LLM decided to generate final response
                                logger.info(
                                    f"Iteration {iteration}: LLM decided to generate final response "
                                    "(no more tool calls)"
                                )
                        else:
                            logger.warning(
                                f"Iteration {iteration}: Tool detection returned None, "
                                "falling back to streaming"
                            )

                    # Stream final response (after tool execution or if no tools needed)
                    if self.streaming_service.should_stream_response(
                        iteration, functions, has_tool_calls
                    ):
                        # Disable tools for final response generation
                        disable_tools = True
                        if iteration >= self.max_tool_iterations:
                            logger.info(
                                f"Iteration {iteration}: Reached max iterations "
                                f"({self.max_tool_iterations}), forcing final response"
                            )
                        else:
                            logger.info(
                                f"Iteration {iteration}: LLM decided not to call tools, "
                                "generating final response"
                            )

                        chunk_count_in_iteration = 0
                        stream_start = time.time()
                        async for chunk in self.streaming_service.stream_llm_response(
                            messages, system_prompt, disable_tools=disable_tools
                        ):
                            accumulated_content += chunk
                            chunk_count_in_iteration += 1
                            yield {"type": "chunk", "content": chunk}
                        stream_time = time.time() - stream_start
                        logger.info(
                            f"[PERF] Iteration {iteration} streaming took {stream_time:.3f}s, "
                            f"received {chunk_count_in_iteration} chunks"
                        )

                        # If we received 0 chunks after tool execution, stop immediately
                        if iteration > 1 and chunk_count_in_iteration == 0:
                            logger.warning(
                                f"Iteration {iteration}: Received 0 chunks after tool execution. "
                                "Stopping to prevent infinite loop."
                            )
                            if not accumulated_content:
                                tools_used_but_no_info = check_tools_used_but_no_info(
                                    messages
                                )
                                if tools_used_but_no_info:
                                    yield {
                                        "type": "chunk",
                                        "content": "很抱歉，我尝试了多种方法查找相关信息，但未能找到您问题的答案。建议您联系Harry获取更具体的帮助。",
                                    }
                                else:
                                    yield {
                                        "type": "chunk",
                                        "content": "抱歉，处理请求时遇到问题，请重试。",
                                    }
                            break

                        # If we got content and tools are disabled, we're done
                        if chunk_count_in_iteration > 0 and disable_tools:
                            logger.info(
                                f"Iteration {iteration}: Got {chunk_count_in_iteration} chunks "
                                "with tools disabled, completing"
                            )
                            # Check if tools were used but didn't find useful information
                            if iteration > 1:
                                tools_used_but_no_info = check_tools_used_but_no_info(
                                    messages
                                )
                                if tools_used_but_no_info and not response_suggests_contact_harry(
                                    accumulated_content
                                ):
                                    yield {
                                        "type": "chunk",
                                        "content": "\n\n如果您需要更具体的帮助，建议您联系Harry。",
                                    }
                            break

                    iter_time = time.time() - iter_start_time
                    logger.info(f"[PERF] Iteration {iteration} total time: {iter_time:.3f}s")

                    # Check if we're done
                    if accumulated_content:
                        logger.info(
                            f"Completed with content (length: {len(accumulated_content)})"
                        )
                        # Check if tools were used but didn't find useful information
                        if iteration > 1:
                            tools_used_but_no_info = check_tools_used_but_no_info(messages)
                            if tools_used_but_no_info and not response_suggests_contact_harry(
                                accumulated_content
                            ):
                                yield {
                                    "type": "chunk",
                                    "content": "\n\n如果您需要更具体的帮助，建议您联系Harry。",
                                }
                        break
                    elif iteration >= self.max_tool_iterations:
                        logger.warning(
                            f"Reached max iterations ({self.max_tool_iterations}) without content"
                        )
                        if not accumulated_content:
                            tools_used_but_no_info = check_tools_used_but_no_info(messages)
                            if tools_used_but_no_info:
                                yield {
                                    "type": "chunk",
                                    "content": "很抱歉，我尝试了多种方法查找相关信息，但未能找到您问题的答案。建议您联系Harry获取更具体的帮助。",
                                }
                            else:
                                yield {
                                    "type": "chunk",
                                    "content": "抱歉，处理请求时遇到问题，请重试。",
                                }
                        break

                except LLMError as exc:
                    error_msg = format_error_message(exc, "Error processing request")
                    yield {"type": "chunk", "content": error_msg}
                    break
                except Exception as exc:
                    logger.error(
                        f"Unexpected error during LLM streaming: {exc}", exc_info=True
                    )
                    yield {
                        "type": "chunk",
                        "content": f"An unexpected error occurred: {str(exc)}",
                    }
                    break

            if iteration >= self.max_tool_iterations:
                logger.warning(
                    f"Reached maximum tool calling iterations ({self.max_tool_iterations})"
                )

            total_time = time.time() - chat_start_time
            logger.info(
                f"[PERF] Total chat_stream took {total_time:.3f}s, "
                f"completed {iteration} iterations"
            )

        except Exception as exc:
            total_time = time.time() - chat_start_time
            logger.error(
                f"[PERF] chat_stream failed after {total_time:.3f}s: {exc}", exc_info=True
            )
            yield {
                "type": "chunk",
                "content": f"An error occurred while processing your request: {str(exc)}",
            }
