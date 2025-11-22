from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Fix for Windows: Use ProactorEventLoop for subprocess support (required by MCP SDK)
# ProactorEventLoop is the default on Windows 3.8+ and supports subprocess
# This must be set before any event loop is created
if sys.platform == "win32":
    # Windows ProactorEventLoop supports subprocess operations
    # Set the policy before any event loop is created
    if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Ensure backend directory is in sys.path for imports
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Use absolute imports for consistency
from app.api import (
    admin_router,
    chat_router,
    common_router,
    setup_chat_routes,
)
from app.logger import setup_logging
from app.llm import LLMClient
from app.service.chat import ChatService

# Configure logging to output to both console and file
# Use DEBUG level in development if LOG_LEVEL env var is set to DEBUG
log_level_env = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = logging.DEBUG if log_level_env == "DEBUG" else logging.INFO

setup_logging(
    log_level=log_level,
    log_dir=str(Path(__file__).parent.parent / "logs"),
    log_file="app.log",
    console_output=True,
    file_output=True
)

load_dotenv()

app = FastAPI(title="Travel Agent", version="1.0.0")

# CORS configuration
# Allow origins from environment variable, or default to allow all origins
# Format: comma-separated list, e.g., "http://localhost:5173,http://10.150.117.242:56906"
cors_origins_env = os.getenv("CORS_ALLOWED_ORIGINS", "")
if cors_origins_env:
    # Parse comma-separated origins from environment variable
    allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
else:
    # Default: allow all origins (for development/testing)
    # In production, you should set CORS_ALLOWED_ORIGINS environment variable
    allowed_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Initialize services
llm_client = LLMClient()
chat_service = ChatService(llm_client=llm_client)

# Setup routes with service dependencies
setup_chat_routes(chat_service=chat_service)

# Register routers
app.include_router(common_router)
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(chat_router)


def main():
    """启动 FastAPI 应用"""
    # Fix for Windows: Ensure ProactorEventLoop is set before uvicorn starts
    if sys.platform == "win32":
        if hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    # 使用导入字符串以支持 reload 功能
    # Use DEBUG level if LOG_LEVEL env var is set to DEBUG
    uvicorn_log_level = "debug" if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" else "info"
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=uvicorn_log_level
    )


if __name__ == "__main__":
    main()

