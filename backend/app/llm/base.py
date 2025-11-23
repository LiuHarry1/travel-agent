"""
Base classes and enums for LLM providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, AsyncGenerator, Dict, List, Optional
import threading

import httpx

from ..config import get_config


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    QWEN = "qwen"  # Alibaba DashScope
    AZURE_OPENAI = "azure_openai"  # Azure OpenAI
    OLLAMA = "ollama"  # Ollama (supports any model)


class LLMError(RuntimeError):
    """Base exception for LLM API errors."""
    pass


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients with async HTTP client and connection pooling."""

    def __init__(self, api_key: Optional[str] = None, config=None):
        self.api_key = api_key or self._get_api_key()
        self._config = config or get_config()
        # Shared async HTTP client with connection pooling for better performance
        self._async_client: Optional[httpx.AsyncClient] = None
        self._client_lock = threading.Lock()
    
    def _get_async_client(self) -> httpx.AsyncClient:
        """
        Get or create shared async HTTP client with connection pooling.
        This reuses connections for better performance and lower latency.
        """
        if self._async_client is None:
            with self._client_lock:
                # Double-check locking pattern
                if self._async_client is None:
                    timeout = httpx.Timeout(
                        connect=30.0,
                        read=self._config.llm_timeout,
                        write=30.0,
                        pool=30.0
                    )
                    # Create async client with connection pool
                    # limits.max_connections: max connections per host
                    # limits.max_keepalive_connections: keep-alive connections
                    limits = httpx.Limits(
                        max_connections=100,  # Max connections in pool
                        max_keepalive_connections=20  # Keep-alive connections
                    )
                    self._async_client = httpx.AsyncClient(
                        timeout=timeout,
                        limits=limits,
                        http2=True  # Enable HTTP/2 for better performance
                    )
        return self._async_client
    
    async def close(self):
        """Close async HTTP client and release resources."""
        if self._async_client is not None:
            with self._client_lock:
                if self._async_client is not None:
                    await self._async_client.aclose()
                    self._async_client = None

    @abstractmethod
    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment or config."""
        pass

    @abstractmethod
    def _get_base_url(self) -> str:
        """Get base URL for the API."""
        pass

    @abstractmethod
    def _get_model_name(self) -> str:
        """Get model name from config."""
        pass

    @abstractmethod
    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make async HTTP request to LLM API."""
        pass

    @abstractmethod
    async def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Make async streaming HTTP request to LLM API. Returns async generator of chunks."""
        pass

    @abstractmethod
    def _normalize_payload(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        """Normalize payload format for the specific provider."""
        pass

    @abstractmethod
    def _extract_response(self, data: Dict[str, Any]) -> str:
        """Extract response text from provider-specific response format."""
        pass

    @abstractmethod
    def _extract_stream_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Extract text chunk from streaming response. Returns None if not a content chunk."""
        pass

    @property
    def has_api_key(self) -> bool:
        """Check if API key is available."""
        return bool(self.api_key)

    @property
    def model(self) -> str:
        """Get model name."""
        return self._get_model_name()

