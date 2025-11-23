"""Application settings with Pydantic validation."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class LLMSettings(BaseModel):
    """LLM configuration settings."""
    provider: str = Field(default="qwen", description="LLM provider name")
    model: str = Field(default="qwen-max", description="Default model name")
    timeout: float = Field(default=30.0, description="Request timeout in seconds")
    system_prompt_template: str = Field(
        default="",
        description="System prompt template"
    )
    azure_model: Optional[str] = Field(default=None, description="Azure OpenAI model")
    ollama_model: Optional[str] = Field(default=None, description="Ollama model")
    
    @field_validator("system_prompt_template")
    @classmethod
    def validate_system_prompt(cls, v: str) -> str:
        """Ensure system prompt is not empty."""
        if not v or not v.strip():
            raise ValueError("system_prompt_template is required")
        return v


class ChecklistItem(BaseModel):
    """Checklist item model."""
    id: str
    description: str


class Settings(BaseModel):
    """Application settings."""
    llm: LLMSettings = Field(default_factory=LLMSettings)
    default_checklist: List[ChecklistItem] = Field(default_factory=list)
    config_path: str = Field(
        default_factory=lambda: str(Path(__file__).parent.parent.parent / "config.yaml")
    )
    
    @classmethod
    def from_yaml(cls, config_path: Optional[str] = None) -> Settings:
        """
        Load settings from YAML file.
        
        Args:
            config_path: Path to config file. If None, uses default.
            
        Returns:
            Settings instance
        """
        if config_path is None:
            config_path = os.getenv(
                "TRAVEL_AGENT_CONFIG",
                str(Path(__file__).parent.parent.parent / "config.yaml")
            )
        
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, "r", encoding="utf-8") as f:
            config_data = yaml.safe_load(f) or {}
        
        # Build settings from config data
        llm_data = config_data.get("llm", {})
        llm_settings = LLMSettings(
            provider=llm_data.get("provider", "qwen"),
            model=llm_data.get("model", "qwen-max"),
            timeout=float(llm_data.get("timeout", 30.0)),
            system_prompt_template=llm_data.get("system_prompt_template", ""),
            azure_model=llm_data.get("azure_model"),
            ollama_model=llm_data.get("ollama_model")
        )
        
        checklist_data = config_data.get("default_checklist", [])
        checklist = [
            ChecklistItem(id=item["id"], description=item["description"])
            for item in checklist_data
        ]
        
        return cls(
            llm=llm_settings,
            default_checklist=checklist,
            config_path=str(config_path)
        )
    
    def save_to_yaml(self, config_path: Optional[str] = None) -> None:
        """
        Save settings to YAML file.
        
        Args:
            config_path: Path to config file. If None, uses current config_path.
        """
        if config_path is None:
            config_path = self.config_path
        
        config_file = Path(config_path)
        
        # Load existing config to preserve other settings
        existing_config: Dict[str, Any] = {}
        if config_file.exists():
            with open(config_file, "r", encoding="utf-8") as f:
                existing_config = yaml.safe_load(f) or {}
        
        # Update LLM settings
        if "llm" not in existing_config:
            existing_config["llm"] = {}
        existing_config["llm"]["provider"] = self.llm.provider
        existing_config["llm"]["model"] = self.llm.model
        existing_config["llm"]["timeout"] = self.llm.timeout
        existing_config["llm"]["system_prompt_template"] = self.llm.system_prompt_template
        if self.llm.azure_model:
            existing_config["llm"]["azure_model"] = self.llm.azure_model
        if self.llm.ollama_model:
            existing_config["llm"]["ollama_model"] = self.llm.ollama_model
        
        # Update checklist
        existing_config["default_checklist"] = [
            {"id": item.id, "description": item.description}
            for item in self.default_checklist
        ]
        
        # Write to file
        with open(config_file, "w", encoding="utf-8") as f:
            yaml.dump(existing_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        
        # Update config_path
        self.config_path = str(config_path)
    
    def save_llm_config(self, provider: str, model: str) -> None:
        """Save LLM provider and model configuration."""
        self.llm.provider = provider
        if provider == "ollama":
            self.llm.ollama_model = model
        elif provider == "azure_openai":
            self.llm.azure_model = model
        else:
            self.llm.model = model
        self.save_to_yaml()
    
    def save_system_prompt_template(self, template: str) -> None:
        """Save system prompt template."""
        self.llm.system_prompt_template = template
        self.save_to_yaml()


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings.from_yaml()
    return _settings


def reload_settings(config_path: Optional[str] = None) -> Settings:
    """Reload settings from file."""
    global _settings
    _settings = Settings.from_yaml(config_path)
    return _settings

