"""Secure local token persistence in the runtime directory."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from src.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class StoredToken:
    """Stored OAuth token representation."""

    access_token: str
    refresh_token: Optional[str] = None
    expires_at: float = 0.0  # Unix timestamp
    api_domain: Optional[str] = None
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        """Check if access token is expired or about to expire in the next 60 seconds."""
        if not self.access_token:
            return True
        if self.expires_at <= 0:
            return False
        return time.time() >= (self.expires_at - 60)


class TokenStore:
    """Handles reading, writing, and clearing local tokens."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.token_file: Path = self.settings.tokens_dir / "token.json"

    def save_token(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        api_domain: Optional[str] = None,
        token_type: str = "Bearer",
    ) -> StoredToken:
        """Save token data to local disk with restricted file permissions."""
        self.settings.ensure_runtime_dirs()

        # If existing refresh token is present and new one is omitted, preserve old one
        existing = self.load_token()
        final_refresh_token = refresh_token or (existing.refresh_token if existing else None)

        expires_at = (time.time() + expires_in) if expires_in else 0.0

        token_obj = StoredToken(
            access_token=access_token,
            refresh_token=final_refresh_token,
            expires_at=expires_at,
            api_domain=api_domain,
            token_type=token_type,
        )

        temp_file = self.token_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(asdict(token_obj), f, indent=2)
            # Restrict file permissions to current user only (rw-------)
            os.chmod(temp_file, 0o600)
            temp_file.replace(self.token_file)
            logger.debug("Successfully saved OAuth tokens to %s", self.token_file)
        finally:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)

        return token_obj

    def load_token(self) -> Optional[StoredToken]:
        """Load stored token from disk if exists."""
        if not self.token_file.exists():
            return None
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return StoredToken(
                access_token=data.get("access_token", ""),
                refresh_token=data.get("refresh_token"),
                expires_at=float(data.get("expires_at", 0.0)),
                api_domain=data.get("api_domain"),
                token_type=data.get("token_type", "Bearer"),
            )
        except Exception as e:
            logger.warning("Failed to load stored token: %s", str(e))
            return None

    def clear(self) -> None:
        """Delete stored token file."""
        if self.token_file.exists():
            self.token_file.unlink(missing_ok=True)
            logger.debug("Deleted token file %s", self.token_file)
