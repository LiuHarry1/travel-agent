"""FastAPI dependencies for dependency injection."""
from __future__ import annotations

from fastapi import Depends

from ..core.container import Container, get_container
from ..service.chat import ChatService


def get_container_dep() -> Container:
    """Dependency to get container instance."""
    return get_container()


def get_chat_service(container: Container = Depends(get_container_dep)) -> ChatService:
    """Dependency to get chat service instance."""
    return container.chat_service

