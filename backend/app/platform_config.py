"""Platform-specific configuration and setup."""
from __future__ import annotations

import asyncio
import logging
import sys
import warnings
from typing import Optional

# Use a basic logger that works even if logging isn't fully configured yet
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Set up a basic handler if logging isn't configured yet
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def setup_event_loop_policy() -> None:
    """
    Set up event loop policy to support subprocess operations.
    
    This function attempts to configure the event loop policy to support
    subprocess operations, which is required for external stdio MCP servers.
    On Windows, this requires ProactorEventLoop. On other platforms, the
    default policy usually supports subprocess.
    
    This function is called early in the application startup, before any
    asyncio operations are performed.
    
    Note: Windows-specific logic is only executed on Windows platform.
    """
    # Only configure event loop policy on Windows
    # On other platforms, the default policy usually supports subprocess
    if not is_windows():
        logger.debug("Not on Windows - using default event loop policy (should support subprocess)")
        return
    
    # Windows-specific: Set ProactorEventLoop policy for subprocess support
    try:
        if hasattr(asyncio, 'WindowsProactorEventLoopPolicy'):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            logger.info("Set event loop policy to WindowsProactorEventLoopPolicy for subprocess support")
        else:
            logger.warning("WindowsProactorEventLoopPolicy not available - subprocess operations may not work")
    except Exception as e:
        # If setting policy fails, log warning but continue
        # External stdio servers will fail gracefully if subprocess is not supported
        logger.warning(f"Failed to set event loop policy: {e}. Subprocess operations may not work.")


def setup_warnings() -> None:
    """
    Configure warning filters for platform-specific harmless warnings.
    
    Some platforms (especially Windows) may produce harmless warnings related
    to resource cleanup that don't affect functionality. This function
    filters out those warnings for cleaner logs.
    
    Note: Some warning filters are applied on all platforms, while others
    are Windows-specific.
    """
    # Suppress harmless asyncio resource warnings (all platforms)
    # These warnings occur when subprocess transports are cleaned up after event loop closes
    warnings.filterwarnings("ignore", category=ResourceWarning, message=".*unclosed.*")
    warnings.filterwarnings("ignore", message=".*Event loop is closed.*")
    warnings.filterwarnings("ignore", message=".*I/O operation on closed pipe.*")
    warnings.filterwarnings("ignore", message=".*Exception ignored.*")
    
    # Windows-specific warning filters
    if is_windows():
        # Additional Windows-specific warnings that can be safely ignored
        warnings.filterwarnings("ignore", message=".*Cancelling an overlapped future failed.*")
        warnings.filterwarnings("ignore", message=".*unclosed transport.*")


def initialize_platform() -> None:
    """
    Initialize platform-specific configuration.
    
    This function should be called early in the application startup,
    before any asyncio operations or imports that use asyncio.
    
    It sets up:
    - Event loop policy for subprocess support
    - Warning filters for cleaner logs
    """
    setup_event_loop_policy()
    setup_warnings()
    logger.info("Platform configuration initialized")


def get_event_loop_info() -> dict[str, any]:
    """
    Get information about the current event loop configuration.
    
    Returns:
        Dictionary with event loop information
    """
    try:
        loop = asyncio.get_running_loop()
        loop_type = type(loop).__name__
        
        is_proactor = 'Proactor' in loop_type
        is_selector = 'Selector' in loop_type
        
        # Determine subprocess support based on platform
        if is_windows():
            # On Windows, only ProactorEventLoop actually supports subprocess
            # _WindowsSelectorEventLoop has subprocess_exec but it raises NotImplementedError
            if is_selector:
                supports_subprocess = False  # SelectorEventLoop doesn't actually support subprocess on Windows
            elif is_proactor:
                supports_subprocess = True  # ProactorEventLoop supports subprocess
            else:
                supports_subprocess = False  # Unknown loop type on Windows, assume no support
        else:
            # On other platforms, check if method exists
            supports_subprocess = hasattr(loop, 'subprocess_exec')
        
        return {
            "loop_type": loop_type,
            "is_running": loop.is_running(),
            "supports_subprocess": supports_subprocess,
            "is_proactor": is_proactor,
            "is_selector": is_selector,
        }
    except RuntimeError:
        # No running loop
        try:
            policy = asyncio.get_event_loop_policy()
            policy_type = type(policy).__name__
            is_proactor_policy = 'Proactor' in policy_type
            
            return {
                "loop_type": "None (no running loop)",
                "policy_type": policy_type,
                "is_proactor_policy": is_proactor_policy,
                "supports_subprocess": "unknown (no loop to check)",
            }
        except Exception:
            return {
                "loop_type": "Unknown",
                "error": "Could not get event loop information",
            }


def is_windows() -> bool:
    """
    Check if running on Windows platform.
    
    Returns:
        True if running on Windows, False otherwise
    """
    return sys.platform == "win32"


def verify_event_loop_policy() -> dict[str, any]:
    """
    Verify that the event loop policy is set correctly and supports subprocess.
    
    This function checks the event loop policy and determines if it supports
    subprocess operations, which is critical for external stdio MCP servers.
    
    Returns:
        Dictionary with verification results including:
        - policy_type: Type of event loop policy
        - loop_type: Type of event loop that would be created
        - supports_subprocess: Whether subprocess operations are supported
        - warnings: List of warning messages if any issues detected
    """
    logger = logging.getLogger(__name__)
    warnings_list = []
    
    try:
        policy = asyncio.get_event_loop_policy()
        test_loop = policy.new_event_loop()
        loop_type = type(test_loop).__name__
        
        # On Windows, only ProactorEventLoop actually supports subprocess
        is_proactor = 'Proactor' in loop_type
        is_selector = 'Selector' in loop_type
        
        # Determine subprocess support based on platform and loop type
        if is_windows():
            # On Windows, only ProactorEventLoop supports subprocess
            if is_selector:
                supports_subprocess = False  # SelectorEventLoop on Windows doesn't support subprocess
            elif is_proactor:
                supports_subprocess = True  # ProactorEventLoop supports subprocess
            else:
                supports_subprocess = False  # Unknown loop type on Windows, assume no support
        else:
            # On non-Windows platforms, check if method exists
            supports_subprocess = hasattr(test_loop, 'subprocess_exec')
        
        test_loop.close()
        
        logger.info(f"Event loop policy verified: {type(policy).__name__} -> {loop_type}, supports_subprocess: {supports_subprocess}")
        
        if not supports_subprocess:
            warning_msg = "Event loop does not support subprocess operations. External stdio MCP servers may not work."
            warnings_list.append(warning_msg)
            logger.warning(warning_msg)
            
            if is_selector and is_windows():
                # Windows-specific warning about SelectorEventLoop
                selector_warning = "  Detected SelectorEventLoop on Windows. This does not support subprocess operations."
                local_tools_warning = "  Consider using local tools (type: 'local') instead of stdio servers."
                warnings_list.append(selector_warning)
                warnings_list.append(local_tools_warning)
                logger.warning(selector_warning)
                logger.warning(local_tools_warning)
        
        return {
            "policy_type": type(policy).__name__,
            "loop_type": loop_type,
            "supports_subprocess": supports_subprocess,
            "is_proactor": is_proactor,
            "is_selector": is_selector,
            "warnings": warnings_list,
        }
    except Exception as e:
        error_msg = f"Could not verify event loop policy: {e}"
        logger.warning(error_msg)
        return {
            "policy_type": "Unknown",
            "loop_type": "Unknown",
            "supports_subprocess": False,
            "error": error_msg,
            "warnings": [error_msg],
        }


def is_windows_socket_error(error_msg: str) -> bool:
    """
    Check if an error message indicates a Windows-specific socket error.
    
    Windows socket error 10054 (WSAECONNRESET) occurs when the remote host
    forcibly closes an existing connection. This is common on Windows and
    may need special handling.
    
    Args:
        error_msg: Error message string to check
        
    Returns:
        True if the error appears to be a Windows socket error
    """
    windows_socket_indicators = [
        "10054",  # WSAECONNRESET
        "远程主机强迫关闭",  # Chinese error message for connection reset
        "Connection reset",
    ]
    return any(indicator in error_msg for indicator in windows_socket_indicators)


def format_network_error(error_msg: str, is_socket_error: bool = False) -> str:
    """
    Format network error messages with platform-appropriate guidance.
    
    Args:
        error_msg: Original error message
        is_socket_error: Whether this is a socket connection error
        
    Returns:
        Formatted error message with helpful guidance
    """
    if is_socket_error:
        return (
            "连接被远程主机关闭：可能是网络不稳定、服务器限流或代理服务器问题。"
            "请检查网络连接，稍后重试，或检查代理服务器配置。"
        )
    
    if "nodename" in error_msg or "not known" in error_msg or "getaddrinfo" in error_msg:
        return (
            "网络连接错误：无法解析服务器地址。请检查网络连接和DNS设置。"
        )
    
    return f"网络错误：{error_msg}"


def check_event_loop_for_uvicorn() -> None:
    """
    Check the event loop type after uvicorn starts and log warnings if needed.
    
    This function should be called in the lifespan startup to verify that
    uvicorn is using the correct event loop type, especially on Windows where
    ProactorEventLoop is required for subprocess operations.
    
    Note: Windows-specific checks are only performed on Windows.
    """
    import asyncio
    
    try:
        loop = asyncio.get_running_loop()
        loop_type = type(loop).__name__
        is_selector = 'Selector' in loop_type
        is_proactor = 'Proactor' in loop_type
        
        logger.info(f"Running event loop type: {loop_type}")
        
        # Windows-specific checks
        if is_windows():
            if is_selector:
                logger.error("=" * 60)
                logger.error("WARNING: uvicorn created SelectorEventLoop instead of ProactorEventLoop!")
                logger.error("This means subprocess operations (required for stdio MCP servers) will NOT work.")
                logger.error("=" * 60)
                logger.error("Possible solutions:")
                logger.error("  1. Use local tools (type: 'local') instead of stdio servers")
                logger.error("  2. Run uvicorn with: python -m uvicorn app.main:app (may help)")
                logger.error("  3. Set environment variable: PYTHONASYNCIODEBUG=1 for more info")
                logger.error("=" * 60)
            elif is_proactor:
                logger.info("✓ ProactorEventLoop detected - subprocess operations should work")
        else:
            # On non-Windows platforms, just log the loop type
            if is_proactor:
                logger.info("✓ ProactorEventLoop detected")
            elif is_selector:
                logger.info("✓ SelectorEventLoop detected (normal on non-Windows platforms)")
    except RuntimeError:
        logger.warning("No running event loop to check")

