"""Authentication status endpoint."""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends

from src.api.schemas import AuthStatusResponse
from src.auth.oauth_client import ZohoOAuthClient
from src.config import Settings, get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_oauth_client(settings: Settings = Depends(get_settings)) -> ZohoOAuthClient:
    return ZohoOAuthClient(settings)


@router.get("/status", response_model=AuthStatusResponse)
def get_auth_status(oauth: ZohoOAuthClient = Depends(get_oauth_client)) -> AuthStatusResponse:
    """Return sanitized OAuth authentication status (no secrets)."""
    status = oauth.get_status()
    return AuthStatusResponse(
        is_authenticated=status.is_authenticated,
        has_refresh_token=status.has_refresh_token,
        is_expired=status.is_expired,
        expires_at_iso=status.expires_at_iso,
        accounts_url=status.accounts_url,
        message=status.message,
    )
