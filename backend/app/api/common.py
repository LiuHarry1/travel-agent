"""Common API routes (health check, configuration)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..config import get_config, reload_config
from ..models import ConfigUpdateRequest
from ..utils.exceptions import format_error_message

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "ok"}


@router.get("/config")
def get_default_config() -> dict:
    """Get default configuration including system prompt template and checklist."""
    config = get_config()
    return {
        "system_prompt_template": config.system_prompt_template,
        "checklist": [{"id": item.id, "description": item.description} for item in config.default_checklist],
    }


@router.post("/config")
def save_config(request: ConfigUpdateRequest) -> dict:
    """Save system prompt template and checklist configuration."""
    try:
        get_config().save_config(request.system_prompt_template, request.checklist)
        reload_config()
        return {"status": "success", "message": "Configuration saved successfully"}
    except Exception as exc:
        error_msg = format_error_message(exc, "Failed to save configuration")
        raise HTTPException(status_code=500, detail=error_msg) from exc

