# 架构说明

## LLM 客户端架构

LLM 客户端功能已拆分为独立的模块，支持不同的使用场景。

### 模块结构

```
backend/app/llm/
├── __init__.py          # 导出接口，保持向后兼容
├── base_client.py       # 基础客户端，包含通用 API 调用逻辑
├── completion_client.py # Completion 客户端（用于一次性审查）
└── chatbot_client.py    # Chatbot 客户端（用于对话交互）
```

### 客户端类型

#### 1. BaseLLMClient (`base_client.py`)

基础客户端类，提供：
- API 密钥管理
- 通用 HTTP 请求方法
- 配置管理
- 错误处理

#### 2. CompletionClient (`completion_client.py`)

用于 **Completion** 任务（一次性审查）：
- `review()`: 审查 MRT 内容
- `_heuristic_review()`: 启发式审查（无 API key 时的回退）
- `_parse_suggestions_from_llm()`: 解析 LLM 响应
- `_extract_summary()`: 提取摘要

**使用场景**：
- 传统审查模式（表单提交）
- 需要一次性获取完整审查结果

#### 3. ChatbotClient (`chatbot_client.py`)

用于 **Chatbot** 任务（对话交互）：
- `chat()`: 发送对话消息并获取回复
- `_heuristic_chat()`: 启发式回复（无 API key 时的回退）
- `_extract_response()`: 提取回复内容

**使用场景**：
- 智能对话模式
- 需要多轮交互的场景
- 自定义对话流程

### 使用示例

#### Completion 使用

```python
from app.llm import CompletionClient

client = CompletionClient()
response = client.review(mrt_content, checklist)
```

#### Chatbot 使用

```python
from app.llm import ChatbotClient

client = ChatbotClient()
messages = [
    {"role": "user", "content": "请帮我审查这个 MRT"}
]
response = client.chat(messages, system_prompt="你是测试审查助手")
```

### 向后兼容

为了保持向后兼容，`LLMClient` 仍然可用，它实际上是 `CompletionClient` 的别名：

```python
from app.llm import LLMClient  # 等同于 CompletionClient
```

### 配置

两个客户端共享相同的配置（`config.yaml`）：
- `llm.system_prompt`: 系统提示词
- `llm.model`: 模型名称
- `llm.timeout`: 超时时间

ChatbotClient 可以在调用时覆盖系统提示词。

### 错误处理

所有客户端都使用 `DashScopeError` 处理 API 错误：

```python
from app.llm import DashScopeError

try:
    response = client.review(...)
except DashScopeError as e:
    # 处理 API 错误
    pass
```

