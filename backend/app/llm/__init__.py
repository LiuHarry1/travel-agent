"""LLM client module."""
from .client import LLMClient
from .factory import LLMClientFactory
from .provider import LLMError, LLMProvider

# Backward compatibility
CompletionClient = LLMClient
ChatbotClient = LLMClient
DashScopeError = LLMError

__all__ = [
    "LLMClient",
    "LLMClientFactory",
    "LLMError",
    "LLMProvider",
    "CompletionClient",  # Backward compatibility
    "ChatbotClient",     # Backward compatibility
    "DashScopeError",    # Backward compatibility
]

