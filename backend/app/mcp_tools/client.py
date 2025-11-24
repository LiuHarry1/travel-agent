"""MCP client for connecting to MCP servers with persistent connections."""
from __future__ import annotations

import asyncio
import json
import logging
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
    logger.warning("MCP SDK not available, using fallback implementation")

# Try to import anyio exceptions for better error handling
try:
    from anyio import ClosedResourceError
    ANYIO_AVAILABLE = True
except ImportError:
    ClosedResourceError = None
    ANYIO_AVAILABLE = False

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to MCP servers via stdio with persistent connection."""
    
    def __init__(self, command: str, args: List[str], env: Optional[Dict[str, str]] = None, cwd: Optional[str] = None):
        """
        Initialize MCP client.
        
        Args:
            command: Command to start the MCP server (e.g., "python", "npx")
            args: Arguments for the command (e.g., ["-m", "app.mcp_tools.faq.server"])
            env: Environment variables to pass to the server process
            cwd: Working directory for the server process
        """
        self.command = command
        self.args = args
        self.env = env or {}
        self.cwd = cwd
        self._tools: List[Dict[str, Any]] = []
        
        # 持久连接相关
        self._stdio_context = None  # stdio_client 的 context manager
        self._read_stream = None
        self._write_stream = None
        self._session: Optional[ClientSession] = None
        self._session_context = None  # ClientSession 的 context manager
        self._connection_lock = asyncio.Lock()  # 保护连接的锁
        self._is_connected = False
        self._connection_established = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3
        
        # Create server parameters with environment variables and working directory
        if MCP_AVAILABLE:
            # Prepare environment variables
            server_env = dict(env) if env else {}
            
            # For Python module servers, ensure PYTHONPATH includes the working directory
            if cwd and command == "python":
                import os
                pythonpath = server_env.get("PYTHONPATH", "")
                if pythonpath:
                    pythonpath = f"{cwd}{os.pathsep}{pythonpath}"
                else:
                    pythonpath = cwd
                server_env["PYTHONPATH"] = pythonpath
            
            try:
                # StdioServerParameters supports command, args, env, and cwd
                self._server_params = StdioServerParameters(
                    command=command,
                    args=args,
                    env=server_env if server_env else None,
                    cwd=cwd
                )
            except TypeError:
                # Fallback if cwd is not supported
                try:
                    self._server_params = StdioServerParameters(
                        command=command,
                        args=args,
                        env=server_env if server_env else None
                    )
                except TypeError:
                    # Fallback if env is not supported either
                    self._server_params = StdioServerParameters(
                        command=command,
                        args=args
                    )
        else:
            self._server_params = None
    
    async def _establish_connection(self) -> None:
        """
        建立持久连接（如果尚未建立）。
        线程安全，支持并发调用。
        """
        # 如果已经连接，直接返回
        if self._is_connected and self._session is not None:
            return
        
        async with self._connection_lock:
            # 双重检查（double-check locking）
            if self._is_connected and self._session is not None:
                return
            
            try:
                # Re-check MCP SDK availability at runtime
                try:
                    from mcp import ClientSession, StdioServerParameters
                    from mcp.client.stdio import stdio_client
                    runtime_mcp_available = True
                except ImportError:
                    runtime_mcp_available = False
                
                if not runtime_mcp_available and not MCP_AVAILABLE:
                    raise RuntimeError("MCP SDK not available")
                
                # If MCP SDK is available but _server_params is None, recreate it
                if runtime_mcp_available and (not hasattr(self, '_server_params') or self._server_params is None):
                    from mcp import StdioServerParameters
                    import os
                    
                    # Prepare environment variables
                    server_env = dict(self.env) if self.env else {}
                    
                    # For Python module servers, ensure PYTHONPATH includes the working directory
                    if self.cwd and self.command == "python":
                        pythonpath = server_env.get("PYTHONPATH", "")
                        if pythonpath:
                            pythonpath = f"{self.cwd}{os.pathsep}{pythonpath}"
                        else:
                            pythonpath = self.cwd
                        server_env["PYTHONPATH"] = pythonpath
                    
                    try:
                        self._server_params = StdioServerParameters(
                            command=self.command,
                            args=self.args,
                            env=server_env if server_env else None,
                            cwd=self.cwd
                        )
                    except TypeError:
                        # Fallback if cwd is not supported
                        try:
                            self._server_params = StdioServerParameters(
                                command=self.command,
                                args=self.args,
                                env=server_env if server_env else None
                            )
                        except TypeError:
                            # Fallback if env is not supported either
                            self._server_params = StdioServerParameters(
                                command=self.command,
                                args=self.args
                            )
                
                # Import at runtime to ensure MCP SDK is available
                import os
                from pathlib import Path
                
                # Log server parameters for debugging
                logger.info(f"[MCPClient] Establishing persistent connection with command: {self.command}, args: {self.args}")
                if self.cwd:
                    logger.info(f"[MCPClient] Working directory: {self.cwd}")
                if self.env:
                    logger.info(f"[MCPClient] Environment variables: {list(self.env.keys())}")
                
                # Verify working directory exists if specified
                if self.cwd and not Path(self.cwd).exists():
                    logger.warning(f"[MCPClient] Working directory does not exist: {self.cwd}")
                
                from mcp.client.stdio import stdio_client
                from mcp import ClientSession
                
                # 建立 stdio_client 连接（持久化）
                logger.info(f"[MCPClient] Creating persistent stdio connection...")
                self._stdio_context = stdio_client(self._server_params)
                self._read_stream, self._write_stream = await self._stdio_context.__aenter__()
                
                # 建立 ClientSession（持久化）
                logger.info(f"[MCPClient] Creating persistent ClientSession...")
                self._session_context = ClientSession(self._read_stream, self._write_stream)
                self._session = await self._session_context.__aenter__()
                
                # 初始化会话
                await self._session.initialize()
                
                # 获取工具列表（仅在首次连接时）
                if not self._tools:
                    tools_result = await self._session.list_tools()
                    self._tools = [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        }
                        for tool in tools_result.tools
                    ]
                    logger.info(f"[MCPClient] Loaded {len(self._tools)} tools")
                
                self._is_connected = True
                self._connection_established = True
                self._reconnect_attempts = 0
                
                logger.info(f"[MCPClient] Persistent connection established successfully")
                
            except NotImplementedError as e:
                # This error occurs when the event loop doesn't support subprocess operations
                # This can happen on Windows if not using ProactorEventLoop
                error_msg = str(e)
                logger.error(f"[MCPClient] Failed to establish persistent connection: {error_msg}")
                logger.error(f"[MCPClient] Command: {self.command}, Args: {self.args}")
                logger.error(f"[MCPClient] Working directory: {self.cwd}")
                
                # Provide helpful error message about event loop requirements
                try:
                    from ..platform_config import get_event_loop_info
                    loop_info = get_event_loop_info()
                    logger.error(f"[MCPClient] Event loop info: {loop_info}")
                    logger.error(f"[MCPClient] The event loop does not support subprocess operations.")
                    logger.error(f"[MCPClient] For stdio servers, you need an event loop that supports subprocess.")
                    logger.error(f"[MCPClient] Consider using local tools (type: 'local') instead of stdio servers for better compatibility.")
                except Exception:
                    # If we can't get loop info, just log the basic error
                    logger.error(f"[MCPClient] The event loop does not support subprocess operations.")
                    logger.error(f"[MCPClient] Consider using local tools (type: 'local') instead of stdio servers.")
                
                await self._cleanup_connection()
                raise RuntimeError(
                    f"Failed to establish MCP connection: Event loop does not support subprocess operations. "
                    f"Consider using local tools (type: 'local') instead of stdio servers."
                ) from e
            except Exception as e:
                error_msg = str(e)
                logger.error(f"[MCPClient] Failed to establish persistent connection: {error_msg}")
                logger.error(f"[MCPClient] Command: {self.command}, Args: {self.args}")
                logger.error(f"[MCPClient] Working directory: {self.cwd}")
                logger.error(f"[MCPClient] Full error details:", exc_info=True)
                
                await self._cleanup_connection()
                
                # Try to get more details about the subprocess error
                if "Connection closed" in error_msg:
                    logger.error(f"[MCPClient] Connection closed - this usually means the MCP server process failed to start or crashed immediately")
                    logger.error(f"[MCPClient] Please check:")
                    logger.error(f"[MCPClient]   1. The MCP server module can be imported: python -m {self.args[1] if len(self.args) > 1 else 'N/A'}")
                    logger.error(f"[MCPClient]   2. The working directory is correct: {self.cwd or 'Not set'}")
                    logger.error(f"[MCPClient]   3. Python can find the module from the working directory")
                
                raise
    
    async def _cleanup_connection(self) -> None:
        """清理连接资源。"""
        self._is_connected = False
        
        try:
            if self._session_context is not None:
                try:
                    await self._session_context.__aexit__(None, None, None)
                except (asyncio.CancelledError, RuntimeError) as e:
                    # 忽略取消错误和运行时错误（可能由于事件循环关闭）
                    logger.debug(f"[MCPClient] Session cleanup cancelled or interrupted: {e}")
                except Exception as e:
                    logger.warning(f"[MCPClient] Error closing session: {e}")
                finally:
                    self._session_context = None
            self._session = None
        except Exception as e:
            logger.warning(f"[MCPClient] Error during session cleanup: {e}")
        
        try:
            if self._stdio_context is not None:
                try:
                    await self._stdio_context.__aexit__(None, None, None)
                except (asyncio.CancelledError, RuntimeError) as e:
                    # 忽略取消错误和运行时错误（可能由于事件循环关闭）
                    logger.debug(f"[MCPClient] Stdio cleanup cancelled or interrupted: {e}")
                except Exception as e:
                    logger.warning(f"[MCPClient] Error closing stdio client: {e}")
                finally:
                    self._stdio_context = None
            self._read_stream = None
            self._write_stream = None
        except Exception as e:
            logger.warning(f"[MCPClient] Error during stdio cleanup: {e}")
    
    async def _reconnect(self) -> None:
        """重新建立连接（用于错误恢复）。"""
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            raise RuntimeError(f"Failed to reconnect after {self._max_reconnect_attempts} attempts")
        
        self._reconnect_attempts += 1
        logger.warning(f"[MCPClient] Attempting to reconnect (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})...")
        
        await self._cleanup_connection()
        await asyncio.sleep(0.5)  # 短暂延迟后重连
        await self._establish_connection()
    
    async def _ensure_connected(self) -> None:
        """确保连接已建立（带重试）。"""
        if not self._is_connected or self._session is None:
            await self._establish_connection()
    
    async def initialize(self) -> None:
        """Initialize connection to MCP server and get tools list (establishes persistent connection)."""
        await self._establish_connection()
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """Get list of tools from MCP server."""
        await self._ensure_connected()
        return self._tools
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool on the MCP server using persistent connection.
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool result
        """
        max_retries = 2
        tool_timeout = 30.0  # 30 seconds timeout for tool calls
        
        for attempt in range(max_retries):
            try:
                # 确保连接已建立
                await self._ensure_connected()
                
                if self._session is None:
                    raise RuntimeError("Session is None after ensuring connection")
                
                logger.info(f"[MCPClient] Calling tool '{name}' with args: {arguments}")
                
                # 使用持久连接调用工具（带超时）
                try:
                    result = await asyncio.wait_for(
                        self._session.call_tool(name, arguments),
                        timeout=tool_timeout
                    )
                    logger.info(f"[MCPClient] Tool '{name}' call completed successfully")
                except asyncio.TimeoutError:
                    logger.error(f"[MCPClient] Tool '{name}' call timed out after {tool_timeout}s")
                    raise
                
                # Extract text content from result
                if result.content and len(result.content) > 0:
                    # Get text from first content item
                    text = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                    # Try to parse as JSON, otherwise return as plain text string
                    try:
                        parsed = json.loads(text)
                        # If parsed successfully and it's a dict, return it
                        if isinstance(parsed, dict):
                            return parsed
                        else:
                            return text
                    except json.JSONDecodeError:
                        # Not JSON, return as plain text string
                        return text
                
                return ""
                
            except asyncio.TimeoutError:
                error_msg = f"Tool call '{name}' timed out after {tool_timeout} seconds"
                logger.error(f"[MCPClient] {error_msg}")
                raise RuntimeError(error_msg)
            except Exception as e:
                # 检查是否是连接相关的错误（包括 anyio.ClosedResourceError）
                error_type = type(e).__name__
                error_msg = str(e)
                
                # 检查是否是 anyio.ClosedResourceError 或其他连接关闭错误
                is_connection_error = (
                    # 检查是否是 anyio.ClosedResourceError
                    (ANYIO_AVAILABLE and isinstance(e, ClosedResourceError)) or
                    error_type == "ClosedResourceError" or
                    "ClosedResourceError" in error_msg or
                    # 检查是否是其他连接相关错误
                    isinstance(e, (ConnectionError, BrokenPipeError, OSError)) or
                    # 检查错误消息中是否包含连接关闭的关键词
                    ("closed" in error_msg.lower() and ("resource" in error_msg.lower() or "connection" in error_msg.lower() or "stream" in error_msg.lower()))
                )
                
                if is_connection_error:
                    logger.warning(
                        f"[MCPClient] Connection error during tool call (attempt {attempt + 1}/{max_retries}): "
                        f"{error_type}: {error_msg}"
                    )
                    
                    # 标记连接断开
                    self._is_connected = False
                    
                    # 如果是最后一次尝试，抛出异常
                    if attempt == max_retries - 1:
                        logger.error(f"[MCPClient] Failed to call tool after {max_retries} attempts")
                        raise RuntimeError(f"Tool call '{name}' failed: connection closed ({error_msg})")
                    
                    # 尝试重连
                    try:
                        logger.info(f"[MCPClient] Attempting to reconnect before retry...")
                        await self._reconnect()
                        logger.info(f"[MCPClient] Reconnection successful, retrying tool call...")
                        continue  # 重试工具调用
                    except Exception as reconnect_error:
                        logger.error(f"[MCPClient] Reconnection failed: {reconnect_error}")
                        if attempt == max_retries - 1:
                            raise RuntimeError(f"Tool call '{name}' failed: reconnection failed ({reconnect_error})")
                        continue
                else:
                    # 非连接错误，直接抛出
                    logger.error(f"[MCPClient] Error in call_tool: {e}", exc_info=True)
                    raise
    
    async def close(self) -> None:
        """Close the persistent connection to MCP server."""
        logger.info(f"[MCPClient] Closing persistent connection...")
        await self._cleanup_connection()
        logger.info(f"[MCPClient] Connection closed")
    
    async def health_check(self) -> bool:
        """
        健康检查：验证连接是否仍然有效。
        
        Returns:
            True if connection is healthy, False otherwise
        """
        try:
            if not self._is_connected or self._session is None:
                return False
            
            # 尝试调用 list_tools（轻量级操作）
            await self._session.list_tools()
            return True
        except Exception as e:
            logger.warning(f"[MCPClient] Health check failed: {e}")
            self._is_connected = False
            return False
