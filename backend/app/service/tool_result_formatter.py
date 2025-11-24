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
        
        # Handle tools that return answer field (like FAQ tool)
        # Check based on data structure, not tool name (tool-agnostic)
        if "answer" in tool_result or "found" in tool_result:
            found = tool_result.get("found", tool_result.get("answer") is not None)
            answer = tool_result.get("answer")
            
            if not found or answer is None:
                # Tool didn't find an answer - format clearly for LLM
                message = tool_result.get("message", "未找到匹配的答案。")
                formatted = f"工具结果: {message}\n建议: 可以尝试使用其他工具搜索相关信息。"
                logger.info(f"Tool {tool_name} did not find answer, formatted for LLM: {formatted[:100]}")
                return formatted
            else:
                # Tool found an answer - format clearly to indicate this is the complete answer
                # Add strong instructions to use ONLY this information
                formatted = f"""工具返回的结果（必须严格基于此结果回答，不要添加其他信息）：

{answer}

【重要提示】这是工具提供的完整答案。你必须：
1. 严格基于上述工具结果来回答用户问题
2. 不要添加工具结果中没有的信息
3. 不要编造或猜测任何细节
4. 如果工具结果已经完整回答了问题，直接使用这个结果回答用户
5. 如果需要对内容进行重新组织，保持所有事实和细节与工具结果完全一致

请基于上述工具结果生成回答。"""
                logger.info(f"Tool {tool_name} found answer, formatted for LLM (length: {len(answer)})")
                return formatted
        
        # Handle tools that return results field but found no results
        # Check based on data structure, not tool name (tool-agnostic)
        if "results" in tool_result:
            results = tool_result.get("results", [])
            if not results or len(results) == 0:
                # No results found - format clearly for LLM
                formatted = """工具返回的结果：在知识库中没有找到相关信息。

【重要提示】由于工具没有找到相关信息，你必须：
1. 明确告诉用户工具没有找到相关信息
2. 不要编造或猜测答案
3. 如果还有其他工具可用，可以建议尝试其他工具
4. 如果所有工具都没有找到有用信息，提醒用户联系Harry获取更具体的帮助"""
                logger.info(f"Tool {tool_name} found no results, formatted for LLM")
                return formatted
            
            # If results are found, format them with instructions
            results_text = json.dumps(results, ensure_ascii=False, indent=2)
            formatted = f"""工具返回的结果（必须严格基于此结果回答，不要添加其他信息）：

{results_text}

【重要提示】这是工具提供的搜索结果。你必须：
1. 严格基于上述工具结果来回答用户问题
2. 从工具结果中提取相关信息并组织成清晰的回答
3. 不要添加工具结果中没有的信息
4. 不要编造或猜测任何细节
5. 如果工具结果不足以完整回答问题，明确说明哪些信息缺失

请基于上述工具结果生成回答。"""
            logger.info(f"Tool {tool_name} found {len(results)} results, formatted for LLM")
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

