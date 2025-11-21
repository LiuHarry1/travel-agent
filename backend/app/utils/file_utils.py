"""File handling utilities."""

import base64
import logging
from typing import Optional

from .constants import BINARY_FILE_PREFIX, BINARY_FILE_SUFFIX, TEXT_EXTENSIONS

logger = logging.getLogger(__name__)


def is_binary_file(file_content: str) -> bool:
    """Check if file content is a binary file marker."""
    return file_content.startswith(BINARY_FILE_PREFIX)


def parse_binary_file_marker(file_content: str) -> tuple[Optional[str], Optional[str]]:
    """
    Parse binary file marker to extract extension and base64 content.
    
    Args:
        file_content: File content with binary marker
        
    Returns:
        Tuple of (file_extension, base64_content) or (None, None) if parsing fails
    """
    if not is_binary_file(file_content):
        return None, None
    
    try:
        content = file_content[len(BINARY_FILE_PREFIX):]
        if content.endswith(BINARY_FILE_SUFFIX):
            content = content[:-len(BINARY_FILE_SUFFIX)]
        
        parts = content.split(":", 1)
        file_ext = parts[0] if parts else ""
        base64_content = parts[1] if len(parts) > 1 else ""
        
        return file_ext, base64_content
    except Exception as e:
        logger.error(f"Failed to parse binary file marker: {e}")
        return None, None


def decode_binary_content(base64_content: str) -> Optional[bytes]:
    """Decode base64 content to bytes."""
    try:
        return base64.b64decode(base64_content)
    except Exception as e:
        logger.error(f"Failed to decode base64 content: {e}")
        return None


def is_text_file(file_name: str) -> bool:
    """Check if file is a text file based on extension."""
    file_name_lower = file_name.lower()
    return any(file_name_lower.endswith(ext) for ext in TEXT_EXTENSIONS)


def truncate_content(content: str, max_size: int, file_name: str = "") -> str:
    """
    Truncate content if it exceeds max size.
    
    Args:
        content: Content to truncate
        max_size: Maximum size in characters
        file_name: Optional file name for error message
        
    Returns:
        Truncated content with note if truncated
    """
    if len(content) <= max_size:
        return content
    
    truncated = content[:max_size]
    note = f"\n\n[Note: File content truncated. Original size: {len(content)} characters]"
    if file_name:
        note = f"\n\n[Note: {file_name} content truncated. Original size: {len(content)} characters]"
    
    return truncated + note

