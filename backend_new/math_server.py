"""简单的数学服务器 MCP 工具（用于测试 WebSocket 传输）"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

try:
    from mcp.server import Server
    from mcp.server.sse import sse_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("MCP SDK not available. Please install: pip install mcp")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 MCP 服务器
app = Server("math-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用工具"""
    return [
        Tool(
            name="add",
            description="Add two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number"
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number"
                    }
                },
                "required": ["a", "b"]
            }
        ),
        Tool(
            name="multiply",
            description="Multiply two numbers",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number"
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number"
                    }
                },
                "required": ["a", "b"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """执行工具调用"""
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    a = arguments.get("a")
    b = arguments.get("b")
    
    if name == "add":
        result = a + b
        return [TextContent(type="text", text=json.dumps({"result": result, "operation": "add", "a": a, "b": b}))]
    
    elif name == "multiply":
        result = a * b
        return [TextContent(type="text", text=json.dumps({"result": result, "operation": "multiply", "a": a, "b": b}))]
    
    else:
        return [TextContent(type="text", text=f"Error: Unknown tool: {name}")]


async def main():
    """运行 MCP 服务器（WebSocket）"""
    # 注意：MCP SDK 的 WebSocket 服务器实现可能需要不同的方式
    # 这里使用 stdio 作为示例，实际 WebSocket 需要不同的实现
    from mcp.server.stdio import stdio_server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

