"""Travel document retriever MCP server entry point (backward compatibility)."""
from __future__ import annotations

from ..servers.retriever_server import create_retriever_server

# Create server instance for backward compatibility
server = create_retriever_server()
app = server.app

# For direct execution
if __name__ == "__main__":
    server.run()

