"""简单的文件服务器 MCP 工具（用于测试 stdio 传输）"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    print("MCP SDK not available. Please install: pip install mcp")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建 MCP 服务器
app = Server("file-server")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """列出所有可用工具"""
    return [
        Tool(
            name="read_file",
            description="Read content from a file",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="list_files",
            description="List files in a directory",
            inputSchema={
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path to list files from"
                    }
                },
                "required": ["directory"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
    """执行工具调用"""
    logger.info(f"Calling tool: {name} with arguments: {arguments}")
    
    if name == "read_file":
        file_path = arguments.get("file_path")
        if not file_path:
            return [TextContent(type="text", text="Error: file_path is required")]
        
        try:
            path = Path(file_path)
            if not path.exists():
                return [TextContent(type="text", text=f"Error: File not found: {file_path}")]
            
            content = path.read_text(encoding="utf-8")
            result = {
                "success": True,
                "file_path": str(path),
                "content": content,
                "size": len(content)
            }
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error reading file: {str(e)}")]
    
    elif name == "list_files":
        directory = arguments.get("directory")
        if not directory:
            return [TextContent(type="text", text="Error: directory is required")]
        
        try:
            path = Path(directory)
            if not path.exists():
                return [TextContent(type="text", text=f"Error: Directory not found: {directory}")]
            
            if not path.is_dir():
                return [TextContent(type="text", text=f"Error: Not a directory: {directory}")]
            
            files = []
            for item in path.iterdir():
                files.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
            
            result = {
                "success": True,
                "directory": str(path),
                "files": files,
                "count": len(files)
            }
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=f"Error listing files: {str(e)}")]
    
    else:
        return [TextContent(type="text", text=f"Error: Unknown tool: {name}")]


async def main():
    """运行 MCP 服务器"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

