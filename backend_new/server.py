"""
FastAPI + SSE 流式接口示例
演示如何在 Web 环境中使用流式 Agent
"""
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI

from agent import ChatAgent
from tools import TOOLS

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Streaming Chat Agent API", version="1.0.0")

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局 Agent 实例
_agent: Optional[ChatAgent] = None


def get_agent() -> ChatAgent:
    """获取或创建 Agent 实例"""
    global _agent
    
    if _agent is None:
        # 创建客户端
        provider = os.getenv("LLM_PROVIDER", "qwen").lower()
        
        if provider == "qwen":
            api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")
            if not api_key:
                raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            model = os.getenv("QWEN_MODEL", "qwen-plus")
        elif provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("请设置环境变量 OPENAI_API_KEY")
            base_url = "https://api.openai.com/v1"
            model = os.getenv("OPENAI_MODEL", "gpt-4")
        else:
            raise ValueError(f"不支持的 provider: {provider}")
        
        client = OpenAI(api_key=api_key, base_url=base_url)
        _agent = ChatAgent(model=model, client=client)
        
        # 注册所有工具
        for name, info in TOOLS.items():
            _agent.register_tool(name, info["schema"], info["function"])
        
        logger.info(f"Agent initialized with {len(TOOLS)} tools")
    
    return _agent


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Streaming Chat Agent API",
        "version": "1.0.0",
        "endpoints": {
            "/chat/stream": "POST - 流式对话接口",
            "/health": "GET - 健康检查"
        }
    }


@app.get("/health")
async def health():
    """健康检查"""
    try:
        agent = get_agent()
        return {
            "status": "healthy",
            "tools_count": len(agent.tools),
            "tools": list(agent.tools.keys())
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.post("/chat/stream")
async def chat_stream(request: Request):
    """
    流式对话接口 (SSE)
    
    请求体:
    {
        "message": "用户消息",
        "session_id": "会话ID（可选）"
    }
    
    响应: Server-Sent Events (SSE)
    """
    try:
        data = await request.json()
        user_input = data.get("message", "")
        session_id = data.get("session_id", "default")
        
        if not user_input:
            return StreamingResponse(
                _error_stream("消息不能为空"),
                media_type="text/event-stream"
            )
        
        logger.info(f"Received chat request: session={session_id}, message_length={len(user_input)}")
        
        agent = get_agent()
        
        # 如果需要会话隔离，可以为每个 session_id 创建独立的 agent
        # 这里简化处理，使用全局 agent
        
        return StreamingResponse(
            _stream_chat(agent, user_input, session_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
        
    except Exception as e:
        logger.error(f"Error in chat_stream: {e}", exc_info=True)
        return StreamingResponse(
            _error_stream(str(e)),
            media_type="text/event-stream"
        )


async def _stream_chat(agent: ChatAgent, user_input: str, session_id: str):
    """
    流式对话生成器
    
    输出格式 (SSE):
    data: {"type": "chunk", "content": "..."}
    data: {"type": "tool_call", "name": "...", "args": {...}}
    data: {"type": "tool_result", "name": "...", "result": "..."}
    data: {"type": "done"}
    """
    try:
        async for content, tool_info in agent.chat_stream(user_input):
            if tool_info:
                # 工具调用或工具结果
                event_data = {
                    "type": "tool_call" if "result" not in tool_info else "tool_result",
                    **tool_info
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
                
            elif content:
                # 普通文本内容
                event_data = {
                    "type": "chunk",
                    "content": content
                }
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
        
        # 发送完成信号
        yield "data: " + json.dumps({"type": "done"}, ensure_ascii=False) + "\n\n"
        
    except Exception as e:
        logger.error(f"Error in stream_chat: {e}", exc_info=True)
        error_data = {
            "type": "error",
            "error": str(e)
        }
        yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


async def _error_stream(error_message: str):
    """错误流生成器"""
    error_data = {
        "type": "error",
        "error": error_message
    }
    yield f"data: {json.dumps(error_data, ensure_ascii=False)}\n\n"


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8001))
    logger.info(f"Starting server on port {port}")
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=True
    )

