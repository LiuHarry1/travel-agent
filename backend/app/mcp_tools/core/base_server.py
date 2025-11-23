"""Base classes for MCP servers."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Dummy classes for type hints when MCP is not available
    class Server:
        pass
    class Tool:
        pass
    class TextContent:
        pass

from .base_tool import BaseMCPTool

logger = logging.getLogger(__name__)


class BaseMCPServer:
    """Base class for MCP servers."""
    
    def __init__(self, server_name: str, tools: List[BaseMCPTool]):
        """
        Initialize MCP server.
        
        Args:
            server_name: Name of the server
            tools: List of tools provided by this server
        """
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not available. Please install mcp package (requires Python >= 3.10).")
        
        self.server_name = server_name
        self.tools = {tool.name: tool for tool in tools}
        self.app = Server(server_name)
        self.logger = logging.getLogger(f"{__name__}.{server_name}")
        
        # Register handlers
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register MCP server handlers."""
        
        @self.app.list_tools()
        async def list_tools() -> list[Tool]:
            """List all available tools."""
            return [
                Tool(
                    name=tool.name,
                    description=tool.description,
                    inputSchema=tool.get_input_schema()
                )
                for tool in self.tools.values()
            ]
        
        @self.app.call_tool()
        async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
            """Execute a tool call."""
            self.logger.info(f"[{self.server_name}] Calling tool: {name} with arguments: {arguments}")
            
            tool = self.tools.get(name)
            if not tool:
                error_msg = f"Unknown tool: {name}. Available tools: {list(self.tools.keys())}"
                self.logger.error(f"[{self.server_name}] {error_msg}")
                return [TextContent(type="text", text=f"Error: {error_msg}")]
            
            try:
                result = await tool.execute_with_validation(arguments)
                
                if result.success:
                    # Format successful result
                    response_text = self._format_tool_result(result)
                    metadata_info = ""
                    if result.metadata:
                        metadata_info = f" (metadata: {result.metadata})"
                    self.logger.info(f"[{self.server_name}] Tool '{name}' executed successfully{metadata_info}")
                    return [TextContent(type="text", text=response_text)]
                else:
                    # Format error result
                    error_msg = result.error or "Unknown error"
                    self.logger.error(f"[{self.server_name}] Tool '{name}' failed: {error_msg}")
                    return [TextContent(type="text", text=f"Error: {error_msg}")]
            
            except Exception as e:
                error_msg = f"Error executing tool {name}: {str(e)}"
                self.logger.error(f"[{self.server_name}] {error_msg}", exc_info=True)
                return [TextContent(type="text", text=f"Error: {error_msg}")]
    
    def _format_tool_result(self, result: Any) -> str:
        """
        Format tool execution result as text.
        This method handles ToolExecutionResult and dict formats.
        
        Args:
            result: ToolExecutionResult or dict
            
        Returns:
            Formatted text string
        """
        # Handle ToolExecutionResult
        if hasattr(result, 'data') and hasattr(result, 'success'):
            if not result.success:
                return f"Error: {result.error or 'Unknown error'}"
            return self._format_tool_result(result.data)
        
        if isinstance(result, dict):
            # Handle dict results
            if "error" in result:
                return f"Error: {result['error']}"
            
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
    
    def run(self) -> None:
        """Run the MCP server using stdio transport."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        
        async def run_server():
            async with stdio_server() as streams:
                await self.app.run(streams[0], streams[1], self.app.create_initialization_options())
        
        asyncio.run(run_server())


def create_mcp_server(server_name: str, tools: List[BaseMCPTool]) -> BaseMCPServer:
    """
    Factory function to create an MCP server.
    
    Args:
        server_name: Name of the server
        tools: List of tools to register
        
    Returns:
        Configured MCP server instance
    """
    return BaseMCPServer(server_name, tools)
