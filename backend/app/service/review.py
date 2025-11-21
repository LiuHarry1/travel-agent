"""Review service for MRT content."""
from __future__ import annotations

from typing import Optional

from ..llm import LLMClient
from ..models import ReviewRequest, ReviewResponse


class ReviewService:
    """Service for reviewing MRT content."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize review service."""
        self.llm_client = llm_client or LLMClient()

    def review(self, request: ReviewRequest) -> ReviewResponse:
        """Review MRT content based on request."""
        return self.llm_client.review(
            mrt_content=request.mrt_content,
            software_requirement=request.software_requirement,
        )

