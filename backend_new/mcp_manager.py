"""MCP Manager - 统一管理所有工具（支持本地 in-process、WebSocket、stdio）"""
from __future__ import annotations

import importlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    ClientSession = None
    StdioServerParameters = None
    stdio_client = None
    logger = logging.getLogger(__name__)
    logger.warning("MCP SDK not available, external servers will not work")

from tools.base_tool import BaseTool

logger = logging.getLogger(__name__)


class MCPManager:
    """
    MCP 管理器 - 统一管理所有工具
    
    支持多种模式：
    1. local: 本地工具，直接调用（无 subprocess，无 Windows 兼容性问题）
    2. external (stdio): 外部 MCP 服务器（使用 stdio 传输）
    3. external (ws): 外部 MCP 服务器（使用 WebSocket 传输）
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "mcp.json"
        self.local_tools: Dict[str, BaseTool] = {}  # 本地工具（直接调用）
        self.external_clients: Dict[str, Any] = {}  # 外部 MCP 客户端
        self.tool_index: Dict[str, str] = {}  # tool_name -> server_id
        self.server_types: Dict[str, str] = {}  # server_id -> "local" | "external_stdio" | "external_ws"
        self.server_transports: Dict[str, str] = {}  # server_id -> transport type
        
    async def load(self):
        """加载所有工具配置"""
        config_path = Path(self.config_path)
        if not config_path.exists():
            logger.warning(f"MCP config not found: {config_path}")
            return
        
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        
        servers = config.get("servers", [])
        
        for server_conf in servers:
            server_id = server_conf.get("id")
            server_type = server_conf.get("type", "external")
            transport = server_conf.get("transport", "stdio")
            
            try:
                if server_type == "local":
                    await self._load_local_tool(server_id, server_conf)
                elif transport == "ws":
                    await self._load_websocket_server(server_id, server_conf)
                elif transport == "stdio":
                    await self._load_stdio_server(server_id, server_conf)
                else:
                    logger.warning(f"Unknown transport type: {transport} for server {server_id}")
            except Exception as e:
                logger.error(f"Failed to load server {server_id}: {e}", exc_info=True)
                continue
        
        logger.info(
            f"MCP Manager loaded: {len(self.local_tools)} local tools, "
            f"{len(self.external_clients)} external servers, "
            f"{len(self.tool_index)} total tools"
        )
    
    async def _load_local_tool(self, server_id: str, config: Dict):
        """加载本地工具（直接调用，无 subprocess）"""
        module_path = config.get("module")
        if not module_path:
            raise ValueError(f"Module path not specified for server {server_id}")
        
        # 动态导入工具类
        try:
            module = importlib.import_module(module_path)
            
            # 查找工具类（通常是模块名 + Tool）
            class_name = module_path.split(".")[-1].replace("_tool", "").title() + "Tool"
            if not hasattr(module, class_name):
                # 尝试其他命名约定
                for attr_name in dir(module):
                    if attr_name.endswith("Tool") and attr_name != "BaseTool":
                        class_name = attr_name
                        break
                else:
                    raise ValueError(f"Tool class not found in {module_path}")
            
            tool_class = getattr(module, class_name)
            tool = tool_class()
            
            self.local_tools[tool.name] = tool
            self.tool_index[tool.name] = server_id
            self.server_types[server_id] = "local"
            self.server_transports[server_id] = "local"
            
            logger.info(f"Loaded local tool: {tool.name} from {server_id}")
            
        except Exception as e:
            logger.error(f"Error loading local tool {server_id} from {module_path}: {e}")
            raise
    
    async def _load_websocket_server(self, server_id: str, config: Dict):
        """加载 WebSocket MCP 服务器"""
        endpoint = config.get("endpoint")
        if not endpoint:
            raise ValueError(f"WebSocket endpoint not specified for server {server_id}")
        
        logger.info(f"WebSocket server {server_id} configured at {endpoint}")
        
        # 检查 MCP SDK 是否支持 WebSocket
        backend_path = Path(__file__).parent.parent / "backend"
        websocket_supported = False
        
        if backend_path.exists():
            import sys
            backend_str = str(backend_path)
            if backend_str not in sys.path:
                sys.path.insert(0, backend_str)
            
            # 检查是否有 WebSocket 客户端实现
            try:
                # MCP SDK 可能不直接支持 WebSocket
                # 需要检查是否有自定义实现
                from mcp import ClientSession
                logger.info(f"MCP SDK available, checking WebSocket support...")
                
                # 尝试导入 WebSocket 相关模块
                try:
                    from mcp.client.websocket import websocket_client
                    websocket_supported = True
                    logger.info(f"WebSocket client available in MCP SDK")
                except ImportError:
                    logger.warning(f"WebSocket client not available in MCP SDK")
                    logger.info(f"  Note: MCP SDK may primarily support stdio transport")
                    logger.info(f"  WebSocket support may require custom implementation")
                    websocket_supported = False
            except ImportError:
                logger.warning(f"MCP SDK not available")
                websocket_supported = False
        
        if not websocket_supported:
            logger.warning(f"WebSocket transport not fully supported, skipping {server_id}")
            logger.info(f"  To enable WebSocket:")
            logger.info(f"    1. Ensure MCP SDK supports WebSocket (may need newer version)")
            logger.info(f"    2. Or implement custom WebSocket client")
            logger.info(f"    3. Ensure WebSocket server is running at {endpoint}")
            return
        
        # TODO: 实现 WebSocket 客户端连接
        # 这里需要根据 MCP SDK 的 WebSocket API 实现
        try:
            # 示例代码（需要根据实际 API 调整）
            # from mcp.client.websocket import websocket_client
            # client = websocket_client(endpoint)
            # await client.connect()
            # self.external_clients[server_id] = client
            # self.server_types[server_id] = "external_ws"
            # self.server_transports[server_id] = "ws"
            logger.info(f"WebSocket connection to {server_id} would be established here")
        except Exception as e:
            logger.error(f"Error loading WebSocket server {server_id}: {e}")
            raise
    
    async def _load_stdio_server(self, server_id: str, config: Dict):
        """加载 stdio MCP 服务器"""
        command = config.get("command")
        args = config.get("args", [])
        env = config.get("env", {})
        cwd = config.get("cwd")
        
        if not command:
            raise ValueError(f"Command not specified for stdio server {server_id}")
        
        # 尝试从 backend 导入 MCP SDK 或 MCPClient
        backend_path = Path(__file__).parent.parent / "backend"
        backend_mcp_available = False
        
        if backend_path.exists():
            import sys
            backend_str = str(backend_path)
            if backend_str not in sys.path:
                sys.path.insert(0, backend_str)
            
            # 尝试导入 backend 的 MCPClient（它已经处理了 MCP SDK）
            try:
                from app.mcp_tools.client import MCPClient
                backend_mcp_available = True
            except ImportError:
                pass
        
        if not MCP_AVAILABLE and not backend_mcp_available:
            logger.warning(f"MCP SDK not available, skipping stdio server {server_id}")
            logger.info(f"  To enable: pip install mcp")
            logger.info(f"  Or ensure backend/app/mcp_tools/client.py is available")
            return
        
        try:
            # 优先使用 backend 的 MCPClient（如果可用，因为它有更好的错误处理）
            if backend_mcp_available:
                from app.mcp_tools.client import MCPClient
                
                # 设置工作目录
                if not cwd:
                    # 对于 file_server.py，使用当前目录
                    if "file_server.py" in args:
                        cwd = str(Path(__file__).parent)
                    elif command == "python" and args:
                        cwd = str(backend_path)
                
                logger.info(f"Loading stdio server {server_id} with command: {command} {args}")
                logger.info(f"  Working directory: {cwd}")
                if env:
                    logger.info(f"  Environment variables: {list(env.keys())}")
                
                client = MCPClient(command, args, env=env, cwd=cwd)
                await client.initialize()
                
                self.external_clients[server_id] = client
                self.server_types[server_id] = "external_stdio"
                self.server_transports[server_id] = "stdio"
                
                # 获取工具列表
                tools = await client.list_tools()
                for tool in tools:
                    tool_name = tool.get("name")
                    if tool_name:
                        self.tool_index[tool_name] = server_id
                        logger.info(f"Loaded external tool: {tool_name} from {server_id}")
                
                logger.info(f"Successfully loaded stdio server {server_id} with {len(tools)} tools")
                return
            else:
                logger.warning(f"Backend MCPClient not available, cannot load stdio server {server_id}")
                logger.info(f"  Please ensure backend/app/mcp_tools/client.py is available")
                
        except Exception as e:
            logger.error(f"Error loading stdio server {server_id}: {e}", exc_info=True)
            # 不抛出异常，允许其他服务器继续加载
            logger.warning(f"Skipping stdio server {server_id} due to error")
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        调用工具 - 自动路由到本地或外部服务器
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
            
        Returns:
            工具执行结果
        """
        server_id = self.tool_index.get(tool_name)
        if not server_id:
            raise ValueError(f"Unknown tool: {tool_name}. Available: {list(self.tool_index.keys())}")
        
        server_type = self.server_types.get(server_id)
        
        if server_type == "local":
            # 直接调用本地工具（无 subprocess，无 Windows 问题）
            tool = self.local_tools.get(tool_name)
            if not tool:
                raise ValueError(f"Local tool not found: {tool_name}")
            
            result = await tool.execute_with_validation(arguments)
            if result.success:
                return result.data
            else:
                raise RuntimeError(result.error or "Tool execution failed")
        
        elif server_type in ("external_stdio", "external_ws"):
            # 通过 MCP 协议调用外部服务器
            client = self.external_clients.get(server_id)
            if not client:
                raise ValueError(f"External server client not found: {server_id}")
            
            return await client.call_tool(tool_name, arguments)
        
        else:
            raise NotImplementedError(f"Unknown server type: {server_type} for {server_id}")
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """列出所有工具"""
        tools = []
        
        # 本地工具
        for tool in self.local_tools.values():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.get_input_schema(),
                "server": "local",
                "transport": "local"
            })
        
        # 外部工具（需要从客户端获取，这里简化处理）
        # 实际应该从客户端缓存获取
        return tools
    
    async def close(self):
        """关闭所有连接"""
        # 关闭外部客户端
        for server_id, client in self.external_clients.items():
            try:
                if hasattr(client, 'close'):
                    await client.close()
            except Exception as e:
                logger.warning(f"Error closing client for {server_id}: {e}")
        
        self.external_clients.clear()
        self.local_tools.clear()
        self.tool_index.clear()
        logger.info("MCP Manager closed")
