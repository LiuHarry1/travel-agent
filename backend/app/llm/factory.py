"""
LLM Client Factory for creating provider-specific clients.
"""
from __future__ import annotations

from typing import Optional

from .provider import LLMProvider, BaseLLMClient, QwenClient, AzureOpenAIClient, OllamaClient, LLMError


class LLMClientFactory:
    """Factory for creating LLM clients based on provider configuration."""

    @staticmethod
    def create_client(provider: Optional[LLMProvider] = None, api_key: Optional[str] = None):
        """
        Create LLM client instance based on provider.

        Args:
            provider: LLM provider (qwen, azure_openai). If None, reads from config.
            api_key: Optional API key override

        Returns:
            BaseLLMClient instance

        Raises:
            ValueError: If provider is not supported or configuration is invalid
        """
        from ..config import get_config

        config = get_config()

        # Get provider from config if not specified
        if provider is None:
            provider_name = config._config.get("llm", {}).get("provider", "qwen")
            try:
                provider = LLMProvider(provider_name.lower())
            except ValueError:
                raise ValueError(
                    f"Unsupported LLM provider: {provider_name}. "
                    f"Supported providers: {[p.value for p in LLMProvider]}"
                )

        # Create client based on provider
        if provider == LLMProvider.QWEN:
            return QwenClient(api_key=api_key, config=config)
        elif provider == LLMProvider.AZURE_OPENAI:
            return AzureOpenAIClient(api_key=api_key, config=config)
        elif provider == LLMProvider.OLLAMA:
            return OllamaClient(api_key=api_key, config=config)
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    @staticmethod
    def get_default_client():
        """Get default LLM client from configuration."""
        return LLMClientFactory.create_client()


