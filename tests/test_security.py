"""Tests for security utilities and secret masking."""

from src.utils.security import mask_secret, mask_text, sanitize_payload


def test_mask_secret() -> None:
    assert mask_secret("") == ""
    assert mask_secret(None) == ""
    assert mask_secret("short") == "[REDACTED]"
    assert mask_secret("1000.abcd1234efgh5678ijkl") == "*********************ijkl"


def test_mask_text_zoho_token() -> None:
    text = "Sending request with header Zoho-oauthtoken 1000.abcdef123456 to endpoint"
    masked = mask_text(text)
    assert "1000.abcdef123456" not in masked
    assert "Zoho-oauthtoken [MASKED_TOKEN]" in masked


def test_mask_text_bearer_and_openai_key() -> None:
    text = "Bearer secret_jwt_token_here and key sk-12345678901234567890abcdef"
    masked = mask_text(text)
    assert "secret_jwt_token_here" not in masked
    assert "sk-12345678901234567890abcdef" not in masked
    assert "[MASKED_API_KEY]" in masked


def test_mask_text_url_params() -> None:
    text = "https://accounts.zoho.in/token?client_secret=supersecret123&code=mycode123"
    masked = mask_text(text)
    assert "supersecret123" not in masked
    assert "mycode123" not in masked


def test_sanitize_payload_recursive() -> None:
    payload = {
        "client_id": "1000.XYZ",
        "client_secret": "my_super_secret_key_1234",
        "tokens": {
            "access_token": "1000.access_token_value_here",
            "refresh_token": "1000.refresh_token_value_here",
        },
        "nested_list": [
            {"password": "secretpassword", "safe_name": "Task 1"}
        ],
        "normal_text": "Story description without keys",
    }
    sanitized = sanitize_payload(payload)

    assert sanitized["client_secret"] != "my_super_secret_key_1234"
    assert sanitized["tokens"]["access_token"] != "1000.access_token_value_here"
    assert sanitized["tokens"]["refresh_token"] != "1000.refresh_token_value_here"
    assert sanitized["nested_list"][0]["password"] != "secretpassword"
    assert sanitized["nested_list"][0]["safe_name"] == "Task 1"
    assert sanitized["normal_text"] == "Story description without keys"
