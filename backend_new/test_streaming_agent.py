"""
简单测试脚本 - 验证流式 Agent 功能
不需要交互式输入，直接运行测试用例
"""
import asyncio
import os
import sys
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
    else:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("❌ 错误: 请设置环境变量 OPENAI_API_KEY")
            sys.exit(1)
        base_url = "https://api.openai.com/v1"
        model = os.getenv("OPENAI_MODEL", "gpt-4")
    
    client = OpenAI(api_key=api_key, base_url=base_url)
    return client, model


async def test_case(agent: ChatAgent, user_input: str, description: str):
    """测试单个用例"""
    print(f"\n{'='*60}")
    print(f"🧪 测试: {description}")
    print(f"输入: {user_input}")
    print(f"{'='*60}\n")
    
    print("🤖 AI: ", end="", flush=True)
    
    accumulated_text = ""
    tool_calls = []
    
    try:
        async for content, tool_info in agent.chat_stream(user_input):
            if tool_info:
                if tool_info.get("type") == "tool_result":
                    print(f"\n\n[✅ 工具执行完成: {tool_info['name']}]")
                    print(f"[结果: {str(tool_info['result'])[:150]}...]")
                    print("\n🤖 AI: ", end="", flush=True)
                    tool_calls.append(tool_info)
                elif tool_info.get("name"):
                    print(f"\n\n[🔧 检测到工具调用: {tool_info['name']}]")
                    print(f"[参数: {tool_info['args']}]")
                    tool_calls.append(tool_info)
                elif tool_info.get("type") == "tool_error":
                    print(f"\n\n[❌ 工具执行错误: {tool_info.get('error', 'Unknown')}]")
            elif content:
                print(content, end="", flush=True)
                accumulated_text += content
        
        print("\n")
        print(f"✅ 测试完成 - 文本长度: {len(accumulated_text)}, 工具调用: {len(tool_calls)}")
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        print(f"\n❌ 错误: {str(e)}")
    
    # 重置对话（可选）
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
        
        print(f"✅ Agent 初始化完成 - 模型: {model}, 工具数: {len(TOOLS)}")
        
        # 测试用例
        test_cases = [
            ("你好，介绍一下你自己", "普通对话（不使用工具）"),
            ("帮我查一下上海的天气", "天气查询工具调用"),
            ("计算 2 + 3 * 4", "计算器工具调用"),
            ("先查一下北京的天气，然后计算 10 + 20", "多轮工具调用"),
        ]
        
        for user_input, description in test_cases:
            await test_case(agent, user_input, description)
            await asyncio.sleep(1)  # 短暂延迟
        
        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"初始化失败: {e}", exc_info=True)
        print(f"❌ 初始化失败: {str(e)}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 测试中断")

