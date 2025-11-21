from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ChecklistItem(BaseModel):
    id: str = Field(..., description="Checklist identifier")
    description: str = Field(..., description="Description of the checklist item")


class Suggestion(BaseModel):
    checklist_id: str = Field(..., description="Checklist identifier the suggestion refers to")
    message: str = Field(..., description="Suggested improvement text")


class ReviewRequest(BaseModel):
    mrt_content: str = Field(..., description="Raw manual regression test content provided by the user")
    software_requirement: Optional[str] = Field(
        default=None,
        description="Software requirement content. Used to review test cases against requirements to ensure comprehensive coverage.",
    )
    checklist: Optional[List[ChecklistItem]] = Field(
        default=None,
        description="Optional custom checklist to use for the review. If omitted, the default checklist is applied.",
    )
    system_prompt: Optional[str] = Field(
        default=None,
        description="Optional custom system prompt. If omitted, the default system prompt is used.",
    )


class ReviewResponse(BaseModel):
    suggestions: List[Suggestion] = Field(..., description="List of suggestions derived from the review")
    summary: Optional[str] = Field(default=None, description="Optional overall summary of the review")
    raw_content: Optional[str] = Field(default=None, description="Raw content output from the model")


class ChatRequest(BaseModel):
    session_id: Optional[str] = Field(
        default=None,
        description="Existing session identifier. Leave empty to start a new session.",
    )
    message: Optional[str] = Field(
        default=None,
        description="Free form user message to the agent.",
    )
    messages: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Full conversation history from frontend. Format: [{'role': 'user/assistant', 'content': '...'}, ...]",
    )
    mrt_content: Optional[str] = Field(
        default=None,
        description="Manual regression test content provided outside of the conversational message.",
    )
    software_requirement: Optional[str] = Field(
        default=None,
        description="Software requirement content provided outside of the conversational message.",
    )
    checklist: Optional[List[ChecklistItem]] = Field(
        default=None,
        description="Optional custom checklist provided outside of the conversational message.",
    )
    files: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="List of uploaded files with name and content. Format: [{'name': '...', 'content': '...'}, ...]",
    )


class ConfigUpdateRequest(BaseModel):
    system_prompt_template: str = Field(..., description="System prompt template to save")
    checklist: List[ChecklistItem] = Field(..., description="Checklist items to save")


class ToolCall(BaseModel):
    """Represents a tool call in the conversation."""
    id: Optional[str] = Field(default=None, description="Tool call ID")
    name: str = Field(..., description="Tool name")
    arguments: Dict[str, Any] = Field(..., description="Tool call arguments")
