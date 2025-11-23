"""Tool result formatting logic for chat service."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def format_tool_result_for_llm(tool_result: Any, tool_name: str) -> str:
    """
    Format tool result for LLM consumption.
    
    Args:
        tool_result: Tool execution result (can be str, dict, or other)
        tool_name: Name of the tool (for logging)
        
    Returns:
        Formatted string content for LLM
    """
    if isinstance(tool_result, str):
        logger.debug(f"Tool {tool_name} returned string result (length: {len(tool_result)})")
        return tool_result
    elif isinstance(tool_result, dict):
        # If it's a dict, check if it has a 'text' key (from MCPClient fallback)
        if "text" in tool_result:
            logger.debug(f"Tool {tool_name} returned dict with 'text' key (length: {len(tool_result['text'])})")
            return tool_result["text"]
        
        # Handle tools that return answer field but didn't find a match
        # Check based on data structure, not tool name (tool-agnostic)
        if "answer" in tool_result or "found" in tool_result:
            found = tool_result.get("found", tool_result.get("answer") is not None)
            if not found or tool_result.get("answer") is None:
                # Tool didn't find an answer - format clearly for LLM
                message = tool_result.get("message", "未找到匹配的答案。")
                formatted = f"工具结果: {message}\n建议: 可以尝试使用其他工具搜索相关信息。"
                logger.info(f"Tool {tool_name} did not find answer, formatted for LLM: {formatted[:100]}")
                return formatted
        
        # Handle tools that return results field but found no results
        # Check based on data structure, not tool name (tool-agnostic)
        if "results" in tool_result:
            results = tool_result.get("results", [])
            if not results or len(results) == 0:
                # No results found - format clearly for LLM
                formatted = "工具结果: 在知识库中没有找到相关信息。\n建议: 如果所有工具都没有找到有用信息，可以提醒用户联系Harry获取更具体的帮助。"
                logger.info(f"Tool {tool_name} found no results, formatted for LLM")
                return formatted
        
        # Otherwise, serialize the dict as JSON
        content = json.dumps(tool_result, ensure_ascii=False)
        logger.debug(f"Tool {tool_name} returned dict (serialized length: {len(content)}, keys: {list(tool_result.keys())})")
        return content
    else:
        # Fallback: convert to string
        content = str(tool_result)
        logger.debug(f"Tool {tool_name} returned non-string/dict result (converted length: {len(content)})")
        return content


def check_tools_used_but_no_info(messages: list[dict[str, str]]) -> bool:
    """
    Check if tools were used but didn't find useful information.
    
    Args:
        messages: Conversation messages
        
    Returns:
        True if tools were used but didn't find useful information
    """
    tool_messages = [msg for msg in messages if msg.get("role") == "tool"]
    if not tool_messages:
        return False
    
    # Check if any tool message indicates no useful information was found
    for msg in tool_messages:
        content = msg.get("content", "")
        # Check for indicators that tools didn't find useful information
        if any(indicator in content for indicator in [
            "没有找到",
            "没有找到匹配",
            "没有找到相关信息",
            "未能找到",
            "找不到",
            "无法找到"
        ]):
            return True
    
    return False


def response_suggests_contact_harry(content: str) -> bool:
    """
    Check if the response already suggests contacting Harry.
    
    Args:
        content: Response content
        
    Returns:
        True if response already suggests contacting Harry
    """
    harry_indicators = ["联系Harry", "联系harry", "联系 Harry", "联系 harry", "contact Harry", "contact harry"]
    return any(indicator in content for indicator in harry_indicators)

