"""
Logging and Usage for module

Note: The logging module must be initialized before use by calling
`initialize()` with the OTEL log file path. This is typically done
automatically when importing `agents.config`.
"""
from .otel import (
    initialize,
    get_logfire as get_logfire_instance,
    set_usage_metadata,
    reset_usage_metadata,
    get_usage_metadata,
)
from ..app_logging import get_logger, setup_logging
from .azure_blob_writer import AzureBlobWriter
from .usage import (
    # Usage JSONL writer
    UsageRecord,
    UsageWriter,
    initialize_usage_writer,
    get_usage_writer,
    # Quota tracking
    QuotaLimits,
    QuotaExceededError,
    QuotaTracker,
    initialize_quota_tracker,
    get_quota_tracker,
    set_quota_tracker,
    UsageSnapshot,
)


def get_logfire():
    """
    Get the LocalLogfire instance for advanced use cases.
    
    Use this when you need direct access to Logfire features like
    instrumentation methods, custom span processing, or span context managers.
    
    Returns:
        The configured LocalLogfire instance
        
    Raises:
        RuntimeError: If logging has not been initialized yet.
    """
    return get_logfire_instance()


__all__ = [
    "initialize",
    "get_logger",
    "get_logfire_instance",
    "setup_logging",
    "get_logfire",
    "set_usage_metadata",
    "reset_usage_metadata",
    "get_usage_metadata",
    # Azure Blob Storage writer
    "AzureBlobWriter",
    # Usage JSONL writer
    "UsageRecord",
    "UsageWriter",
    "initialize_usage_writer",
    "get_usage_writer",
    # Quota tracking
    "QuotaLimits",
    "QuotaExceededError",
    "QuotaTracker",
    "initialize_quota_tracker",
    "get_quota_tracker",
    "set_quota_tracker",
    "UsageSnapshot",
]
