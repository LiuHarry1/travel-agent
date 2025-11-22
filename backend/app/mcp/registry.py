"""MCP tool registry and execution."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .client import MCPClient
from .config import load_mcp_config, MCPToolConfig

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call request."""
    name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None


@dataclass
class ToolResult:
    """Represents the result of a tool call."""
    tool_name: str
    success: bool
    result: Any
    error: Optional[str] = None


class MCPToolRegistry:
    """Registry for MCP tools that loads tool definitions from MCP servers."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize registry with tools from MCP servers."""
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._tool_to_server: Dict[str, str] = {}  # Map tool name to server name
        self._mcp_clients: Dict[str, MCPClient] = {}  # Map server name to MCP client
        self._load_tools_from_servers(config_path)
    
    def _load_tools_from_servers(self, config_path: Optional[str] = None) -> None:
        """Load tool definitions from MCP servers using standard MCP SDK."""
        config = load_mcp_config(config_path)
        servers = config.get("mcpServers", {})
        
        logger.info(f"[MCPToolRegistry] Loading tools from {len(servers)} MCP servers")
        
        # All servers (internal and external) are connected via MCP client
        self._mcp_clients: Dict[str, MCPClient] = {}
        
        # Get backend directory for setting working directory
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent.parent
        
        # Create MCP clients for all servers
        for server_name, server_config in servers.items():
            try:
                command = server_config.get("command", "")
                args = server_config.get("args", [])
                env = server_config.get("env", {})
                
                # Set working directory to backend directory for Python module servers
                # This ensures Python can find the 'app' module
                cwd = None
                if command == "python" and args and len(args) >= 2 and args[0] == "-m":
                    # Python module server - set cwd to backend directory
                    cwd = str(backend_dir)
                    logger.info(f"[MCPToolRegistry] Setting cwd to {cwd} for Python module server: {server_name}")
                
                # All servers use MCP client (standard MCP protocol)
                logger.info(f"[MCPToolRegistry] Setting up MCP client for server: {server_name}")
                client = MCPClient(command, args, env=env, cwd=cwd)
                # Store client for later initialization
                self._mcp_clients[server_name] = client
                logger.info(f"[MCPToolRegistry] MCP client created for server '{server_name}' (will load tools on first use)")
                
            except Exception as e:
                logger.error(f"[MCPToolRegistry] Failed to create MCP client for server {server_name}: {e}", exc_info=True)
        
        logger.info(f"[MCPToolRegistry] Created {len(self._mcp_clients)} MCP clients (tools will be loaded on first use)")
    
    def list_tools(self) -> List[MCPToolConfig]:
        """List all registered tools (returns MCPToolConfig for backward compatibility)."""
        result = []
        for tool in self.tools.values():
            result.append(MCPToolConfig(
                name=tool.get("name", ""),
                tool_type="",  # Not needed when using MCP servers
                description=tool.get("description", ""),
                inputSchema=tool.get("inputSchema", {})
            ))
        return result
    
    def list_tools_dict(self) -> List[Dict[str, Any]]:
        """List all registered tools as dictionaries."""
        return list(self.tools.values())
    
    async def _ensure_tools_loaded(self) -> None:
        """Lazily load tools from all MCP servers (both internal and external)."""
        # Check MCP SDK availability at runtime (not just at module import time)
        import sys
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            mcp_available = True
            logger.info(f"[MCPToolRegistry] MCP SDK is available. Python version: {sys.version}")
        except ImportError as e:
            mcp_available = False
            logger.error(f"[MCPToolRegistry] MCP SDK import failed: {e}. Python version: {sys.version}, Python path: {sys.executable}")
        
        if not mcp_available:
            logger.error(f"[MCPToolRegistry] MCP SDK not available. Please install mcp package (requires Python >= 3.10).")
            logger.error(f"[MCPToolRegistry] Current Python: {sys.executable}, Version: {sys.version}")
            raise RuntimeError(f"MCP SDK not available. Please install mcp package (requires Python >= 3.10) to use MCP servers.")
        
        for server_name, client in self._mcp_clients.items():
            try:
                if not client._initialized:
                    # Check if MCP SDK is available and _server_params is set
                    # If _server_params is None, the client will recreate it in initialize()
                    logger.info(f"[MCPToolRegistry] Initializing MCP client for server: {server_name}")
                    await client.initialize()
                    
                    # Get tools from this server
                    tools = await client.list_tools()
                    for tool in tools:
                        tool_name = tool.get("name", "")
                        if tool_name and tool_name not in self.tools:
                            self.tools[tool_name] = tool
                            self._tool_to_server[tool_name] = server_name
                            logger.info(f"[MCPToolRegistry] Loaded tool '{tool_name}' from server '{server_name}'")
                
            except RuntimeError as e:
                if "MCP SDK not available" in str(e):
                    logger.error(f"[MCPToolRegistry] MCP SDK not available for server '{server_name}'. Please install mcp package (requires Python >= 3.10).")
                    raise
                else:
                    logger.error(f"[MCPToolRegistry] Failed to load tools from server {server_name}: {e}")
                    logger.warning(f"[MCPToolRegistry] Continuing with other servers despite failure of {server_name}")
            except Exception as e:
                logger.error(f"[MCPToolRegistry] Failed to load tools from server {server_name}: {e}")
                logger.warning(f"[MCPToolRegistry] Continuing with other servers despite failure of {server_name}")
    
    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call using MCP client (standard MCP protocol).
        
        Args:
            tool_call: Tool call request
            
        Returns:
            ToolResult with execution result
        """
        logger.info(f"[MCPToolRegistry] Calling tool: {tool_call.name} with arguments: {tool_call.arguments}")
        
        # Ensure tools are loaded from all servers
        await self._ensure_tools_loaded()
        
        # Find which server this tool belongs to
        server_name = self._tool_to_server.get(tool_call.name)
        if not server_name:
            error_msg = f"Tool '{tool_call.name}' not found. Available tools: {list(self.tools.keys())}"
            logger.error(f"[MCPToolRegistry] {error_msg}")
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                result=None,
                error=error_msg
            )
        
        client = self._mcp_clients.get(server_name)
        if not client:
            error_msg = f"MCP client for server '{server_name}' not found"
            logger.error(f"[MCPToolRegistry] {error_msg}")
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                result=None,
                error=error_msg
            )
        
        try:
            # Call tool via MCP client (standard MCP protocol)
            result = await client.call_tool(tool_call.name, tool_call.arguments)
            logger.info(f"[MCPToolRegistry] Tool '{tool_call.name}' executed successfully via server '{server_name}'")
            
            return ToolResult(
                tool_name=tool_call.name,
                success=True,
                result=result
            )
        except Exception as e:
            logger.error(f"[MCPToolRegistry] Error executing tool {tool_call.name}: {e}", exc_info=True)
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                result=None,
                error=str(e)
            )
    
    async def get_tool_function_definitions(self) -> list[Dict[str, Any]]:
        """
        Get function definitions for LLM function calling from MCP servers.
        Tool definitions are loaded dynamically from MCP server's list_tools().
        
        Returns:
            List of function definitions in OpenAI format
        """
        # Ensure tools are loaded from all servers
        await self._ensure_tools_loaded()
        
        functions = []
        for tool in self.tools.values():
            # Convert MCP Tool format to OpenAI function format
            function_def = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})
            }
            functions.append(function_def)
        
        logger.info(f"[MCPToolRegistry] Generated {len(functions)} function definitions from MCP servers")
        return functions
    
    def get_tool_function_definitions_sync(self) -> list[Dict[str, Any]]:
        """Synchronous wrapper for get_tool_function_definitions."""
        import asyncio
        import sys
        # Fix for Windows: Ensure ProactorEventLoop is used for subprocess support
        if sys.platform == "win32":
            if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.get_tool_function_definitions())

