"""FAQ MCP server entry point (backward compatibility)."""
from __future__ import annotations

from ..servers.faq_server import create_faq_server

# Create server instance for backward compatibility
server = create_faq_server()
app = server.app

# For direct execution
if __name__ == "__main__":
    server.run()
