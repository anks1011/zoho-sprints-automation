"""Zoho OAuth 2.0 Client for authorization, code exchange, and token refresh."""

from __future__ import annotations

import logging
import urllib.parse
from dataclasses import dataclass
from typing import Any, Dict, Optional

import requests

from src.auth.token_store import StoredToken, TokenStore
from src.config import Settings, get_settings
from src.utils.security import mask_secret

logger = logging.getLogger(__name__)


class OAuthError(Exception):
    """Exception raised for OAuth errors."""

    def __init__(self, message: str, error_code: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.details = details or {}


@dataclass
class AuthStatus:
    """Status of current Zoho OAuth authentication."""

    is_authenticated: bool
    has_refresh_token: bool
    is_expired: bool
    expires_at_iso: Optional[str]
    api_domain: Optional[str]
    accounts_url: str
    message: str


class ZohoOAuthClient:
    """Manages Zoho OAuth 2.0 lifecycle."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        token_store: Optional[TokenStore] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.token_store = token_store or TokenStore(self.settings)
        self.session = session or requests.Session()

    @property
    def auth_url(self) -> str:
        return f"{self.settings.zoho_accounts_url}/oauth/v2/auth"

    @property
    def token_url(self) -> str:
        return f"{self.settings.zoho_accounts_url}/oauth/v2/token"

    def get_authorization_url(self, scope: Optional[str] = None, state: Optional[str] = None) -> str:
        """Generate the browser URL for the user to grant authorization."""
        if not self.settings.zoho_client_id:
            raise OAuthError("ZOHO_CLIENT_ID is not configured in environment or .env file.")

        params = {
            "scope": scope or self.settings.zoho_scopes,
            "client_id": self.settings.zoho_client_id,
            "response_type": "code",
            "access_type": "offline",
            "redirect_uri": self.settings.zoho_redirect_uri,
            "prompt": "consent",
        }
        if state:
            params["state"] = state

        return f"{self.auth_url}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str) -> StoredToken:
        """Exchange an authorization code for access and refresh tokens."""
        if not self.settings.zoho_client_id or not self.settings.zoho_client_secret:
            raise OAuthError("ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET must be configured.")

        data = {
            "code": code.strip(),
            "client_id": self.settings.zoho_client_id,
            "client_secret": self.settings.zoho_client_secret,
            "grant_type": "authorization_code",
        }
        if self.settings.zoho_redirect_uri:
            data["redirect_uri"] = self.settings.zoho_redirect_uri

        logger.debug("Exchanging authorization code with %s", self.token_url)
        try:
            response = self.session.post(self.token_url, data=data, timeout=30)
            payload = response.json()
        except requests.RequestException as e:
            raise OAuthError(f"Network error during authorization code exchange: {str(e)}") from e
        except Exception as e:
            raise OAuthError(f"Unexpected error parsing OAuth response: {str(e)}") from e

        if "error" in payload:
            error_code = payload.get("error", "oauth_error")
            error_desc = payload.get("error_description")
            error_msg = f"[{error_code}] {error_desc}" if error_desc else str(error_code)
            raise OAuthError(
                f"OAuth code exchange failed: {error_msg}",
                error_code=error_code,
                details=payload,
            )

        access_token = payload.get("access_token")
        if not access_token:
            raise OAuthError("OAuth response did not contain an access_token", details=payload)

        refresh_token = payload.get("refresh_token")
        expires_in = payload.get("expires_in", 3600)
        api_domain = payload.get("api_domain")

        stored = self.token_store.save_token(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=expires_in,
            api_domain=api_domain,
            token_type=payload.get("token_type", "Bearer"),
        )
        logger.info("Successfully exchanged authorization code and stored OAuth tokens.")
        return stored

    def refresh_access_token(self, refresh_token: Optional[str] = None) -> StoredToken:
        """Use a refresh token to obtain a new access token."""
        stored = self.token_store.load_token()
        token_to_use = refresh_token or (stored.refresh_token if stored else None) or self.settings.zoho_refresh_token

        if not token_to_use:
            raise OAuthError(
                "No refresh token available. Run 'auth' command or configure ZOHO_REFRESH_TOKEN."
            )

        if not self.settings.zoho_client_id or not self.settings.zoho_client_secret:
            raise OAuthError("ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET must be configured.")

        data = {
            "refresh_token": token_to_use,
            "client_id": self.settings.zoho_client_id,
            "client_secret": self.settings.zoho_client_secret,
            "grant_type": "refresh_token",
        }

        logger.debug("Refreshing access token via %s", self.token_url)
        try:
            response = self.session.post(self.token_url, data=data, timeout=30)
            payload = response.json()
        except requests.RequestException as e:
            raise OAuthError(f"Network error during token refresh: {str(e)}") from e
        except Exception as e:
            raise OAuthError(f"Unexpected error parsing refresh token response: {str(e)}") from e

        if "error" in payload:
            error_code = payload.get("error", "oauth_error")
            error_desc = payload.get("error_description")
            error_msg = f"[{error_code}] {error_desc}" if error_desc else str(error_code)
            raise OAuthError(
                f"OAuth token refresh failed: {error_msg}",
                error_code=error_code,
                details=payload,
            )

        new_access_token = payload.get("access_token")
        if not new_access_token:
            raise OAuthError("Refresh response did not contain an access_token", details=payload)

        expires_in = payload.get("expires_in", 3600)
        api_domain = payload.get("api_domain")

        stored = self.token_store.save_token(
            access_token=new_access_token,
            refresh_token=token_to_use,
            expires_in=expires_in,
            api_domain=api_domain,
            token_type=payload.get("token_type", "Bearer"),
        )
        logger.info("Successfully refreshed access token.")
        return stored

    def get_valid_access_token(self) -> str:
        """Get a currently valid access token, auto-refreshing if expired."""
        stored = self.token_store.load_token()

        # If token store has an active token
        if stored and stored.access_token and not stored.is_expired:
            return stored.access_token

        # If expired or not in store, attempt refresh
        refresh_token = (stored.refresh_token if stored else None) or self.settings.zoho_refresh_token
        if refresh_token:
            try:
                new_token = self.refresh_access_token(refresh_token)
                return new_token.access_token
            except Exception as e:
                logger.warning("Automatic token refresh failed: %s", str(e))

        # Fall back to settings access token if set
        if self.settings.zoho_access_token:
            return self.settings.zoho_access_token

        raise OAuthError(
            "Authentication required: No valid access token or refresh token found. "
            "Please run 'python -m src.main auth' to authenticate."
        )

    def get_status(self) -> AuthStatus:
        """Inspect the current authentication state."""
        import datetime

        stored = self.token_store.load_token()
        has_token = bool(stored and stored.access_token) or bool(self.settings.zoho_access_token)
        has_refresh = bool(stored and stored.refresh_token) or bool(self.settings.zoho_refresh_token)

        is_expired = True
        expires_at_iso = None
        api_domain = None

        if stored and stored.access_token:
            is_expired = stored.is_expired
            api_domain = stored.api_domain
            if stored.expires_at > 0:
                expires_at_iso = datetime.datetime.fromtimestamp(
                    stored.expires_at, tz=datetime.timezone.utc
                ).isoformat()

        if has_token and not is_expired:
            message = "Authentication active and token is valid."
            is_auth = True
        elif has_refresh:
            message = "Access token expired or not loaded, but refresh token is available."
            is_auth = True
        else:
            message = "Not authenticated. Run 'python -m src.main auth' to authenticate."
            is_auth = False

        return AuthStatus(
            is_authenticated=is_auth,
            has_refresh_token=has_refresh,
            is_expired=is_expired,
            expires_at_iso=expires_at_iso,
            api_domain=api_domain,
            accounts_url=self.settings.zoho_accounts_url,
            message=message,
        )
