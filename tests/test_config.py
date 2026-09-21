"""Tests for configuration settings and path management."""

from pathlib import Path
from src.config import Settings


def test_settings_defaults(tmp_path: Path) -> None:
    settings = Settings(
        runtime_dir=tmp_path / ".runtime",
        zoho_accounts_url="https://accounts.zoho.in/",
        zoho_api_base_url="https://sprintsapi.zoho.in/zsapi/",
    )

    # Check trailing slashes are cleanly stripped
    assert settings.zoho_accounts_url == "https://accounts.zoho.in"
    assert settings.zoho_api_base_url == "https://sprintsapi.zoho.in/zsapi"

    # Check subdirectories
    assert settings.tokens_dir == tmp_path / ".runtime" / "tokens"
    assert settings.plans_dir == tmp_path / ".runtime" / "plans"
    assert settings.executions_dir == tmp_path / ".runtime" / "executions"

    # Test ensure_runtime_dirs creates directories
    settings.ensure_runtime_dirs()
    assert settings.tokens_dir.exists()
    assert settings.plans_dir.exists()
    assert settings.executions_dir.exists()
    assert settings.cache_dir.exists()


def test_settings_custom_env(tmp_path: Path) -> None:
    settings = Settings(
        zoho_client_id="test_client_id",
        zoho_client_secret="test_client_secret",
        zoho_team_id="12345",
        zoho_project_id="67890",
        runtime_dir=tmp_path,
    )
    assert settings.zoho_client_id == "test_client_id"
    assert settings.zoho_client_secret == "test_client_secret"
    assert settings.zoho_team_id == "12345"
    assert settings.zoho_project_id == "67890"
