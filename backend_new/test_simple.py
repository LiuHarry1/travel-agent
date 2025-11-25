"""
简单测试 - 测试使用工具和不使用工具的场景
"""
import asyncio
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from openai import OpenAI
from agent import ChatAgent
from tools import TOOLS

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def create_client():
    """创建 OpenAI 客户端"""
    provider = os.getenv("LLM_PROVIDER", "qwen").lower()
    
    if provider == "qwen":
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key:
            print("❌ 请设置环境变量 DASHSCOPE_API_KEY")
            sys.exit(1)
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        model = os.getenv("QWEN_MODEL", "qwen-plus")
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 请设置环境变量 OPENAI_API_KEY")
            sys.exit(1)
        base_url = "https://api.openai.com/v1"
        model = os.getenv("OPENAI_MODEL", "gpt-4")
    
    return OpenAI(api_key=api_key, base_url=base_url), model


async def test_case(agent: ChatAgent, user_input: str, case_type: str):
    """测试单个用例"""
    print(f"\n{'='*60}")
    print(f"🧪 {case_type}: {user_input}")
    print(f"{'='*60}\n")
    
    print("🤖 AI: ", end="", flush=True)
    
    accumulated_text = ""
    tool_calls = []
    errors = []
    
    try:
        async for content, tool_info in agent.chat_stream(user_input):
            if tool_info:
                if tool_info.get("type") == "tool_result":
                    print(f"\n\n[✅ 工具执行: {tool_info['name']}]")
                    print(f"[结果: {str(tool_info.get('result', ''))[:100]}...]")
                    print("\n🤖 AI: ", end="", flush=True)
                    tool_calls.append(tool_info)
                elif tool_info.get("type") == "tool_error":
                    print(f"\n\n[❌ 工具错误: {tool_info.get('error', 'Unknown')}]")
                    errors.append(tool_info)
                elif tool_info.get("name"):
                    print(f"\n\n[🔧 工具调用: {tool_info['name']}]")
                    print(f"[参数: {tool_info.get('args', {})}]")
                    tool_calls.append(tool_info)
            elif content:
                print(content, end="", flush=True)
                accumulated_text += content
        
        print("\n")
        
        # 验证结果
        if case_type == "不使用工具" and len(tool_calls) == 0 and accumulated_text:
            print(f"✅ 通过: 没有调用工具，有文本回复 ({len(accumulated_text)} 字符)")
            return True
        elif case_type == "使用工具" and len(tool_calls) > 0:
            print(f"✅ 通过: 调用了 {len(tool_calls)} 个工具")
            return True
        elif errors:
            print(f"❌ 失败: 有错误发生")
            return False
        else:
            print(f"⚠️  结果异常")
            return False
            
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        print(f"\n❌ 错误: {str(e)}")
        return False
    finally:
        agent.reset_conversation()


async def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 流式 Agent 功能测试")
    print("=" * 60)
    
    try:
        client, model = create_client()
        agent = ChatAgent(model=model, client=client)
        
        # 注册工具
        for name, info in TOOLS.items():
            agent.register_tool(name, info["schema"], info["function"])
        
        print(f"\n✅ Agent 初始化 - 模型: {model}, 工具数: {len(TOOLS)}\n")
        
        # 测试用例
        test_cases = [
            ("你好，介绍一下你自己", "不使用工具"),
            ("我是谁？", "不使用工具"),
            ("帮我查一下上海的天气", "使用工具"),
            ("计算 2 + 3 * 4", "使用工具"),
        ]
        
        results = []
        for user_input, case_type in test_cases:
            success = await test_case(agent, user_input, case_type)
            results.append(success)
            await asyncio.sleep(1)
        
        # 总结
        print("\n" + "=" * 60)
        print(f"📊 测试结果: {sum(results)}/{len(results)} 通过")
        print("=" * 60)
        
        if all(results):
            print("🎉 所有测试通过！")
        else:
            print("⚠️  部分测试失败")
        
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        print(f"\n❌ 初始化失败: {str(e)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 测试中断")

