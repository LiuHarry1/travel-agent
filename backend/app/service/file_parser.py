"""File parsing utilities for PDF, Word, and text files."""
from __future__ import annotations

import logging
from typing import Optional

from ..utils.constants import BINARY_EXTENSIONS, TEXT_EXTENSIONS
from ..utils.file_utils import (
    decode_binary_content,
    is_binary_file,
    is_text_file,
    parse_binary_file_marker,
)

logger = logging.getLogger(__name__)


def parse_file_content(file_name: str, file_content: str) -> Optional[str]:
    """
    Parse file content and extract text.
    
    Args:
        file_name: Name of the file
        file_content: File content as base64 encoded string (for binary) or plain text
    
    Returns:
        Extracted text content or None if parsing fails
    """
    # Check if it's a base64 encoded binary file
    if is_binary_file(file_content):
        file_ext, base64_content = parse_binary_file_marker(file_content)
        if file_ext and base64_content:
            # Ensure file extension starts with dot
            if not file_ext.startswith('.'):
                file_ext = '.' + file_ext
            if file_ext in BINARY_EXTENSIONS:
                file_bytes = decode_binary_content(base64_content)
                if file_bytes:
                    return parse_binary_file(file_ext, file_bytes)
        return None
    
    # Handle text files - already plain text
    if is_text_file(file_name):
        return file_content
    
    return None


def parse_binary_file(file_ext: str, file_bytes: bytes) -> Optional[str]:
    """
    Parse binary file (PDF/Word) from bytes.
    
    Args:
        file_ext: File extension (.pdf, .doc, .docx)
        file_bytes: File content as bytes
    
    Returns:
        Extracted text content or None if parsing fails
    """
    try:
        if file_ext == ".pdf":
            return parse_pdf(file_bytes)
        elif file_ext in [".doc", ".docx"]:
            return parse_word(file_bytes, file_ext)
    except Exception as e:
        logger.error(f"Failed to parse binary file {file_ext}: {e}")
        return None
    
    return None


def parse_pdf(file_bytes: bytes) -> Optional[str]:
    """Parse PDF file and extract text."""
    from io import BytesIO
    
    try:
        # Try PyPDF2 first (more common)
        try:
            import PyPDF2
            
            pdf_file = BytesIO(file_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            
            text_parts = []
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())
            
            return "\n".join(text_parts)
        except ImportError:
            logger.warning("PyPDF2 not installed, trying pdfplumber")
        
        # Fallback to pdfplumber
        try:
            import pdfplumber
            
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                text_parts = []
                for page in pdf.pages:
                    text_parts.append(page.extract_text() or "")
                
                return "\n".join(text_parts)
        except ImportError:
            logger.warning("pdfplumber not installed, PDF parsing not available")
            return None
            
    except Exception as e:
        logger.error(f"Failed to parse PDF: {e}")
        return None


def parse_word(file_bytes: bytes, file_ext: str) -> Optional[str]:
    """Parse Word file (.doc or .docx) and extract text."""
    from io import BytesIO
    
    try:
        if file_ext == ".docx":
            # Use python-docx for .docx files
            try:
                from docx import Document
                
                doc = Document(BytesIO(file_bytes))
                paragraphs = [para.text for para in doc.paragraphs]
                return "\n".join(paragraphs)
            except ImportError:
                logger.warning("python-docx not installed, .docx parsing not available")
                return None
        elif file_ext == ".doc":
            # For .doc files, we'd need antiword or similar
            # For now, return None and suggest user to convert to .docx
            logger.warning(".doc files require additional libraries. Please convert to .docx or use .txt")
            return None
            
    except Exception as e:
        logger.error(f"Failed to parse Word file: {e}")
        return None
    
    return None

