"""基础工具类"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class ToolExecutionResult:
    """工具执行结果"""
    success: bool
    data: Any
    error: Optional[str] = None


class BaseTool(ABC):
    """基础工具类"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """执行工具"""
        pass
    
    def get_input_schema(self) -> Dict[str, Any]:
        """获取输入 schema"""
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    async def execute_with_validation(self, arguments: Dict[str, Any]) -> ToolExecutionResult:
        """执行工具（带验证）"""
        try:
            return await self.execute(arguments)
        except Exception as e:
            return ToolExecutionResult(
                success=False,
                data=None,
                error=str(e)
            )

