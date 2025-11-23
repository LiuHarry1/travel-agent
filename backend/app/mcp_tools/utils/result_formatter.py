"""Utility for formatting tool results."""
from __future__ import annotations

from typing import Any, Dict

from ..core.base_tool import ToolExecutionResult


def format_tool_result(result: Any) -> str:
    """
    Format tool execution result as text.
    
    Args:
        result: ToolExecutionResult or dict
        
    Returns:
        Formatted text string
    """
    # Handle ToolExecutionResult
    if isinstance(result, ToolExecutionResult):
        if not result.success:
            return f"Error: {result.error or 'Unknown error'}"
        return format_tool_result(result.data)
    
    if isinstance(result, dict):
        # Handle dict results
        if "error" in result:
            return f"Error: {result['error']}"
        
        # Format common result patterns based on data structure (tool-agnostic)
        # For results with both answer and results fields: combine them
        # This pattern can be used by any tool, not specific to any tool name
        if "answer" in result and "results" in result:
            answer = result.get("answer", "")
            results = result.get("results", [])
            
            parts = []
            if answer:
                parts.append(answer)
            
            if results:
                parts.append(f"\n\nFound {len(results)} search results:")
                for i, item in enumerate(results, 1):
                    if isinstance(item, dict):
                        title = item.get("title", "")
                        content = item.get("content", "")
                        url = item.get("url", "")
                        parts.append(f"\n[{i}] {title}")
                        if url:
                            parts.append(f"URL: {url}")
                        if content:
                            content_preview = content[:300] + "..." if len(content) > 300 else content
                            parts.append(f"Content: {content_preview}")
                    else:
                        parts.append(f"\n[{i}] {item}")
            
            return "\n".join(parts)
        
        # For results with answer field only: format answer with optional metadata
        # This pattern can be used by any tool that returns an answer field
        if "answer" in result:
            # Handle None answer (when tool doesn't find a match)
            answer = result["answer"]
            if answer is None:
                # Tool didn't find answer - return message if available
                message = result.get("message", "未找到匹配的答案。")
                text = message
            else:
                text = answer or ""
            
            if "matched_key" in result and result["matched_key"]:
                text += f"\n\n(Matched topic: {result['matched_key']})"
            if "source" in result:
                text += f"\n(Source: {result['source']})"
            return text
        
        # For results with results field only: format as list of results
        # This pattern can be used by any tool that returns a list of results
        if "results" in result:
            query = result.get("query", "")
            results = result.get("results", [])
            total = result.get("total_found", len(results))
            
            parts = [f"Found {total} results for query: {query}\n"]
            for i, item in enumerate(results, 1):
                if isinstance(item, dict):
                    title = item.get("title", "")
                    content = item.get("content", "")
                    category = item.get("category", "")
                    url = item.get("url", "")
                    parts.append(f"\n[{i}] {title}")
                    if url:
                        parts.append(f"URL: {url}")
                    if category:
                        parts.append(f"Category: {category}")
                    if content:
                        # Truncate long content
                        content_preview = content[:300] + "..." if len(content) > 300 else content
                        parts.append(f"Content: {content_preview}")
                else:
                    parts.append(f"\n[{i}] {item}")
            
            if "source" in result:
                parts.append(f"\nSource: {result['source']}")
            return "\n".join(parts)
        
        # Generic dict formatting
        return str(result)
    
    # Fallback to string representation
    return str(result)

