"""MCP client for connecting to MCP servers."""
from __future__ import annotations

import asyncio
import json
import logging
import subprocess
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("MCP SDK not available, using fallback implementation")

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to MCP servers via stdio."""
    
    def __init__(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None):
        """
        Initialize MCP client.
        
        Args:
            command: Command to start the MCP server (e.g., "python", "npx")
            args: Arguments for the command (e.g., ["-m", "app.mcp.faq.server"])
            env: Environment variables to pass to the server process
            cwd: Working directory for the server process
        """
        self.command = command
        self.args = args
        self.env = env or {}
        self.cwd = cwd
        self.session: Optional[ClientSession] = None
        self._initialized = False
        self._tools: List[Dict[str, Any]] = []
        
        # Create server parameters with environment variables and working directory
        if MCP_AVAILABLE:
            # Prepare environment variables
            server_env = dict(env) if env else {}
            
            # For Python module servers, ensure PYTHONPATH includes the working directory
            if cwd and command == "python":
                import os
                pythonpath = server_env.get("PYTHONPATH", "")
                if pythonpath:
                    pythonpath = f"{cwd}{os.pathsep}{pythonpath}"
                else:
                    pythonpath = cwd
                server_env["PYTHONPATH"] = pythonpath
            
            try:
                # StdioServerParameters supports command, args, env, and cwd
                self._server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=server_env if server_env else None,
                    cwd=cwd
                )
            except TypeError:
                # Fallback if cwd is not supported
                try:
                    self._server_params = StdioServerParameters(
                        command=command,
                        args=args,
                        env=server_env if server_env else None
                    )
                except TypeError:
                    # Fallback if env is not supported either
                    self._server_params = StdioServerParameters(
                        command=command,
                        args=args
                    )
        else:
            self._server_params = None
    
    async def initialize(self) -> None:
        """Initialize connection to MCP server and get tools list."""
        if self._initialized:
            return
        
        # Re-check MCP SDK availability at runtime (in case it was installed after module import)
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            runtime_mcp_available = True
        except ImportError:
            runtime_mcp_available = False
        
        if not runtime_mcp_available and not MCP_AVAILABLE:
            logger.error("[MCPClient] MCP SDK not available. Please install mcp package.")
            raise RuntimeError("MCP SDK not available")
        
        # If MCP SDK is available but _server_params is None, recreate it
        if runtime_mcp_available and (not hasattr(self, '_server_params') or self._server_params is None):
            from mcp import StdioServerParameters
            import os
            
            # Prepare environment variables
            server_env = dict(self.env) if self.env else {}
            
            # For Python module servers, ensure PYTHONPATH includes the working directory
            if self.cwd and self.command == "python":
                pythonpath = server_env.get("PYTHONPATH", "")
                if pythonpath:
                    pythonpath = f"{self.cwd}{os.pathsep}{pythonpath}"
                else:
                    pythonpath = self.cwd
                server_env["PYTHONPATH"] = pythonpath
            
            try:
                self._server_params = StdioServerParameters(
                    command=self.command,
                    args=self.args,
                    env=server_env if server_env else None,
                    cwd=self.cwd
                )
            except TypeError:
                # Fallback if cwd is not supported
                try:
                    self._server_params = StdioServerParameters(
                        command=self.command,
                        args=self.args,
                        env=server_env if server_env else None
                    )
                except TypeError:
                    # Fallback if env is not supported either
                    self._server_params = StdioServerParameters(
                        command=self.command,
                        args=self.args
                    )
        
        try:
            # Import at runtime to ensure MCP SDK is available
            import sys
            import asyncio
            import os
            from pathlib import Path
            
            # Ensure Windows uses ProactorEventLoop for subprocess support
            if sys.platform == "win32":
                if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            
            # Log server parameters for debugging
            logger.info(f"[MCPClient] Initializing connection with command: {self.command}, args: {self.args}")
            if self.cwd:
                logger.info(f"[MCPClient] Working directory: {self.cwd}")
            if self.env:
                logger.info(f"[MCPClient] Environment variables: {list(self.env.keys())}")
            
            # Verify working directory exists if specified
            if self.cwd and not Path(self.cwd).exists():
                logger.warning(f"[MCPClient] Working directory does not exist: {self.cwd}")
            
            from mcp.client.stdio import stdio_client
            from mcp import ClientSession
            
            # Create stdio client connection
            logger.info(f"[MCPClient] Creating stdio client connection...")
            async with stdio_client(self._server_params) as (read, write):
                logger.info(f"[MCPClient] Stdio client connected, creating session...")
                async with ClientSession(read, write) as session:
                    # Initialize the session
                    logger.info(f"[MCPClient] Initializing MCP session...")
                    await session.initialize()
                    logger.info(f"[MCPClient] MCP session initialized successfully")
                    
                    # Get tools list
                    tools_result = await session.list_tools()
                    self._tools = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools_result.tools
                    ]
                    
                    logger.info(f"[MCPClient] Connected to server and loaded {len(self._tools)} tools")
                    
                    # Store session for later use (note: this won't work with context manager)
                    # We need to keep the connection alive
                    self.session = session
                    self._initialized = True
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[MCPClient] Failed to initialize connection: {error_msg}")
            logger.error(f"[MCPClient] Command: {self.command}, Args: {self.args}")
            logger.error(f"[MCPClient] Working directory: {self.cwd}")
            logger.error(f"[MCPClient] Full error details:", exc_info=True)
            
            # Try to get more details about the subprocess error
            if "Connection closed" in error_msg:
                logger.error(f"[MCPClient] Connection closed - this usually means the MCP server process failed to start or crashed immediately")
                logger.error(f"[MCPClient] Please check:")
                logger.error(f"[MCPClient]   1. The MCP server module can be imported: python -m {self.args[1] if len(self.args) > 1 else 'N/A'}")
                logger.error(f"[MCPClient]   2. The working directory is correct: {self.cwd or 'Not set'}")
                logger.error(f"[MCPClient]   3. Python can find the module from the working directory")
            
            raise
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of tools from MCP server."""
        if not self._initialized:
            await self.initialize()
        
        return self._tools
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the MCP server.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        # Re-check MCP SDK availability at runtime
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            runtime_mcp_available = True
        except ImportError:
            runtime_mcp_available = False
        
        if not runtime_mcp_available and not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not available")
        
        if not self._initialized:
            await self.initialize()
        
        # Recreate connection for each call (since we can't keep it alive easily)
        # Import at runtime to ensure MCP SDK is available
        from mcp.client.stdio import stdio_client
        from mcp import ClientSession
        
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Call the tool
                result = await session.call_tool(name, arguments)
                
                # Extract text content from result
                if result.content and len(result.content) > 0:
                    # Get text from first content item
                    text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                    # Try to parse as JSON, otherwise return as text
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"text": text}
        
        return {}
    
    def close(self) -> None:
        """Close the connection to MCP server."""
        # Session is managed by context manager, so we just mark as uninitialized
        self._initialized = False
        self.session = None

