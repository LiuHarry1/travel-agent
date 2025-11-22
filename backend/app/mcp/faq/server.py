"""Standard MCP server for FAQ tool."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .tool import FAQTool

logger = logging.getLogger(__name__)

# Create server instance
app = Server("faq-server")

# Initialize tool implementation
faq_tool = FAQTool()


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="faq",
            description="Search travel FAQ knowledge base for answers to common travel questions",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The travel-related question to search in FAQ"
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
    logger.info(f"[FAQ MCP Server] Calling tool: {name} with arguments: {arguments}")
    
    try:
        if name == "faq":
            result = await faq_tool.execute(arguments)
            
            # Log after successful execution
            answer = result.get("answer", "")
            matched_key = result.get("matched_key")
            logger.info(f"[FAQ MCP Server] Tool '{name}' executed successfully. Matched key: {matched_key}, Answer length: {len(answer)} chars")
            
            # Format result as text content
            source = result.get("source", "")
            
            response_text = answer
            if matched_key:
                response_text += f"\n\n(Matched topic: {matched_key}, Source: {source})"
            
            return [TextContent(type="text", text=response_text)]
        else:
            error_msg = f"Unknown tool: {name}"
            logger.error(f"[FAQ MCP Server] {error_msg}")
            return [TextContent(type="text", text=f"Error: {error_msg}")]
    
    except Exception as e:
        error_msg = f"Error executing tool {name}: {str(e)}"
        logger.error(f"[FAQ MCP Server] {error_msg}", exc_info=True)
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

