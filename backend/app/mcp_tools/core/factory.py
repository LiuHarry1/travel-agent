"""Factory for creating MCP tools and servers."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Type

from .base_tool import BaseMCPTool
from .base_server import BaseMCPServer

logger = logging.getLogger(__name__)


class MCPToolFactory:
    """Factory for creating and registering MCP tools."""
    
    _tool_registry: Dict[str, Type[BaseMCPTool]] = {}
    
    @classmethod
    def register_tool(cls, tool_class: Type[BaseMCPTool]) -> None:
        """
        Register a tool class.
        
        Args:
            tool_class: Tool class to register
        """
        tool_instance = tool_class()
        cls._tool_registry[tool_instance.name] = tool_class
        logger.debug(f"Registered tool: {tool_instance.name}")
    
    @classmethod
    def create_tool(cls, tool_name: str, **kwargs) -> Optional[BaseMCPTool]:
        """
        Create a tool instance by name.
        
        Args:
            tool_name: Name of the tool
            **kwargs: Additional arguments for tool initialization
            
        Returns:
            Tool instance or None if not found
        """
        tool_class = cls._tool_registry.get(tool_name)
        if tool_class:
            return tool_class(**kwargs)
        return None
    
    @classmethod
    def list_registered_tools(cls) -> List[str]:
        """List all registered tool names."""
        return list(cls._tool_registry.keys())


class MCPServerFactory:
    """Factory for creating MCP servers."""
    
    _server_factories: Dict[str, callable] = {}
    
    @classmethod
    def register_server(cls, server_name: str, factory_func: callable) -> None:
        """
        Register a server factory function.
        
        Args:
            server_name: Name of the server
            factory_func: Function that creates the server
        """
        cls._server_factories[server_name] = factory_func
        logger.debug(f"Registered server factory: {server_name}")
    
    @classmethod
    def create_server(cls, server_name: str, **kwargs) -> Optional[BaseMCPServer]:
        """
        Create a server instance by name.
        
        Args:
            server_name: Name of the server
            **kwargs: Additional arguments for server creation
            
        Returns:
            Server instance or None if not found
        """
        factory_func = cls._server_factories.get(server_name)
        if factory_func:
            return factory_func(**kwargs)
        return None
    
    @classmethod
    def list_registered_servers(cls) -> List[str]:
        """List all registered server names."""
        return list(cls._server_factories.keys())

