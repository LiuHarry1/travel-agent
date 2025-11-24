"""Dependency injection container for application services."""
from __future__ import annotations

import logging
from typing import Optional

from ..config import get_config
from ..llm import LLMClient
from ..mcp_tools import MCPManager
from ..service.chat import ChatService

logger = logging.getLogger(__name__)


class Container:
    """
    Dependency injection container.
    
    Manages the lifecycle of all application services and provides
    a single source of truth for service instances.
    """
    
    def __init__(self):
        """Initialize container with lazy service creation."""
        self._llm_client: Optional[LLMClient] = None
        self._mcp_manager: Optional[MCPManager] = None
        self._chat_service: Optional[ChatService] = None
        self._initialized = False
    
    @property
    def llm_client(self) -> LLMClient:
        """Get or create LLM client instance."""
        if self._llm_client is None:
            logger.info("Creating LLM client...")
            self._llm_client = LLMClient()
        return self._llm_client
    
    @property
    def mcp_manager(self) -> MCPManager:
        """Get or create MCP manager instance."""
        if self._mcp_manager is None:
            logger.info("Creating MCP manager...")
            self._mcp_manager = MCPManager()
        return self._mcp_manager
    
    @property
    def mcp_registry(self) -> MCPManager:
        """Alias for mcp_manager (backward compatibility)."""
        return self.mcp_manager
    
    @property
    def chat_service(self) -> ChatService:
        """Get or create chat service instance."""
        if self._chat_service is None:
            logger.info("Creating chat service...")
            self._chat_service = ChatService(
                llm_client=self.llm_client,
                mcp_registry=self.mcp_manager
            )
        return self._chat_service
    
    async def initialize(self) -> None:
        """
        Initialize all services that require async initialization.
        
        This should be called during application startup.
        """
        if self._initialized:
            logger.info("Container already initialized")
            return
        
        logger.info("Initializing container services...")
        
        # Initialize MCP servers
        try:
            await self.mcp_manager.load()
            logger.info(
                f"MCP servers initialized. "
                f"Loaded {len(self.mcp_manager.tool_index)} tools."
            )
        except Exception as e:
            logger.warning(f"Failed to initialize MCP servers: {e}", exc_info=True)
        
        self._initialized = True
        logger.info("Container initialization complete")
    
    async def shutdown(self) -> None:
        """
        Cleanup all services.
        
        This should be called during application shutdown.
        """
        logger.info("Shutting down container...")
        
        if self._mcp_manager:
            try:
                await self._mcp_manager.close()
                logger.info("MCP connections closed")
            except Exception as e:
                logger.error(f"Error closing MCP connections: {e}", exc_info=True)
        
        self._initialized = False
        logger.info("Container shutdown complete")


# Global container instance
_container: Optional[Container] = None


def get_container() -> Container:
    """Get global container instance."""
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Reset container (useful for testing)."""
    global _container
    _container = None

