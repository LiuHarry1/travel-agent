"""MCP tool registry and execution."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .config import get_mcp_tools, MCPToolConfig

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
    """Registry for MCP tools."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize registry with tools from config."""
        self.tools: Dict[str, MCPToolConfig] = {}
        self._tool_implementations: Dict[str, Any] = {}
        self._load_tools(config_path)
    
    def _load_tools(self, config_path: Optional[str] = None) -> None:
        """Load tools from configuration."""
        tool_configs = get_mcp_tools(config_path)
        
        for tool_config in tool_configs:
            self.tools[tool_config.name] = tool_config
            # Load tool implementation based on type
            implementation = self._load_tool_implementation(tool_config)
            if implementation:
                self._tool_implementations[tool_config.name] = implementation
    
    def _load_tool_implementation(self, tool_config: MCPToolConfig):
        """Load tool implementation based on type."""
        tool_type = tool_config.type
        
        if tool_type == "faq":
            from .tools.faq_tool import FAQTool
            return FAQTool()
        elif tool_type == "retriever":
            from .tools.retriever_tool import RetrieverTool
            return RetrieverTool()
        else:
            logger.warning(f"Unknown tool type: {tool_type} for tool {tool_config.name}")
            return None
    
    def get_tool(self, name: str) -> Optional[Any]:
        """Get tool implementation by name."""
        return self._tool_implementations.get(name)
    
    def get_tool_config(self, name: str) -> Optional[MCPToolConfig]:
        """Get tool configuration by name."""
        return self.tools.get(name)
    
    def list_tools(self) -> list[MCPToolConfig]:
        """List all registered tools."""
        return list(self.tools.values())
    
    async def call_tool(self, tool_call: ToolCall) -> ToolResult:
        """
        Execute a tool call.
        
        Args:
            tool_call: Tool call request
            
        Returns:
            ToolResult with execution result
        """
        tool_impl = self.get_tool(tool_call.name)
        if not tool_impl:
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                result=None,
                error=f"Tool '{tool_call.name}' not found"
            )
        
        try:
            # Call the tool's execute method
            if hasattr(tool_impl, "execute"):
                result = await tool_impl.execute(tool_call.arguments)
            elif hasattr(tool_impl, "__call__"):
                result = await tool_impl(tool_call.arguments)
            else:
                return ToolResult(
                    tool_name=tool_call.name,
                    success=False,
                    result=None,
                    error=f"Tool '{tool_call.name}' does not have execute method"
                )
            
            return ToolResult(
                tool_name=tool_call.name,
                success=True,
                result=result
            )
        except Exception as e:
            logger.error(f"Error executing tool {tool_call.name}: {e}", exc_info=True)
            return ToolResult(
                tool_name=tool_call.name,
                success=False,
                result=None,
                error=str(e)
            )
    
    def get_tool_function_definitions(self) -> list[Dict[str, Any]]:
        """
        Get function definitions for LLM function calling.
        
        Returns:
            List of function definitions in OpenAI format
        """
        functions = []
        
        for tool_config in self.list_tools():
            # Define function schema based on tool type
            if tool_config.type == "faq":
                function_def = {
                    "name": tool_config.name,
                    "description": tool_config.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The travel-related question to search in FAQ"
                            }
                        },
                        "required": ["query"]
                    }
                }
            elif tool_config.type == "retriever":
                function_def = {
                    "name": tool_config.name,
                    "description": tool_config.description,
                    "parameters": {
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
                }
            else:
                # Generic tool definition
                function_def = {
                    "name": tool_config.name,
                    "description": tool_config.description,
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            
            functions.append(function_def)
        
        return functions

