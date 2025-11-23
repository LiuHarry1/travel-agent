"""Base classes for MCP tools."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolExecutionResult:
    """Result of tool execution."""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "success": self.success,
            "data": self.data
        }
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class BaseMCPTool(ABC):
    """Base class for all MCP tools."""
    
    def __init__(self, name: str, description: str):
        """
        Initialize base tool.
        
        Args:
            name: Tool name
            description: Tool description
        """
        self.name = name
        self.description = description
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """
        Execute the tool with given arguments.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            ToolExecutionResult with execution result
        """
        pass
    
    def get_input_schema(self) -> Dict[str, Any]:
        """
        Get input schema for the tool.
        
        Returns:
            JSON schema for tool input
        """
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def validate_arguments(self, arguments: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate tool arguments.
        
        Args:
            arguments: Tool arguments to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        schema = self.get_input_schema()
        required = schema.get("required", [])
        
        for field in required:
            if field not in arguments:
                return False, f"Missing required argument: {field}"
        
        return True, None
    
    async def execute_with_validation(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """
        Execute tool with argument validation.
        
        Args:
            arguments: Tool arguments
            
        Returns:
            ToolExecutionResult
        """
        is_valid, error_msg = self.validate_arguments(arguments)
        if not is_valid:
            return ToolExecutionResult(
                success=False,
                data=None,
                error=error_msg
            )
        
        try:
            self.logger.info(f"Executing tool '{self.name}' with arguments: {arguments}")
            result = await self.execute(arguments)
            self.logger.info(f"Tool '{self.name}' executed successfully")
            return result
        except Exception as e:
            self.logger.error(f"Tool '{self.name}' execution failed: {e}", exc_info=True)
            return ToolExecutionResult(
                success=False,
                data=None,
                error=str(e)
            )

