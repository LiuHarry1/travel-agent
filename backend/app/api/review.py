"""Single-pass MRT review API routes."""
from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from ..llm import DashScopeError
from ..models import ReviewRequest, ReviewResponse
from ..service.file_parser import parse_file_content
from ..utils.constants import MAX_FILE_SIZE_BYTES, SUPPORTED_EXTENSIONS
from ..utils.exceptions import FileProcessingError, format_error_message

if TYPE_CHECKING:
    from ..service.review import ReviewService
else:
    ReviewService = Any

router = APIRouter()

# Global service instance (will be set by setup_review_routes)
_review_service: ReviewService | None = None


def get_review_service() -> ReviewService:
    """Dependency to get review service."""
    if _review_service is None:
        raise RuntimeError("Review service not initialized. Call setup_review_routes first.")
    return _review_service


def setup_review_routes(review_service: ReviewService) -> None:
    """
    Setup review route handlers with service dependencies.
    
    Args:
        review_service: Review service instance
    """
    global _review_service
    _review_service = review_service


@router.post("/review", response_model=ReviewResponse)
def review(
    request: ReviewRequest,
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewResponse:
    """Review MRT content using single-pass review."""
    try:
        return review_service.review(request)
    except DashScopeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/upload/file")
def upload_file(file: UploadFile = File(...)) -> dict:
    """Upload and parse file, returning text content."""
    try:
        # Validate file size
        content = file.file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f}MB"
            )
        
        # Validate file extension
        file_ext = file.filename.lower().split('.')[-1] if '.' in file.filename else ''
        if file_ext and f".{file_ext}" not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: .{file_ext}. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
            )
        
        # Determine if binary or text
        if file_ext in ['pdf', 'doc', 'docx']:
            # Encode as base64 for binary files
            base64_content = base64.b64encode(content).decode('utf-8')
            file_content = f"[BINARY_FILE:.{file_ext}:{base64_content}]"
        else:
            # Text file
            try:
                file_content = content.decode('utf-8')
            except UnicodeDecodeError:
                file_content = content.decode('utf-8', errors='ignore')
        
        # Parse file
        text_content = parse_file_content(file.filename, file_content)
        
        if text_content is None:
            raise FileProcessingError(
                f"Failed to parse file {file.filename}. "
                f"Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}"
            )
        
        return {
            "filename": file.filename,
            "content": text_content,
            "size": len(text_content)
        }
    except HTTPException:
        raise
    except FileProcessingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        error_msg = format_error_message(exc, "Failed to process file")
        raise HTTPException(status_code=500, detail=error_msg) from exc

