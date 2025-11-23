"""MCP configuration loader."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class MCPToolConfig:
    """Configuration for a single MCP tool."""

    def __init__(self, name: str, tool_type: str, description: str, **kwargs):
        self.name = name
        self.type = tool_type
        self.description = description
        self.extra = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "description": self.description,
            **self.extra,
        }


def load_mcp_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load MCP configuration from JSON file.
    
    Args:
        config_path: Path to mcp.json file. If None, looks for mcp.json in backend directory.
        
    Returns:
        Dictionary containing MCP configuration
    """
    if config_path is None:
        # Default to backend/mcp.json
        backend_dir = Path(__file__).parent.parent.parent
        config_path = str(backend_dir / "mcp.json")
    
    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"MCP config file not found: {config_path}, using empty config")
        return {"tools": [], "servers": {}}
    
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = json.load(f)
        logger.info(f"Loaded MCP config from {config_path} with {len(config.get('tools', []))} tools")
        return config
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse MCP config JSON: {e}")
        return {"tools": [], "servers": {}}
    except Exception as e:
        logger.error(f"Failed to load MCP config: {e}")
        return {"tools": [], "servers": {}}

