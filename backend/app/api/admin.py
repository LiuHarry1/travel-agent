"""Admin API routes for managing LLM configuration."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import get_config, reload_config
from ..llm.provider import LLMProvider
from ..mcp_tools.config import load_mcp_config
from ..utils.exceptions import format_error_message

router = APIRouter()


class ProviderInfo(BaseModel):
    """Provider information."""
    value: str = Field(..., description="Provider identifier")
    label: str = Field(..., description="Provider display name")


class ProvidersResponse(BaseModel):
    """Response model for available providers."""
    providers: List[ProviderInfo]


class LLMConfigResponse(BaseModel):
    """Response model for LLM configuration."""
    provider: str = Field(..., description="Current LLM provider")
    model: str = Field(..., description="Current model name")
    ollama_url: Optional[str] = Field(None, description="Ollama base URL (if provider is ollama)")


class LLMConfigUpdateRequest(BaseModel):
    """Request model for updating LLM configuration."""
    provider: str = Field(..., description="LLM provider (qwen, azure_openai, ollama)")
    model: str = Field(..., description="Model name")
    ollama_url: Optional[str] = Field(None, description="Ollama base URL (optional, for fetching models)")


class OllamaModelInfo(BaseModel):
    """Ollama model information."""
    name: str
    size: Optional[int] = None
    modified_at: Optional[str] = None


class ModelsResponse(BaseModel):
    """Response model for available models."""
    provider: str
    models: List[str]
    ollama_models: Optional[List[OllamaModelInfo]] = None


@router.get("/providers", response_model=ProvidersResponse)
def get_providers() -> ProvidersResponse:
    """Get list of available LLM providers."""
    providers = [
        ProviderInfo(value="qwen", label="Qwen (Alibaba DashScope)"),
        ProviderInfo(value="azure_openai", label="Azure OpenAI"),
        ProviderInfo(value="ollama", label="Ollama"),
    ]
    return ProvidersResponse(providers=providers)


@router.get("/config", response_model=LLMConfigResponse)
def get_llm_config() -> LLMConfigResponse:
    """Get current LLM configuration."""
    try:
        config = get_config()
        provider = config.llm_provider
        
        # Get model based on provider
        if provider == "ollama":
            model = config.llm_ollama_model
        elif provider == "azure_openai":
            model = config.llm_azure_model
        else:
            model = config.llm_model
        
        # Get Ollama URL from environment or use default
        ollama_url = None
        if provider == "ollama":
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        return LLMConfigResponse(provider=provider, model=model, ollama_url=ollama_url)
    except Exception as exc:
        error_msg = format_error_message(exc, "Failed to get LLM configuration")
        raise HTTPException(status_code=500, detail=error_msg) from exc


@router.post("/config", response_model=Dict[str, Any])
def update_llm_config(request: LLMConfigUpdateRequest) -> Dict[str, Any]:
    """Update LLM configuration."""
    try:
        # Validate provider
        try:
            LLMProvider(request.provider.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported provider: {request.provider}. Supported providers: {[p.value for p in LLMProvider]}"
            )
        
        # Update Ollama URL if provided
        if request.provider.lower() == "ollama" and request.ollama_url:
            os.environ["OLLAMA_BASE_URL"] = request.ollama_url.rstrip("/")
        
        # Save configuration
        config = get_config()
        config.save_llm_config(request.provider.lower(), request.model)
        
        # Reload config to ensure changes take effect
        reload_config()
        
        return {
            "status": "success",
            "message": "LLM configuration updated successfully",
            "provider": request.provider.lower(),
            "model": request.model
        }
    except HTTPException:
        raise
    except Exception as exc:
        error_msg = format_error_message(exc, "Failed to update LLM configuration")
        raise HTTPException(status_code=500, detail=error_msg) from exc


@router.get("/models", response_model=ModelsResponse)
def get_available_models(provider: Optional[str] = None, ollama_url: Optional[str] = None) -> ModelsResponse:
    """Get available models for a provider."""
    try:
        config = get_config()
        
        # Use provided provider or get from config
        if provider is None:
            provider = config.llm_provider
        else:
            # Validate provider
            try:
                LLMProvider(provider.lower())
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported provider: {provider}. Supported providers: {[p.value for p in LLMProvider]}"
                )
        
        provider_lower = provider.lower()
        
        if provider_lower == "ollama":
            # Fetch models from Ollama API
            base_url = ollama_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            base_url = base_url.rstrip("/")
            
            try:
                # Call Ollama API to get available models
                url = f"{base_url}/api/tags"
                timeout = httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0)
                
                with httpx.Client(timeout=timeout) as client:
                    response = client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Extract model names from Ollama response
                    models = []
                    ollama_models = []
                    if "models" in data:
                        for model_info in data["models"]:
                            model_name = model_info.get("name", "")
                            if model_name:
                                models.append(model_name)
                                ollama_models.append(OllamaModelInfo(
                                    name=model_name,
                                    size=model_info.get("size"),
                                    modified_at=model_info.get("modified_at")
                                ))
                    
                    return ModelsResponse(
                        provider=provider_lower,
                        models=models,
                        ollama_models=ollama_models
                    )
            except httpx.ConnectError:
                raise HTTPException(
                    status_code=503,
                    detail=f"无法连接到Ollama服务 ({base_url})。请确保Ollama服务正在运行。"
                )
            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=504,
                    detail=f"连接Ollama服务超时 ({base_url})。"
                )
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    status_code=exc.response.status_code,
                    detail=f"Ollama API错误: {exc.response.text[:200]}"
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail=f"获取Ollama模型列表失败: {str(exc)}"
                )
        
        elif provider_lower == "qwen":
            # Qwen models (common models)
            models = [
                "qwen-plus",
                "qwen-max",
                "qwen-turbo",
                "qwen-max-longcontext",
                "qwen-plus-longcontext"
            ]
            return ModelsResponse(provider=provider_lower, models=models)
        
        elif provider_lower == "azure_openai":
            # Azure OpenAI models (common models)
            # Note: The actual deployment name in Azure may differ from these model names
            models = [
                "gpt-4",
                "gpt-4-turbo",
                "gpt-4-32k",
                "gpt-3.5-turbo",
                "gpt-35-turbo",
            ]
            return ModelsResponse(provider=provider_lower, models=models)
        
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Provider {provider_lower} does not support model listing"
            )
    
    except HTTPException:
        raise
    except Exception as exc:
        error_msg = format_error_message(exc, "Failed to get available models")
        raise HTTPException(status_code=500, detail=error_msg) from exc


class MCPConfigResponse(BaseModel):
    """Response model for MCP configuration."""
    config: Dict[str, Any] = Field(..., description="MCP configuration (mcpServers)")
    server_count: int = Field(..., description="Number of configured MCP servers")
    tool_count: int = Field(..., description="Total number of tools from all servers")


class MCPConfigUpdateRequest(BaseModel):
    """Request model for updating MCP configuration."""
    config: Dict[str, Any] = Field(..., description="MCP configuration (mcpServers)")


@router.get("/mcp-config", response_model=MCPConfigResponse)
def get_mcp_config() -> MCPConfigResponse:
    """Get current MCP configuration."""
    try:
        config = load_mcp_config()
        mcp_servers = config.get("mcpServers", {})
        
        # Count tools (we need to load them from registry)
        # For now, just return server count
        # Tool count will be approximate since tools are loaded lazily
        from ..core.container import get_container
        try:
            container = get_container()
            chat_service = container.chat_service
            tool_count = len(chat_service.mcp_registry.tools)
        except Exception:
            # If registry not available, return 0
            tool_count = 0
        
        return MCPConfigResponse(
            config={"mcpServers": mcp_servers},
            server_count=len(mcp_servers),
            tool_count=tool_count
        )
    except Exception as exc:
        error_msg = format_error_message(exc, "Failed to get MCP configuration")
        raise HTTPException(status_code=500, detail=error_msg) from exc


@router.post("/mcp-config", response_model=Dict[str, Any])
def update_mcp_config(request: MCPConfigUpdateRequest) -> Dict[str, Any]:
    """Update MCP configuration."""
    try:
        # Validate JSON structure
        if "mcpServers" not in request.config:
            raise HTTPException(
                status_code=400,
                detail="Invalid MCP configuration: 'mcpServers' key is required"
            )
        
        # Get config file path
        from pathlib import Path
        backend_dir = Path(__file__).parent.parent.parent
        config_path = backend_dir / "mcp.json"
        
        # Validate JSON by trying to serialize it
        try:
            json.dumps(request.config)
        except (TypeError, ValueError) as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON configuration: {str(e)}"
            )
        
        # Write to file
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(request.config, f, indent=2, ensure_ascii=False)
        
        # Reload MCP registry (gracefully closes old connections, reinitializes everything)
        from ..core.container import get_container
        import asyncio
        try:
            container = get_container()
            chat_service = container.chat_service
            # reload_config is now async, need to run it
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            loop.run_until_complete(chat_service.mcp_registry.reload_config(str(config_path)))
            
            # Get updated server info
            server_info = chat_service.mcp_registry.server_manager.list_servers()
            
            return {
                "status": "success",
                "message": "MCP configuration updated and reloaded successfully",
                "server_count": len(request.config.get("mcpServers", {})),
                "tool_count": len(chat_service.mcp_registry.tools),
                "servers": server_info
            }
        except Exception as e:
            # Log error and fail the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to reload MCP registry: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Configuration saved but failed to reload: {str(e)}"
            )
    except HTTPException:
        raise
    except Exception as exc:
        error_msg = format_error_message(exc, "Failed to update MCP configuration")
        raise HTTPException(status_code=500, detail=error_msg) from exc

