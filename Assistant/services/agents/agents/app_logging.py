"""
Application logging utilities integrating Python's logging with Logfire.

Provides logging setup that routes Python standard library logs through
Logfire's built-in LogfireLoggingHandler for OpenTelemetry integration.
"""

import logging
import sys
from typing import Optional

import logfire
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme


# Custom theme for log levels
_LOG_THEME = Theme({
    "logging.level.debug": "dim cyan",
    "logging.level.info": "green",
    "logging.level.warning": "yellow",
    "logging.level.error": "bold red",
    "logging.level.critical": "bold white on red",
    "log.time": "dim",
    "log.message": "default",
    "log.path": "dim",
})

# Shared console instance with custom theme
_console = Console(theme=_LOG_THEME, stderr=True)


# Root logger name for the agents module
ROOT_LOGGER_NAME = 'agents'
# LLM Router logger name (app-level handlers should cover this too)
LLM_ROUTER_LOGGER_NAME = 'agents.llm_router'

# Module-level cache for logger instances
_loggers: dict[str, logging.Logger] = {}

# Track if logging has been set up
_logging_configured = False


def setup_logging(
    level: str = 'INFO',
    log_format: Optional[str] = None,
    include_console: bool = True,
    rich_tracebacks: bool = True,
    show_path: bool = True,
    show_time: bool = True,
    dev_mode: bool = False,
    include_logfire: bool = False,
) -> None:
    """
    Setup logging for the agents module with Logfire integration and console output.

    This configures the root 'agents' logger with Logfire's built-in logging handler
    and optionally a console handler (Rich in dev mode, standard in prod).

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Custom format string for Logfire handler. If None, uses default format.
        include_console: Whether to also log to console (default: True)
        rich_tracebacks: Whether to use rich for exception tracebacks (default: True)
        show_path: Whether to show file path in console logs (default: True)
        show_time: Whether to show timestamp in console logs (default: True)
        dev_mode: Whether to use rich console output (default: False)
        include_logfire: Whether to attach Logfire logging handler (default: False)
    """
    global _logging_configured

    if log_format is None:
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    level_value = getattr(logging, level.upper())

    def build_handlers() -> list[logging.Handler]:
        handlers: list[logging.Handler] = []
        if include_logfire:
            # Add Logfire's built-in logging handler
            # Use NullHandler as fallback to avoid duplicate console output
            logfire_handler = logfire.LogfireLoggingHandler(
                fallback=logging.NullHandler(),
            )
            logfire_handler.setLevel(level_value)
            logfire_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(logfire_handler)

        # Optionally add console handler
        if include_console:
            if dev_mode:
                console_handler: logging.Handler = RichHandler(
                    console=_console,
                    level=level_value,
                    show_time=show_time,
                    show_path=show_path,
                    rich_tracebacks=rich_tracebacks,
                    tracebacks_show_locals=True,
                    markup=True,
                )
            else:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(logging.Formatter(log_format))
            console_handler.setLevel(level_value)
            handlers.append(console_handler)

        return handlers

    def configure_logger(logger_name: str) -> None:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level_value)
        logger.handlers.clear()
        for handler in build_handlers():
            logger.addHandler(handler)
        # Prevent propagation to root logger
        logger.propagate = False

    # Configure app logger and route llm_router logs through the same style
    configure_logger(ROOT_LOGGER_NAME)
    configure_logger(LLM_ROUTER_LOGGER_NAME)

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the specified component.

    Returns a standard Python logging.Logger that is configured to route
    logs through Logfire. The logger is a child of the 'agents' root logger.

    Args:
        name: The name of the component (e.g., 'personas', 'tools.db')
              Will be prefixed with 'agents.' automatically.

    Returns:
        A configured logging.Logger instance

    Usage:
        from agents.app_logging import get_logger

        logger = get_logger("my_module")
        logger.info("Hello world")
        logger.debug("Debug info", extra={"item_count": 42})
    """
    full_name = f"{ROOT_LOGGER_NAME}.{name}" if name else ROOT_LOGGER_NAME

    if full_name not in _loggers:
        logger = logging.getLogger(full_name)

        # Add NullHandler to prevent "No handler found" warnings
        # when setup_logging hasn't been called
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())

        _loggers[full_name] = logger

    return _loggers[full_name]


# Create root logger on module import with NullHandler
_root_logger = logging.getLogger(ROOT_LOGGER_NAME)
_root_logger.addHandler(logging.NullHandler())
