# 代理服务器配置说明

## 测试结果

测试脚本已成功找到可用的配置！代理服务器 `api.gptsapi.net` 使用 **OpenAI 兼容格式**，不是 Azure OpenAI 格式。

## 配置步骤

### 1. 设置环境变量

在 Windows PowerShell 中：
```powershell
$env:AZURE_OPENAI_ENDPOINT="https://api.gptsapi.net/v1"
$env:AZURE_OPENAI_API_KEY="sk-8oV6db93aa678ac0b4263f32ef139be5de87c7d259ad6jpR"
```

或者在 `.env` 文件中添加：
```
AZURE_OPENAI_ENDPOINT=https://api.gptsapi.net/v1
AZURE_OPENAI_API_KEY=sk-8oV6db93aa678ac0b4263f32ef139be5de87c7d259ad6jpR
```

### 2. 在 Admin 页面配置模型

1. 打开 Admin Settings 页面
2. 选择 Provider: **Azure OpenAI**
3. 选择 Model: **gpt-4-turbo** (或其他可用模型，如 gpt-4, gpt-3.5-turbo, gpt-4o, gpt-4o-mini)
4. 点击 "Update Configuration"

### 3. 可用的模型列表

根据测试结果，以下模型可用：
- `gpt-4-turbo` ✅
- `gpt-4` ✅
- `gpt-3.5-turbo` ✅
- `gpt-4o` ✅
- `gpt-4o-mini` ✅

## 技术细节

### 代理服务器格式

代理服务器使用 **OpenAI 兼容格式**：
- **Base URL**: `https://api.gptsapi.net/v1`
- **Endpoint**: `/chat/completions`
- **认证**: `Authorization: Bearer {api_key}` (不是 `api-key` 头部)
- **模型名称**: 在请求体中（不是 URL 中）

### 代码自动检测

系统会自动检测代理服务器（通过检查 URL 中是否包含 `gptsapi.net`），并自动使用 OpenAI 兼容格式。

## 测试

运行测试脚本验证配置：
```powershell
python backend\test_azure_proxy.py sk-8oV6db93aa678ac0b4263f32ef139be5de87c7d259ad6jpR
```

## 注意事项

1. **Base URL 必须包含 `/v1`**: `https://api.gptsapi.net/v1`
2. **API Key 格式**: 使用 `sk-` 开头的 OpenAI 格式密钥
3. **模型名称**: 在 Admin 页面选择，会保存在 `config.yaml` 的 `azure_model` 字段中

