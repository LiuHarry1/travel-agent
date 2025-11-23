"""
Qwen (Alibaba DashScope) LLM client implementation.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional
import logging
import time

import httpx

from .base import BaseLLMClient, LLMError


class QwenClient(BaseLLMClient):
    """Qwen (Alibaba DashScope) LLM client."""

    def _get_api_key(self) -> Optional[str]:
        import os
        return os.getenv("DASHSCOPE_API_KEY") or os.getenv("QWEN_API_KEY")

    def _get_base_url(self) -> str:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"

    def _get_model_name(self) -> str:
        return self._config.llm_model

    def _normalize_payload(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        """Normalize payload for DashScope/Qwen API."""
        return {
            "model": model or self._get_model_name(),
            "messages": messages,
        }

    def _extract_response(self, data: Dict[str, Any]) -> str:
        """Extract response from DashScope/Qwen format."""
        return data.get("choices", [{}])[0].get("message", {}).get("content", "未能获取模型回复。")

    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make async HTTP request to DashScope API with connection pooling."""
        logger = logging.getLogger(__name__)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint}"

        model = payload.get("model", "unknown")
        messages_count = len(payload.get("messages", []))
        logger.debug(f"Qwen API request (async) - URL: {url}, Model: {model}, Messages: {messages_count}")

        request_start = time.time()
        try:
            client = self._get_async_client()
            response = await client.post(url, json=payload, headers=headers)
            request_time = time.time() - request_start

            logger.debug(f"Qwen API response - Status: {response.status_code}, Time: {request_time:.2f}s")
            response.raise_for_status()

            result = response.json()
            logger.debug(f"Qwen response parsed successfully - Size: {len(str(result))} chars")
            return result

        except httpx.TimeoutException as exc:
            request_time = time.time() - request_start
            logger.error(f"Qwen API timeout after {request_time:.2f}s")
            raise LLMError(f"请求超时：API响应时间超过 {self._config.llm_timeout} 秒。") from exc
        except httpx.ConnectError as exc:
            request_time = time.time() - request_start
            logger.error(f"Qwen API connection error after {request_time:.2f}s: {str(exc)}")
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"连接错误：无法连接到AI服务。请检查网络连接。") from exc
        except httpx.HTTPStatusError as exc:
            request_time = time.time() - request_start
            logger.error(f"Qwen API HTTP error {exc.response.status_code}")
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{exc.response.text[:200]}") from exc
        except Exception as exc:
            request_time = time.time() - request_start
            logger.error(f"Qwen API error after {request_time:.2f}s: {str(exc)}", exc_info=True)
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg or "getaddrinfo" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"API错误：{error_msg}") from exc

    async def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Make async streaming HTTP request to DashScope API with connection pooling."""
        logger = logging.getLogger(__name__)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint}"

        # Enable streaming
        payload = payload.copy()
        payload["stream"] = True

        logger.debug(f"Qwen streaming request (async) - URL: {url}, Model: {payload.get('model', 'unknown')}")

        try:
            client = self._get_async_client()
            async with client.stream("POST", url, json=payload, headers=headers) as response:
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
            logger.error(f"Qwen streaming timeout: {str(exc)}")
            raise LLMError(f"请求超时：流式响应时间超过限制。") from exc
        except httpx.ConnectError as exc:
            logger.error(f"Qwen streaming connection error: {str(exc)}")
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"连接错误：无法连接到AI服务。请检查网络连接。") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"Qwen streaming HTTP error {exc.response.status_code}: {str(exc)}")
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{exc.response.text[:200]}") from exc
        except Exception as exc:
            logger.error(f"Qwen streaming error: {str(exc)}", exc_info=True)
            error_msg = str(exc)
            if "nodename" in error_msg or "not known" in error_msg or "getaddrinfo" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"流式请求错误：{error_msg}") from exc

    def _extract_stream_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Extract text chunk from Qwen streaming response."""
        if "choices" not in chunk_data or not chunk_data["choices"]:
            return None
        delta = chunk_data["choices"][0].get("delta", {})
        content = delta.get("content", "")
        return content if content else None

