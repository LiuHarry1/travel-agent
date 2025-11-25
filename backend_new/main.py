"""
命令行测试入口 - ChatGPT/豆包风格的智能对话
演示流式输出中判断是否使用 function call
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

# 配置日志
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_client() -> OpenAI:
    """
    创建 OpenAI 客户端
    支持切换 Qwen（豆包）和 GPT-4
    """
    # 从环境变量读取配置
    provider = os.getenv("LLM_PROVIDER", "qwen").lower()
    
    if provider == "qwen":
        # Qwen (DashScope) - 豆包背后同款 API
        api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
        if not api_key:
            raise ValueError("请设置环境变量 DASHSCOPE_API_KEY 或 QWEN_API_KEY")
        
        base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        model = os.getenv("QWEN_MODEL", "qwen-plus")
        logger.info(f"使用 Qwen (DashScope) API, 模型: {model}")
        
    elif provider == "openai":
        # OpenAI GPT-4/5
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("请设置环境变量 OPENAI_API_KEY")
        
        base_url = "https://api.openai.com/v1"
        model = os.getenv("OPENAI_MODEL", "gpt-4")
        logger.info(f"使用 OpenAI API, 模型: {model}")
        
    else:
        raise ValueError(f"不支持的 provider: {provider}，请使用 'qwen' 或 'openai'")
    
    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )
    
    return client, model


async def main():
    """主函数"""
    print("=" * 60)
    print("🚀 ChatGPT/豆包风格智能对话系统")
    print("支持流式输出 + 自动工具调用")
    print("=" * 60)
    print()
    
    try:
        # 创建客户端和 Agent
        client, model = create_client()
        agent = ChatAgent(model=model, client=client)
        
        # 注册所有工具
        print(f"📦 注册 {len(TOOLS)} 个工具:")
        for name, info in TOOLS.items():
            agent.register_tool(name, info["schema"], info["function"])
            print(f"  - {name}: {info['schema'].get('description', '')[:50]}")
        print()
        
        print("💬 开始对话 (输入 'quit' 或 'exit' 退出, 'reset' 重置对话历史)")
        print("-" * 60)
        
        while True:
            try:
                # 获取用户输入
                user_input = input("\n👤 You: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 再见！")
                    break
                
                if user_input.lower() == 'reset':
                    agent.reset_conversation()
                    print("✅ 对话历史已重置")
                    continue
                
                # 流式对话
                print("\n🤖 AI: ", end="", flush=True)
                
                accumulated_text = ""
                tool_called = False
                
                async for content, tool_info in agent.chat_stream(user_input):
                    if tool_info:
                        # 工具调用
                        if tool_info.get("type") == "tool_result":
                            print(f"\n\n[✅ 工具执行完成: {tool_info['name']}]")
                            print(f"[结果: {tool_info['result'][:100]}...]")
                            print("\n🤖 AI: ", end="", flush=True)
                            tool_called = True
                        elif tool_info.get("type") == "tool_error":
                            print(f"\n\n[❌ 工具执行错误: {tool_info.get('error', 'Unknown error')}]")
                        else:
                            # 检测到工具调用
                            print(f"\n\n[🔧 检测到工具调用: {tool_info['name']}]")
                            print(f"[参数: {tool_info['args']}]")
                            print("[执行中...]")
                            tool_called = True
                    elif content:
                        # 普通文本内容
                        print(content, end="", flush=True)
                        accumulated_text += content
                
                if not tool_called and accumulated_text:
                    print()  # 换行
                
                print()  # 额外换行
                
            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                logger.error(f"Error in conversation: {e}", exc_info=True)
                print(f"\n❌ 错误: {str(e)}")
                
    except Exception as e:
        logger.error(f"Failed to initialize: {e}", exc_info=True)
        print(f"❌ 初始化失败: {str(e)}")
        print("\n提示:")
        print("  1. 设置环境变量: export DASHSCOPE_API_KEY=your_key (Qwen)")
        print("  或: export OPENAI_API_KEY=your_key (OpenAI)")
        print("  2. 可选: export LLM_PROVIDER=qwen 或 openai")
        print("  3. 可选: export QWEN_MODEL=qwen-plus")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 再见！")

