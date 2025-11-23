"""LLM client module."""
from .client import LLMClient
from .factory import LLMClientFactory
from .provider import LLMError, LLMProvider

# Backward compatibility (only for existing code)
DashScopeError = LLMError

__all__ = [
    "LLMClient",
    "LLMClientFactory",
    "LLMError",
    "LLMProvider",
    "DashScopeError",  # Backward compatibility
]

