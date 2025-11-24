from __future__ import annotations

import sys
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure backend directory is in sys.path for imports
# This must be done before importing app modules
_backend_dir = Path(__file__).parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

# Initialize platform-specific configuration early
# This must be done before any other imports that might use asyncio
from app.platform_config import initialize_platform
initialize_platform()

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

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

# Initialize container
container = get_container()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI application.
    Handles startup and shutdown events.
    """
    logger = logging.getLogger(__name__)
    
    # Verify event loop policy is set correctly (in case uvicorn created a new process)
    from app.platform_config import setup_event_loop_policy, check_event_loop_for_uvicorn
    
    # Re-set policy in case uvicorn created a new process
    setup_event_loop_policy()
    
    # Check the actual running event loop and log platform-specific warnings
    check_event_loop_for_uvicorn()
    
    # Startup
    try:
        await container.initialize()
    except Exception as e:
        logger.warning(f"Failed to initialize services: {e}. They will be initialized on first use.", exc_info=True)
    
    yield
    
    # Shutdown
    try:
        await container.shutdown()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}", exc_info=True)


app = FastAPI(title="Travel Agent", version="1.0.0", lifespan=lifespan)

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

# Register routers
app.include_router(common_router)
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(chat_router)

# Mount static files directories
logger = logging.getLogger(__name__)
backend_dir = Path(__file__).parent.parent

# Mount static directory if it exists
static_dir = backend_dir / "static"
if static_dir.exists() and static_dir.is_dir():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info(f"Mounted static files directory: {static_dir} -> /static")
    
    # Also mount pic subdirectory for easier access
    pic_dir = static_dir / "pic"
    if pic_dir.exists() and pic_dir.is_dir():
        app.mount("/static/pic", StaticFiles(directory=str(pic_dir)), name="pic")
        logger.info(f"Mounted pic directory: {pic_dir} -> /static/pic")


async def run_server():
    """Async function to run uvicorn server with proper event loop."""
    import asyncio
    from uvicorn import Config, Server
    
    # Event loop policy is already set by initialize_platform() at module import
    # and by setup_event_loop_policy() in main() function
    # No need to set it again here
    
    # Verify the event loop is correct
    loop = asyncio.get_running_loop()
    loop_type = type(loop).__name__
    logger = logging.getLogger(__name__)
    logger.info(f"Running server with event loop: {loop_type}")
    
    # Use DEBUG level if LOG_LEVEL env var is set to DEBUG
    uvicorn_log_level = "debug" if os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG" else "info"
    
    # Create uvicorn config and server
    config = Config(
        app="app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level=uvicorn_log_level,
        reload=False,  # Disable reload to ensure proper event loop
    )
    server = Server(config)
    
    # Run the server
    await server.serve()


def main():
    """启动 FastAPI 应用"""
    # Event loop policy is already set by initialize_platform() at module import
    # But we verify it here to ensure it's correct (especially if uvicorn creates new process)
    from app.platform_config import setup_event_loop_policy, verify_event_loop_policy
    import asyncio
    
    # Re-set policy in case uvicorn or other code created a new process/thread
    # This is especially important on Windows where ProactorEventLoop is required
    setup_event_loop_policy()
    
    # Verify the policy is set correctly
    verification_result = verify_event_loop_policy()
    # Warnings are already logged by verify_event_loop_policy
    
    # Use asyncio.run() to ensure proper event loop is used
    # This is similar to how backend_new test scripts work
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger = logging.getLogger(__name__)
        logger.info("Server stopped by user")


if __name__ == "__main__":
    main()

