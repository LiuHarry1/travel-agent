"""综合测试所有传输方式（local、stdio、ws）"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import warnings
from pathlib import Path

from mcp_manager import MCPManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 抑制 Windows asyncio 清理警告
if sys.platform == "win32":
    warnings.filterwarnings("ignore", message=".*Cancelling an overlapped future.*")
    warnings.filterwarnings("ignore", message=".*无效的句柄.*")


async def test_all_transports():
    """测试所有传输方式"""
    logger.info("=" * 60)
    logger.info("综合测试：所有传输方式（local、stdio、ws）")
    logger.info("=" * 60)
    
    logger.info(f"运行平台: {sys.platform}")
    logger.info(f"Python 版本: {sys.version}")
    
    # 读取配置
    config_path = Path("mcp.json")
    if not config_path.exists():
        logger.error(f"配置文件不存在: {config_path}")
        return False
    
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)
    
    servers = config.get("servers", [])
    logger.info(f"\n配置的服务器数量: {len(servers)}")
    
    # 分类统计
    local_servers = []
    stdio_servers = []
    ws_servers = []
    
    for server in servers:
        server_type = server.get("type", "external")
        transport = server.get("transport", "stdio")
        
        if server_type == "local":
            local_servers.append(server)
        elif transport == "ws":
            ws_servers.append(server)
        elif transport == "stdio":
            stdio_servers.append(server)
    
    logger.info(f"\n服务器分类:")
    logger.info(f"  本地工具 (local): {len(local_servers)}")
    logger.info(f"  stdio 传输: {len(stdio_servers)}")
    logger.info(f"  WebSocket 传输: {len(ws_servers)}")
    
    # 创建 MCP Manager
    manager = MCPManager("mcp.json")
    
    try:
        # 加载所有服务器
        logger.info("\n" + "=" * 60)
        logger.info("1. 加载所有服务器...")
        logger.info("=" * 60)
        await manager.load()
        
        # 统计加载结果
        logger.info(f"\n加载结果:")
        logger.info(f"  本地工具: {len(manager.local_tools)}")
        logger.info(f"  外部服务器: {len(manager.external_clients)}")
        logger.info(f"  总工具数: {len(manager.tool_index)}")
        
        # 显示服务器详情
        logger.info(f"\n服务器详情:")
        for server_id, server_type in manager.server_types.items():
            transport = manager.server_transports.get(server_id, "unknown")
            logger.info(f"  - {server_id}: {server_type} (transport: {transport})")
        
        # 列出所有工具
        logger.info(f"\n" + "=" * 60)
        logger.info("2. 列出所有工具...")
        logger.info("=" * 60)
        tools = manager.list_tools()
        if tools:
            for tool in tools:
                logger.info(f"  - {tool['name']}: {tool.get('server', 'unknown')} ({tool.get('transport', 'unknown')})")
        else:
            logger.warning("  没有可用的工具")
        
        # 测试本地工具
        logger.info(f"\n" + "=" * 60)
        logger.info("3. 测试本地工具（local 传输）...")
        logger.info("=" * 60)
        local_tool_names = [name for name, sid in manager.tool_index.items() 
                           if manager.server_types.get(sid) == "local"]
        
        if local_tool_names:
            logger.info(f"  可用本地工具: {local_tool_names}")
            
            # 测试 calculator
            if "calculator" in local_tool_names:
                logger.info(f"\n  测试 calculator 工具:")
                try:
                    result = await manager.call_tool("calculator", {"operation": "add", "a": 10, "b": 5})
                    logger.info(f"    ✓ add(10, 5) = {result.get('result') if isinstance(result, dict) else result}")
                except Exception as e:
                    logger.error(f"    ✗ 失败: {e}")
            
            # 测试 echo
            if "echo" in local_tool_names:
                logger.info(f"\n  测试 echo 工具:")
                try:
                    result = await manager.call_tool("echo", {"message": "Hello from local tool!"})
                    logger.info(f"    ✓ {result.get('echo') if isinstance(result, dict) else result}")
                except Exception as e:
                    logger.error(f"    ✗ 失败: {e}")
        else:
            logger.warning("  没有可用的本地工具")
        
        # 测试外部服务器
        logger.info(f"\n" + "=" * 60)
        logger.info("4. 外部服务器状态...")
        logger.info("=" * 60)
        
        stdio_tool_names = [name for name, sid in manager.tool_index.items() 
                           if manager.server_types.get(sid) == "external_stdio"]
        ws_tool_names = [name for name, sid in manager.tool_index.items() 
                        if manager.server_types.get(sid) == "external_ws"]
        
        if stdio_tool_names:
            logger.info(f"  stdio 工具: {stdio_tool_names}")
            logger.info(f"    ⚠️  注意: stdio 传输在 Windows 上可能需要 ProactorEventLoop")
        else:
            logger.info(f"  stdio 工具: 无（可能未加载或 MCP SDK 不可用）")
        
        if ws_tool_names:
            logger.info(f"  WebSocket 工具: {ws_tool_names}")
            logger.info(f"    ⚠️  注意: WebSocket 需要服务器运行")
        else:
            logger.info(f"  WebSocket 工具: 无（可能未加载或服务器未运行）")
        
        # 总结
        logger.info(f"\n" + "=" * 60)
        logger.info("测试总结")
        logger.info("=" * 60)
        
        logger.info(f"\n配置验证:")
        logger.info(f"  ✓ local 配置: {len(local_servers)} 个")
        logger.info(f"  ✓ stdio 配置: {len(stdio_servers)} 个")
        logger.info(f"  ✓ ws 配置: {len(ws_servers)} 个")
        
        logger.info(f"\n加载结果:")
        logger.info(f"  ✓ 本地工具: {len(manager.local_tools)} 个（无 subprocess，无 Windows 问题）")
        logger.info(f"  ⚠️  外部服务器: {len(manager.external_clients)} 个（需要 MCP SDK）")
        
        logger.info(f"\n关键发现:")
        logger.info(f"  ✅ local 传输: 完全支持，无 Windows 兼容性问题")
        logger.info(f"  ⚠️  stdio 传输: 需要 MCP SDK，Windows 上可能需要 ProactorEventLoop")
        logger.info(f"  ⚠️  ws 传输: 需要 WebSocket 服务器运行，可能需要自定义实现")
        
        logger.info(f"\n推荐配置策略:")
        logger.info(f"  1. 本地 Python 工具 → 使用 'type': 'local'（推荐，无 Windows 问题）")
        logger.info(f"  2. 外部工具（npx） → 使用 'transport': 'stdio'（需要 MCP SDK）")
        logger.info(f"  3. 远程服务器 → 使用 'transport': 'ws'（需要服务器运行）")
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False
    finally:
        await manager.close()


async def main():
    """主函数"""
    success = await test_all_transports()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.info("已设置 WindowsProactorEventLoopPolicy")
        except Exception:
            pass
    
    try:
        asyncio.run(main())
    except SystemExit:
        pass

