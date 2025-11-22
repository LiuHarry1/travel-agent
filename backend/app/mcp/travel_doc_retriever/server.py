"""Standard MCP server for travel document retriever tool."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tool import RetrieverTool

logger = logging.getLogger(__name__)

# Create server instance
app = Server("travel-doc-retriever-server")

# Initialize tool implementation
retriever_tool = RetrieverTool()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="retriever",
            description="Retrieve relevant information from vectorized knowledge database containing travel documents, guides, and resources",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to retrieve relevant travel information"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 5
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
    logger.info(f"[Travel Doc Retriever MCP Server] Calling tool: {name} with arguments: {arguments}")
    
    try:
        if name == "retriever":
            result = await retriever_tool.execute(arguments)
            
            # Log after successful execution
            query = result.get("query", "")
            results = result.get("results", [])
            total_found = result.get("total_found", 0)
            logger.info(f"[Travel Doc Retriever MCP Server] Tool '{name}' executed successfully. Query: '{query}', Found {total_found} results")
            
            # Format results as text content
            source = result.get("source", "")
            
            response_parts = [f"Found {total_found} results for query: {query}\n"]
            
            for i, doc in enumerate(results, 1):
                title = doc.get("title", "")
                content = doc.get("content", "")
                category = doc.get("category", "")
                response_parts.append(f"\n[{i}] {title}")
                if category:
                    response_parts.append(f"Category: {category}")
                response_parts.append(f"Content: {content}")
            
            response_parts.append(f"\nSource: {source}")
            response_text = "\n".join(response_parts)
            
            return [TextContent(type="text", text=response_text)]
        else:
            error_msg = f"Unknown tool: {name}"
            logger.error(f"[Travel Doc Retriever MCP Server] {error_msg}")
            return [TextContent(type="text", text=f"Error: {error_msg}")]
    
    except Exception as e:
        error_msg = f"Error executing tool {name}: {str(e)}"
        logger.error(f"[Travel Doc Retriever MCP Server] {error_msg}", exc_info=True)
        return [TextContent(type="text", text=f"Error: {error_msg}")]


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run the server using stdio transport
    # stdio_server is a context manager that yields (read_stream, write_stream)
    async def run_server():
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())
    
    asyncio.run(run_server())

