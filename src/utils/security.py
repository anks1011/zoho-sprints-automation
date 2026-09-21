"""Security utilities for credential masking and payload sanitization."""

from __future__ import annotations

import re
from typing import Any, Mapping

# Patterns identifying sensitive keys
SENSITIVE_KEY_PATTERNS = [
    r"token",
    r"secret",
    r"password",
    r"authorization",
    r"api[_-]?key",
    r"auth[_-]?code",
    r"code",
]

SENSITIVE_KEY_REGEX = re.compile("|".join(SENSITIVE_KEY_PATTERNS), re.IGNORECASE)

# Patterns identifying sensitive values in text strings
SECRET_PATTERNS = [
    (re.compile(r"(Zoho-oauthtoken\s+)([A-Za-z0-9._~+/-]+)", re.IGNORECASE), r"\1[MASKED_TOKEN]"),
    (re.compile(r"(Bearer\s+)([A-Za-z0-9._~+/-]+)", re.IGNORECASE), r"\1[MASKED_TOKEN]"),
    (re.compile(r"(sk-[A-Za-z0-9_-]{20,})", re.IGNORECASE), r"[MASKED_API_KEY]"),
    (re.compile(r"(client_secret=)([^&\s]+)", re.IGNORECASE), r"\1[MASKED_SECRET]"),
    (re.compile(r"(refresh_token=)([^&\s]+)", re.IGNORECASE), r"\1[MASKED_TOKEN]"),
    (re.compile(r"(code=)([^&\s]+)", re.IGNORECASE), r"\1[MASKED_CODE]"),
]


def mask_secret(value: str | None, visible_chars: int = 4) -> str:
    """Mask a secret string preserving only trailing visible characters if long enough."""
    if not value:
        return ""
    if len(value) <= visible_chars * 2:
        return "[REDACTED]"
    return f"{'*' * (len(value) - visible_chars)}{value[-visible_chars:]}"


def mask_text(text: str) -> str:
    """Mask known sensitive patterns within arbitrary log or error text."""
    if not text:
        return text
    result = text
    for pattern, replacement in SECRET_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def sanitize_payload(data: Any) -> Any:
    """Recursively sanitize dictionaries/lists by masking sensitive key-values."""
    if isinstance(data, Mapping):
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, (Mapping, list, tuple, set)):
                sanitized[key] = sanitize_payload(value)
            elif isinstance(key, str) and SENSITIVE_KEY_REGEX.search(key):
                if isinstance(value, str):
                    sanitized[key] = mask_secret(value)
                else:
                    sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = sanitize_payload(value)
        return sanitized
    elif isinstance(data, (list, tuple, set)):
        return [sanitize_payload(item) for item in data]
    elif isinstance(data, str):
        return mask_text(data)
    return data
