"""Legacy configuration module - maintained for backward compatibility."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import ChecklistItem
from .shared.config import Settings, get_settings


class Config:
    """
    Application configuration loader.
    
    This is a legacy compatibility wrapper around the new Settings class.
    New code should use app.shared.config.Settings directly.
    """

    def __init__(self, config_path: Optional[str] = None):
        # Use new Settings class internally
        self._settings = Settings.from_yaml(config_path) if config_path else get_settings()
        self._config = self._load_config(self._settings.config_path)
        self._default_checklist: Optional[List[ChecklistItem]] = None

    @staticmethod
    def _load_config(path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        config_file = Path(path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
        with open(config_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @property
    def system_prompt_template(self) -> str:
        """Get default system prompt template from config.yaml."""
        return self._settings.llm.system_prompt_template

    @property
    def llm_model(self) -> str:
        """Get LLM model name."""
        return self._settings.llm.model

    @property
    def llm_timeout(self) -> float:
        """Get LLM request timeout in seconds."""
        return self._settings.llm.timeout



    @property
    def config_path(self) -> str:
        """Get the path to the configuration file."""
        return os.getenv("TRAVEL_AGENT_CONFIG", str(Path(__file__).parent / "config.yaml"))

    def save_config(self, system_prompt_template: str, checklist: List[ChecklistItem]) -> None:
        """Save system prompt template and checklist to configuration file."""
        self._settings.llm.system_prompt_template = system_prompt_template
        self._settings.default_checklist = checklist
        self._settings.save_to_yaml()
        self._config = self._load_config(self._settings.config_path)
        self._default_checklist = None  # Reset cache

    def save_system_prompt_template(self, system_prompt_template: str) -> None:
        """Save system prompt template to configuration file."""
        self._settings.save_system_prompt_template(system_prompt_template)
        self._config = self._load_config(self._settings.config_path)

    def save_llm_config(self, provider: str, model: str) -> None:
        """Save LLM provider and model to configuration file."""
        self._settings.save_llm_config(provider, model)
        self._config = self._load_config(self._settings.config_path)

    @property
    def llm_provider(self) -> str:
        """Get LLM provider name."""
        return self._settings.llm.provider

    @property
    def llm_azure_model(self) -> str:
        """Get Azure OpenAI model name."""
        return self._settings.llm.azure_model or "gpt-4"

    @property
    def llm_ollama_model(self) -> str:
        """Get Ollama model name."""
        return self._settings.llm.ollama_model or "qwen2.5:32b"


# Global configuration instance
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config(config_path: Optional[str] = None) -> Config:
    """Reload configuration from file."""
    global _config_instance
    _config_instance = Config(config_path)
    return _config_instance

