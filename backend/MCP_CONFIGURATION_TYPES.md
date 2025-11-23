# MCP 配置方式完整说明

本文档说明所有支持的 MCP 服务器配置方式。

## 支持的配置类型

系统支持以下 4 种 MCP 服务器配置类型：

### 1. 本地 Python 模块服务器 (LOCAL_PYTHON)

**用途**：运行项目内部的 Python MCP 服务器模块

**配置格式**：
```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["-m", "app.mcp_tools.module_name.server"]
    }
  }
}
```

**特点**：
- 模块路径必须以 `app.mcp_tools.` 开头
- 无需安装，直接使用项目内的代码
- 自动设置工作目录为 `backend/` 目录

**示例**：
- `faq` - FAQ 服务器
- `travel-doc-retriever` - 旅行文档检索服务器

**测试文件**：`mcp.json.test.local`

---

### 2. 外部 NPX 服务器 (EXTERNAL_NPX)

**用途**：通过 npx 运行 npm 包中的 MCP 服务器

**配置格式**：
```json
{
  "mcpServers": {
    "server-name": {
      "command": "npx",
      "args": ["-y", "package-name@version"],
      "env": {
        "ENV_VAR": "value"
      }
    }
  }
}
```

**特点**：
- 使用 `npx` 命令运行
- `-y` 参数自动下载和安装包（如果未安装）
- 支持环境变量配置
- 需要系统安装 Node.js 和 npm

**示例**：
- `tavily-mcp` - Tavily 搜索服务器

**测试文件**：`mcp.json.test.external_npx`

---

### 3. 外部 Python 包服务器 (EXTERNAL_PYTHON)

**用途**：运行外部安装的 Python 包中的 MCP 服务器

**配置格式**：
```json
{
  "mcpServers": {
    "server-name": {
      "command": "python",
      "args": ["-m", "external_package.module.server"],
      "env": {
        "API_KEY": "your-api-key"
      }
    }
  }
}
```

**特点**：
- 模块路径不以 `app.mcp_tools.` 开头
- 需要先安装外部 Python 包（`pip install package-name`）
- 支持环境变量配置

**示例**：
```json
{
  "example-external-python": {
    "command": "python",
    "args": ["-m", "some_external_mcp_package.server"],
    "env": {
      "API_KEY": "your-api-key-here"
    }
  }
}
```

**测试文件**：`mcp.json.test.external_python`

---

### 4. 外部二进制服务器 (EXTERNAL_BINARY)

**用途**：运行外部二进制可执行文件或脚本

**配置格式**：
```json
{
  "mcpServers": {
    "server-name": {
      "command": "/path/to/binary",
      "args": ["--option", "value"],
      "env": {
        "ENV_VAR": "value"
      }
    }
  }
}
```

**特点**：
- 可以是任何可执行文件（二进制、脚本等）
- 支持绝对路径或系统 PATH 中的命令
- 支持命令行参数和环境变量

**示例**：
```json
{
  "example-binary": {
    "command": "/path/to/mcp-server-binary",
    "args": ["--config", "/path/to/config.json"]
  },
  "example-script": {
    "command": "bash",
    "args": ["/path/to/mcp-server.sh"],
    "env": {
      "ENV_VAR": "value"
    }
  }
}
```

**测试文件**：`mcp.json.test.external_binary`

---

## 配置选项说明

所有配置类型都支持以下选项：

### 必需选项

- `command`: 启动命令（字符串）
- `args`: 命令参数列表（数组）

### 可选选项

- `env`: 环境变量字典（对象）
  ```json
  "env": {
    "API_KEY": "your-key",
    "MAX_RESULTS": "10"
  }
  ```

- `cwd`: 工作目录（字符串，代码支持但当前未在配置中使用）
  ```json
  "cwd": "/path/to/working/directory"
  ```

---

## 类型检测规则

系统根据以下规则自动检测服务器类型：

1. **LOCAL_PYTHON**: `command == "python"` 且 `args[0] == "-m"` 且 `args[1].startswith("app.mcp_tools.")`
2. **EXTERNAL_NPX**: `command == "npx"`
3. **EXTERNAL_PYTHON**: `command == "python"` 且 `args[0] == "-m"` 且 `args[1]` 不以 `app.mcp_tools.` 开头
4. **EXTERNAL_BINARY**: 其他所有情况

---

## 测试配置文件

已创建以下测试配置文件，可用于测试每种配置类型：

1. `mcp.json.test.local` - 本地 Python 模块配置
2. `mcp.json.test.external_npx` - 外部 NPX 配置
3. `mcp.json.test.external_python` - 外部 Python 包配置
4. `mcp.json.test.external_binary` - 外部二进制配置
5. `mcp.json.test.complete` - 完整配置（包含所有类型）

---

## 测试脚本

运行测试脚本验证配置：

```bash
# 简化版测试（仅配置检测，不实际连接）
python test_mcp_configs_simple.py

# 完整版测试（包含实际连接测试）
python test_mcp_configs.py
```

---

## 当前使用的配置

查看 `mcp.json` 了解当前实际使用的配置：

- `faq` - LOCAL_PYTHON
- `travel-doc-retriever` - LOCAL_PYTHON
- `tavily-mcp` - EXTERNAL_NPX

---

## 注意事项

1. **外部服务器可用性**：外部服务器（NPX、Python 包、二进制）需要确保已正确安装或路径正确
2. **环境变量**：敏感信息（如 API 密钥）应通过 `env` 配置，不要硬编码在配置文件中
3. **工作目录**：本地 Python 模块服务器会自动设置工作目录，其他类型需要手动指定（如需要）
4. **错误处理**：如果外部服务器不可用，系统会记录警告但不会阻止其他服务器运行


