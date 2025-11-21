# LLM Provider 配置指南

本系统支持多个 LLM 提供商，可以在 `config.yaml` 中灵活切换。

## 支持的提供商

1. **Qwen (Alibaba DashScope)** - 默认提供商
2. **Azure OpenAI** - Microsoft Azure OpenAI Service
3. **Ollama** - Ollama 本地部署（支持任何 Ollama 模型）

## 配置方式

### 在 config.yaml 中配置

```yaml
llm:
  # 选择提供商: qwen, azure_openai 或 ollama
  provider: qwen  # 或 azure_openai, ollama
  
  # 模型配置
  model: qwen-plus  # Qwen 提供商使用的模型，或 Ollama 使用的模型
  azure_model: gpt-4  # Azure OpenAI 提供商使用的部署名称
  # ollama_model: qwen2.5:32b  # 可选：Ollama 专用模型配置（如果设置，会优先使用）
  
  # 请求超时（秒）
  timeout: 60.0
```

### 环境变量配置

#### Qwen (DashScope) 配置

```bash
export DASHSCOPE_API_KEY="your-api-key-here"
# 或
export QWEN_API_KEY="your-api-key-here"
```

#### Azure OpenAI 配置

```bash
export AZURE_OPENAI_API_KEY="your-api-key-here"
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com"
export AZURE_OPENAI_API_VERSION="2024-02-15-preview"  # 可选，默认值
```

#### Ollama 配置

```bash
# Ollama 基础 URL（可选，默认：http://localhost:11434）
export OLLAMA_BASE_URL="http://localhost:11434"

# API Key（可选，Ollama 通常不需要 API Key）
export OLLAMA_API_KEY="your-api-key-here"  # 可选
```

**注意**：
- 确保 Ollama 服务正在运行（默认地址：`http://localhost:11434`）
- 确保已安装并拉取了所需的模型，例如：
  - `ollama pull qwen2.5:32b` - Qwen2.5 32B 模型
  - `ollama pull llama2` - Llama2 模型
  - `ollama pull mistral` - Mistral 模型
  - 等等...
- 在 `config.yaml` 中通过 `model` 或 `ollama_model` 字段指定要使用的模型
- 如果 Ollama 运行在其他地址或端口，请设置 `OLLAMA_BASE_URL` 环境变量

## 切换提供商

### 方法 1: 修改 config.yaml

1. 打开 `backend/app/config.yaml`
2. 修改 `llm.provider` 字段：
   ```yaml
   llm:
     provider: ollama  # 切换到 Ollama
     model: qwen2.5:32b  # 指定要使用的 Ollama 模型
     # 或者使用 ollama_model 字段（优先级更高）
     # ollama_model: qwen2.5:32b
   ```
3. 确保 Ollama 服务正在运行，并且已拉取指定的模型
4. 重启应用，配置会自动生效

### 方法 2: 程序化切换

```python
from app.llm.factory import LLMClientFactory
from app.llm.provider import LLMProvider

# 创建指定提供商的客户端
qwen_client = LLMClientFactory.create_client(LLMProvider.QWEN)
azure_client = LLMClientFactory.create_client(LLMProvider.AZURE_OPENAI)
ollama_client = LLMClientFactory.create_client(LLMProvider.OLLAMA)

# 使用客户端
from app.llm import LLMClient

llm = LLMClient(provider_client=qwen_client)
```

## 架构说明

### 架构设计

```
┌─────────────────────────────────────┐
│  CompletionClient / ChatbotClient   │  (服务层)
│  - 统一的业务接口                    │
│  - 使用 Provider Client 处理请求     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│      LLMClientFactory                │  (工厂层)
│  - 根据配置创建 Provider Client      │
│  - 支持动态切换                      │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│    BaseLLMClient (抽象基类)          │
│  - QwenClient (DashScope)           │
│  - AzureOpenAIClient                │
│  - OllamaClient                     │
│  - 统一的 Provider 接口              │
└─────────────────────────────────────┘
```

### 关键组件

1. **provider.py**: 定义 Provider 实现
   - `BaseLLMClient`: 抽象基类
   - `QwenClient`: DashScope/Qwen 实现
   - `AzureOpenAIClient`: Azure OpenAI 实现
   - `OllamaClient`: Ollama 实现（支持任何 Ollama 模型）
   - `LLMProvider`: 提供商枚举

2. **factory.py**: 工厂类
   - `LLMClientFactory.create_client()`: 创建指定提供商的客户端
   - `LLMClientFactory.get_default_client()`: 从配置创建默认客户端

3. **completion_client.py**: 完成任务客户端
   - 使用 Provider Client 处理请求
   - 统一的业务接口

4. **chatbot_client.py**: 聊天任务客户端
   - 使用 Provider Client 处理请求
   - 统一的业务接口

## 添加新的提供商

如果需要添加新的提供商（例如 OpenAI、Claude 等），只需：

1. 在 `provider.py` 中添加新的 Provider 类：
   ```python
   class NewProviderClient(BaseLLMClient):
       def _get_api_key(self) -> Optional[str]:
           import os
           return os.getenv("NEW_PROVIDER_API_KEY")
       
       def _get_base_url(self) -> str:
           return "https://api.newprovider.com/v1"
       
       # 实现其他必需的方法...
   ```

2. 在 `LLMProvider` 枚举中添加新选项：
   ```python
   class LLMProvider(str, Enum):
       QWEN = "qwen"
       AZURE_OPENAI = "azure_openai"
       NEW_PROVIDER = "new_provider"  # 新增
   ```

3. 在 `LLMClientFactory.create_client()` 中添加分支：
   ```python
   if provider == LLMProvider.NEW_PROVIDER:
       return NewProviderClient(api_key=api_key, config=config)
   ```

4. 更新 `config.yaml` 注释说明新提供商

## 注意事项

1. **API Key 安全**: 请确保 API Key 存储在环境变量中，不要提交到代码仓库
2. **模型兼容性**: 不同提供商的模型名称可能不同，确保在配置中使用正确的模型/部署名称
3. **超时设置**: 根据提供商和网络环境调整 `timeout` 值
4. **错误处理**: 所有 Provider 统一抛出 `LLMError` 异常，便于统一处理

## 测试连通性

### 使用测试脚本

我们提供了一个专门的测试脚本来测试所有提供商的连通性：

```bash
# 在 backend 目录下运行
cd backend
python test_llm_connectivity.py
```

测试脚本会：
1. 检查环境变量配置
2. 测试 Qwen 提供商连通性
3. 测试 Azure OpenAI 提供商连通性
4. 显示详细的测试结果和错误信息

### 程序化测试

```python
# 测试 Qwen 提供商
from app.llm.factory import LLMClientFactory
from app.llm.provider import LLMProvider

client = LLMClientFactory.create_client(LLMProvider.QWEN)
print(f"Provider: {type(client).__name__}")
print(f"Model: {client.model}")
print(f"Has API Key: {client.has_api_key}")

# 测试 Azure OpenAI 提供商
azure_client = LLMClientFactory.create_client(LLMProvider.AZURE_OPENAI)
print(f"Provider: {type(azure_client).__name__}")
print(f"Model: {azure_client.model}")

# 测试 Ollama 提供商
ollama_client = LLMClientFactory.create_client(LLMProvider.OLLAMA)
print(f"Provider: {type(ollama_client).__name__}")
print(f"Model: {ollama_client.model}")
print(f"Base URL: {ollama_client._get_base_url()}")

# 使用测试函数（如果存在）
# from test_llm_connectivity import test_provider
# result = test_provider(LLMProvider.QWEN, "Qwen")
# print(f"Status: {result['status']}")
# if result['status'] == 'success':
#     print(f"Response: {result['response']}")
```

## 向后兼容性

- `DashScopeError` 已重命名为 `LLMError`，但保留了 `DashScopeError` 作为别名以保持向后兼容
- 现有的 `CompletionClient` 和 `ChatbotClient` 接口保持不变，内部实现已更新为使用新的 Provider 架构

