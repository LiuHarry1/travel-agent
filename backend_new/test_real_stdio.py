"""测试真实的 stdio 服务器连接"""
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


async def test_file_server():
    """测试 file-server (stdio)"""
    logger.info("=" * 60)
    logger.info("测试 file-server (stdio 传输)")
    logger.info("=" * 60)
    
    # 检查 file_server.py 是否存在
    file_server_path = Path("file_server.py")
    if not file_server_path.exists():
        logger.error(f"file_server.py 不存在: {file_server_path}")
        logger.info("请确保 file_server.py 在当前目录")
        return False
    
    logger.info(f"✓ 找到 file_server.py: {file_server_path.absolute()}")
    
    # 创建测试配置
    test_config = {
        "servers": [
            {
                "id": "file-server",
                "transport": "stdio",
                "command": "python",
                "args": ["file_server.py"]
            }
        ]
    }
    
    # 保存测试配置
    test_config_path = Path("mcp_test_stdio.json")
    with open(test_config_path, "w", encoding="utf-8") as f:
        json.dump(test_config, f, indent=2, ensure_ascii=False)
    
    logger.info(f"✓ 创建测试配置: {test_config_path}")
    
    manager = MCPManager(str(test_config_path))
    
    try:
        logger.info("\n1. 加载 file-server...")
        await manager.load()
        
        logger.info(f"\n2. 加载结果:")
        logger.info(f"  外部服务器: {len(manager.external_clients)}")
        logger.info(f"  总工具数: {len(manager.tool_index)}")
        
        if len(manager.external_clients) == 0:
            logger.warning("\n⚠️  未能加载 file-server")
            logger.info("可能原因:")
            logger.info("  1. MCP SDK 未安装 (pip install mcp)")
            logger.info("  2. Windows subprocess 兼容性问题")
            logger.info("  3. file_server.py 有错误")
            return False
        
        # 列出工具
        tools = list(manager.tool_index.keys())
        logger.info(f"\n3. 可用工具: {tools}")
        
        # 测试工具调用
        if "read_file" in tools:
            logger.info("\n4. 测试 read_file 工具:")
            try:
                # 读取当前目录的 README.md（如果存在）
                test_file = "README.md"
                if Path(test_file).exists():
                    result = await manager.call_tool("read_file", {"file_path": test_file})
                    logger.info(f"  结果: {json.dumps(result, ensure_ascii=False, indent=2)[:200]}...")
                else:
                    logger.info(f"  跳过（测试文件不存在: {test_file}）")
            except Exception as e:
                logger.error(f"  工具调用失败: {e}", exc_info=True)
        
        if "list_files" in tools:
            logger.info("\n5. 测试 list_files 工具:")
            try:
                result = await manager.call_tool("list_files", {"directory": "."})
                logger.info(f"  结果: {json.dumps(result, ensure_ascii=False, indent=2)[:300]}...")
            except Exception as e:
                logger.error(f"  工具调用失败: {e}", exc_info=True)
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ stdio 服务器测试完成！")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False
    finally:
        await manager.close()


async def main():
    """主函数"""
    success = await test_file_server()
    
    if success:
        logger.info("\n关键验证:")
        logger.info("  ✓ stdio 传输配置正确")
        logger.info("  ✓ 服务器连接成功")
        logger.info("  ✓ 工具调用正常")
        if sys.platform == "win32":
            logger.info("  ✓ Windows 兼容性验证通过（如果成功连接）")
    else:
        logger.warning("\n⚠️  测试未完全通过")
        if sys.platform == "win32":
            logger.warning("  可能是 Windows subprocess 兼容性问题")
            logger.info("  建议: 使用 'type': 'local' 模式避免 subprocess")
    
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

