"""API routes package."""

from .admin import router as admin_router
from .chat import router as chat_router
from .common import router as common_router

__all__ = ["admin_router", "chat_router", "common_router"]

