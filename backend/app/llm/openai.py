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

    def _extract_response(self, data: Dict[str, Any]) -> str:
        """Extract response from OpenAI format."""
        return data.get("choices", [{}])[0].get("message", {}).get("content", "未能获取模型回复。")

    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make async HTTP request to OpenAI API with connection pooling."""
        base_url = self._get_base_url()
        model = payload.get("model", self._get_model_name())
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Convert functions to tools format for OpenAI API
        payload = self._convert_functions_to_tools(payload.copy())
        
        messages_count = len(payload.get("messages", []))
        logger.info(f"OpenAI API request (async) - URL: {url}, Model: {model}, Messages: {messages_count}")
        if "tools" in payload:
            logger.debug(f"Using {len(payload['tools'])} tools (converted from functions)")

        request_start = time.time()
        try:
            client = self._get_async_client()
            response = await client.post(url, json=payload, headers=headers)
            request_time = time.time() - request_start

            logger.debug(f"OpenAI API response - Status: {response.status_code}, Time: {request_time:.2f}s")
            response.raise_for_status()

            result = response.json()
            logger.debug(f"OpenAI response parsed successfully")
            return result

        except httpx.TimeoutException as exc:
            request_time = time.time() - request_start
            logger.error(f"OpenAI API timeout after {request_time:.2f}s")
            raise LLMError(f"请求超时：API响应时间超过 {self._config.llm_timeout} 秒。") from exc
        except httpx.HTTPStatusError as exc:
            request_time = time.time() - request_start
            logger.error(f"OpenAI API HTTP error {exc.response.status_code}")
            error_text = exc.response.text[:200] if exc.response.text else ""
            if exc.response.status_code == 401:
                raise LLMError(
                    "API密钥无效或已过期。请检查 OPENAI_API_KEY 环境变量或配置中的API密钥。"
                ) from exc
            elif exc.response.status_code == 404:
                raise LLMError(
                    f"模型 '{model}' 不存在或无法访问。请检查模型名称是否正确。"
                ) from exc
            elif exc.response.status_code == 429:
                raise LLMError(
                    "请求速率限制：API请求过于频繁。请稍后重试。"
                ) from exc
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{error_text}") from exc
        except httpx.ConnectError as exc:
            request_time = time.time() - request_start
            logger.error(f"OpenAI API connection error: {str(exc)}")
            error_msg = str(exc)
            if "10054" in error_msg or "远程主机强迫关闭" in error_msg or "Connection reset" in error_msg:
                raise LLMError(
                    "连接被远程主机关闭：可能是网络不稳定、服务器限流或代理服务器问题。"
                    "请检查网络连接，稍后重试，或检查代理服务器配置。"
                ) from exc
            if "nodename" in error_msg or "not known" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"连接错误：无法连接到OpenAI服务。请检查网络连接和端点配置。") from exc
        except Exception as exc:
            request_time = time.time() - request_start
            logger.error(f"OpenAI API error after {request_time:.2f}s: {str(exc)}")
            raise LLMError(f"API错误：{str(exc)}") from exc

    async def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Make async streaming HTTP request to OpenAI API with connection pooling."""
        base_url = self._get_base_url()
        model = payload.get("model", self._get_model_name())
        url = f"{base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Convert functions to tools format for OpenAI API
        request_payload = self._convert_functions_to_tools(payload.copy())
        request_payload["stream"] = True

        logger.info(f"OpenAI streaming request (async) - URL: {url}, Model: {model}")
        if "tools" in request_payload:
            logger.debug(f"Using {len(request_payload['tools'])} tools (converted from functions)")

        try:
            client = self._get_async_client()
            async with client.stream("POST", url, json=request_payload, headers=headers) as response:
                # Check status before processing stream
                if response.status_code != 200:
                    # Read error response
                    error_text = ""
                    try:
                        error_text = (await response.aread()).decode('utf-8', errors='ignore')[:500]
                    except:
                        pass
                    logger.error(f"OpenAI streaming error response (status {response.status_code}): {error_text}")
                    response.raise_for_status()
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
            raise LLMError(f"请求超时：流式响应时间超过限制。请检查网络连接或稍后重试。") from exc
        except httpx.ConnectError as exc:
            logger.error(f"OpenAI streaming connection error: {str(exc)}")
            error_msg = str(exc)
            if "10054" in error_msg or "远程主机强迫关闭" in error_msg or "Connection reset" in error_msg:
                raise LLMError(
                    "连接被远程主机关闭：可能是网络不稳定、服务器限流或代理服务器问题。"
                    "请检查网络连接，稍后重试，或检查代理服务器配置。"
                ) from exc
            if "nodename" in error_msg or "not known" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"连接错误：无法连接到OpenAI服务。请检查网络连接和端点配置。") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"OpenAI streaming HTTP error {exc.response.status_code}: {str(exc)}")
            error_text = exc.response.text[:200] if exc.response.text else ""
            if exc.response.status_code == 401:
                raise LLMError(
                    "API密钥无效或已过期。请检查 OPENAI_API_KEY 环境变量或配置中的API密钥。"
                ) from exc
            elif exc.response.status_code == 404:
                raise LLMError(
                    f"模型 '{model}' 不存在或无法访问。请检查模型名称是否正确。"
                ) from exc
            elif exc.response.status_code == 429:
                raise LLMError(
                    "请求速率限制：API请求过于频繁。请稍后重试。"
                ) from exc
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{error_text}") from exc
        except Exception as exc:
            logger.error(f"OpenAI streaming error: {str(exc)}", exc_info=True)
            error_msg = str(exc)
            # Use platform-specific error handling
            from ..platform_config import is_windows_socket_error, format_network_error
            if is_windows_socket_error(error_msg):
                raise LLMError(format_network_error(error_msg, is_socket_error=True)) from exc
            formatted_error = format_network_error(error_msg)
            if formatted_error != f"网络错误：{error_msg}":
                raise LLMError(formatted_error) from exc
            raise LLMError(f"流式请求错误：{error_msg}") from exc

    def _extract_stream_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Extract text chunk from OpenAI streaming response."""
        if "choices" not in chunk_data or not chunk_data["choices"]:
            return None
        delta = chunk_data["choices"][0].get("delta", {})
        content = delta.get("content", "")
        return content if content else None

