# 配置说明

MRT Review Agent 的配置通过 YAML 文件管理，默认配置文件位于 `backend/app/config.yaml`。

## 配置文件位置

默认配置文件：`backend/app/config.yaml`

也可以通过环境变量 `MRT_REVIEW_CONFIG` 指定自定义配置文件路径：

```bash
export MRT_REVIEW_CONFIG=/path/to/your/config.yaml
```

## 配置项说明

### LLM 配置 (`llm`)

- `system_prompt`: LLM 系统提示词，用于指导模型如何审查 MRT
- `model`: 使用的 LLM 模型名称（默认：`qwen-max`）
- `timeout`: API 请求超时时间（秒，默认：30.0）

### 默认 Checklist (`default_checklist`)

包含默认的检查项列表，每个检查项包含：
- `id`: 检查项标识符（如 `CHK-001`）
- `description`: 检查项描述

### 关键词映射 (`keyword_mapping`)

为每个 checklist_id 配置关键词列表，用于启发式审查（当 LLM API 不可用时）。如果 MRT 内容中不包含这些关键词，系统会建议补充。

格式：
```yaml
keyword_mapping:
  CHK-001:
    - "objective"
    - "目标"
    - "目的"
  CHK-002:
    - "precondition"
    - "前提"
```

### 额外建议 (`additional_suggestions`)

配置额外的检查建议，这些建议会应用于所有审查，不依赖于 checklist。每个建议包含：
- `id`: 建议标识符
- `keywords`: 关键词列表（如果 MRT 中不包含这些关键词，会触发建议）
- `message`: 建议消息

格式：
```yaml
additional_suggestions:
  - id: "CHK-GEN-REQ"
    keywords:
      - "req-"
      - "需求"
    message: "建议引用需求编号（如 REQ-123）以增强需求追溯性。"
```

## 修改配置

### 修改 Prompt

编辑 `config.yaml` 中的 `llm.system_prompt` 字段：

```yaml
llm:
  system_prompt: |
    你的自定义提示词内容
    可以多行
```

### 修改默认 Checklist

编辑 `config.yaml` 中的 `default_checklist` 部分：

```yaml
default_checklist:
  - id: "CHK-001"
    description: "你的检查项描述"
  - id: "CHK-002"
    description: "另一个检查项"
```

### 添加新的检查项

在 `default_checklist` 列表中添加新项，并为其配置关键词映射：

```yaml
default_checklist:
  - id: "CHK-001"
    description: "测试目标明确且可衡量"
  - id: "CHK-006"  # 新增项
    description: "新的检查项描述"

keyword_mapping:
  CHK-001:
    - "objective"
    - "目标"
  CHK-006:  # 为新项配置关键词
    - "coverage"
    - "覆盖率"
    - "覆盖"
```

**注意**：如果某个 checklist_id 没有在 `keyword_mapping` 中配置，系统会使用通用的检查消息。

### 删除检查项

从 `default_checklist` 列表中移除不需要的项即可。

## 配置生效

修改配置文件后，需要重启后端服务才能生效：

```bash
# 停止当前服务（Ctrl+C）
# 然后重新启动
uvicorn app.main:app --reload --port 8000
```

## 配置验证

配置文件必须是有效的 YAML 格式。如果格式错误，服务启动时会报错。

## 示例配置

完整的配置示例请参考 `backend/app/config.yaml`。

DASHSCOPE_API_KEY=sk-f256c03643e9491fb1ebc278dd958c2d
AZURE_OPENAI_API_KEY=sk-8oV6db93aa678ac0b4263f32ef139be5de87c7d259ad6jpR
AZURE_OPENAI_ENDPOINT=https://api.gptsapi.net/v1