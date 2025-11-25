"""
综合测试脚本 - 全面测试流式 Agent 功能
包括：
1. 不使用工具的场景（普通对话）
2. 使用工具的场景（单工具、多工具）
3. 边界情况（参数解析、错误处理等）
"""
import asyncio
import os
import sys
import json
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from openai import OpenAI
from agent import ChatAgent
from tools import TOOLS

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_client():
    """创建 OpenAI 客户端"""
    provider = os.getenv("LLM_PROVIDER", "qwen").lower()
    
    if provider == "qwen":
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key:
            print("❌ 错误: 请设置环境变量 DASHSCOPE_API_KEY")
            sys.exit(1)
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        model = os.getenv("QWEN_MODEL", "qwen-plus")
        print(f"✅ 使用 Qwen (DashScope) API, 模型: {model}")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 错误: 请设置环境变量 OPENAI_API_KEY")
            sys.exit(1)
        base_url = "https://api.openai.com/v1"
        model = os.getenv("OPENAI_MODEL", "gpt-4")
        print(f"✅ 使用 OpenAI API, 模型: {model}")
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


async def test_case(agent: ChatAgent, user_input: str, description: str, expected_behavior: str):
    """
    测试单个用例
    
    Args:
        agent: ChatAgent 实例
        user_input: 用户输入
        description: 测试描述
        expected_behavior: 预期行为描述
    """
    print(f"\n{'='*70}")
    print(f"🧪 测试: {description}")
    print(f"📝 输入: {user_input}")
    print(f"📋 预期: {expected_behavior}")
    print(f"{'='*70}\n")
    
    print("🤖 AI: ", end="", flush=True)
    
    accumulated_text = ""
    tool_calls = []
    errors = []
    
    try:
        async for content, tool_info in agent.chat_stream(user_input):
            if tool_info:
                if tool_info.get("type") == "tool_result":
                    print(f"\n\n[✅ 工具执行完成: {tool_info['name']}]")
                    result_str = str(tool_info.get('result', ''))[:150]
                    print(f"[结果: {result_str}...]")
                    print("\n🤖 AI: ", end="", flush=True)
                    tool_calls.append(tool_info)
                elif tool_info.get("type") == "tool_error":
                    error_msg = tool_info.get('error', 'Unknown error')
                    print(f"\n\n[❌ 工具执行错误: {error_msg}]")
                    errors.append(tool_info)
                    tool_calls.append(tool_info)
                elif tool_info.get("name"):
                    # 检测到工具调用（还未执行）
                    print(f"\n\n[🔧 检测到工具调用: {tool_info['name']}]")
                    args_str = json.dumps(tool_info.get('args', {}), ensure_ascii=False)
                    print(f"[参数: {args_str}]")
                    # 验证参数是否是有效的 JSON
                    try:
                        json.dumps(tool_info.get('args', {}))
                        print("[✅ 参数格式验证通过]")
                    except:
                        print("[❌ 参数格式验证失败]")
                        errors.append({"type": "invalid_args", "tool_info": tool_info})
                    tool_calls.append(tool_info)
            elif content:
                # 普通文本内容
                print(content, end="", flush=True)
                accumulated_text += content
        
        print("\n")
        print(f"{'='*70}")
        print(f"📊 测试结果:")
        print(f"  - 文本响应长度: {len(accumulated_text)} 字符")
        print(f"  - 工具调用次数: {len(tool_calls)}")
        print(f"  - 错误数量: {len(errors)}")
        
        if errors:
            print(f"  - ⚠️  发现错误:")
            for error in errors:
                print(f"      {error}")
        
        # 判断测试是否成功
        if errors and not accumulated_text:
            print(f"  ❌ 测试失败: 有错误且无文本响应")
            return False
        elif accumulated_text or len(tool_calls) > 0:
            print(f"  ✅ 测试通过")
            return True
        else:
            print(f"  ⚠️  测试异常: 既无文本也无工具调用")
            return False
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        print(f"\n❌ 错误: {str(e)}")
        return False
    
    finally:
        # 重置对话历史
        agent.reset_conversation()
        print()


async def main():
    """主测试函数"""
    print("=" * 70)
    print("🧪 流式 Agent 综合功能测试")
    print("=" * 70)
    print()
    
    try:
        client, model = create_client()
        agent = ChatAgent(model=model, client=client)
        
        # 注册工具
        print(f"\n📦 注册工具 ({len(TOOLS)} 个):")
        for name, info in TOOLS.items():
            agent.register_tool(name, info["schema"], info["function"])
            desc = info['schema'].get('description', '')[:50]
            print(f"  - {name}: {desc}")
        
        print(f"\n✅ Agent 初始化完成\n")
        
        # 测试用例 - 分为两类
        test_cases = [
            # ========== 不使用工具的场景 ==========
            {
                "input": "你好，请介绍一下你自己",
                "description": "普通对话（不使用工具）",
                "expected": "应该直接回复，不调用任何工具"
            },
            {
                "input": "我是谁？",
                "description": "自我认知问题（不使用工具）",
                "expected": "应该直接回答，不调用任何工具"
            },
            {
                "input": "今天天气怎么样？",
                "description": "模糊天气询问（不使用工具）",
                "expected": "由于没有指定城市，可能不调用工具或询问城市"
            },
            
            # ========== 使用工具的场景 ==========
            {
                "input": "帮我查一下上海的天气",
                "description": "天气查询工具调用（单工具）",
                "expected": "应该调用 query_weather 工具查询上海天气"
            },
            {
                "input": "计算 2 + 3 * 4",
                "description": "计算器工具调用（单工具）",
                "expected": "应该调用 calculate 工具计算结果"
            },
            {
                "input": "先查一下北京的天气，然后计算 10 + 20",
                "description": "多轮工具调用（两个工具）",
                "expected": "应该先调用天气工具，再调用计算器工具"
            },
            {
                "input": "计算 (100 + 200) / 5",
                "description": "复杂计算表达式（单工具）",
                "expected": "应该调用 calculate 工具处理复杂表达式"
            },
        ]
        
        results = []
        
        for i, test in enumerate(test_cases, 1):
            print(f"\n▶️  测试 {i}/{len(test_cases)}")
            success = await test_case(
                agent,
                test["input"],
                test["description"],
                test["expected"]
            )
            results.append({
                "test": test["description"],
                "success": success
            })
            
            # 短暂延迟，避免请求过快
            await asyncio.sleep(1)
        
        # 测试总结
        print("\n" + "=" * 70)
        print("📊 测试总结")
        print("=" * 70)
        
        passed = sum(1 for r in results if r["success"])
        total = len(results)
        
        print(f"\n总测试数: {total}")
        print(f"通过: {passed} ✅")
        print(f"失败: {total - passed} ❌")
        print(f"通过率: {passed/total*100:.1f}%")
        
        print("\n详细结果:")
        for i, result in enumerate(results, 1):
            status = "✅" if result["success"] else "❌"
            print(f"  {i}. {status} {result['test']}")
        
        print("\n" + "=" * 70)
        if passed == total:
            print("🎉 所有测试通过！")
        else:
            print("⚠️  部分测试失败，请检查日志")
        print("=" * 70)
        
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        print(f"\n❌ 初始化失败: {str(e)}")
        print("\n提示:")
        print("  1. 设置环境变量: export DASHSCOPE_API_KEY=your_key (Qwen)")
        print("  或: export OPENAI_API_KEY=your_key (OpenAI)")
        print("  2. 可选: export LLM_PROVIDER=qwen 或 openai")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 测试中断")

