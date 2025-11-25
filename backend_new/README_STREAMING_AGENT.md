# 🚀 流式输出中判断 Function Call 的示例

这是一个演示如何在流式输出过程中立即判断是否使用 function call 的完整示例。

## ✨ 特性

- ✅ **流式输出**: 实时流式输出响应内容
- ✅ **实时判断**: 在第一帧就能判断是否需要调用工具
- ✅ **自动执行**: 自动执行工具并继续对话
- ✅ **多轮对话**: 支持多轮工具调用循环
- ✅ **Qwen/GPT 通用**: 支持 Qwen（豆包）和 OpenAI GPT-4/5

## 📁 项目结构

```
backend_new/
├── agent.py          # 核心 Agent 逻辑（流式判断 function call）
├── main.py           # 命令行测试入口
├── server.py         # FastAPI SSE 流式接口
├── tools/
│   ├── __init__.py   # 工具导出
│   ├── weather.py    # 天气查询工具
│   └── calculator.py # 计算器工具
└── README_STREAMING_AGENT.md
```

## 🚀 快速开始

### 1. 安装依赖

```bash
cd backend_new
pip install -r requirements.txt
```

### 2. 配置 API Key

**使用 Qwen (DashScope):**
```bash
export DASHSCOPE_API_KEY=your_dashscope_api_key
export LLM_PROVIDER=qwen  # 可选，默认就是 qwen
export QWEN_MODEL=qwen-plus  # 可选，默认 qwen-plus
```

**使用 OpenAI:**
```bash
export OPENAI_API_KEY=your_openai_api_key
export LLM_PROVIDER=openai
export OPENAI_MODEL=gpt-4  # 可选，默认 gpt-4
```

### 3. 命令行测试

```bash
python main.py
```

**运行示例:**
```
👤 You: 帮我查一下上海的天气
🤖 AI: 我来帮您查询上海的天气...

[🔧 检测到工具调用: query_weather]
[参数: {'city': '上海'}]
[执行中...]

[✅ 工具执行完成: query_weather]
[结果: {"city": "上海", "weather": "晴天", "temperature": "28°C", "humidity": "65%"}...]

🤖 AI: 上海的天气情况如下：
- 天气：晴天
- 温度：28°C
- 湿度：65%
```

### 4. Web API 测试

**启动服务器:**
```bash
python server.py
# 或
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**测试接口:**
```bash
# 使用 curl
curl -X POST http://localhost:8001/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "计算 2 + 3 * 4"}' \
  --no-buffer

# 使用 Python
import requests
import json

response = requests.post(
    "http://localhost:8001/chat/stream",
    json={"message": "计算 2 + 3 * 4"},
    stream=True
)

for line in response.iter_lines():
    if line:
        data = line.decode('utf-8')
        if data.startswith('data: '):
            event = json.loads(data[6:])
            print(event)
```

## 🧠 核心逻辑说明

### 流式判断 Function Call 的关键代码

在 `agent.py` 的 `chat_stream` 方法中：

```python
async for chunk in stream:
    delta = chunk.choices[0].delta
    
    # 检查 tool_calls（OpenAI 格式）
    if hasattr(delta, 'tool_calls') and delta.tool_calls:
        tool_call_detected = True
        # 收集 tool call 信息
        ...
    
    # 检查普通文本内容
    if hasattr(delta, 'content') and delta.content:
        if not tool_call_detected:
            # 只在没有检测到 tool call 时输出文本
            yield (content, None)
```

### 工作流程

1. **用户输入** → 添加到消息历史
2. **流式请求** → 开始流式接收响应
3. **实时判断**:
   - 如果检测到 `tool_calls` → 立即停止文本输出，收集工具调用信息
   - 如果只有 `content` → 持续流式输出文本
4. **执行工具** → 如果检测到工具调用，执行工具函数
5. **继续对话** → 将工具结果添加到消息历史，让模型继续回复
6. **循环** → 支持多轮工具调用

## 🎯 与参考代码的区别

参考代码使用的是同步流式处理，本示例使用异步流式处理，更适合 Web 应用场景。

关键改进：
- ✅ 完全异步，支持高并发
- ✅ 更清晰的错误处理
- ✅ 支持会话隔离（可扩展）
- ✅ 标准 SSE 格式输出

## 📝 添加新工具

1. 在 `tools/` 目录创建新工具文件
2. 实现工具函数和 schema
3. 在 `tools/__init__.py` 中导出

示例:
```python
# tools/my_tool.py
def my_tool(param: str) -> dict:
    return {"result": f"处理了: {param}"}

schema = {
    "description": "工具描述",
    "parameters": {
        "type": "object",
        "properties": {
            "param": {"type": "string"}
        },
        "required": ["param"]
    }
}
```

## 🧪 测试用例

```bash
# 1. 普通对话（不使用工具）
"你好，介绍一下你自己"

# 2. 天气查询（使用工具）
"帮我查一下北京的天气"

# 3. 数学计算（使用工具）
"计算 (10 + 5) * 3"

# 4. 多轮工具调用
"先查一下上海的天气，然后计算 20 + 30"
```

## 🔧 调试技巧

1. **查看日志**: 设置 `logging.INFO` 查看详细流程
2. **检查工具注册**: 访问 `/health` 端点查看已注册的工具
3. **测试工具单独执行**: 在 Python 中直接调用工具函数

## 📚 参考

- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
- [DashScope (Qwen) API](https://help.aliyun.com/zh/dashscope/)
- [FastAPI Streaming](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)

