"""
Ollama LLM client implementation.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional
import logging
import time

import httpx

from .base import BaseLLMClient, LLMError


class OllamaClient(BaseLLMClient):
    """Ollama LLM client supporting any Ollama model."""

    def _get_api_key(self) -> Optional[str]:
        """Ollama typically doesn't require API key, but can be configured."""
        import os
        return os.getenv("OLLAMA_API_KEY")  # Optional, usually None

    @property
    def has_api_key(self) -> bool:
        """Ollama doesn't require API key, so always return True."""
        return True

    def _get_base_url(self) -> str:
        """Get Ollama base URL from environment or use default."""
        import os
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        return base_url.rstrip("/")

    def _get_model_name(self) -> str:
        """Get model name from config."""
        llm_config = self._config._config.get("llm", {})
        # First try ollama_model, then fall back to model, then default
        return llm_config.get("ollama_model") or llm_config.get("model") or "qwen2.5:32b"

    def _normalize_payload(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        """Normalize payload for Ollama native API format."""
        # Convert messages to Ollama format
        # Ollama uses a simple messages array format
        return {
            "model": model or self._get_model_name(),
            "messages": messages,
        }

    def _extract_response(self, data: Dict[str, Any]) -> str:
        """Extract response from Ollama native API format."""
        # Ollama native API returns: {"message": {"content": "...", "role": "assistant"}, ...}
        message = data.get("message", {})
        if message:
            return message.get("content", "未能获取模型回复。")
        # Fallback to OpenAI-compatible format if available
        return data.get("choices", [{}])[0].get("message", {}).get("content", "未能获取模型回复。")

    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make async HTTP request to Ollama API with connection pooling."""
        logger = logging.getLogger(__name__)
        headers = {"Content-Type": "application/json"}
        
        # Add API key to headers if available
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        base_url = self._get_base_url()
        # Use Ollama native API endpoint
        if endpoint == "chat/completions":
            url = f"{base_url}/api/chat"
        else:
            url = f"{base_url}/{endpoint}"

        model = payload.get("model", "unknown")
        messages_count = len(payload.get("messages", []))
        logger.debug(f"Ollama API request (async) - URL: {url}, Model: {model}, Messages: {messages_count}")
        logger.debug(f"Ollama API request payload: {payload}")

        request_start = time.time()
        try:
            client = self._get_async_client()
            response = await client.post(url, json=payload, headers=headers)
            request_time = time.time() - request_start

            logger.debug(f"Ollama API response - Status: {response.status_code}, Time: {request_time:.2f}s")
            if response.status_code != 200:
                error_text = response.text[:500] if response.text else ""
                logger.error(f"Ollama API error response: {error_text}")
            response.raise_for_status()

            result = response.json()
            logger.debug(f"Ollama response parsed successfully - Size: {len(str(result))} chars")
            return result

        except httpx.TimeoutException as exc:
            request_time = time.time() - request_start
            logger.error(f"Ollama API timeout after {request_time:.2f}s")
            raise LLMError(f"请求超时：API响应时间超过 {self._config.llm_timeout} 秒。") from exc
        except httpx.ConnectError as exc:
            request_time = time.time() - request_start
            logger.error(f"Ollama API connection error after {request_time:.2f}s: {str(exc)}")
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置，确保Ollama服务正在运行。"
                ) from exc
            if "Connection refused" in error_msg or "refused" in error_msg:
                raise LLMError(
                    "连接被拒绝：无法连接到Ollama服务。请确保Ollama服务正在运行（默认地址：http://localhost:11434）。"
                ) from exc
            raise LLMError(f"连接错误：无法连接到Ollama服务。请检查网络连接和Ollama服务状态。") from exc
        except httpx.HTTPStatusError as exc:
            request_time = time.time() - request_start
            logger.error(f"Ollama API HTTP error {exc.response.status_code}")
            error_text = exc.response.text[:200] if exc.response.text else ""
            model_name = payload.get("model", "unknown")
            if exc.response.status_code == 404:
                raise LLMError(
                    f"模型 '{model_name}' 不存在或无法访问。"
                    f"请确保模型已正确安装（使用 'ollama pull {model_name}'），"
                    f"或检查 config.yaml 中的模型名称是否正确。"
                ) from exc
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{error_text}") from exc
        except Exception as exc:
            request_time = time.time() - request_start
            logger.error(f"Ollama API error after {request_time:.2f}s: {str(exc)}", exc_info=True)
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg or "getaddrinfo" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"API错误：{error_msg}") from exc

    async def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Make async streaming HTTP request to Ollama API with connection pooling."""
        logger = logging.getLogger(__name__)
        headers = {"Content-Type": "application/json"}
        
        # Add API key to headers if available
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        base_url = self._get_base_url()
        # Use Ollama native API endpoint
        if endpoint == "chat/completions":
            url = f"{base_url}/api/chat"
        else:
            url = f"{base_url}/{endpoint}"

        # Enable streaming
        payload = payload.copy()
        payload["stream"] = True

        logger.debug(f"Ollama streaming request (async) - URL: {url}, Model: {payload.get('model', 'unknown')}")
        logger.debug(f"Ollama streaming request payload: {payload}")

        try:
            client = self._get_async_client()
            async with client.stream("POST", url, json=payload, headers=headers) as response:
                # Check status before processing stream
                if response.status_code != 200:
                    # Read error response
                    error_text = ""
                    try:
                        error_text = (await response.aread()).decode('utf-8', errors='ignore')[:500]
                    except:
                        pass
                    logger.error(f"Ollama streaming error response (status {response.status_code}): {error_text}")
                    response.raise_for_status()
                response.raise_for_status()
                # Ollama native API returns JSON lines (one JSON object per line)
                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json
                            chunk_data = json.loads(line)
                            # Check if this is the final chunk
                            if chunk_data.get("done", False):
                                break
                            content = self._extract_stream_chunk(chunk_data)
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.warning(f"Error parsing stream chunk: {e}")
                            continue
        except httpx.TimeoutException as exc:
            logger.error(f"Ollama streaming timeout: {str(exc)}")
            raise LLMError(f"请求超时：流式响应时间超过限制。") from exc
        except httpx.ConnectError as exc:
            logger.error(f"Ollama streaming connection error: {str(exc)}")
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置，确保Ollama服务正在运行。"
                ) from exc
            if "Connection refused" in error_msg or "refused" in error_msg:
                raise LLMError(
                    "连接被拒绝：无法连接到Ollama服务。请确保Ollama服务正在运行（默认地址：http://localhost:11434）。"
                ) from exc
            raise LLMError(f"连接错误：无法连接到Ollama服务。请检查网络连接和Ollama服务状态。") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"Ollama streaming HTTP error {exc.response.status_code}: {str(exc)}")
            error_text = exc.response.text[:200] if exc.response.text else ""
            model_name = payload.get("model", "unknown")
            if exc.response.status_code == 404:
                raise LLMError(
                    f"模型 '{model_name}' 不存在或无法访问。"
                    f"请确保模型已正确安装（使用 'ollama pull {model_name}'），"
                    f"或检查 config.yaml 中的模型名称是否正确。"
                ) from exc
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{error_text}") from exc
        except Exception as exc:
            logger.error(f"Ollama streaming error: {str(exc)}", exc_info=True)
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg or "getaddrinfo" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"流式请求错误：{error_msg}") from exc

    def _extract_stream_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Extract text chunk from Ollama streaming response."""
        # Ollama native API streaming format: {"message": {"content": "...", ...}, "done": false}
        message = chunk_data.get("message", {})
        if message:
            content = message.get("content", "")
            return content if content else None
        # Fallback to OpenAI-compatible format if available
        if "choices" in chunk_data and chunk_data["choices"]:
            delta = chunk_data["choices"][0].get("delta", {})
            content = delta.get("content", "")
            return content if content else None
        return None

