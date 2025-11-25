"""工具模块 - 导出所有可用工具"""

from .weather import query_weather, schema as weather_schema
from .calculator import calculate, schema as calculator_schema

# 统一导出所有工具
TOOLS = {
    "query_weather": {
        "schema": weather_schema,
        "function": query_weather
    },
    "calculate": {
        "schema": calculator_schema,
        "function": calculate
    }
}

__all__ = ["TOOLS", "query_weather", "calculate"]
