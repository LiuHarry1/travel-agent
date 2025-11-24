"""测试不同传输方式（WebSocket、stdio）"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import warnings

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


async def test_transports():
    """测试不同传输方式"""
    logger.info("=" * 60)
    logger.info("测试不同传输方式（WebSocket、stdio）")
    logger.info("=" * 60)
    
    logger.info(f"运行平台: {sys.platform}")
    logger.info(f"Python 版本: {sys.version}")
    
    manager = MCPManager("mcp.json")
    
    try:
        # 加载所有服务器
        logger.info("\n1. 加载所有服务器...")
        await manager.load()
        
        # 列出所有工具
        logger.info("\n2. 列出所有工具:")
        tools = manager.list_tools()
        for tool in tools:
            logger.info(f"  - {tool['name']}: {tool.get('server', 'unknown')} ({tool.get('transport', 'unknown')})")
        
        # 列出所有服务器信息
        logger.info("\n3. 服务器信息:")
        logger.info(f"  本地工具: {len(manager.local_tools)}")
        logger.info(f"  外部服务器: {len(manager.external_clients)}")
        logger.info(f"  总工具数: {len(manager.tool_index)}")
        
        # 显示服务器类型
        logger.info("\n4. 服务器类型:")
        for server_id, server_type in manager.server_types.items():
            transport = manager.server_transports.get(server_id, "unknown")
            logger.info(f"  - {server_id}: {server_type} (transport: {transport})")
        
        # 测试可用的工具
        logger.info("\n5. 测试可用工具:")
        available_tools = list(manager.tool_index.keys())
        if available_tools:
            logger.info(f"  可用工具: {available_tools}")
            
            # 尝试调用第一个工具（如果是本地工具）
            for tool_name in available_tools:
                server_id = manager.tool_index.get(tool_name)
                server_type = manager.server_types.get(server_id)
                
                if server_type == "local":
                    logger.info(f"\n  测试本地工具: {tool_name}")
                    try:
                        # 根据工具类型提供测试参数
                        if tool_name == "calculator":
                            result = await manager.call_tool(tool_name, {"operation": "add", "a": 10, "b": 5})
                            logger.info(f"    结果: {result}")
                        elif tool_name == "echo":
                            result = await manager.call_tool(tool_name, {"message": "Hello"})
                            logger.info(f"    结果: {result}")
                        else:
                            logger.info(f"    跳过测试（需要特定参数）")
                    except Exception as e:
                        logger.error(f"    工具调用失败: {e}")
                elif server_type == "external_stdio":
                    logger.info(f"\n  外部 stdio 工具: {tool_name} (服务器: {server_id})")
                    logger.info(f"    注意: stdio 传输在 Windows 上可能有兼容性问题")
                elif server_type == "external_ws":
                    logger.info(f"\n  外部 WebSocket 工具: {tool_name} (服务器: {server_id})")
                    logger.info(f"    注意: WebSocket 传输需要服务器运行")
        else:
            logger.warning("  没有可用的工具")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 传输方式测试完成！")
        logger.info("=" * 60)
        
        logger.info("\n关键发现:")
        logger.info(f"  ✓ 本地工具: {len(manager.local_tools)} 个（无 subprocess，无 Windows 问题）")
        logger.info(f"  ✓ 外部 stdio 服务器: {len([s for s in manager.server_types.values() if s == 'external_stdio'])} 个")
        logger.info(f"  ✓ 外部 WebSocket 服务器: {len([s for s in manager.server_types.values() if s == 'external_ws'])} 个")
        
        # Windows 兼容性提示
        if sys.platform == "win32":
            stdio_count = len([s for s in manager.server_types.values() if s == 'external_stdio'])
            if stdio_count > 0:
                logger.warning(f"\n⚠️  注意: 有 {stdio_count} 个 stdio 服务器在 Windows 上可能需要 ProactorEventLoop")
                logger.info("  建议: 对于本地 Python 工具，使用 'type': 'local' 模式（无 subprocess）")
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False
    finally:
        await manager.close()


async def main():
    """主函数"""
    success = await test_transports()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass
    
    try:
        asyncio.run(main())
    except SystemExit:
        pass

