# MCP Architecture Documentation

## Overview

This module implements a refactored and optimized MCP (Model Context Protocol) architecture with improved extensibility, reusability, and maintainability.

## Architecture

### Directory Structure

```
app/mcp_tools/
├── core/                    # Core infrastructure
│   ├── base_tool.py         # BaseMCPTool abstract base class
│   ├── base_server.py       # BaseMCPServer base class
│   ├── factory.py           # Factory classes for tools and servers
│   └── __init__.py
├── tools/                   # Tool implementations
│   ├── faq_tool.py          # FAQ search tool
│   ├── retriever_tool.py    # Document retrieval tool
│   └── __init__.py
├── servers/                 # Server implementations
│   ├── faq_server.py        # FAQ MCP server
│   ├── retriever_server.py  # Retriever MCP server
│   └── __init__.py
├── utils/                   # Utility functions
│   ├── result_formatter.py  # Result formatting utilities
│   └── __init__.py
├── faq/                     # Backward compatibility entry points
│   └── server.py
├── travel_doc_retriever/    # Backward compatibility entry points
│   └── server.py
├── client.py                # MCP client for connecting to servers
├── config.py                # MCP configuration loader
├── registry.py              # Tool registry and execution manager
└── server_manager.py        # Server manager for external/local server handling
```

## Core Components

### 1. BaseMCPTool (`core/base_tool.py`)

Abstract base class for all MCP tools. Provides:

- **Unified Interface**: All tools implement `execute()` method
- **Validation**: Automatic argument validation via `validate_arguments()`
- **Error Handling**: Standardized error handling with `ToolExecutionResult`
- **Schema Definition**: Tools define their input schema via `get_input_schema()`

**Key Features:**
- `execute()`: Abstract method that tools must implement
- `execute_with_validation()`: Wraps execution with validation
- `validate_arguments()`: Validates input against schema
- `get_input_schema()`: Returns JSON schema for tool input

**Example:**
```python
from app.mcp_tools.core.base_tool import BaseMCPTool, ToolExecutionResult

class MyTool(BaseMCPTool):
    def __init__(self):
        super().__init__(
            name="my_tool",
            description="My custom tool"
        )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments):
        return ToolExecutionResult(
            success=True,
            data={"result": "..."}
        )
```

### 2. BaseMCPServer (`core/base_server.py`)

Base class for MCP servers. Provides:

- **Automatic Tool Registration**: Tools are automatically registered
- **Standard MCP Protocol**: Implements MCP server protocol
- **Result Formatting**: Automatic result formatting using utility functions
- **Error Handling**: Unified error handling and logging

**Key Features:**
- `__init__()`: Initializes server with list of tools
- `_register_handlers()`: Registers MCP protocol handlers
- `run()`: Runs the server using stdio transport

**Example:**
```python
from app.mcp_tools.core.base_server import BaseMCPServer
from app.mcp_tools.tools.my_tool import MyTool

server = BaseMCPServer(
    server_name="my-server",
    tools=[MyTool()]
)
server.run()
```

### 3. ToolExecutionResult (`core/base_tool.py`)

Standardized result format for tool execution:

```python
@dataclass
class ToolExecutionResult:
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

### 4. MCPToolRegistry (`registry.py`)

Manages connections to multiple MCP servers and provides unified tool discovery and execution.

**Key Features:**
- Lazy loading of tools from servers
- Unified tool execution interface
- Automatic tool discovery from MCP servers
- Error handling with graceful degradation

## Adding New Tools

### Step 1: Create Tool Implementation

Create a new file in `app/mcp_tools/tools/`:

```python
# app/mcp_tools/tools/my_new_tool.py
from app.mcp_tools.core.base_tool import BaseMCPTool, ToolExecutionResult

class MyNewTool(BaseMCPTool):
    def __init__(self):
        super().__init__(
            name="my_new_tool",
            description="Description of my new tool"
        )
    
    def get_input_schema(self):
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"}
            },
            "required": ["query"]
        }
    
    async def execute(self, arguments):
        # Your tool logic here
        return ToolExecutionResult(
            success=True,
            data={"result": "..."}
        )
```

### Step 2: Create Server

Create a new file in `app/mcp_tools/servers/`:

```python
# app/mcp_tools/servers/my_new_server.py
from app.mcp_tools.core.base_server import BaseMCPServer
from app.mcp_tools.tools.my_new_tool import MyNewTool

def create_my_new_server() -> BaseMCPServer:
    tools = [MyNewTool()]
    return BaseMCPServer("my-new-server", tools)

if __name__ == "__main__":
    server = create_my_new_server()
    server.run()
```

### Step 3: Create Entry Point (for backward compatibility)

Create a new directory and entry point:

```python
# app/mcp_tools/my_new/server.py
from app.mcp_tools.servers.my_new_server import create_my_new_server

server = create_my_new_server()
app = server.app

if __name__ == "__main__":
    server.run()
```

### Step 4: Update mcp.json

Add server configuration to `backend/mcp.json`:

```json
{
  "mcpServers": {
    "my-new": {
      "command": "python",
      "args": ["-m", "app.mcp.my_new.server"]
    }
  }
}
```

## Benefits of This Architecture

### 1. **Extensibility**
- Easy to add new tools by extending `BaseMCPTool`
- New servers can be created with minimal code
- Factory pattern allows dynamic tool/server creation

### 2. **Reusability**
- Common functionality in base classes
- Utility functions for common operations
- Standardized interfaces reduce duplication

### 3. **Maintainability**
- Clear separation of concerns
- Consistent code structure
- Comprehensive error handling

### 4. **Testability**
- Tools can be tested independently
- Mock implementations easy to create
- Clear interfaces for unit testing

### 5. **Type Safety**
- Type hints throughout
- Dataclasses for structured data
- Clear return types

## Best Practices

1. **Always extend BaseMCPTool**: Don't implement tools from scratch
2. **Use ToolExecutionResult**: Always return standardized results
3. **Validate inputs**: Use `validate_arguments()` or implement custom validation
4. **Handle errors gracefully**: Return `ToolExecutionResult` with `success=False`
5. **Add metadata**: Include useful metadata in results for logging/debugging
6. **Document schemas**: Provide clear descriptions in input schemas

## Migration Guide

### From Old Architecture

Old tools that returned dictionaries can be migrated:

**Before:**
```python
async def execute(self, arguments):
    return {"answer": "...", "source": "..."}
```

**After:**
```python
async def execute(self, arguments):
    return ToolExecutionResult(
        success=True,
        data={"answer": "...", "source": "..."}
    )
```

The `format_tool_result()` utility function handles both formats for backward compatibility.

