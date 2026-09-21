"""Logging configuration with secret masking filter."""

from __future__ import annotations

import logging
import sys
from typing import Any

from src.utils.security import mask_text


class SecretMaskingFilter(logging.Filter):
    """Filter that masks sensitive tokens, secrets, and credentials in log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_text(record.msg)
        if record.args:
            if isinstance(record.args, tuple):
                record.args = tuple(
                    mask_text(arg) if isinstance(arg, str) else arg for arg in record.args
                )
            elif isinstance(record.args, dict):
                record.args = {
                    k: (mask_text(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
        return True


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configure structured console logging with secret masking."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if called multiple times
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(numeric_level)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(SecretMaskingFilter())

    root_logger.addHandler(handler)
    return logging.getLogger("zoho_sprints")
