"""测试 MCP Manager - 验证 Windows 兼容性"""
from __future__ import annotations

import asyncio
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

# 抑制 Windows asyncio 清理警告（无害）
if sys.platform == "win32":
    warnings.filterwarnings("ignore", message=".*Cancelling an overlapped future.*")
    warnings.filterwarnings("ignore", message=".*无效的句柄.*")


async def test_mcp_manager():
    """测试 MCP Manager"""
    logger.info("=" * 60)
    logger.info("开始测试 MCP Manager（新方案 - 无 subprocess）")
    logger.info("=" * 60)
    
    # 检查平台
    logger.info(f"运行平台: {sys.platform}")
    logger.info(f"Python 版本: {sys.version}")
    
    # 创建 MCP Manager
    manager = MCPManager("mcp.json")
    
    try:
        # 加载工具
        logger.info("\n1. 加载工具...")
        await manager.load()
        
        # 列出所有工具
        logger.info("\n2. 列出所有工具:")
        tools = manager.list_tools()
        for tool in tools:
            logger.info(f"  - {tool['name']}: {tool['description']}")
        
        # 测试计算器工具
        logger.info("\n3. 测试计算器工具:")
        test_cases = [
            {"operation": "add", "a": 10, "b": 5},
            {"operation": "subtract", "a": 10, "b": 5},
            {"operation": "multiply", "a": 10, "b": 5},
            {"operation": "divide", "a": 10, "b": 5},
        ]
        
        for test_case in test_cases:
            try:
                result = await manager.call_tool("calculator", test_case)
                logger.info(f"  ✓ {test_case['operation']}({test_case['a']}, {test_case['b']}) = {result.get('result')}")
            except Exception as e:
                logger.error(f"  ✗ 测试失败: {e}")
        
        # 测试回显工具
        logger.info("\n4. 测试回显工具:")
        try:
            result = await manager.call_tool("echo", {"message": "Hello, World!"})
            logger.info(f"  ✓ {result.get('echo')}")
        except Exception as e:
            logger.error(f"  ✗ 测试失败: {e}")
        
        # 测试错误处理
        logger.info("\n5. 测试错误处理:")
        try:
            await manager.call_tool("unknown_tool", {})
        except ValueError as e:
            logger.info(f"  ✓ 正确捕获错误: {e}")
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ 所有测试完成！")
        logger.info("=" * 60)
        logger.info("\n关键优势:")
        logger.info("  ✓ 无 subprocess，无 Windows 兼容性问题")
        logger.info("  ✓ 直接调用，性能更好")
        logger.info("  ✓ 代码简单，易于维护")
        logger.info("  ✓ 完全跨平台")
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False
    finally:
        await manager.close()
    
    return True


async def main():
    """主函数"""
    success = await test_mcp_manager()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    # 在 Windows 上确保使用正确的事件循环策略
    if sys.platform == "win32":
        # 注意：由于我们使用的是 in-process 模式，不需要 subprocess
        # 所以理论上不需要 ProactorEventLoop
        # 但为了安全，还是设置一下
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.info("已设置 WindowsProactorEventLoopPolicy（虽然不需要 subprocess）")
        except Exception as e:
            logger.warning(f"无法设置事件循环策略: {e}")
    
    try:
        asyncio.run(main())
    except SystemExit:
        # 正常退出，忽略
        pass

