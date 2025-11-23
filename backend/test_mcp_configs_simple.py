#!/usr/bin/env python3
"""
简化版 MCP 配置测试 - 只测试配置检测，不实际连接服务器
"""
import json
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.mcp_tools.server_manager import MCPServerManager, ServerType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_config_file(config_path: str, config_name: str) -> dict:
    """
    测试指定的配置文件（仅配置检测，不实际连接）
    
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
            
            # 对于外部服务器，做快速检查
            if server_type == ServerType.EXTERNAL_NPX:
                import shutil
                if shutil.which("npx"):
                    logger.info(f"  ✓ npx 命令可用")
                    server_info["available"] = True
                else:
                    logger.warning(f"  ✗ npx 命令不可用")
                    server_info["available"] = False
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
            elif server_type == ServerType.LOCAL_PYTHON:
                logger.info(f"  ✓ 本地 Python 模块（无需检查）")
                server_info["available"] = True
            elif server_type == ServerType.EXTERNAL_BINARY:
                command = server_config.get("command", "")
                import shutil
                if shutil.which(command) or Path(command).exists():
                    logger.info(f"  ✓ 二进制文件存在或命令可用")
                    server_info["available"] = True
                else:
                    logger.warning(f"  ⚠ 二进制文件不存在（路径: {command}）")
                    server_info["available"] = False
            
            result["servers"][server_name] = server_info
            logger.info("")
        
        result["success"] = True
        logger.info(f"✓ 配置测试完成")
        
    except Exception as e:
        logger.error(f"测试配置时出错: {e}", exc_info=True)
        result["error"] = str(e)
        result["success"] = False
    
    return result


def main():
    """主测试函数"""
    logger.info("="*80)
    logger.info("MCP 配置方式完整测试（仅配置检测）")
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
        result = test_config_file(str(config_path), config_name)
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
                    logger.info(f"      可用: ?")


if __name__ == "__main__":
    main()


