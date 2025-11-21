"""Logging configuration for the application."""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Track if logging has been configured
_logging_configured = False


def setup_logging(
    log_level=logging.INFO,
    log_dir: str = "logs",
    log_file: str = "app.log",
    console_output: bool = True,
    file_output: bool = True,
    force: bool = False,
):
    """
    Setup logging configuration for both console and file output.
    Only configures once unless force=True.
    
    Args:
        log_level: Logging level (default: INFO)
        log_dir: Directory to store log files (default: "logs")
        log_file: Name of the log file (default: "app.log")
        console_output: Whether to output logs to console (default: True)
        file_output: Whether to output logs to file (default: True)
        force: Force reconfiguration even if already configured (default: False)
    """
    global _logging_configured
    
    # If already configured and not forcing, skip
    if _logging_configured and not force:
        return
    
    # Create log directory if it doesn't exist
    log_file_path = None
    if file_output:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        log_file_path = log_path / log_file
    
    # Create formatter
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if file_output and log_file_path:
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,  # Keep 5 backup files
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Suppress watchfiles info logs (used by uvicorn reload)
    watchfiles_logger = logging.getLogger("watchfiles")
    watchfiles_logger.setLevel(logging.WARNING)
    
    # Mark as configured
    _logging_configured = True
    
    # Log the configuration
    root_logger.info(f"Logging configured - Level: {logging.getLevelName(log_level)}, Console: {console_output}, File: {file_output}")
    if file_output and log_file_path:
        root_logger.info(f"Log file: {log_file_path}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the given name.
    Use this in any module instead of logging.getLogger().
    
    Example:
        from app.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Log message")
    """
    return logging.getLogger(name)

