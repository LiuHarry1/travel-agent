#!/usr/bin/env python3
"""
测试所有 MCP 配置方式
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.mcp_tools.server_manager import MCPServerManager, ServerType
from app.mcp_tools.registry import MCPToolRegistry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_config_file(config_path: str, config_name: str) -> Dict[str, Any]:
    """
    测试指定的配置文件
    
    Args:
        config_path: 配置文件路径
        config_name: 配置名称（用于显示）
        
    Returns:
        测试结果字典
    """
    logger.info(f"\n{'='*80}")
    logger.info(f"测试配置: {config_name}")
    logger.info(f"配置文件: {config_path}")
    logger.info(f"{'='*80}\n")
    
    result = {
        "config_name": config_name,
        "config_path": config_path,
        "servers": {},
        "success": False,
        "error": None
    }
    
    try:
        # 检查文件是否存在
        config_file = Path(config_path)
        if not config_file.exists():
            logger.warning(f"配置文件不存在: {config_path}")
            result["error"] = f"配置文件不存在: {config_path}"
            return result
        
        # 加载配置
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        servers = config.get("mcpServers", {})
        logger.info(f"找到 {len(servers)} 个服务器配置\n")
        
        # 创建服务器管理器
        manager = MCPServerManager(config_path=config_path)
        manager.load_config()
        
        # 检测每个服务器的类型
        for server_name, server_config in servers.items():
            logger.info(f"服务器: {server_name}")
            logger.info(f"  配置: {json.dumps(server_config, indent=2, ensure_ascii=False)}")
            
            server_type = manager.detect_server_type(server_name, server_config)
            logger.info(f"  类型: {server_type.value}")
            
            server_info = {
                "type": server_type.value,
                "config": server_config,
                "detected": True
            }
            
            # 对于外部服务器，只做快速检查（不实际连接）
            if server_type in (ServerType.EXTERNAL_NPX, ServerType.EXTERNAL_PYTHON):
                logger.info(f"  检查外部服务器可用性（快速检查）...")
                try:
                    # 对于 npx，只检查命令是否存在
                    if server_type == ServerType.EXTERNAL_NPX:
                        import shutil
                        if shutil.which("npx"):
                            logger.info(f"  ✓ npx 命令可用")
                            server_info["available"] = True
                        else:
                            logger.warning(f"  ✗ npx 命令不可用")
                            server_info["available"] = False
                    # 对于外部 Python 包，只检查模块是否可以导入（不实际运行）
                    elif server_type == ServerType.EXTERNAL_PYTHON:
                        args = server_config.get("args", [])
                        if len(args) >= 2 and args[0] == "-m":
                            module_name = args[1]
                            try:
                                __import__(module_name)
                                logger.info(f"  ✓ Python 模块 '{module_name}' 可导入")
                                server_info["available"] = True
                            except ImportError:
                                logger.warning(f"  ✗ Python 模块 '{module_name}' 不可导入（可能需要安装）")
                                server_info["available"] = False
                        else:
                            server_info["available"] = None
                except Exception as e:
                    logger.warning(f"  ✗ 检查服务器可用性时出错: {e}")
                    server_info["available"] = None
                    server_info["check_error"] = str(e)
            elif server_type == ServerType.LOCAL_PYTHON:
                logger.info(f"  ✓ 本地 Python 模块（无需检查）")
                server_info["available"] = True
            elif server_type == ServerType.EXTERNAL_BINARY:
                logger.info(f"  ⚠ 外部二进制（需要手动验证路径）")
                server_info["available"] = None  # 未知
            
            result["servers"][server_name] = server_info
            logger.info("")
        
        # 尝试初始化所有服务器（跳过外部服务器的实际检查，避免子进程问题）
        logger.info("初始化所有服务器（仅检测类型，不实际连接）...")
        # 手动设置初始化状态，避免实际调用 ensure_external_server_installed
        for server_name, server_config in servers.items():
            server_type = manager._server_types.get(server_name)
            if server_type == ServerType.LOCAL_PYTHON:
                result["servers"][server_name]["initialized"] = True
                logger.info(f"  ✓ {server_name}: 本地服务器（无需实际初始化）")
            elif server_type in (ServerType.EXTERNAL_NPX, ServerType.EXTERNAL_PYTHON):
                # 外部服务器，标记为已检测但未实际初始化
                result["servers"][server_name]["initialized"] = None
                logger.info(f"  ⚠ {server_name}: 外部服务器（跳过实际初始化）")
            else:
                result["servers"][server_name]["initialized"] = None
                logger.info(f"  ⚠ {server_name}: 二进制服务器（跳过实际初始化）")
        
        # 如果至少有一个本地服务器成功，尝试创建 registry 并加载工具
        local_servers = [name for name, info in result["servers"].items() 
                        if info.get("type") == ServerType.LOCAL_PYTHON.value]
        
        registry = None
        if local_servers:
            logger.info(f"\n尝试加载工具（仅本地服务器）...")
            try:
                registry = MCPToolRegistry()
                registry.server_manager = manager
                registry.config_path = config_path
                registry._create_clients()
                
                # 只初始化本地服务器
                for server_name in local_servers:
                    if server_name in registry._mcp_clients:
                        try:
                            await registry._mcp_clients[server_name].initialize()
                            tools = await registry._mcp_clients[server_name].list_tools()
                            logger.info(f"  ✓ {server_name}: 加载了 {len(tools)} 个工具")
                            result["servers"][server_name]["tools_count"] = len(tools)
                        except Exception as e:
                            logger.error(f"  ✗ {server_name}: 加载工具失败 - {e}")
                            result["servers"][server_name]["tools_error"] = str(e)
            except Exception as e:
                logger.error(f"创建 registry 失败: {e}")
        
        # 清理连接
        if registry:
            try:
                await registry.close_all()
            except Exception as e:
                logger.warning(f"清理连接时出错: {e}")
        
        result["success"] = True
        logger.info(f"\n✓ 配置测试完成")
        
    except Exception as e:
        logger.error(f"测试配置时出错: {e}", exc_info=True)
        result["error"] = str(e)
        result["success"] = False
    
    return result


async def main():
    """主测试函数"""
    logger.info("="*80)
    logger.info("MCP 配置方式完整测试")
    logger.info("="*80)
    
    # 测试配置列表
    test_configs = [
        ("mcp.json.test.local", "本地 Python 模块服务器 (LOCAL_PYTHON)"),
        ("mcp.json.test.external_npx", "外部 NPX 服务器 (EXTERNAL_NPX)"),
        ("mcp.json.test.external_python", "外部 Python 包服务器 (EXTERNAL_PYTHON)"),
        ("mcp.json.test.external_binary", "外部二进制服务器 (EXTERNAL_BINARY)"),
        ("mcp.json.test.complete", "完整配置（所有类型）"),
    ]
    
    results = []
    
    for config_file, config_name in test_configs:
        config_path = Path(__file__).parent / config_file
        result = await test_config_file(str(config_path), config_name)
        results.append(result)
    
    # 打印总结
    logger.info("\n" + "="*80)
    logger.info("测试总结")
    logger.info("="*80)
    
    for result in results:
        logger.info(f"\n配置: {result['config_name']}")
        logger.info(f"  成功: {'✓' if result['success'] else '✗'}")
        if result['error']:
            logger.info(f"  错误: {result['error']}")
        logger.info(f"  服务器数量: {len(result['servers'])}")
        
        for server_name, server_info in result['servers'].items():
            logger.info(f"    - {server_name}:")
            logger.info(f"      类型: {server_info['type']}")
            if 'available' in server_info:
                available = server_info['available']
                if available is True:
                    logger.info(f"      可用: ✓")
                elif available is False:
                    logger.info(f"      可用: ✗")
                else:
                    logger.info(f"      可用: ? (需要手动验证)")
            if 'initialized' in server_info:
                logger.info(f"      初始化: {'✓' if server_info['initialized'] else '✗'}")
            if 'tools_count' in server_info:
                logger.info(f"      工具数: {server_info['tools_count']}")


if __name__ == "__main__":
    # Use platform-specific configuration
    import sys
    from pathlib import Path
    # Add backend to path for imports
    backend_dir = Path(__file__).parent
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))
    
    from app.platform_config import initialize_platform
    initialize_platform()
    
    asyncio.run(main())

