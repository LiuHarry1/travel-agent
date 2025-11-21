from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .models import ChecklistItem


class Config:
    """Application configuration loader."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = os.getenv("MRT_REVIEW_CONFIG", str(Path(__file__).parent / "config.yaml"))
        self._config = self._load_config(config_path)
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
        template = self._config.get("llm", {}).get("system_prompt_template", "")
        if not template or not template.strip():
            raise ValueError(
                "system_prompt_template is required in config.yaml. "
                "Please ensure config.yaml contains llm.system_prompt_template."
            )
        return template

    @property
    def llm_model(self) -> str:
        """Get LLM model name."""
        return self._config.get("llm", {}).get("model", "qwen-max")

    @property
    def llm_timeout(self) -> float:
        """Get LLM request timeout in seconds."""
        return float(self._config.get("llm", {}).get("timeout", 30.0))

    @property
    def default_checklist(self) -> List[ChecklistItem]:
        """Get default checklist items."""
        if self._default_checklist is None:
            items = self._config.get("default_checklist", [])
            self._default_checklist = [
                ChecklistItem(id=str(item["id"]), description=str(item["description"]))
                for item in items
                if isinstance(item, dict) and "id" in item and "description" in item
            ]
        return self._default_checklist


    @staticmethod
    def resolve_checklist(items: Optional[List[ChecklistItem]]) -> List[ChecklistItem]:
        """Resolve checklist items, using default if none provided."""
        if not items:
            return get_config().default_checklist
        return items


    @property
    def config_path(self) -> str:
        """Get the path to the configuration file."""
        return os.getenv("MRT_REVIEW_CONFIG", str(Path(__file__).parent / "config.yaml"))

    def save_config(self, system_prompt_template: str, checklist: List[ChecklistItem]) -> None:
        """Save system prompt template and checklist to configuration file."""
        config_file = Path(self.config_path)
        
        # Load existing config to preserve other settings
        existing_config = self._config.copy()
        
        # Update system prompt template
        if "llm" not in existing_config:
            existing_config["llm"] = {}
        existing_config["llm"]["system_prompt_template"] = system_prompt_template
        
        # Update checklist
        existing_config["default_checklist"] = [
            {"id": item.id, "description": item.description} for item in checklist
        ]
        
        # Write back to file
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(existing_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # Reload config
        self._config = existing_config
        self._default_checklist = None  # Reset cache

    def save_llm_config(self, provider: str, model: str) -> None:
        """Save LLM provider and model to configuration file."""
        config_file = Path(self.config_path)
        
        # Load existing config to preserve other settings
        existing_config = self._config.copy()
        
        # Update LLM provider and model
        if "llm" not in existing_config:
            existing_config["llm"] = {}
        existing_config["llm"]["provider"] = provider
        
        # Update model based on provider
        if provider == "ollama":
            existing_config["llm"]["ollama_model"] = model
        elif provider == "azure_openai":
            existing_config["llm"]["azure_model"] = model
        else:
            existing_config["llm"]["model"] = model
        
        # Write back to file
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(existing_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # Reload config
        self._config = existing_config

    @property
    def llm_provider(self) -> str:
        """Get LLM provider name."""
        return self._config.get("llm", {}).get("provider", "qwen")

    @property
    def llm_azure_model(self) -> str:
        """Get Azure OpenAI model name."""
        return self._config.get("llm", {}).get("azure_model", "gpt-4")

    @property
    def llm_ollama_model(self) -> str:
        """Get Ollama model name."""
        return self._config.get("llm", {}).get("ollama_model", "qwen2.5:32b")


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

