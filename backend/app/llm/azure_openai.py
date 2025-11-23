"""
Azure OpenAI LLM client implementation.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional
import logging
import os
import time

import httpx

from .base import BaseLLMClient, LLMError


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

    async def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Make async HTTP request to Azure OpenAI API with connection pooling."""
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

        messages_count = len(payload.get("messages", []))
        format_type = "OpenAI兼容" if is_proxy else "Azure OpenAI"
        logger.info(f"Azure OpenAI API request (async) ({format_type}) - URL: {url}, Model: {deployment_name}, Messages: {messages_count}")

        request_start = time.time()
        try:
            client = self._get_async_client()
            response = await client.post(url, json=request_payload, headers=headers)
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

    async def _make_stream_request(self, endpoint: str, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Make async streaming HTTP request to Azure OpenAI API with connection pooling."""
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

        format_type = "OpenAI兼容" if is_proxy else "Azure OpenAI"
        logger.info(f"Azure OpenAI streaming request (async) ({format_type}) - URL: {url}, Model: {deployment_name}")

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
                    logger.error(f"Azure OpenAI streaming error response (status {response.status_code}): {error_text}")
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

