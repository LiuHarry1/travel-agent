"""MCP Server Manager - Handles external and local MCP servers."""
from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ServerType(Enum):
    """Type of MCP server."""
    LOCAL_PYTHON = "local_python"  # Python module server (app.mcp_tools.*)
    EXTERNAL_NPX = "external_npx"  # External npm package via npx
    EXTERNAL_PYTHON = "external_python"  # External Python package
    EXTERNAL_BINARY = "external_binary"  # External binary executable


class MCPServerManager:
    """
    Manages MCP servers (both local and external).
    
    Responsibilities:
    - Detect server type (local vs external)
    - Ensure external servers are installed
    - Manage server lifecycle
    - Handle configuration updates
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize server manager.
        
        Args:
            config_path: Path to mcp.json config file
        """
        self.config_path = config_path
        self.servers: Dict[str, Dict[str, Any]] = {}
        self._server_types: Dict[str, ServerType] = {}
        self._initialized = False
    
    def load_config(self) -> Dict[str, Any]:
        """Load MCP configuration from file."""
        from .config import load_mcp_config
        config = load_mcp_config(self.config_path)
        self.servers = config.get("mcpServers", {})
        return config
    
    def detect_server_type(self, server_name: str, server_config: Dict[str, Any]) -> ServerType:
        """
        Detect the type of MCP server.
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
            
        Returns:
            ServerType enum
        """
        command = server_config.get("command", "").lower()
        args = server_config.get("args", [])
        
        if command == "python" and args:
            # Check if it's a local Python module
            if len(args) >= 2 and args[0] == "-m":
                module_name = args[1]
                if module_name.startswith("app.mcp_tools."):
                    return ServerType.LOCAL_PYTHON
                else:
                    return ServerType.EXTERNAL_PYTHON
        elif command == "npx":
            return ServerType.EXTERNAL_NPX
        else:
            # Assume it's an external binary
            return ServerType.EXTERNAL_BINARY
    
    async def ensure_external_server_installed(self, server_name: str, server_config: Dict[str, Any]) -> bool:
        """
        Ensure external server is installed (for npx servers).
        
        Args:
            server_name: Name of the server
            server_config: Server configuration
            
        Returns:
            True if server is available, False otherwise
        """
        server_type = self.detect_server_type(server_name, server_config)
        
        if server_type == ServerType.EXTERNAL_NPX:
            # npx automatically downloads packages, so we just verify it's available
            command = server_config.get("command", "")
            args = server_config.get("args", [])
            
            try:
                # First, check if command exists in PATH (more reliable than subprocess)
                command_path = shutil.which(command)
                if not command_path:
                    logger.warning(f"[ServerManager] Command '{command}' not found in PATH for server '{server_name}'")
                    return False
                
                logger.debug(f"[ServerManager] Found '{command}' at: {command_path}")
                
                # Try async subprocess first, fallback to sync if needed
                try:
                    result = await asyncio.create_subprocess_exec(
                        command, "--version",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5.0)
                    await result.wait()
                    if result.returncode == 0:
                        version_info = stdout.decode('utf-8', errors='ignore').strip()[:50]
                        logger.info(f"[ServerManager] npx is available for server '{server_name}' (version: {version_info})")
                        return True
                    else:
                        logger.warning(f"[ServerManager] npx version check failed for server '{server_name}' (return code: {result.returncode})")
                        return False
                except asyncio.TimeoutError:
                    logger.warning(f"[ServerManager] npx version check timed out for server '{server_name}'")
                    return False
                except (NotImplementedError, RuntimeError):
                    # Fallback to synchronous subprocess if async is not supported
                    logger.debug(f"[ServerManager] Async subprocess not supported, using sync fallback for '{server_name}'")
                    try:
                        result = subprocess.run(
                            [command, "--version"],
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        if result.returncode == 0:
                            logger.info(f"[ServerManager] npx is available for server '{server_name}' (sync check)")
                            return True
                        else:
                            logger.warning(f"[ServerManager] npx version check failed for server '{server_name}' (return code: {result.returncode})")
                            return False
                    except subprocess.TimeoutExpired:
                        logger.warning(f"[ServerManager] npx version check timed out for server '{server_name}'")
                        return False
                    except Exception as e2:
                        logger.warning(f"[ServerManager] Sync fallback also failed for '{server_name}': {e2}")
                        # If command exists, assume it's available even if version check fails
                        logger.info(f"[ServerManager] Assuming '{command}' is available (found in PATH)")
                        return True
                except Exception as e:
                    logger.warning(f"[ServerManager] Failed to check npx version for server '{server_name}': {e}")
                    # If command exists, assume it's available even if version check fails
                    logger.info(f"[ServerManager] Assuming '{command}' is available (found in PATH)")
                    return True
                
            except Exception as e:
                logger.error(f"[ServerManager] Failed to check npx for server '{server_name}': {e}", exc_info=True)
                return False
        
        elif server_type == ServerType.EXTERNAL_PYTHON:
            # For external Python packages, check if module is importable
            args = server_config.get("args", [])
            if len(args) >= 2 and args[0] == "-m":
                module_name = args[1]
                try:
                    # Try to import the module
                    __import__(module_name)
                    logger.info(f"[ServerManager] External Python module '{module_name}' is available")
                    return True
                except ImportError:
                    logger.warning(f"[ServerManager] External Python module '{module_name}' not found. Please install it.")
                    return False
        
        # Local servers don't need installation
        return True
    
    async def initialize_servers(self) -> Dict[str, bool]:
        """
        Initialize all servers (check external servers, prepare local servers).
        
        Returns:
            Dictionary mapping server names to initialization success status
        """
        if self._initialized:
            return {name: True for name in self.servers.keys()}
        
        results = {}
        
        for server_name, server_config in self.servers.items():
            try:
                # Detect server type
                server_type = self.detect_server_type(server_name, server_config)
                self._server_types[server_name] = server_type
                
                logger.info(f"[ServerManager] Detected server '{server_name}' as {server_type.value}")
                
                # For external servers, ensure they're installed
                if server_type in (ServerType.EXTERNAL_NPX, ServerType.EXTERNAL_PYTHON):
                    is_available = await self.ensure_external_server_installed(server_name, server_config)
                    results[server_name] = is_available
                    if not is_available:
                        logger.warning(f"[ServerManager] Server '{server_name}' is not available")
                else:
                    # Local servers are always available
                    results[server_name] = True
                    
            except Exception as e:
                logger.error(f"[ServerManager] Failed to initialize server '{server_name}': {e}", exc_info=True)
                results[server_name] = False
        
        self._initialized = True
        return results
    
    def get_server_info(self, server_name: str) -> Dict[str, Any]:
        """Get information about a server."""
        if server_name not in self.servers:
            return {}
        
        server_config = self.servers[server_name]
        server_type = self._server_types.get(server_name)
        
        return {
            "name": server_name,
            "type": server_type.value if server_type else "unknown",
            "command": server_config.get("command", ""),
            "args": server_config.get("args", []),
            "env": server_config.get("env", {}),
            "is_local": server_type == ServerType.LOCAL_PYTHON if server_type else False,
        }
    
    def list_servers(self) -> List[Dict[str, Any]]:
        """List all configured servers with their information."""
        return [self.get_server_info(name) for name in self.servers.keys()]
    
    def reload_config(self, config_path: Optional[str] = None) -> None:
        """Reload configuration from file."""
        if config_path:
            self.config_path = config_path
        self.load_config()
        self._server_types.clear()
        self._initialized = False

