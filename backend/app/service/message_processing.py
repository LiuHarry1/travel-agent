"""Message processing logic for chat service."""
from __future__ import annotations

import logging
from typing import Dict, List

from ..models import ChatRequest
from ..utils.constants import MAX_CONVERSATION_TURNS
from .chat_file_handler import format_files_for_message

logger = logging.getLogger(__name__)


class MessageProcessingService:
    """Service for processing and formatting messages."""

    def __init__(self, config_getter):
        """Initialize message processing service."""
        self._get_config = config_getter
        self._mcp_registry = None

    def set_mcp_registry(self, mcp_registry):
        """Set MCP registry for tool information."""
        self._mcp_registry = mcp_registry

    def build_agent_system_prompt(self) -> str:
        """
        Build system prompt for travel agent.
        Reads base prompt from config.yaml (user-configurable) and adds available tools dynamically.
        Tool descriptions come from MCP tool schemas, which contain detailed usage instructions.
        No hardcoded tool names or usage guidelines - everything is dynamic and tool-agnostic.
        """
        # Get base system prompt template from config (user-configurable via UI)
        try:
            config = self._get_config()
            base_prompt = config.system_prompt_template
        except (ValueError, FileNotFoundError) as e:
            logger.warning(f"Could not load system prompt from config: {e}. Using default prompt.")
            base_prompt = "You are a helpful travel agent assistant. Your goal is to help users with travel-related questions and planning."
        
        # Get available tools from MCP servers (loaded dynamically - no hardcoded tool names)
        if not self._mcp_registry:
            return base_prompt
        
        tools = self._mcp_registry.list_tools()
        
        if not tools:
            # No tools available, return base prompt only
            return base_prompt
        
        # Build tool list with detailed descriptions
        # Tool descriptions come from MCP tool schemas and contain usage instructions
        # All tool-specific usage information is in the tool descriptions themselves
        tool_descriptions = []
        for tool in tools:
            # Get detailed description from tool schema
            tool_name = tool.name
            tool_desc = tool.description or ""
            
            # Get parameter descriptions from input schema for additional context
            # Parameter descriptions often contain important usage hints
            input_schema = getattr(tool, 'inputSchema', None) or getattr(tool, 'extra', {}).get('inputSchema', {})
            param_descriptions = []
            
            if isinstance(input_schema, dict):
                properties = input_schema.get("properties", {})
                for param_name, param_info in properties.items():
                    if isinstance(param_info, dict) and "description" in param_info:
                        param_desc = param_info["description"]
                        # Include parameter descriptions that contain usage hints (longer descriptions)
                        if param_desc and len(param_desc) > 50:
                            param_descriptions.append(f"  - {param_name}: {param_desc}")
            
            # Build tool entry
            tool_entry = f"- {tool_name}: {tool_desc}"
            if param_descriptions:
                # Include parameter descriptions that contain usage hints
                tool_entry += "\n" + "\n".join(param_descriptions)
            
            tool_descriptions.append(tool_entry)
        
        tool_list = "\n".join(tool_descriptions)
        
        # Append tools section to base prompt
        # All tool-specific usage instructions are in the tool descriptions themselves
        # No hardcoded tool names or usage guidelines - fully dynamic
        prompt = f"""{base_prompt}

Available Tools:
{tool_list}

Use the available tools when you need specific information to answer user questions. Each tool's description and parameters contain detailed usage instructions.

Important: If you have tried using the available tools but still cannot provide a helpful answer to the user's travel-related question, politely inform the user that you could not find the information and suggest they contact Harry for more specific assistance."""
        
        logger.info(f"Generated system prompt: {prompt}")
        return prompt

    def trim_history(self, messages: List[Dict[str, str]], max_turns: int = MAX_CONVERSATION_TURNS) -> List[Dict[str, str]]:
        """
        Trim conversation history to keep only recent messages.
        
        Args:
            messages: Full conversation history
            max_turns: Maximum number of message turns to keep
            
        Returns:
            Trimmed conversation history
        """
        if len(messages) <= max_turns:
            return messages

        # Keep system message if exists, then recent messages
        if messages and messages[0].get("role") == "system":
            return [messages[0]] + messages[-(max_turns - 1):]
        return messages[-max_turns:]

    def prepare_messages(self, request: ChatRequest) -> List[Dict[str, str]]:
        """
        Prepare messages from request, including file handling.
        Filters out tool messages and tool_calls - only keeps user and assistant messages.
        
        Args:
            request: Chat request with message and files
            
        Returns:
            List of message dictionaries (only user and assistant, no tool messages)
        """
        # Handle file uploads - format as part of user message
        file_content = format_files_for_message(request.files)
        
        # Build user message
        user_message = request.message or ""
        if file_content:
            if user_message:
                user_message = f"{user_message}\n\n{file_content}"
            else:
                user_message = file_content

        # Get conversation history from request
        messages = request.messages or []
        
        # Filter out tool messages and tool_calls - only keep user and assistant messages
        # Also remove tool_calls from assistant messages
        filtered_messages = []
        for msg in messages:
            role = msg.get("role", "")
            # Only include user and assistant messages
            if role in ("user", "assistant"):
                # Create a clean message without tool_calls
                clean_msg = {
                    "role": role,
                    "content": msg.get("content", "") or ""  # Ensure content is always a string
                }
                # Explicitly exclude tool_calls, tool_call_id, name, etc.
                filtered_messages.append(clean_msg)
            # Skip tool messages (role == "tool")
        
        # Add current user message to history
        if user_message:
            filtered_messages.append({"role": "user", "content": user_message})

        # Trim history to keep it manageable
        return self.trim_history(filtered_messages)

