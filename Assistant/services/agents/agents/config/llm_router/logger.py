"""
Logging utilities for LLM Router module.

Provides hierarchical logging with security-conscious token sanitization.
"""

import logging
import sys
from typing import Optional


# Root logger for the module
ROOT_LOGGER_NAME = 'agents.llm_router'


def setup_logging(level: str = 'INFO', log_format: Optional[str] = None) -> None:
    """
    Setup logging for LLM Router.

    This configures the llm_router logger level and only adds a handler
    when no app-level handlers are present.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom format string. If None, uses default format.
    """
    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    # Configure root logger for llm_router
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper()))

    # Only add a handler if app-level logging hasn't configured one already
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(getattr(logging, level.upper()))
        handler.setFormatter(logging.Formatter(log_format))
        logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module component.

    Args:
        name: Component name (e.g., 'core.location', 'auth.azure')

    Returns:
        Configured logger instance
    """
    full_name = f"{ROOT_LOGGER_NAME}.{name}" if name else ROOT_LOGGER_NAME
    logger = logging.getLogger(full_name)

    # Add NullHandler to prevent "No handler found" warnings
    # Users can configure their own handlers
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    return logger


def sanitize_token(token: Optional[str], show_chars: int = 4) -> str:
    """
    Sanitize a token for logging by showing only first and last few characters.

    Args:
        token: Token string to sanitize
        show_chars: Number of characters to show from start and end

    Returns:
        Sanitized token string (e.g., "abcd...xyz9")
    """
    if not token:
        return "<empty>"

    if len(token) <= show_chars * 2:
        # Token too short, just mask it
        return "***"

    return f"{token[:show_chars]}...{token[-show_chars:]}"


def sanitize_dict(data: dict, sensitive_keys: Optional[list] = None) -> dict:
    """
    Sanitize a dictionary for logging by masking sensitive values.

    Args:
        data: Dictionary to sanitize
        sensitive_keys: List of keys to sanitize (defaults to common sensitive keys)

    Returns:
        New dictionary with sensitive values sanitized
    """
    if sensitive_keys is None:
        sensitive_keys = [
            'token', 'access_token', 'refresh_token', 'id_token',
            'password', 'secret', 'api_key', 'apikey', 'key',
            'credentials', 'authorization'
        ]

    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()

        # Check if key contains any sensitive keyword
        is_sensitive = any(sensitive in key_lower for sensitive in sensitive_keys)

        if is_sensitive and isinstance(value, str):
            sanitized[key] = sanitize_token(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_dict(value, sensitive_keys)
        else:
            sanitized[key] = value

    return sanitized


# Create root logger on module import
_root_logger = logging.getLogger(ROOT_LOGGER_NAME)
_root_logger.addHandler(logging.NullHandler())
