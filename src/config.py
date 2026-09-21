"""Configuration management using Pydantic Settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Zoho OAuth Credentials
    zoho_client_id: str = Field(default="", description="Zoho OAuth Client ID")
    zoho_client_secret: str = Field(default="", description="Zoho OAuth Client Secret")
    zoho_redirect_uri: str = Field(
        default="http://localhost:8080/callback",
        description="Zoho OAuth registered redirect URI",
    )
    zoho_accounts_url: str = Field(
        default="https://accounts.zoho.in",
        description="Zoho Accounts OAuth domain (e.g. https://accounts.zoho.in or https://accounts.zoho.com)",
    )
    zoho_api_base_url: str = Field(
        default="https://sprintsapi.zoho.in/zsapi",
        description="Zoho Sprints REST API Base URL",
    )
    zoho_scopes: str = Field(
        default="ZohoSprints.fullaccess.ALL",
        description="Zoho OAuth Scopes required for Sprints",
    )

    # Pre-generated or stored tokens
    zoho_access_token: str = Field(default="", description="Initial access token (optional)")
    zoho_refresh_token: str = Field(default="", description="Refresh token for automatic renewals")

    # Optional Zoho Context Defaults
    zoho_team_id: Optional[str] = Field(default="", description="Default Zoho Sprints Team ID")
    zoho_project_id: Optional[str] = Field(default="", description="Default Zoho Sprints Project ID")
    zoho_sprint_id: Optional[str] = Field(default="", description="Default Zoho Sprints Sprint ID")
    zoho_default_item_type_id: Optional[str] = Field(
        default="", description="Default Item Type ID for tasks"
    )
    zoho_default_priority_id: Optional[str] = Field(
        default="", description="Default Priority ID for tasks"
    )

    # OpenAI-compatible LLM Configuration
    openai_api_key: str = Field(default="", description="API key for OpenAI-compatible model")
    openai_model: str = Field(default="gpt-4o-mini", description="Model name for story analysis")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible API",
    )

    # Runtime and Logging
    log_level: str = Field(default="INFO", description="Logging level")
    runtime_dir: Path = Field(
        default=Path(".runtime"), description="Local runtime directory for plans and tokens"
    )

    @field_validator("zoho_accounts_url", "zoho_api_base_url", "openai_base_url")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/") if v else v

    @property
    def tokens_dir(self) -> Path:
        return self.runtime_dir / "tokens"

    @property
    def plans_dir(self) -> Path:
        return self.runtime_dir / "plans"

    @property
    def executions_dir(self) -> Path:
        return self.runtime_dir / "executions"

    @property
    def cache_dir(self) -> Path:
        return self.runtime_dir / "cache"

    def ensure_runtime_dirs(self) -> None:
        """Create necessary runtime directories."""
        self.tokens_dir.mkdir(parents=True, exist_ok=True)
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.executions_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


# Global settings singleton
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Retrieve or initialize the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
        _settings.ensure_runtime_dirs()
    return _settings


def reset_settings(new_settings: Optional[Settings] = None) -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = new_settings
