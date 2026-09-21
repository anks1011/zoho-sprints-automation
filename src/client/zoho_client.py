"""Base HTTP client for Zoho Sprints REST API."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests

from src.auth.oauth_client import ZohoOAuthClient
from src.config import Settings, get_settings
from src.utils.security import mask_secret, sanitize_payload

logger = logging.getLogger(__name__)


class SprintsAPIError(Exception):
    """Base exception for Zoho Sprints API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class SprintsAuthError(SprintsAPIError):
    """Authentication or authorization failure."""
    pass


class SprintsNotFoundError(SprintsAPIError):
    """Resource not found (404)."""
    pass


class SprintsRateLimitError(SprintsAPIError):
    """Rate limit exceeded (429)."""
    pass


class SprintsValidationError(SprintsAPIError):
    """Payload or parameter validation error (400)."""
    pass


class ZohoHTTPClient:
    """HTTP client with authentication headers, retries, and rate-limiting."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        oauth_client: Optional[ZohoOAuthClient] = None,
        session: Optional[requests.Session] = None,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
    ) -> None:
        self.settings = settings or get_settings()
        self.oauth_client = oauth_client or ZohoOAuthClient(self.settings)
        self.session = session or requests.Session()
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Perform an authenticated HTTP request with automatic token refresh and retries."""
        url = (
            endpoint
            if endpoint.startswith("http://") or endpoint.startswith("https://")
            else f"{self.settings.zoho_api_base_url}/{endpoint.lstrip('/')}"
        )

        req_headers = headers.copy() if headers else {}
        token = self.oauth_client.get_valid_access_token()
        req_headers["Authorization"] = f"Zoho-oauthtoken {token}"
        req_headers["Accept"] = "application/json"
        req_headers["x-convert-response"] = "true"

        # Log sanitized outgoing request
        sanitized_params = sanitize_payload(params) if params else None
        sanitized_data = sanitize_payload(data) if data else None
        sanitized_json = sanitize_payload(json) if json else None
        logger.debug(
            "Zoho Sprints API Request: %s %s | params=%s | data=%s | json=%s",
            method.upper(),
            url,
            sanitized_params,
            sanitized_data,
            sanitized_json,
        )

        attempt = 0
        refreshed_auth = False

        while True:
            attempt += 1
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    data=data,
                    json=json,
                    headers=req_headers,
                    timeout=timeout,
                )
            except requests.RequestException as exc:
                if attempt >= self.max_retries:
                    raise SprintsAPIError(f"Network error communicating with Zoho Sprints: {str(exc)}") from exc
                sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                logger.warning("Network failure (%s), retrying in %.2fs...", str(exc), sleep_time)
                time.sleep(sleep_time)
                continue

            # Check for 401 Unauthorized (token expired or invalidated)
            if response.status_code == 401 and not refreshed_auth:
                logger.info("Access token expired (HTTP 401), refreshing token and retrying...")
                try:
                    new_token_obj = self.oauth_client.refresh_access_token()
                    req_headers["Authorization"] = f"Zoho-oauthtoken {new_token_obj.access_token}"
                    refreshed_auth = True
                    continue
                except Exception as refresh_err:
                    raise SprintsAuthError(
                        f"Failed to refresh Zoho access token upon HTTP 401: {str(refresh_err)}"
                    ) from refresh_err

            # Check for 429 Rate Limit
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                wait_sec = float(retry_after) if retry_after and retry_after.isdigit() else (self.backoff_factor * (2 ** attempt))
                if attempt >= self.max_retries:
                    raise SprintsRateLimitError(
                        f"Zoho Sprints API rate limit exceeded (HTTP 429). Retry after {wait_sec}s.",
                        status_code=429,
                    )
                logger.warning("Zoho Sprints rate limited (HTTP 429). Backing off for %.2fs...", wait_sec)
                time.sleep(wait_sec)
                continue

            # Check for 5xx Server Errors
            if response.status_code >= 500:
                if attempt >= self.max_retries:
                    raise SprintsAPIError(
                        f"Zoho Sprints server error (HTTP {response.status_code}): {response.text}",
                        status_code=response.status_code,
                    )
                sleep_time = self.backoff_factor * (2 ** (attempt - 1))
                logger.warning(
                    "Server error (HTTP %d). Retrying in %.2fs...", response.status_code, sleep_time
                )
                time.sleep(sleep_time)
                continue

            # Handle 404 Not Found
            if response.status_code == 404:
                raise SprintsNotFoundError(
                    f"Resource not found at {url}: {response.text}",
                    status_code=404,
                )

            # Handle other 4xx errors
            if 400 <= response.status_code < 500:
                payload = self._safe_parse_json(response)
                raise SprintsValidationError(
                    f"Zoho Sprints API client error (HTTP {response.status_code}): {response.text}",
                    status_code=response.status_code,
                    details=payload,
                )

            # 2xx Success: Parse JSON response
            payload = self._safe_parse_json(response)
            self._validate_zoho_error_payload(payload, response.status_code)
            return payload

    def _safe_parse_json(self, response: requests.Response) -> Dict[str, Any]:
        """Safely parse JSON response body or wrap text in dict."""
        try:
            return response.json()
        except Exception:
            return {"raw_text": response.text}

    def _validate_zoho_error_payload(self, payload: Dict[str, Any], status_code: int) -> None:
        """Zoho sometimes returns HTTP 200 with error codes in body."""
        if not isinstance(payload, dict):
            return

        # Pattern 1: {"status": "error" | "failed", "message": "..."}
        status_val = str(payload.get("status", "")).lower()
        if status_val in ("error", "failed"):
            msg = payload.get("message") or payload.get("error_msg") or "Zoho Sprints API reported failure"
            data_info = payload.get("data")
            if isinstance(data_info, dict) and "displayName" in data_info:
                msg = f"{msg}: {data_info.get('displayName')}"
            raise SprintsAPIError(
                f"Zoho Sprints API Error: {msg}",
                status_code=status_code,
                error_code=str(payload.get("code") or payload.get("error_code")),
                details=payload,
            )

        # Pattern 2: {"error": {"message": "..."}}
        if "error" in payload and isinstance(payload["error"], dict):
            err_dict = payload["error"]
            msg = err_dict.get("message") or str(err_dict)
            raise SprintsAPIError(
                f"Zoho Sprints API Error: {msg}",
                status_code=status_code,
                error_code=str(err_dict.get("code")),
                details=payload,
            )
