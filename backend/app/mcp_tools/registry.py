"""MCP tool registry and execution with efficient server management."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .client import MCPClient
from .config import load_mcp_config, MCPToolConfig
from .server_manager import MCPServerManager, ServerType

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
    """
    Registry for MCP tools with efficient server management.
    
    Features:
    - Lazy connection initialization (connect only when needed)
    - Automatic external server installation check
    - Efficient configuration reload
    - Connection pooling and caching
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize registry with tools from MCP servers.
        
        Args:
            config_path: Optional path to mcp.json config file
        """
        self.config_path = config_path
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._tool_to_server: Dict[str, str] = {}
        self._mcp_clients: Dict[str, MCPClient] = {}
        self._client_initialized: Dict[str, bool] = {}  # Track which clients are initialized
        self._fully_initialized: bool = False  # Track if all initialization is complete
        
        # Initialize server manager
        self.server_manager = MCPServerManager(config_path)
        self.server_manager.load_config()
        
        # Create client instances (but don't initialize connections yet)
        self._create_clients()
    
    def _create_clients(self) -> None:
        """Create MCP client instances for all servers (lazy initialization)."""
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent.parent
        
        for server_name, server_config in self.server_manager.servers.items():
            try:
                command = server_config.get("command", "")
                args = server_config.get("args", [])
                env = server_config.get("env", {})
                
                # Set working directory for local Python module servers
                cwd = None
                server_type = self.server_manager._server_types.get(server_name)
                if server_type == ServerType.LOCAL_PYTHON and command == "python" and args and len(args) >= 2 and args[0] == "-m":
                    cwd = str(backend_dir)
                    logger.info(f"[MCPToolRegistry] Setting cwd to {cwd} for local server: {server_name}")
                
                # Create client (connection will be established on first use)
                client = MCPClient(command, args, env=env, cwd=cwd)
                self._mcp_clients[server_name] = client
                self._client_initialized[server_name] = False
                
                logger.info(f"[MCPToolRegistry] Created client for server '{server_name}' (lazy initialization)")
                
            except Exception as e:
                logger.error(f"[MCPToolRegistry] Failed to create client for server {server_name}: {e}", exc_info=True)
        
        logger.info(f"[MCPToolRegistry] Created {len(self._mcp_clients)} MCP clients (lazy initialization)")
    
    def list_tools(self) -> List[MCPToolConfig]:
        """
        List all registered tools (returns MCPToolConfig for backward compatibility).
        
        Returns:
            List of MCPToolConfig objects
        """
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
        """
        List all registered tools as dictionaries.
        
        Returns:
            List of tool dictionaries
        """
        return list(self.tools.values())
    
    async def initialize_all(self) -> None:
        """
        Complete initialization: check MCP SDK, initialize servers, establish connections, load tools.
        
        This method should only be called:
        1. At application startup
        2. After configuration reload
        
        It performs all checks and initialization upfront, so tool calls can be fast.
        """
        import sys
        
        logger.info("[MCPToolRegistry] Starting complete initialization...")
        
        # Check MCP SDK availability
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            logger.info(f"[MCPToolRegistry] MCP SDK is available. Python version: {sys.version}")
        except ImportError as e:
            logger.error(f"[MCPToolRegistry] MCP SDK import failed: {e}. Python version: {sys.version}, Python path: {sys.executable}")
            raise RuntimeError("MCP SDK not available. Please install mcp package (requires Python >= 3.10) to use MCP servers.")
        
        # Initialize server manager (check external servers)
        await self.server_manager.initialize_servers()
        
        # Load tools from each server (establish all connections)
        for server_name, client in self._mcp_clients.items():
            try:
                # Check if server is available
                server_info = self.server_manager.get_server_info(server_name)
                if not server_info.get("is_local", True):
                    # For external servers, verify they're available
                    is_available = await self.server_manager.ensure_external_server_installed(
                        server_name, 
                        self.server_manager.servers[server_name]
                    )
                    if not is_available:
                        logger.warning(f"[MCPToolRegistry] Skipping unavailable server: {server_name}")
                        continue
                
                # Initialize client connection
                if not self._client_initialized.get(server_name, False):
                    logger.info(f"[MCPToolRegistry] Initializing connection to server: {server_name}")
                    await client.initialize()
                    self._client_initialized[server_name] = True
                    
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
                    raise
                else:
                    logger.error(f"[MCPToolRegistry] Failed to load tools from server {server_name}: {e}")
                    logger.warning(f"[MCPToolRegistry] Continuing with other servers despite failure of {server_name}")
            except Exception as e:
                logger.error(f"[MCPToolRegistry] Failed to load tools from server {server_name}: {e}")
                logger.warning(f"[MCPToolRegistry] Continuing with other servers despite failure of {server_name}")
        
        self._fully_initialized = True
        logger.info(f"[MCPToolRegistry] Complete initialization finished. Loaded {len(self.tools)} tools from {len(self._mcp_clients)} servers.")
    
    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call using MCP client.
        
        This method assumes all initialization is complete (done at startup or config reload).
        No checks or initialization are performed here for maximum performance.
        
        Args:
            tool_call: Tool call request
            
        Returns:
            ToolResult with execution result
        """
        logger.info(f"[MCPToolRegistry] Calling tool: {tool_call.name} with arguments: {tool_call.arguments}")
        
        # Direct call - no checks, no initialization (assumes already initialized)
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
            # Direct call - connection should already be established
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
        
        Returns:
            List of function definitions in OpenAI format
        """
        # If not initialized, initialize now (for backward compatibility)
        # But in normal flow, this should already be initialized at startup
        if not self._fully_initialized:
            await self.initialize_all()
        
        functions = []
        for tool in self.tools.values():
            function_def = {
                "name": tool.get("name", ""),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})
            }
            functions.append(function_def)
        
        logger.info(f"[MCPToolRegistry] Generated {len(functions)} function definitions from MCP servers")
        return functions
    
    async def reload_config(self, config_path: Optional[str] = None) -> None:
        """
        Reload MCP configuration and reinitialize servers.
        
        This method gracefully closes existing connections, reloads config, and reinitializes everything.
        Should be called when mcp.json is updated from the admin page.
        
        Args:
            config_path: Optional path to mcp.json config file. If None, uses default path.
        """
        logger.info("[MCPToolRegistry] Reloading MCP configuration...")
        
        # Close existing clients gracefully
        for server_name, client in self._mcp_clients.items():
            try:
                if hasattr(client, 'close'):
                    await client.close()
            except Exception as e:
                logger.warning(f"[MCPToolRegistry] Error closing client for {server_name}: {e}")
        
        # Clear existing state
        self.tools.clear()
        self._tool_to_server.clear()
        self._mcp_clients.clear()
        self._client_initialized.clear()
        self._fully_initialized = False
        
        # Reload server manager configuration
        if config_path:
            self.config_path = config_path
        self.server_manager.reload_config(config_path)
        
        # Create new clients
        self._create_clients()
        
        # Reinitialize everything (check servers, establish connections, load tools)
        await self.initialize_all()
        
        logger.info(f"[MCPToolRegistry] Configuration reloaded and reinitialized. {len(self.tools)} tools loaded from {len(self._mcp_clients)} servers.")
    
    async def close_all(self) -> None:
        """关闭所有持久连接（应用关闭时调用）。"""
        logger.info("[MCPToolRegistry] Closing all persistent connections...")
        
        for server_name, client in self._mcp_clients.items():
            try:
                if hasattr(client, 'close'):
                    await client.close()
            except Exception as e:
                logger.warning(f"[MCPToolRegistry] Error closing {server_name}: {e}")
        
        self._fully_initialized = False
        self._client_initialized.clear()
        logger.info("[MCPToolRegistry] All connections closed")
