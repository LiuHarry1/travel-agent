"""FAQ MCP server."""
from __future__ import annotations

from ..core.base_server import BaseMCPServer
from ..tools.faq_tool import FAQTool


def create_faq_server() -> BaseMCPServer:
    """Create and configure FAQ MCP server."""
    tools = [FAQTool()]
    return BaseMCPServer("faq-server", tools)


# For backward compatibility and direct execution
if __name__ == "__main__":
    server = create_faq_server()
    server.run()

