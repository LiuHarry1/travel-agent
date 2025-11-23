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
    
    # Suppress asyncio resource warnings on Windows
    # These warnings occur when subprocess transports are cleaned up after event loop closes
    # They are harmless and don't affect functionality
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*")
    warnings.filterwarnings("ignore", message=".*Event loop is closed.*")
    warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")
    warnings.filterwarnings("ignore", message=".*Exception ignored.*")

# Ensure backend directory is in sys.path for imports
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Use absolute imports for consistency
from app.api import (
    admin_router,
    chat_router,
    common_router,
)
from app.core.container import get_container
from app.logger import setup_logging

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

# Initialize container
container = get_container()

# Pre-warm services at startup
@app.on_event("startup")
async def startup_event():
    """Initialize services at application startup."""
    import logging
    import sys
    import asyncio
    logger = logging.getLogger(__name__)
    
    # On Windows, check if we can use subprocess with current event loop
    if sys.platform == "win32":
        try:
            loop = asyncio.get_running_loop()
            if not isinstance(loop, asyncio.ProactorEventLoop):
                logger.info("Current event loop is not ProactorEventLoop. Skipping pre-warm (will initialize on first use).")
                return
        except RuntimeError:
            logger.info("No running event loop. Skipping pre-warm (will initialize on first use).")
            return
    
    try:
        await container.initialize()
    except NotImplementedError as e:
        logger.info(f"Skipping pre-warm due to Windows subprocess limitation: {e}. Services will initialize on first use.")
    except Exception as e:
        logger.warning(f"Failed to initialize services: {e}. They will be initialized on first use.", exc_info=True)

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services at application shutdown."""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        await container.shutdown()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)

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

