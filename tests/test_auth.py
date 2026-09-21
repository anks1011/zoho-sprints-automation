"""Tests for Zoho OAuth 2.0 flow and token store."""

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.auth.oauth_client import OAuthError, ZohoOAuthClient
from src.auth.token_store import StoredToken, TokenStore
from src.config import Settings


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    return Settings(
        zoho_client_id="dummy_client_id",
        zoho_client_secret="dummy_client_secret",
        zoho_redirect_uri="http://localhost:8080/callback",
        zoho_accounts_url="https://accounts.zoho.in",
        runtime_dir=tmp_path / ".runtime",
    )


def test_token_store_save_and_load(mock_settings: Settings) -> None:
    store = TokenStore(mock_settings)
    assert store.load_token() is None

    stored = store.save_token(
        access_token="test_access_token_123",
        refresh_token="test_refresh_token_456",
        expires_in=3600,
        api_domain="https://sprintsapi.zoho.in",
    )
    assert stored.access_token == "test_access_token_123"
    assert stored.refresh_token == "test_refresh_token_456"
    assert not stored.is_expired

    loaded = store.load_token()
    assert loaded is not None
    assert loaded.access_token == "test_access_token_123"
    assert loaded.refresh_token == "test_refresh_token_456"
    assert loaded.api_domain == "https://sprintsapi.zoho.in"


def test_stored_token_expiry() -> None:
    # Expired token (expires_at in past)
    expired_token = StoredToken(
        access_token="expired_tok",
        expires_at=time.time() - 100,
    )
    assert expired_token.is_expired is True

    # Token expiring within 30 seconds (within 60s buffer)
    near_expiry_token = StoredToken(
        access_token="near_tok",
        expires_at=time.time() + 30,
    )
    assert near_expiry_token.is_expired is True

    # Valid token
    valid_token = StoredToken(
        access_token="valid_tok",
        expires_at=time.time() + 1000,
    )
    assert valid_token.is_expired is False


def test_get_authorization_url(mock_settings: Settings) -> None:
    client = ZohoOAuthClient(mock_settings)
    url = client.get_authorization_url()
    assert "https://accounts.zoho.in/oauth/v2/auth" in url
    assert "client_id=dummy_client_id" in url
    assert "response_type=code" in url
    assert "access_type=offline" in url


def test_exchange_code_success(mock_settings: Settings) -> None:
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "new_access_123",
        "refresh_token": "new_refresh_456",
        "expires_in": 3600,
        "api_domain": "https://sprintsapi.zoho.in",
        "token_type": "Bearer",
    }
    mock_session.post.return_value = mock_response

    client = ZohoOAuthClient(mock_settings, session=mock_session)
    stored = client.exchange_code("sample_auth_code")

    assert stored.access_token == "new_access_123"
    assert stored.refresh_token == "new_refresh_456"

    # Verify POST parameters
    mock_session.post.assert_called_once()
    _, kwargs = mock_session.post.call_args
    assert kwargs["data"]["code"] == "sample_auth_code"
    assert kwargs["data"]["grant_type"] == "authorization_code"


def test_exchange_code_error(mock_settings: Settings) -> None:
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "error": "invalid_code",
        "error_description": "The grant code has expired or is invalid.",
    }
    mock_session.post.return_value = mock_response

    client = ZohoOAuthClient(mock_settings, session=mock_session)
    with pytest.raises(OAuthError) as exc_info:
        client.exchange_code("expired_code")
    assert "invalid_code" in str(exc_info.value)


def test_refresh_access_token_success(mock_settings: Settings) -> None:
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "refreshed_access_token_789",
        "expires_in": 3600,
    }
    mock_session.post.return_value = mock_response

    client = ZohoOAuthClient(mock_settings, session=mock_session)
    # Pre-save refresh token
    client.token_store.save_token(
        access_token="old_access",
        refresh_token="existing_refresh_token",
        expires_in=0,
    )

    stored = client.refresh_access_token()
    assert stored.access_token == "refreshed_access_token_789"
    assert stored.refresh_token == "existing_refresh_token"


def test_get_valid_access_token_auto_refresh(mock_settings: Settings) -> None:
    mock_session = MagicMock()
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "access_token": "auto_refreshed_token",
        "expires_in": 3600,
    }
    mock_session.post.return_value = mock_response

    client = ZohoOAuthClient(mock_settings, session=mock_session)
    # Token that expired 5 minutes ago
    client.token_store.save_token(
        access_token="expired_token",
        refresh_token="my_refresh_token",
        expires_in=-300,
    )

    token = client.get_valid_access_token()
    assert token == "auto_refreshed_token"
