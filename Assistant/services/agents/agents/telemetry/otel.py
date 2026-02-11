"""
Use OpenTelemetry to configure Logfire outputs
"""
from contextvars import ContextVar, Token
from dataclasses import dataclass, asdict
import json
import logging
import threading
from pathlib import Path
from typing import Any, Optional, Sequence

import logfire
from opentelemetry.context import Context
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .usage import UsageMetadata

# ContextVar for propagating UsageMetadata to span exporter
_usage_metadata_ctx: ContextVar[Optional[UsageMetadata]] = ContextVar(
    'usage_metadata', default=None
)

# Attribute key for storing captured metadata on spans
_METADATA_ATTR_KEY = "drm.usage_metadata"


def set_usage_metadata(metadata: UsageMetadata) -> Token[Optional[UsageMetadata]]:
    """
    Set UsageMetadata in the current context for span attribution.
    
    Use this at request boundaries (e.g., in handle_request) to ensure
    all spans created during the request have access to user/thread info.
    
    Args:
        metadata: UsageMetadata with user_id and thread_id
        
    Returns:
        Token that can be used to reset the context
        
    Example:
        token = set_usage_metadata(UsageMetadata(user_id="123", ...))
        try:
            # All spans created here will have metadata attached
            await process_request()
        finally:
            reset_usage_metadata(token)
    """
    return _usage_metadata_ctx.set(metadata)


def reset_usage_metadata(token: Token[Optional[UsageMetadata]]) -> None:
    """
    Reset UsageMetadata context to its previous value.
    
    Args:
        token: Token returned from set_usage_metadata()
        
    Warning:
        This will raise ValueError if called from a different async context
        than where the token was created. Use clear_usage_metadata() for
        cross-context cleanup (e.g., in callbacks).
    """
    _usage_metadata_ctx.reset(token)


def clear_usage_metadata() -> None:
    """
    Clear UsageMetadata context by setting it to None.
    
    Use this instead of reset_usage_metadata() when you need to clear
    the metadata from a callback or different async context where the
    original token is not valid.
    
    This is safe to call from any context.
    """
    _usage_metadata_ctx.set(None)


def get_usage_metadata() -> Optional[UsageMetadata]:
    """
    Get the current UsageMetadata from context.
    
    Returns:
        UsageMetadata if set, None otherwise
    """
    return _usage_metadata_ctx.get()


class MetadataCaptureProcessor(SpanProcessor):
    """
    SpanProcessor that captures UsageMetadata from contextvar at span start.
    
    This processor runs synchronously when spans are created (in the request context),
    capturing the metadata and storing it as a JSON string attribute on the span.
    This ensures the metadata is available when the span is later exported
    asynchronously by BatchSpanProcessor.
    """
    
    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        """Capture metadata from contextvar and store on span."""
        metadata = _usage_metadata_ctx.get()
        if metadata is not None:
            # Store as JSON string since OTEL attributes must be primitive types
            span.set_attribute(_METADATA_ATTR_KEY, json.dumps(asdict(metadata)))
    
    def on_end(self, span: ReadableSpan) -> None:
        """No-op - metadata already captured on start."""
        pass
    
    def shutdown(self) -> None:
        """No-op - no resources to clean up."""
        pass
    
    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """No-op - nothing to flush."""
        return True

logger = logging.getLogger(__name__)


def _json_serializer(obj: Any) -> str:
    """Default serializer for non-JSON-serializable types."""
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    if hasattr(obj, "__dict__"):
        return str(obj)
    return repr(obj)


@dataclass
class JsonLine:
    """Represents a single JSON line entry for OTEL span export."""
    # The base log
    name: str
    start_time: Optional[int]
    end_time: Optional[int]

    # Metadata for usage
    metadata: Optional[UsageMetadata]

    # Default attributes
    trace_id: Optional[str]
    span_id: Optional[str]
    parent_span_id: Optional[str]

    # Any additional attributes
    attributes: dict[str, Any]

    def to_json_line(self) -> str:
        """Convert the span to a JSON line string."""
        return json.dumps(asdict(self), default=_json_serializer)

class JsonlFileExporter(SpanExporter):
    """Exports spans to a JSONL file for Logfire ingestion.
    
    Thread-safe implementation with proper error handling for production use.
    """

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self._lock = threading.Lock()
        self._file = None
        self._open_file()

    def _open_file(self) -> None:
        """Open the file handle with proper error handling."""
        try:
            self._file = open(self.file_path, "a", encoding="utf-8")
        except OSError as e:
            logger.error(f"Failed to open OTEL log file {self.file_path}: {e}")
            raise

    def _serialize_span(self, span: ReadableSpan) -> JsonLine:
        """Serialize a span to a dictionary, handling potential errors."""
        # Convert attributes to dict safely
        attributes = {}
        if span.attributes:
            for key, value in span.attributes.items():
                try:
                    # Test if value is JSON serializable
                    json.dumps(value)
                    attributes[key] = value
                except (TypeError, ValueError):
                    attributes[key] = _json_serializer(value)

        # Format span name with request data if available
        span_name = span.name
        if span.attributes and ("request_data" in span.attributes) and ("request_data" in span.name):
            try:
                match span.attributes["request_data"]:
                    case str():
                        attributes["request_data"] = json.loads(span.attributes["request_data"])
                    case _:
                        pass
                span_name = span.name.format(**attributes)
            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f"Failed to format span name with request_data: {e}")

        # Get usage metadata from span attribute (captured at span start)
        metadata: Optional[UsageMetadata] = None
        if span.attributes and _METADATA_ATTR_KEY in span.attributes:
            try:
                metadata_json = span.attributes[_METADATA_ATTR_KEY]
                if isinstance(metadata_json, str):
                    metadata_dict = json.loads(metadata_json)
                    metadata = UsageMetadata(**metadata_dict)
                    # Remove from exported attributes to avoid duplication
                    attributes.pop(_METADATA_ATTR_KEY, None)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                logger.warning(f"Failed to parse usage metadata from span: {e}")

        return JsonLine(
            name=span_name,
            trace_id=format(span.context.trace_id, '032x') if span.context else None,
            span_id=format(span.context.span_id, '016x') if span.context else None,
            parent_span_id=format(span.parent.span_id, '016x') if span.parent else None,
            start_time=span.start_time,
            end_time=span.end_time,
            metadata=metadata,
            attributes=attributes,
        )

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Export spans to the JSONL file with thread safety and error handling."""
        if self._file is None:
            logger.error("Cannot export spans: file handle is not open")
            return SpanExportResult.FAILURE

        try:
            with self._lock:
                for span in spans:
                    try:
                        json_line = self._serialize_span(span)
                        self._file.write(json_line.to_json_line() + '\n')
                    except Exception as e:
                        # Log but don't fail the entire batch for a single bad span
                        logger.warning(f"Failed to export span '{span.name}': {e}")
                self._file.flush()
            return SpanExportResult.SUCCESS
        except OSError as e:
            logger.error(f"Span export I/O error: {e}")
            return SpanExportResult.FAILURE
        except Exception as e:
            logger.error(f"Unexpected span export error: {e}")
            return SpanExportResult.FAILURE

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Force flush any buffered spans."""
        try:
            with self._lock:
                if self._file:
                    self._file.flush()
            return True
        except Exception as e:
            logger.error(f"Failed to force flush: {e}")
            return False

    def shutdown(self) -> None:
        """Shutdown the exporter and close the file handle."""
        with self._lock:
            if self._file:
                try:
                    self._file.flush()
                    self._file.close()
                except Exception as e:
                    logger.error(f"Error during shutdown: {e}")
                finally:
                    self._file = None


def _create_span_processor(otel_log_file: Path) -> BatchSpanProcessor | None:
    """Create the span processor with proper error handling."""
    try:
        exporter = JsonlFileExporter(otel_log_file)
        # BatchSpanProcessor for better performance (async batching)
        return BatchSpanProcessor(
            exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
        )
    except Exception as e:
        logger.error(f"Failed to create span processor: {e}")
        return None


def configure_logfire(
    otel_log_file: Optional[Path] = None,
    service_name: str = "agents",
) -> logfire.Logfire:
    """
    Configure Logfire with proper error handling.
    
    Args:
        otel_log_file: Path to JSONL file for span export. If None, no file export.
        service_name: Service name for Logfire configuration.
    
    Returns:
        Configured Logfire instance.
    """
    try:
        processors: list[SpanProcessor] = [
            # MetadataCaptureProcessor must come first to capture metadata
            # before spans are queued for async export
            MetadataCaptureProcessor()
        ]
        if otel_log_file:
            span_processor = _create_span_processor(otel_log_file)
            if span_processor:
                processors.append(span_processor)
        
        local_logfire = logfire.configure(
            service_name=service_name,
            send_to_logfire="if-token-present",
            console=False,
            additional_span_processors=processors
        )
        local_logfire.instrument_openai()
        local_logfire.instrument_pydantic_ai()
        local_logfire.instrument_mcp()
        logger.info(
            "Logfire instrumentation configured: OpenAI, PydanticAI, MCP (console output disabled)"
        )
        return local_logfire
    except Exception as e:
        logger.error(f"Failed to configure Logfire: {e}")
        raise e


# Module-level Logfire instance (initialized lazily by config module)
LocalLogfire: Optional[logfire.Logfire] = None


def initialize(otel_log_file: Optional[Path] = None, service_name: str = "agents") -> logfire.Logfire:
    """
    Initialize the module-level LocalLogfire instance.
    
    This should be called once during application startup, typically from
    the config module after reading configuration values.
    
    Args:
        otel_log_file: Path to JSONL file for span export.
        service_name: Service name for Logfire configuration.
    
    Returns:
        The configured Logfire instance.
    """
    global LocalLogfire
    if LocalLogfire is None:
        LocalLogfire = configure_logfire(otel_log_file, service_name)
    return LocalLogfire


def get_logfire() -> logfire.Logfire:
    """
    Get the LocalLogfire instance, initializing with defaults if needed.
    
    Returns:
        The Logfire instance.
    
    Raises:
        RuntimeError: If Logfire has not been initialized.
    """
    if LocalLogfire is None:
        raise RuntimeError(
            "Logfire has not been initialized. "
            "Call agents.telemetry.otel.initialize() first, or import agents.config."
        )
    return LocalLogfire
