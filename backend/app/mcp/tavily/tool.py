"""Tavily search tool implementation."""
from __future__ import annotations

import logging
from typing import Any, Dict

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

logger = logging.getLogger(__name__)


class TavilyTool:
    """Tool for searching the web using Tavily API."""
    
    def __init__(self, api_key: str):
        """
        Initialize Tavily tool.
        
        Args:
            api_key: Tavily API key
        """
        self.api_key = api_key
        self.base_url = "https://api.tavily.com"
    
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Tavily search.
        
        Args:
            arguments: Tool arguments containing:
                - query (str): Search query
                - max_results (int, optional): Maximum number of results (default: 5)
                - search_depth (str, optional): "basic" or "advanced" (default: "basic")
        
        Returns:
            Dictionary with search results
        """
        if not HTTPX_AVAILABLE:
            return {
                "error": "httpx package is required. Please install it: pip install httpx"
            }
        
        query = arguments.get("query", "")
        max_results = arguments.get("max_results", 5)
        search_depth = arguments.get("search_depth", "basic")
        
        if not query:
            return {
                "error": "Query parameter is required"
            }
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "max_results": max_results,
                        "search_depth": search_depth
                    },
                    headers={
                        "Content-Type": "application/json"
                    }
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "query": query,
                    "results": result.get("results", []),
                    "answer": result.get("answer", ""),
                    "response_time": result.get("response_time", 0)
                }
        except httpx.HTTPError as e:
            logger.error(f"[TavilyTool] HTTP error: {e}")
            return {
                "error": f"HTTP error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"[TavilyTool] Error executing search: {e}", exc_info=True)
            return {
                "error": f"Error executing search: {str(e)}"
            }

