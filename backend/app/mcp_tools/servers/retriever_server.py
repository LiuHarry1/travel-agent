"""Travel document retriever MCP server."""
from __future__ import annotations

from ..core.base_server import BaseMCPServer
from ..tools.retriever_tool import RetrieverTool


def create_retriever_server() -> BaseMCPServer:
    """Create and configure travel document retriever MCP server."""
    tools = [RetrieverTool()]
    return BaseMCPServer("travel-doc-retriever-server", tools)


# For backward compatibility and direct execution
if __name__ == "__main__":
    server = create_retriever_server()
    server.run()

