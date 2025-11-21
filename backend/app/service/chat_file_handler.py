"""File handling utilities for chat service."""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from ..utils.constants import MAX_FILE_CONTENT_SIZE, MAX_TOTAL_FILE_SIZE
from ..utils.file_utils import is_binary_file, truncate_content
from .file_parser import parse_file_content

logger = logging.getLogger(__name__)


def format_files_for_message(files: Optional[List[Dict[str, str]]]) -> str:
    """
    Handle file uploads and format them for user message in conversation history.
    
    Args:
        files: List of file dictionaries with 'name' and 'content' keys
        
    Returns:
        Formatted file content string to be added to user message.
        Format: "[File: filename]\n{content}" for each file.
    """
    if not files:
        return ""

    file_parts = []

    for file_info in files:
        file_name = file_info.get("name", "untitled")
        file_content = file_info.get("content", "")
        if not file_content:
            continue

        # Parse file content
        parsed_content = None
        if is_binary_file(file_content):
            # Try to parse binary file
            try:
                parsed_content = parse_file_content(file_name, file_content)
            except Exception as e:
                logger.warning(f"Failed to parse binary file {file_name}: {e}")

        if parsed_content is None:
            # Handle text files or failed binary parsing
            if not is_binary_file(file_content):
                parsed_content = file_content
            else:
                # Binary file that couldn't be parsed
                file_parts.append(
                    f"[File: {file_name}]\n"
                    f"[Note: This is a binary file that could not be parsed. "
                    f"Please paste the file content as text or use a text format file.]\n"
                )
                continue

        # Truncate if too long
        parsed_content = truncate_content(parsed_content, MAX_FILE_CONTENT_SIZE, file_name)

        # Check total size
        current_total = sum(len(part) for part in file_parts)
        if current_total + len(parsed_content) > MAX_TOTAL_FILE_SIZE:
            remaining = MAX_TOTAL_FILE_SIZE - current_total
            if remaining > 0:
                truncated = truncate_content(parsed_content, remaining, file_name)
                file_parts.append(
                    f"[File: {file_name}]\n{truncated}\n\n"
                    f"[Note: Remaining file content omitted due to size limit]"
                )
            break

        file_parts.append(f"[File: {file_name}]\n{parsed_content}")

    if file_parts:
        return "\n\n".join(file_parts)
    return ""

