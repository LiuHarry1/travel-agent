"""
ChatGPT/豆包式智能 Agent - 支持流式输出中判断 function call
核心逻辑: 在流式输出的第一帧就能判断是否要调用工具
"""
from __future__ import annotations

import json
import logging
from typing import List, Dict, Callable, Optional, AsyncGenerator, Tuple

from openai import OpenAI

logger = logging.getLogger(__name__)


class ChatAgent:
    """ChatGPT/豆包风格的智能 Agent，支持流式输出和自动工具调用"""

    def __init__(self, model: str = "gpt-4", client: OpenAI = None):
        """
        初始化 Agent
        
        Args:
            model: 模型名称
            client: OpenAI 客户端实例
        """
        self.client = client
        self.model = model
        self.tools: Dict[str, Dict] = {}  # {name: {"schema": ..., "function": ...}}
        self.messages: List[Dict] = []

    def register_tool(self, name: str, description: dict, func: Callable):
        """
        注册一个工具，模型看到结构化 schema，Python 执行真实函数
        
        Args:
            name: 工具名称
            description: 工具描述（OpenAI function schema）
            func: 工具函数
        """
        self.tools[name] = {"schema": description, "function": func}
        logger.info(f"Registered tool: {name}")

    def get_openai_tools_schema(self) -> List[Dict]:
        """获取 OpenAI 格式的工具 schema"""
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    **info["schema"]
                }
            }
            for name, info in self.tools.items()
        ]

    async def chat_stream(
        self, 
        user_input: str,
        max_iterations: int = 10
    ) -> AsyncGenerator[Tuple[str, Optional[Dict]], None]:
        """
        主入口: 流式对话，自动判断是否调用工具
        
        流式输出过程中，在第一帧就能判断是否要调用工具:
        - 如果是普通回复，直接流式输出文本
        - 如果检测到 tool call，立即停止流式输出，执行工具，然后继续对话
        
        Args:
            user_input: 用户输入
            max_iterations: 最大迭代次数（防止无限循环）
            
        Yields:
            Tuple[str, Optional[Dict]]:
            - 第一个元素: 文本内容块（如果是普通回复）
            - 第二个元素: 工具调用信息（如果是 tool call），格式: {"name": "...", "args": {...}, "result": "..."}
        """
        # 添加用户消息
        self.messages.append({"role": "user", "content": user_input})
        
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n{'='*60}\nIteration {iteration}\n{'='*60}")
            
            # Step 1: 流式模型回复（自动判断是否要 tool call）
            tool_call_detected = False
            tool_call_data: Optional[Dict] = None  # Will be set after stream ends if tool call detected
            accumulated_text = ""
            
            # 准备请求
            tools_schema = self.get_openai_tools_schema()
            
            stream_params = {
                "model": self.model,
                "messages": self.messages,
                "stream": True,
            }
            
            # 如果有工具，添加 tools 参数
            if tools_schema:
                stream_params["tools"] = tools_schema
                stream_params["tool_choice"] = "auto"  # 让模型决定
            
            logger.info(f"Starting stream request with {len(tools_schema)} tools available")
            
            try:
                # 创建流式请求
                stream = self.client.chat.completions.create(**stream_params)
                
                # 跟踪 tool call 状态
                current_tool_call: Optional[Dict] = None
                tool_call_id: Optional[str] = None
                tool_call_name: Optional[str] = None
                tool_call_args_buffer = ""
                
                # 处理流式响应（同步流转为异步处理）
                for chunk in stream:
                    # 检查是否是 tool call
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        
                        # 检查 tool_calls（OpenAI 格式）
                        if hasattr(delta, 'tool_calls') and delta.tool_calls:
                            tool_call_detected = True
                            
                            for tool_call_delta in delta.tool_calls:
                                # 初始化 tool call 结构
                                if current_tool_call is None:
                                    tool_call_id = getattr(tool_call_delta, 'id', None)
                                    current_tool_call = {
                                        "id": tool_call_id or f"call_{iteration}",
                                        "type": "function",
                                        "function": {"name": "", "arguments": ""}
                                    }
                                
                                # 累积 tool call 信息
                                func_delta = getattr(tool_call_delta, 'function', None)
                                if func_delta:
                                    func_name = getattr(func_delta, 'name', None)
                                    if func_name:
                                        tool_call_name = func_name
                                        current_tool_call["function"]["name"] = tool_call_name
                                    func_args = getattr(func_delta, 'arguments', None)
                                    if func_args:
                                        tool_call_args_buffer += func_args
                                        current_tool_call["function"]["arguments"] += func_args
                        
                        # 检查普通文本内容
                        content = getattr(delta, 'content', None)
                        if content:
                            if not tool_call_detected:
                                # 只在没有检测到 tool call 时输出文本
                                text_chunk = content
                                accumulated_text += text_chunk
                                yield (text_chunk, None)
                    
                    # 如果检测到 tool call，可以提前停止（可选）
                    # 但为了完整收集 tool call 参数，我们继续处理流
                
                # 流式结束后的处理
                if tool_call_detected and current_tool_call:
                    # 验证并解析 tool call 参数
                    tool_name = tool_call_name or current_tool_call["function"]["name"]
                    
                    if not tool_name:
                        logger.warning("Tool call detected but no name found")
                        # 没有名称，可能还在传输中，继续等待或返回错误
                        yield ("", {
                            "type": "tool_error",
                            "name": "unknown",
                            "error": "工具调用检测到但名称未完成"
                        })
                        return
                    
                    # 验证 arguments 是否是完整的 JSON
                    if not tool_call_args_buffer:
                        # 空参数 - 可能是工具不需要参数
                        args = {}
                        logger.info(f"🔧 Tool call detected: {tool_name} (no arguments)")
                        tool_call_data = {
                            "id": current_tool_call["id"],
                            "name": tool_name,
                            "args": args,
                            "raw": current_tool_call
                        }
                        yield ("", tool_call_data)  # 发送 tool call 信息，无文本内容
                    else:
                        # CRITICAL: 验证 JSON 完整性
                        try:
                            args = json.loads(tool_call_args_buffer)
                            logger.info(f"🔧 Tool call detected: {tool_name} with valid args: {args}")
                            tool_call_data = {
                                "id": current_tool_call["id"],
                                "name": tool_name,
                                "args": args,
                                "raw": current_tool_call
                            }
                            yield ("", tool_call_data)  # 发送 tool call 信息，无文本内容
                        except json.JSONDecodeError as e:
                            # JSON 不完整或无效 - 这是一个严重错误
                            logger.error(
                                f"❌ Failed to parse tool call arguments for '{tool_name}': "
                                f"'{tool_call_args_buffer[:200]}'. Error: {e}. "
                                f"This indicates incomplete or invalid JSON."
                            )
                            # 返回错误并添加到消息历史
                            self.messages.append({
                                "role": "assistant",
                                "tool_calls": [{
                                    "id": current_tool_call["id"],
                                    "type": "function",
                                    "function": {
                                        "name": tool_name,
                                        "arguments": tool_call_args_buffer
                                    }
                                }]
                            })
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": current_tool_call["id"],
                                "content": f"Error: 工具参数解析失败，JSON格式不完整或无效。"
                            })
                            yield ("", {
                                "type": "tool_error",
                                "name": tool_name,
                                "error": f"工具参数解析失败：JSON格式不完整或无效。原始参数: {tool_call_args_buffer[:100]}"
                            })
                            # 不设置 tool_call_data，继续循环让模型处理错误
                            tool_call_data = None
                    
                if accumulated_text and not tool_call_detected:
                    # 普通回复，已经通过 yield 输出了所有文本块
                    logger.info(f"✅ Normal response (length: {len(accumulated_text)})")
                    # 添加助手回复到消息历史
                    self.messages.append({
                        "role": "assistant",
                        "content": accumulated_text
                    })
                    return  # 对话结束
                    
            except Exception as e:
                logger.error(f"Error in stream: {e}", exc_info=True)
                yield (f"Error: {str(e)}", None)
                return
            
            # Step 2: 如果有 tool call，执行工具
            if tool_call_data and tool_call_data.get("name"):
                tool_name = tool_call_data["name"]
                tool_args = tool_call_data.get("args", {})
                
                # 验证工具是否存在
                if tool_name not in self.tools:
                    logger.error(f"Tool '{tool_name}' not found in registered tools")
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_data.get("id", "unknown"),
                        "content": f"Error: 工具 '{tool_name}' 未注册"
                    })
                    yield ("", {
                        "type": "tool_error",
                        "name": tool_name,
                        "error": f"工具 '{tool_name}' 未注册"
                    })
                    continue  # 继续循环，让模型处理错误
                
                # 执行工具
                logger.info(f"⚙️  Executing tool: {tool_name} with args: {tool_args}")
                
                try:
                    tool_func = self.tools[tool_name]["function"]
                    tool_result = tool_func(**tool_args) if tool_args else tool_func()
                    
                    # 如果工具结果是字典，转换为 JSON 字符串
                    if isinstance(tool_result, dict):
                        tool_result_str = json.dumps(tool_result, ensure_ascii=False)
                    else:
                        tool_result_str = str(tool_result)
                    
                    tool_call_data["result"] = tool_result_str
                    logger.info(f"✅ Tool result: {tool_result_str[:200]}")
                    
                    # 发送工具执行结果
                    yield ("", {"type": "tool_result", **tool_call_data})
                    
                    # Step 3: 将工具调用和结果添加到消息历史，让模型继续思考
                    self.messages.append({
                        "role": "assistant",
                        "tool_calls": [{
                            "id": tool_call_data["id"],
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_args, ensure_ascii=False)
                            }
                        }]
                    })
                    
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_data["id"],
                        "content": tool_result_str
                    })
                    
                    # 继续循环，让模型基于工具结果继续回复
                    # 下一次迭代会自动开始
                    
                except Exception as e:
                    logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
                    # 添加错误消息到对话历史
                    self.messages.append({
                        "role": "assistant",
                        "tool_calls": [{
                            "id": tool_call_data.get("id", "unknown"),
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": json.dumps(tool_args, ensure_ascii=False)
                            }
                        }]
                    })
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_data.get("id", "unknown"),
                        "content": f"Error: {str(e)}"
                    })
                    yield ("", {
                        "type": "tool_error",
                        "name": tool_name,
                        "error": str(e)
                    })
                    # 继续循环，让模型处理错误，而不是直接返回
                    continue
            
            else:
                # 没有 tool call，也没有文本（异常情况）
                logger.warning("No tool call and no text content received")
                # 如果已经尝试了多次，停止
                if iteration >= max_iterations:
                    logger.error(f"Reached max iterations ({max_iterations}) without content")
                    yield ("抱歉，处理请求时遇到问题。请重试。", None)
                return


    def reset_conversation(self):
        """重置对话历史"""
        self.messages = []
        logger.info("Conversation history reset")

