"""回显工具"""
from __future__ import annotations

from typing import Any, Dict

from .base_tool import BaseTool, ToolExecutionResult


class EchoTool(BaseTool):
    """简单的回显工具 - 用于测试"""
    
    def __init__(self):
        super().__init__(
            name="echo",
            description="Echo back the input message"
        )
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to echo back"
                }
            },
            "required": ["message"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """执行回显"""
        message = arguments.get("message", "")
        
        return ToolExecutionResult(
            success=True,
            data={"echo": f"Echo: {message}"}
        )

