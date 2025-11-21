"""Prompt building for MRT review."""
from __future__ import annotations

from typing import Optional

from ..config import get_config
from ..models import ChecklistItem


def build_checklist_string(checklist: list[ChecklistItem]) -> str:
    """Build checklist string from checklist items."""
    if not checklist:
        return "No checklist items provided."
    return "\n".join([f"- **{item.id}**: {item.description}" for item in checklist])


def build_system_prompt(software_requirement: Optional[str] = None) -> str:
    """Build system prompt from template. Reads checklist and template from config."""
    config = get_config()
    template = config.system_prompt_template
    checklist = config.default_checklist
    checklist_string = build_checklist_string(checklist)
    
    if software_requirement and software_requirement.strip():
        requirement_section = """### Software Requirements
When software requirements are provided, ensure that:
1. Each software requirement is covered by one or more test cases
2. Test cases cover all scenarios, conditions, and data described in the software requirements
3. Boundary situations, error cases, corner cases, performance, usability, and integration aspects are addressed
4. Test case numbering, title, preconditions, test steps, and verification points are clearly described"""
    else:
        requirement_section = """### Software Requirements
No software requirements provided. Focus on reviewing the test case quality against the checklist items above."""

    return template.format(
        checklist_section=checklist_string,
        requirement_section=requirement_section,
    )


def build_user_message(mrt_content: str, software_requirement: Optional[str] = None) -> str:
    """Build user message with actual task data."""
    parts = [
        "Please review the following Manual Regression Test (MRT) case according to the checklist and guidelines provided in the system prompt."
    ]

    if software_requirement and software_requirement.strip():
        parts.extend([
            "\n## Software Requirement",
            software_requirement.strip(),
        ])

    parts.extend([
        "\n## Manual Regression Test Case",
        mrt_content.strip(),
        "\n---",
        "\nPlease provide your review following the format specified in the system prompt.",
    ])

    return "\n".join(parts)

