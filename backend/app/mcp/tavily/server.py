"""Standard MCP server for Tavily search tool."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tool import TavilyTool

logger = logging.getLogger(__name__)

# Create server instance
app = Server("tavily-server")

# Initialize tool implementation
api_key = os.getenv("TAVILY_API_KEY", "")
if not api_key:
    logger.warning("[Tavily MCP Server] TAVILY_API_KEY not set in environment variables")
tavily_tool = TavilyTool(api_key) if api_key else None


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    if not tavily_tool:
        return []
    
    return [
        Tool(
            name="tavily_search",
            description="Search the web using Tavily API for real-time information, news, and data extraction",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to find information on the web"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of search results to return",
                        "default": 5,
                        "minimum": 1,
                        "maximum": 10
                    },
                    "search_depth": {
                        "type": "string",
                        "description": "Search depth: 'basic' for faster results or 'advanced' for more comprehensive results",
                        "enum": ["basic", "advanced"],
                        "default": "basic"
                    }
                },
                "required": ["query"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """Execute a tool call."""
    # Log before calling MCP server
    logger.info(f"[Tavily MCP Server] Calling tool: {name} with arguments: {arguments}")
    
    if not tavily_tool:
        error_msg = "TAVILY_API_KEY not configured. Please set TAVILY_API_KEY environment variable."
        logger.error(f"[Tavily MCP Server] {error_msg}")
        return [TextContent(type="text", text=f"Error: {error_msg}")]
    
    try:
        if name == "tavily_search":
            result = await tavily_tool.execute(arguments)
            
            # Log after successful execution
            query = result.get("query", "")
            results = result.get("results", [])
            answer = result.get("answer", "")
            logger.info(f"[Tavily MCP Server] Tool '{name}' executed successfully. Query: '{query}', Found {len(results)} results")
            
            # Format results as text content
            if "error" in result:
                return [TextContent(type="text", text=f"Error: {result['error']}")]
            
            response_parts = []
            if answer:
                response_parts.append(f"Answer: {answer}\n")
            
            if results:
                response_parts.append(f"Found {len(results)} results:\n")
                for i, item in enumerate(results, 1):
                    title = item.get("title", "")
                    url = item.get("url", "")
                    content = item.get("content", "")
                    response_parts.append(f"\n[{i}] {title}")
                    response_parts.append(f"URL: {url}")
                    if content:
                        response_parts.append(f"Content: {content[:200]}...")
            
            response_text = "\n".join(response_parts)
            return [TextContent(type="text", text=response_text)]
        else:
            error_msg = f"Unknown tool: {name}"
            logger.error(f"[Tavily MCP Server] {error_msg}")
            return [TextContent(type="text", text=f"Error: {error_msg}")]
    
    except Exception as e:
        error_msg = f"Error executing tool {name}: {str(e)}"
        logger.error(f"[Tavily MCP Server] {error_msg}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {error_msg}")]


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run the server using stdio transport
    # stdio_server() returns a context manager that yields (read_stream, write_stream)
    async def run_server():
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())
    
    asyncio.run(run_server())

