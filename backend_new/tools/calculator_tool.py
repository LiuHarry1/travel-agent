"""简单的计算器工具"""
from __future__ import annotations

from typing import Any, Dict

from .base_tool import BaseTool, ToolExecutionResult


class CalculatorTool(BaseTool):
    """简单的计算器工具 - 用于测试"""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Perform basic arithmetic operations (add, subtract, multiply, divide)"
        )
    
    def get_input_schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "The arithmetic operation to perform"
                },
                "a": {
                    "type": "number",
                    "description": "First number"
                },
                "b": {
                    "type": "number",
                    "description": "Second number"
                }
            },
            "required": ["operation", "a", "b"]
        }
    
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """执行计算"""
        operation = arguments.get("operation")
        a = arguments.get("a")
        b = arguments.get("b")
        
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                return ToolExecutionResult(
                    success=False,
                    data=None,
                    error="Division by zero"
                )
            result = a / b
        else:
            return ToolExecutionResult(
                success=False,
                data=None,
                error=f"Unknown operation: {operation}"
            )
        
        return ToolExecutionResult(
            success=True,
            data={"result": result, "operation": operation, "a": a, "b": b}
        )

