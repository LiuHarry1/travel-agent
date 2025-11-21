"""
LLM Provider definitions and base classes.
Supports multiple LLM providers with unified interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

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
    """Abstract base class for LLM clients."""

    def __init__(self, api_key: Optional[str] = None, config=None):
        self.api_key = api_key or self._get_api_key()
        self._config = config or get_config()

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
    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to LLM API."""
        pass

    @abstractmethod
    def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]):
        """Make streaming HTTP request to LLM API. Returns generator of chunks."""
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

    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to DashScope API."""
        import logging
        import time

        logger = logging.getLogger(__name__)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint}"

        timeout = httpx.Timeout(
            connect=30.0,
            read=self._config.llm_timeout,
            write=30.0,
            pool=30.0
        )

        model = payload.get("model", "unknown")
        messages_count = len(payload.get("messages", []))
        logger.debug(f"Qwen API request - URL: {url}, Model: {model}, Messages: {messages_count}")

        request_start = time.time()
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload, headers=headers)
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

    def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]):
        """Make streaming HTTP request to DashScope API."""
        import logging
        import time

        logger = logging.getLogger(__name__)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        base_url = self._get_base_url()
        url = f"{base_url}/{endpoint}"

        timeout = httpx.Timeout(
            connect=30.0,
            read=self._config.llm_timeout,
            write=30.0,
            pool=30.0
        )

        # Enable streaming
        payload = payload.copy()
        payload["stream"] = True

        logger.debug(f"Qwen streaming request - URL: {url}, Model: {payload.get('model', 'unknown')}")

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
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


class AzureOpenAIClient(BaseLLMClient):
    """Azure OpenAI LLM client."""

    def _get_api_key(self) -> Optional[str]:
        import os
        return os.getenv("AZURE_OPENAI_API_KEY")

    def _get_base_url(self) -> str:
        import os
        base_url = os.getenv("AZURE_OPENAI_ENDPOINT")
        if not base_url:
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT environment variable is required for Azure OpenAI. "
                "Format: https://<resource-name>.openai.azure.com"
            )
        # Azure OpenAI uses different endpoint format
        return base_url.rstrip("/")
    
    def _is_proxy_server(self) -> bool:
        """Check if using a proxy server that requires OpenAI-compatible format."""
        base_url = self._get_base_url()
        # Common proxy server indicators
        proxy_indicators = ["gptsapi.net", "proxy", "openrouter", "together", "anyscale"]
        return any(indicator in base_url.lower() for indicator in proxy_indicators)

    def _get_model_name(self) -> str:
        # Azure OpenAI model name from config
        llm_config = self._config._config.get("llm", {})
        return llm_config.get("azure_model", llm_config.get("model", "gpt-4"))

    def _normalize_payload(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
        """Normalize payload for Azure OpenAI API or OpenAI-compatible proxy."""
        import os
        # Azure OpenAI uses deployment name, which might be different from model name
        deployment_name = model or self._get_model_name()
        
        # For proxy servers using OpenAI format, model should be in payload
        if self._is_proxy_server():
            return {
                "model": deployment_name,
                "messages": messages,
            }
        else:
            # Azure OpenAI format - model is in URL, not payload
            return {
                "messages": messages,
            }

    def _extract_response(self, data: Dict[str, Any]) -> str:
        """Extract response from Azure OpenAI format."""
        return data.get("choices", [{}])[0].get("message", {}).get("content", "未能获取模型回复。")

    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Azure OpenAI API."""
        import logging
        import os
        import time

        logger = logging.getLogger(__name__)
        
        base_url = self._get_base_url()
        is_proxy = self._is_proxy_server()
        
        if is_proxy:
            # OpenAI-compatible proxy server format
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            # OpenAI format: base_url should include /v1, endpoint is /chat/completions
            if base_url.endswith("/v1"):
                url = f"{base_url}/chat/completions"
            elif base_url.endswith("/v1/"):
                url = f"{base_url}chat/completions"
            else:
                url = f"{base_url}/v1/chat/completions"
            deployment_name = payload.get("model", self._get_model_name())
            request_payload = payload  # Keep model in payload for OpenAI format
        else:
            # Azure OpenAI format
            headers = {
                "api-key": self.api_key,
                "Content-Type": "application/json"
            }
            deployment_name = payload.get("model", self._get_model_name())
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
            # Azure OpenAI endpoint format: /openai/deployments/{deployment}/chat/completions?api-version={version}
            url = f"{base_url}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"
            # Remove model from payload for Azure OpenAI (it's in the URL)
            request_payload = {k: v for k, v in payload.items() if k != "model"}

        timeout = httpx.Timeout(
            connect=30.0,
            read=self._config.llm_timeout,
            write=30.0,
            pool=30.0
        )

        messages_count = len(payload.get("messages", []))
        format_type = "OpenAI兼容" if is_proxy else "Azure OpenAI"
        logger.info(f"Azure OpenAI API request ({format_type}) - URL: {url}, Model: {deployment_name}, Messages: {messages_count}")

        request_start = time.time()
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=request_payload, headers=headers)
                request_time = time.time() - request_start

                logger.debug(f"Azure OpenAI API response - Status: {response.status_code}, Time: {request_time:.2f}s")
                response.raise_for_status()

                result = response.json()
                logger.debug(f"Azure OpenAI response parsed successfully")
                return result

        except httpx.TimeoutException as exc:
            request_time = time.time() - request_start
            logger.error(f"Azure OpenAI API timeout after {request_time:.2f}s")
            raise LLMError(f"请求超时：API响应时间超过 {self._config.llm_timeout} 秒。") from exc
        except httpx.HTTPStatusError as exc:
            request_time = time.time() - request_start
            logger.error(f"Azure OpenAI API HTTP error {exc.response.status_code}")
            error_text = exc.response.text[:200] if exc.response.text else ""
            if exc.response.status_code == 404:
                # Check if using proxy server
                is_proxy = "gptsapi.net" in base_url or "proxy" in base_url.lower()
                if is_proxy:
                    raise LLMError(
                        f"部署名称 '{deployment_name}' 在代理服务器上不存在（404错误）。\n"
                        f"可能的原因：\n"
                        f"1. 部署名称不正确 - 请检查代理服务器文档确认正确的模型名称\n"
                        f"2. API版本不匹配 - 当前使用: {api_version}，可能需要: 2024-02-15-preview 或其他版本\n"
                        f"3. 端点格式不同 - 代理服务器可能使用不同的URL格式\n"
                        f"建议：\n"
                        f"- 尝试设置环境变量 AZURE_OPENAI_API_VERSION=2024-02-15-preview\n"
                        f"- 联系代理服务提供商确认正确的部署名称和API版本\n"
                        f"- 当前请求URL: {url}"
                    ) from exc
                else:
                    raise LLMError(
                        f"Azure OpenAI 部署 '{deployment_name}' 不存在或无法访问。"
                        f"请检查Azure门户中的部署名称是否正确。"
                    ) from exc
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{error_text}") from exc
        except Exception as exc:
            request_time = time.time() - request_start
            logger.error(f"Azure OpenAI API error after {request_time:.2f}s: {str(exc)}")
            raise LLMError(f"API错误：{str(exc)}") from exc

    def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]):
        """Make streaming HTTP request to Azure OpenAI API."""
        import logging
        import os
        import socket

        logger = logging.getLogger(__name__)
        
        base_url = self._get_base_url()
        is_proxy = self._is_proxy_server()
        
        if is_proxy:
            # OpenAI-compatible proxy server format
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            # OpenAI format: base_url should include /v1, endpoint is /chat/completions
            if base_url.endswith("/v1"):
                url = f"{base_url}/chat/completions"
            elif base_url.endswith("/v1/"):
                url = f"{base_url}chat/completions"
            else:
                url = f"{base_url}/v1/chat/completions"
            deployment_name = payload.get("model", self._get_model_name())
            request_payload = payload.copy()  # Keep model in payload for OpenAI format
            request_payload["stream"] = True
        else:
            # Azure OpenAI format
            headers = {
                "api-key": self.api_key,
                "Content-Type": "application/json"
            }
            deployment_name = payload.get("model", self._get_model_name())
            api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-06-01")
            # Azure OpenAI endpoint format: /openai/deployments/{deployment}/chat/completions?api-version={version}
            url = f"{base_url}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"
            # Remove model from payload for Azure OpenAI (it's in the URL)
            request_payload = {k: v for k, v in payload.items() if k != "model"}
            request_payload["stream"] = True

        timeout = httpx.Timeout(
            connect=30.0,
            read=self._config.llm_timeout,
            write=30.0,
            pool=30.0
        )

        format_type = "OpenAI兼容" if is_proxy else "Azure OpenAI"
        logger.info(f"Azure OpenAI streaming request ({format_type}) - URL: {url}, Model: {deployment_name}")

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=request_payload, headers=headers) as response:
                    # Check status before processing stream
                    if response.status_code != 200:
                        # Read error response
                        error_text = ""
                        try:
                            error_text = response.read().decode('utf-8', errors='ignore')[:500]
                        except:
                            pass
                        logger.error(f"Azure OpenAI streaming error response (status {response.status_code}): {error_text}")
                        response.raise_for_status()
                    response.raise_for_status()
                    for line in response.iter_lines():
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
            logger.error(f"Azure OpenAI streaming timeout: {str(exc)}")
            raise LLMError(f"请求超时：流式响应时间超过限制。请检查网络连接或稍后重试。") from exc
        except httpx.ConnectError as exc:
            logger.error(f"Azure OpenAI streaming connection error: {str(exc)}")
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
            raise LLMError(f"连接错误：无法连接到Azure OpenAI服务。请检查网络连接和端点配置。") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(f"Azure OpenAI streaming HTTP error {exc.response.status_code}: {str(exc)}")
            error_text = exc.response.text[:200] if exc.response.text else ""
            if exc.response.status_code == 404:
                # Check if using proxy server
                is_proxy = "gptsapi.net" in base_url or "proxy" in base_url.lower()
                if is_proxy:
                    raise LLMError(
                        f"部署名称 '{deployment_name}' 在代理服务器上不存在（404错误）。\n"
                        f"可能的原因：\n"
                        f"1. 部署名称不正确 - 请检查代理服务器文档确认正确的模型名称\n"
                        f"2. API版本不匹配 - 当前使用: {api_version}，可能需要: 2024-02-15-preview 或其他版本\n"
                        f"3. 端点格式不同 - 代理服务器可能使用不同的URL格式\n"
                        f"建议：\n"
                        f"- 尝试设置环境变量 AZURE_OPENAI_API_VERSION=2024-02-15-preview\n"
                        f"- 联系代理服务提供商确认正确的部署名称和API版本\n"
                        f"- 当前请求URL: {url}"
                    ) from exc
                else:
                    raise LLMError(
                        f"Azure OpenAI 部署 '{deployment_name}' 不存在或无法访问。"
                        f"请检查Azure门户中的部署名称是否正确，"
                        f"或确认该部署是否已创建并处于活动状态。"
                    ) from exc
            raise LLMError(f"HTTP错误 {exc.response.status_code}：{error_text}") from exc
        except socket.error as exc:
            logger.error(f"Azure OpenAI streaming socket error: {str(exc)}")
            error_code = getattr(exc, 'winerror', None) or getattr(exc, 'errno', None)
            if error_code == 10054 or "10054" in str(exc) or "远程主机强迫关闭" in str(exc):
                raise LLMError(
                    "连接被远程主机关闭：可能是网络不稳定、服务器限流或代理服务器问题。"
                    "请检查网络连接，稍后重试，或检查代理服务器配置。"
                ) from exc
            raise LLMError(f"网络连接错误：{str(exc)}。请检查网络连接。") from exc
        except Exception as exc:
            logger.error(f"Azure OpenAI streaming error: {str(exc)}", exc_info=True)
            error_msg = str(exc)
            # Check for Windows socket error 10054
            if "10054" in error_msg or "远程主机强迫关闭" in error_msg or "Connection reset" in error_msg:
                raise LLMError(
                    "连接被远程主机关闭：可能是网络不稳定、服务器限流或代理服务器问题。"
                    "请检查网络连接，稍后重试，或检查代理服务器配置。"
                ) from exc
            if "nodename" in error_msg or "not known" in error_msg or "getaddrinfo" in error_msg:
                raise LLMError(
                    "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
                ) from exc
            raise LLMError(f"流式请求错误：{error_msg}") from exc

    def _extract_stream_chunk(self, chunk_data: Dict[str, Any]) -> Optional[str]:
        """Extract text chunk from Azure OpenAI streaming response."""
        if "choices" not in chunk_data or not chunk_data["choices"]:
            return None
        delta = chunk_data["choices"][0].get("delta", {})
        content = delta.get("content", "")
        return content if content else None


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

    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Ollama API."""
        import logging
        import time

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

        timeout = httpx.Timeout(
            connect=30.0,
            read=self._config.llm_timeout,
            write=30.0,
            pool=30.0
        )

        model = payload.get("model", "unknown")
        messages_count = len(payload.get("messages", []))
        logger.debug(f"Ollama API request - URL: {url}, Model: {model}, Messages: {messages_count}")
        logger.debug(f"Ollama API request payload: {payload}")

        request_start = time.time()
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, json=payload, headers=headers)
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

    def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]):
        """Make streaming HTTP request to Ollama API."""
        import logging
        import time

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

        timeout = httpx.Timeout(
            connect=30.0,
            read=self._config.llm_timeout,
            write=30.0,
            pool=30.0
        )

        # Enable streaming
        payload = payload.copy()
        payload["stream"] = True

        logger.debug(f"Ollama streaming request - URL: {url}, Model: {payload.get('model', 'unknown')}")
        logger.debug(f"Ollama streaming request payload: {payload}")

        try:
            with httpx.Client(timeout=timeout) as client:
                with client.stream("POST", url, json=payload, headers=headers) as response:
                    # Check status before processing stream
                    if response.status_code != 200:
                        # Read error response
                        error_text = ""
                        try:
                            error_text = response.read().decode('utf-8', errors='ignore')[:500]
                        except:
                            pass
                        logger.error(f"Ollama streaming error response (status {response.status_code}): {error_text}")
                        response.raise_for_status()
                    response.raise_for_status()
                    # Ollama native API returns JSON lines (one JSON object per line)
                    for line in response.iter_lines():
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


