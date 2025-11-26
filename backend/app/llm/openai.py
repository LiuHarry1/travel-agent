"""
OpenAI LLM client implementation.
Supports OpenAI API and OpenAI-compatible proxy servers.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional
import logging
import os
import time

import httpx

from .base import BaseLLMClient, LLMError

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """OpenAI LLM client for OpenAI API or OpenAI-compatible proxy servers."""

    def _get_api_key(self) -> Optional[str]:
        """Get API key from environment variable."""
        return os.getenv("OPENAI_API_KEY")

    def _get_base_url(self) -> str:
        """Get base URL from environment variable or config."""
        base_url = os.getenv("OPENAI_BASE_URL")
        if not base_url:
            # Try to get from config
            llm_config = self._config._config.get("llm", {})
            base_url = llm_config.get("openai_base_url")
            if not base_url:
                # Default to official OpenAI API
                base_url = "https://api.openai.com/v1"
        # Ensure base_url ends with /v1 or /v1/ for OpenAI-compatible format
        base_url = base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            if base_url.endswith("/v1/"):
                base_url = base_url.rstrip("/")
            else:
                base_url = f"{base_url}/v1"
        return base_url

    def _get_model_name(self) -> str:
        """Get model name from config."""
        llm_config = self._config._config.get("llm", {})
        return llm_config.get("openai_model", llm_config.get("model", "gpt-4"))

    def _normalize_payload(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        """Normalize payload for OpenAI API format."""
        payload = {
            "model": model or self._get_model_name(),
            "messages": messages,
        }
        return payload
    
    def _convert_functions_to_tools(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert 'functions' parameter to 'tools' format for OpenAI API.
        OpenAI API uses 'tools' instead of 'functions', and the format is slightly different.
        """
        if "functions" in payload:
            functions = payload.pop("functions")
            # Convert functions to tools format
            tools = []
            for func in functions:
                tools.append({
                    "type": "function",
                    "function": func
                })
            payload["tools"] = tools
            
            # Convert function_call to tool_choice
            if "function_call" in payload:
                function_call = payload.pop("function_call")
                if function_call == "auto":
                    payload["tool_choice"] = "auto"
                elif function_call == "none":
                    payload["tool_choice"] = "none"
                elif isinstance(function_call, dict) and "name" in function_call:
                    payload["tool_choice"] = {
                        "type": "function",
                        "function": {"name": function_call["name"]}
                    }
        
        return payload

    async def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Make async streaming HTTP request to OpenAI API with connection pooling."""
        base_url = self._get_base_url()
        model = payload.get("model", self._get_model_name())
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Content-Type": "application/json"
        }
        # Add Authorization header only if API key is available
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Convert functions to tools format for OpenAI API
        request_payload = self._convert_functions_to_tools(payload.copy())
        request_payload["stream"] = True

        logger.info(f"OpenAI streaming request (async) - URL: {url}, Model: {model}")
        if "tools" in request_payload:
            logger.debug(f"Using {len(request_payload['tools'])} tools (converted from functions)")

        try:
            client = self._get_async_client()
            async with client.stream("POST", url, json=request_payload, headers=headers) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        if line.startswith("data: "):
                            data_str = line[6:]  # Remove "data: " prefix
                            if data_str == "[DONE]":
                                break
                            try:
                                import json
                                chunk_data = json.loads(data_str)
                                content = self._extract_stream_chunk(chunk_data)
                                if content:
                                    yield content
                            except json.JSONDecodeError:
                                continue
                            except Exception as e:
                                logger.warning(f"Error parsing stream chunk: {e}")
                                continue
        except httpx.TimeoutException as exc:
            logger.error(f"OpenAI streaming timeout: {str(exc)}")
            raise LLMError("Request timeout, please check network connection or try again later") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"OpenAI streaming HTTP error {exc.response.status_code}: {str(exc)}")
            error_text = exc.response.text[:200] if exc.response.text else ""
            raise LLMError(f"API request failed ({exc.response.status_code}): {error_text}") from exc
        except Exception as exc:
            logger.error(f"OpenAI streaming error: {str(exc)}", exc_info=True)
            raise LLMError(f"Request failed: {str(exc)}") from exc

    def _extract_stream_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Extract text chunk from OpenAI streaming response."""
        if "choices" not in chunk_data or not chunk_data["choices"]:
            return None
        delta = chunk_data["choices"][0].get("delta", {})
        content = delta.get("content", "")
        return content if content else None

