#!/usr/bin/env python3
"""
测试 MCP tools 的并发能力

测试场景：
1. 同一工具的并发调用（最严格的情况）
2. 同一服务器的不同工具并发调用
3. 不同服务器的工具并发调用
"""

import asyncio
import time
import sys
import logging
from pathlib import Path

# 添加项目路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app.mcp_tools.registry import MCPToolRegistry, ToolCall

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_concurrent_same_tool(registry: MCPToolRegistry, tool_name: str, concurrency: int = 10):
    """
    测试同一工具的并发调用
    
    Args:
        registry: MCPToolRegistry 实例
        tool_name: 要测试的工具名称
        concurrency: 并发数量
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"测试场景 1: 同一工具 '{tool_name}' 的 {concurrency} 个并发调用")
    logger.info(f"{'='*60}")
    
    async def call_tool(i: int):
        """单个工具调用"""
        tool_call = ToolCall(
            name=tool_name,
            arguments={"query": f"test query {i}"} if tool_name == "faq" else {"query": f"test {i}"}
        )
        start = time.time()
        try:
            result = await registry.call_tool(tool_call)
            elapsed = time.time() - start
            success = result.success
            return elapsed, success, result.error
        except Exception as e:
            elapsed = time.time() - start
            return elapsed, False, str(e)
    
    # 并发执行
    start_time = time.time()
    results = await asyncio.gather(*[call_tool(i) for i in range(concurrency)])
    total_elapsed = time.time() - start_time
    
    # 分析结果
    successful = sum(1 for _, success, _ in results if success)
    failed = concurrency - successful
    avg_time = sum(elapsed for elapsed, _, _ in results) / len(results)
    min_time = min(elapsed for elapsed, _, _ in results)
    max_time = max(elapsed for elapsed, _, _ in results)
    
    logger.info(f"\n结果统计:")
    logger.info(f"  总耗时: {total_elapsed:.3f}s")
    logger.info(f"  成功: {successful}/{concurrency}")
    logger.info(f"  失败: {failed}/{concurrency}")
    logger.info(f"  平均单个调用时间: {avg_time:.3f}s")
    logger.info(f"  最快调用: {min_time:.3f}s")
    logger.info(f"  最慢调用: {max_time:.3f}s")
    
    # 判断并发能力
    if total_elapsed < avg_time * 2:
        logger.info(f"  ✅ 支持并发（总时间 {total_elapsed:.3f}s < 串行时间 {avg_time * concurrency:.3f}s）")
        logger.info(f"  并发效率: {(avg_time * concurrency / total_elapsed):.2f}x")
    else:
        logger.warning(f"  ⚠️  可能不支持并发（总时间 {total_elapsed:.3f}s 接近串行时间 {avg_time * concurrency:.3f}s）")
        logger.warning(f"  并发效率: {(avg_time * concurrency / total_elapsed):.2f}x")
    
    # 检查错误
    if failed > 0:
        logger.error(f"  失败详情:")
        for i, (elapsed, success, error) in enumerate(results):
            if not success:
                logger.error(f"    调用 {i}: {error}")
    
    return {
        "total_time": total_elapsed,
        "successful": successful,
        "failed": failed,
        "avg_time": avg_time,
        "concurrency_supported": total_elapsed < avg_time * 2
    }


async def test_concurrent_different_tools_same_server(registry: MCPToolRegistry, server_tools: list, concurrency: int = 5):
    """
    测试同一服务器的不同工具并发调用
    
    Args:
        registry: MCPToolRegistry 实例
        server_tools: 同一服务器的工具列表
        concurrency: 每个工具的并发数量
    """
    if len(server_tools) < 2:
        logger.info(f"\n跳过测试：服务器只有 {len(server_tools)} 个工具，无法测试不同工具并发")
        return None
    
    logger.info(f"\n{'='*60}")
    logger.info(f"测试场景 2: 同一服务器的不同工具并发调用")
    logger.info(f"  工具: {server_tools}")
    logger.info(f"{'='*60}")
    
    async def call_tool(tool_name: str, i: int):
        """单个工具调用"""
        tool_call = ToolCall(
            name=tool_name,
            arguments={"query": f"test {i}"}
        )
        start = time.time()
        try:
            result = await registry.call_tool(tool_call)
            elapsed = time.time() - start
            return elapsed, result.success
        except Exception as e:
            elapsed = time.time() - start
            return elapsed, False
    
    # 为每个工具创建并发任务
    tasks = []
    for tool_name in server_tools[:2]:  # 只测试前两个工具
        for i in range(concurrency):
            tasks.append(call_tool(tool_name, i))
    
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    total_elapsed = time.time() - start_time
    
    successful = sum(1 for _, success in results if success)
    avg_time = sum(elapsed for elapsed, _ in results) / len(results)
    
    logger.info(f"\n结果统计:")
    logger.info(f"  总耗时: {total_elapsed:.3f}s")
    logger.info(f"  成功: {successful}/{len(tasks)}")
    logger.info(f"  平均单个调用时间: {avg_time:.3f}s")
    
    return {
        "total_time": total_elapsed,
        "successful": successful,
        "avg_time": avg_time
    }


async def test_concurrent_different_servers(registry: MCPToolRegistry, concurrency: int = 5):
    """
    测试不同服务器的工具并发调用
    
    Args:
        registry: MCPToolRegistry 实例
        concurrency: 每个服务器的并发数量
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"测试场景 3: 不同服务器的工具并发调用")
    logger.info(f"{'='*60}")
    
    # 获取不同服务器的工具
    server_to_tools = {}
    for tool_name, server_name in registry._tool_to_server.items():
        if server_name not in server_to_tools:
            server_to_tools[server_name] = []
        server_to_tools[server_name].append(tool_name)
    
    if len(server_to_tools) < 2:
        logger.info(f"跳过测试：只有 {len(server_to_tools)} 个服务器，无法测试不同服务器并发")
        return None
    
    logger.info(f"  服务器: {list(server_to_tools.keys())}")
    
    async def call_tool(tool_name: str, i: int):
        """单个工具调用"""
        tool_call = ToolCall(
            name=tool_name,
            arguments={"query": f"test {i}"}
        )
        start = time.time()
        try:
            result = await registry.call_tool(tool_call)
            elapsed = time.time() - start
            return elapsed, result.success
        except Exception as e:
            elapsed = time.time() - start
            return elapsed, False
    
    # 为每个服务器创建一个工具调用
    tasks = []
    for server_name, tools in list(server_to_tools.items())[:2]:  # 只测试前两个服务器
        tool_name = tools[0]
        for i in range(concurrency):
            tasks.append(call_tool(tool_name, i))
    
    start_time = time.time()
    results = await asyncio.gather(*tasks)
    total_elapsed = time.time() - start_time
    
    successful = sum(1 for _, success in results if success)
    avg_time = sum(elapsed for elapsed, _ in results) / len(results)
    
    logger.info(f"\n结果统计:")
    logger.info(f"  总耗时: {total_elapsed:.3f}s")
    logger.info(f"  成功: {successful}/{len(tasks)}")
    logger.info(f"  平均单个调用时间: {avg_time:.3f}s")
    logger.info(f"  ✅ 预期完全并发（不同服务器独立连接）")
    
    return {
        "total_time": total_elapsed,
        "successful": successful,
        "avg_time": avg_time
    }


async def main():
    """主测试函数"""
    logger.info("="*60)
    logger.info("MCP Tools 并发能力测试")
    logger.info("="*60)
    
    # 初始化 registry
    registry = MCPToolRegistry()
    try:
        logger.info("\n初始化 MCP servers...")
        await registry.initialize_all()
        logger.info(f"已加载 {len(registry.tools)} 个工具")
        logger.info(f"工具列表: {list(registry.tools.keys())}")
        
        # 测试场景 1: 同一工具的并发调用
        # 选择一个工具进行测试
        available_tools = list(registry.tools.keys())
        if not available_tools:
            logger.error("没有可用的工具进行测试")
            return
        
        test_tool = available_tools[0]
        logger.info(f"\n使用工具 '{test_tool}' 进行测试")
        
        result1 = await test_concurrent_same_tool(registry, test_tool, concurrency=10)
        
        # 测试场景 2: 同一服务器的不同工具（如果有）
        server_to_tools = {}
        for tool_name, server_name in registry._tool_to_server.items():
            if server_name not in server_to_tools:
                server_to_tools[server_name] = []
            server_to_tools[server_name].append(tool_name)
        
        # 找到有多个工具的服务器
        multi_tool_server = None
        for server_name, tools in server_to_tools.items():
            if len(tools) >= 2:
                multi_tool_server = (server_name, tools)
                break
        
        if multi_tool_server:
            result2 = await test_concurrent_different_tools_same_server(
                registry, multi_tool_server[1], concurrency=5
            )
        else:
            logger.info("\n没有找到有多个工具的服务器，跳过场景 2")
            result2 = None
        
        # 测试场景 3: 不同服务器的工具
        if len(server_to_tools) >= 2:
            result3 = await test_concurrent_different_servers(registry, concurrency=5)
        else:
            logger.info("\n没有找到多个服务器，跳过场景 3")
            result3 = None
        
        # 总结
        logger.info(f"\n{'='*60}")
        logger.info("测试总结")
        logger.info(f"{'='*60}")
        
        if result1:
            if result1["concurrency_supported"]:
                logger.info("✅ 场景 1 (同一工具并发): 支持并发")
            else:
                logger.warning("⚠️  场景 1 (同一工具并发): 可能不支持并发，需要优化")
        
        if result2:
            logger.info("✅ 场景 2 (同一服务器不同工具): 测试完成")
        
        if result3:
            logger.info("✅ 场景 3 (不同服务器): 测试完成（预期完全并发）")
        
        # 关闭连接
        await registry.close_all()
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())

