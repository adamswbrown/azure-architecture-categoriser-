"""
Track usage statistics for agents.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import json
import logging
from pathlib import Path
import threading
from typing import Optional, TextIO, NamedTuple

from pydantic import BaseModel
from pydantic_ai import RunUsage

from .azure_blob_writer import AzureBlobWriter


logger = logging.getLogger(__name__)


# =============================================================================
# Global Quota Tracker - Abstract Interface
# =============================================================================

# Default daily limits (can be overridden via config)
DEFAULT_DAILY_TOKEN_LIMIT: Optional[int] = None  # None = unlimited
DEFAULT_QUOTA_WINDOW_HOURS: int = 24


class UsageSnapshot(NamedTuple):
    """Snapshot of usage within a time window."""
    tokens: int
    oldest_record_time: Optional[datetime]  # When the oldest record in window was created


@dataclass
class DailyUsageRecord:
    """A single usage consumption record with timestamp for rolling window calculations."""
    timestamp: datetime
    tokens: int
    thread_id: str = ""  # Optional context


@dataclass
class QuotaLimits:
    """Configurable quota limits for a user."""
    daily_token_limit: Optional[int] = None  # None = unlimited
    window_hours: int = 24  # Rolling window size

    def is_unlimited(self) -> bool:
        """Check if the limit is unlimited."""
        return self.daily_token_limit is None


class QuotaExceededError(Exception):
    """Raised when a user exceeds their daily quota."""
    def __init__(
        self, 
        user_id: str, 
        current_usage: int,
        limit: int,
        resume_time: datetime
    ):
        self.user_id = user_id
        self.current_usage = current_usage
        self.limit = limit
        self.resume_time = resume_time
        
        # Format the message as specified in the Jira story
        resume_str = resume_time.strftime("%Y-%m-%d %H:%M:%S UTC")
        super().__init__(
            f"You have exceeded your daily Assistant quota. "
            f"You will be able to continue at {resume_str}."
        )
    
    def to_response_dict(self) -> dict:
        """Convert to a response dictionary for the frontend."""
        return {
            "error": "quota_exceeded",
            "message": str(self),
            "current_usage": self.current_usage,
            "limit": self.limit,
            "resume_time": self.resume_time.isoformat(),
        }


class QuotaTracker(ABC):
    """
    Abstract base class for tracking user quotas with 24-hour rolling window.
    
    Supports token-based limits.
    
    Implementations can be swapped out for different backends:
    - InMemoryQuotaTracker: Single-process, thread-safe (default)
    - RedisQuotaTracker: Distributed, multi-instance (future)
    - DatabaseQuotaTracker: PostgreSQL-backed (future)
    """
    
    @abstractmethod
    def set_limits(self, user_id: str, limits: QuotaLimits) -> None:
        """Set quota limits for a user."""
        pass
    
    @abstractmethod
    def get_limits(self, user_id: str) -> QuotaLimits:
        """Get quota limits for a user. Returns default limits if not set."""
        pass
    
    @abstractmethod
    def record_usage(
        self, 
        user_id: str, 
        tokens: int, 
        thread_id: str = ""
    ) -> None:
        """Record a usage event with timestamp."""
        pass
    
    @abstractmethod
    def get_usage_in_window(
        self, 
        user_id: str, 
        window_hours: Optional[int] = None
    ) -> UsageSnapshot:
        """
        Get total usage within the rolling window.
        
        Args:
            user_id: The user identifier
            window_hours: Override window size (defaults to user's configured window)
            
        Returns:
            UsageSnapshot with total tokens and oldest record time
        """
        pass
    
    @abstractmethod
    def check_quota(
        self, 
        user_id: str,
        additional_tokens: int = 0
    ) -> tuple[bool, Optional[QuotaExceededError]]:
        """
        Check if user would exceed quota with additional usage.
        
        Args:
            user_id: The user identifier
            additional_tokens: Tokens about to be consumed
            
        Returns:
            Tuple of (is_within_quota, error_if_exceeded)
        """
        pass
    
    @abstractmethod
    def get_remaining(self, user_id: str) -> Optional[int]:
        """
        Get remaining token allowance.
        
        Returns:
            Remaining tokens (None indicates unlimited)
        """
        pass
    
    @abstractmethod
    def clear_user(self, user_id: str) -> None:
        """Clear all usage records and limits for a user."""
        pass
    
    @abstractmethod
    def cleanup_old_records(self, user_id: str) -> int:
        """
        Remove records outside the window to prevent memory growth.
        
        Returns:
            Number of records removed
        """
        pass
    
    @abstractmethod
    def has_quota(self, user_id: str) -> bool:
        """Check if user has any limits configured (not unlimited)."""
        pass

    @abstractmethod
    def set_default_limits(self, limits: QuotaLimits) -> None:
        """Set default limits applied to users without specific limits."""
        pass


class InMemoryQuotaTracker(QuotaTracker):
    """
    Thread-safe in-memory quota tracker with 24-hour rolling window.
    
    Stores timestamped usage records per user and calculates usage
    within the rolling window on demand.
    
    Suitable for single-process deployments. For distributed systems,
    swap this out for RedisQuotaTracker or DatabaseQuotaTracker.
    """
    
    _instance: Optional["InMemoryQuotaTracker"] = None
    _init_lock = threading.Lock()
    
    # Instance attributes
    _usage_records: dict[str, list[DailyUsageRecord]]
    _limits: dict[str, QuotaLimits]
    _default_limits: QuotaLimits
    _lock: threading.RLock
    _file_path: Optional[Path]
    
    def __new__(cls) -> "InMemoryQuotaTracker":
        if cls._instance is None:
            with cls._init_lock:
                # Double-check locking pattern
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._usage_records = {}
                    instance._limits = {}
                    instance._default_limits = QuotaLimits(
                        daily_token_limit=DEFAULT_DAILY_TOKEN_LIMIT,
                        window_hours=DEFAULT_QUOTA_WINDOW_HOURS
                    )
                    instance._lock = threading.RLock()
                    instance._file_path = None
                    cls._instance = instance
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (primarily for testing)."""
        with cls._init_lock:
            cls._instance = None
    
    def set_default_limits(self, limits: QuotaLimits) -> None:
        """Set default limits for all users without specific limits."""
        with self._lock:
            self._default_limits = limits
    
    def set_limits(self, user_id: str, limits: QuotaLimits) -> None:
        with self._lock:
            self._limits[user_id] = limits
    
    def get_limits(self, user_id: str) -> QuotaLimits:
        with self._lock:
            return self._limits.get(user_id, self._default_limits)
    
    def record_usage(
        self, 
        user_id: str, 
        tokens: int, 
        thread_id: str = ""
    ) -> None:
        with self._lock:
            if user_id not in self._usage_records:
                self._usage_records[user_id] = []
            
            record = DailyUsageRecord(
                timestamp=datetime.now(timezone.utc),
                tokens=tokens,
                thread_id=thread_id
            )
            self._usage_records[user_id].append(record)
            
            # Periodically cleanup old records (every 100 records)
            if len(self._usage_records[user_id]) % 100 == 0:
                self.cleanup_old_records(user_id)
    
    def get_usage_in_window(
        self, 
        user_id: str, 
        window_hours: Optional[int] = None
    ) -> UsageSnapshot:
        with self._lock:
            limits = self.get_limits(user_id)
            hours = window_hours if window_hours is not None else limits.window_hours
            cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
            
            records = self._usage_records.get(user_id, [])
            
            total_tokens = 0
            oldest_time: Optional[datetime] = None
            
            for record in records:
                if record.timestamp >= cutoff:
                    total_tokens += record.tokens
                    if oldest_time is None or record.timestamp < oldest_time:
                        oldest_time = record.timestamp
            
            return UsageSnapshot(
                tokens=total_tokens,
                oldest_record_time=oldest_time
            )
    
    def check_quota(
        self, 
        user_id: str,
        additional_tokens: int = 0
    ) -> tuple[bool, Optional[QuotaExceededError]]:
        with self._lock:
            limits = self.get_limits(user_id)
            
            # If unlimited, always OK
            if limits.is_unlimited():
                return True, None
            
            usage = self.get_usage_in_window(user_id)
            
            # Check token limit
            if limits.daily_token_limit is not None:
                projected_tokens = usage.tokens + additional_tokens
                if projected_tokens > limits.daily_token_limit:
                    resume_time = self._calculate_resume_time(user_id, limits)
                    return False, QuotaExceededError(
                        user_id=user_id,
                        current_usage=usage.tokens,
                        limit=limits.daily_token_limit,
                        resume_time=resume_time
                    )
            
            return True, None
    
    def _calculate_resume_time(self, user_id: str, limits: QuotaLimits) -> datetime:
        """Calculate when the user can resume (oldest record + window)."""
        usage = self.get_usage_in_window(user_id)
        if usage.oldest_record_time:
            return usage.oldest_record_time + timedelta(hours=limits.window_hours)
        # Fallback: now + window
        return datetime.now(timezone.utc) + timedelta(hours=limits.window_hours)
    
    def get_remaining(self, user_id: str) -> Optional[int]:
        with self._lock:
            limits = self.get_limits(user_id)
            usage = self.get_usage_in_window(user_id)
            
            if limits.daily_token_limit is not None:
                return max(0, limits.daily_token_limit - usage.tokens)
            
            return None
    
    def clear_user(self, user_id: str) -> None:
        with self._lock:
            self._usage_records.pop(user_id, None)
            self._limits.pop(user_id, None)
    
    def cleanup_old_records(self, user_id: str) -> int:
        """Remove records older than the window to prevent memory growth."""
        with self._lock:
            if user_id not in self._usage_records:
                return 0
            
            limits = self.get_limits(user_id)
            # Keep records for slightly longer than window to handle edge cases
            cutoff = datetime.now(timezone.utc) - timedelta(hours=limits.window_hours + 1)
            
            original_count = len(self._usage_records[user_id])
            self._usage_records[user_id] = [
                r for r in self._usage_records[user_id] 
                if r.timestamp >= cutoff
            ]
            return original_count - len(self._usage_records[user_id])
    
    def has_quota(self, user_id: str) -> bool:
        """Check if user has any limits configured (not unlimited)."""
        limits = self.get_limits(user_id)
        return not limits.is_unlimited()
    
    def load_from_file(self, file_path: Path) -> int:
        """
        Load and restore usage records from a JSONL file.
        
        Reads the usage.jsonl file and populates the in-memory tracker with
        records that are still within the rolling window for each user.
        
        Args:
            file_path: Path to the usage.jsonl file
            
        Returns:
            Number of records restored (within window)
        """
        with self._lock:
            self._file_path = file_path
            
            if not file_path.exists():
                logger.info(f"Usage file {file_path} does not exist, starting fresh")
                return 0
            
            restored_count = 0
            total_count = 0
            missing_fields_count = 0
            bad_timestamp_count = 0
            invalid_json_count = 0
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        
                        try:
                            data = json.loads(line)
                            total_count += 1
                            
                            # Extract required fields
                            user_id = data.get('user_id')
                            thread_id = data.get('thread_id', '')
                            timestamp_str = data.get('timestamp')
                            tokens_in = data.get('tokens_in', 0)
                            tokens_out = data.get('tokens_out', 0)
                            
                            if not user_id or not timestamp_str:
                                missing_fields_count += 1
                                continue
                            
                            # Parse timestamp
                            try:
                                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            except ValueError:
                                bad_timestamp_count += 1
                                continue
                            
                            # Check if record is within the window for this user
                            limits = self.get_limits(user_id)
                            cutoff = datetime.now(timezone.utc) - timedelta(hours=limits.window_hours)
                            
                            if timestamp >= cutoff:
                                # Create and store the record
                                record = DailyUsageRecord(
                                    timestamp=timestamp,
                                    tokens=tokens_in + tokens_out,
                                    thread_id=thread_id
                                )
                                
                                if user_id not in self._usage_records:
                                    self._usage_records[user_id] = []
                                
                                self._usage_records[user_id].append(record)
                                restored_count += 1
                        
                        except json.JSONDecodeError:
                            invalid_json_count += 1
                            continue
                
                expired_count = total_count - restored_count
                logger.info(
                    "Restored %d usage records from %s (%d total read, %d expired)",
                    restored_count,
                    file_path,
                    total_count,
                    expired_count
                )
                if missing_fields_count or bad_timestamp_count or invalid_json_count:
                    logger.info(
                        "Skipped %d record(s): missing_fields=%d, bad_timestamp=%d, invalid_json=%d",
                        missing_fields_count + bad_timestamp_count + invalid_json_count,
                        missing_fields_count,
                        bad_timestamp_count,
                        invalid_json_count
                    )
                return restored_count
            
            except OSError as e:
                logger.error(f"Failed to read usage file {file_path}: {e}")
                return 0


# Global quota tracker instance - swap implementation here for distributed
_quota_tracker: QuotaTracker = InMemoryQuotaTracker()


def get_quota_tracker() -> QuotaTracker:
    """Get the global quota tracker instance."""
    return _quota_tracker


def set_quota_tracker(tracker: QuotaTracker) -> None:
    """Set the global quota tracker (for dependency injection/testing)."""
    global _quota_tracker
    _quota_tracker = tracker


# =============================================================================
# Usage Tracking
# =============================================================================

@dataclass
class UsageItem:
        """Represents a usage item with tokens"""
        usage: RunUsage

        # Metadata
        provider_id: str
        model_ref: str
        parent: Optional[str] = None  # If this usage is part of a larger operation

        @property
        def total_tokens(self) -> int:
            """Total tokens used (input + output)"""
            return (self.usage.input_tokens or 0) + (self.usage.output_tokens or 0)


@dataclass
class UsageMetadata:
    """Metadata for usage tracking."""
    user_id: Optional[str]
    thread_id: str


class UsageAggregator(BaseModel):
    """Tracks usage statistics for agents for a thread (conversation), integrated with global quota tracker."""    
    # Metadata
    metadata: UsageMetadata

    # Usage data
    usage: list[UsageItem] = []
    
    # Track if we've initialized quota from global tracker
    _quota_initialized: bool = False

    def model_post_init(self, __context) -> None:
        """Sync with global quota tracker on initialization."""
        if self.metadata.user_id is None:
            # Skip quota tracking for anonymous users
            return
        tracker = get_quota_tracker()
        if tracker.has_quota(self.metadata.user_id):
            # User already has quota tracked globally
            self._quota_initialized = True
    
    def initialize_quota(
        self, 
        daily_token_limit: Optional[int] = None,
        window_hours: int = 24
    ) -> None:
        """
        Initialize quota limits for this user in the global tracker.
        Call this when you know the user's allocated quota (e.g., from JWT claims).
        
        Skipped if user_id is None (anonymous users).
        
        Args:
            daily_token_limit: Maximum tokens allowed per rolling window (None = unlimited)
            window_hours: Rolling window size in hours (default 24)
        """
        if self.metadata.user_id is None:
            return
        tracker = get_quota_tracker()
        limits = QuotaLimits(
            daily_token_limit=daily_token_limit,
            window_hours=window_hours
        )
        tracker.set_limits(self.metadata.user_id, limits)
        self._quota_initialized = True

    def check_quota(
        self,
        additional_tokens: int = 0
    ) -> tuple[bool, Optional[QuotaExceededError]]:
        """
        Check if user would exceed quota with additional usage.
        
        Returns (True, None) if user_id is None (anonymous users have no limits).
        
        Args:
            additional_tokens: Tokens about to be consumed
            
        Returns:
            Tuple of (is_within_quota, error_if_exceeded)
        """
        if self.metadata.user_id is None:
            return True, None
        tracker = get_quota_tracker()
        return tracker.check_quota(
            self.metadata.user_id,
            additional_tokens=additional_tokens
        )

    @property
    def remaining_tokens(self) -> Optional[int]:
        """Get remaining tokens from global tracker (24hr window). Returns None if user_id is None."""
        if self.metadata.user_id is None:
            return None
        return get_quota_tracker().get_remaining(self.metadata.user_id)

    @property
    def usage_in_window(self) -> UsageSnapshot:
        """Get usage snapshot for the current rolling window. Returns empty snapshot if user_id is None."""
        if self.metadata.user_id is None:
            return UsageSnapshot(tokens=0, oldest_record_time=None)
        return get_quota_tracker().get_usage_in_window(self.metadata.user_id)

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens used in this session"""
        return sum(item.usage.input_tokens or 0 for item in self.usage)
    
    @property
    def total_output_tokens(self) -> int:
        """Total output tokens used in this session"""
        return sum(item.usage.output_tokens or 0 for item in self.usage)
    
    @property
    def total_tokens(self) -> int:
        """Total tokens used in this session"""
        return self.total_input_tokens + self.total_output_tokens
    
    def add_usage_item(self, item: UsageItem, enforce_quota: bool = True) -> None:
        """
        Add a usage item to the aggregator and update global quota tracker.
        
        Skips quota tracking if user_id is None (anonymous users).
        
        Args:
            item: The usage item to add
            enforce_quota: If True, raises QuotaExceededError when quota exceeded
            
        Raises:
            QuotaExceededError: If enforce_quota=True and user exceeds quota
        """
        # Track in session (always)
        self.usage.append(item)
        
        # Skip quota tracking for anonymous users
        if self.metadata.user_id is None:
            return
        
        tracker = get_quota_tracker()
        tokens_used = item.total_tokens
        
        # Check quota first if enforcing
        if enforce_quota:
            ok, error = tracker.check_quota(
                self.metadata.user_id,
                additional_tokens=tokens_used,
            )
            if not ok and error:
                raise error
        
        # Record usage in global tracker (for 24hr window)
        tracker.record_usage(
            self.metadata.user_id,
            tokens=tokens_used,
            thread_id=self.metadata.thread_id
        )

    def rollback_usage(self, item: UsageItem) -> None:
        """
        Rollback a usage item (e.g., on error).
        
        Note: In the new time-based model, we don't actually remove records
        from the global tracker (they're needed for audit). The rolling window
        will naturally expire old usage.
        """
        if item in self.usage:
            self.usage.remove(item)

    @property
    def below_quota(self) -> bool:
        """Check if the user is below their quota (in tokens). Returns True if user_id is None."""
        if self.metadata.user_id is None:
            return True
        ok, _ = get_quota_tracker().check_quota(self.metadata.user_id)
        return ok


# =============================================================================
# Usage JSONL Writer
# =============================================================================

@dataclass
class UsageRecord:
    """
    A single usage record for the usage.jsonl file.
    
    Schema matches the Jira story requirements:
    - per user jsons
    - thread id
    - timestamp
    - query
    - response
    - token ins
    - tokens out
    - LLM provider
    - model used
    - persona that provided response
    """
    user_id: Optional[str]
    thread_id: str
    timestamp: str  # ISO 8601 format
    query: str
    response: str
    input_tokens: int
    output_tokens: int
    usage: RunUsage
    provider: str
    model: str
    persona: str

    def to_json_line(self) -> str:
        """Convert the record to a JSON line string."""
        return json.dumps(asdict(self))


class UsageWriter:
    """
    Thread-safe writer for usage records to a JSONL file and optionally Azure Blob Storage.
    
    This writer is separate from the OTEL span exporter and writes
    usage data in the specific schema required by the Jira story.
    
    Usage:
        writer = UsageWriter(
            file_path=Path(".logs/usage.jsonl"),
            storage_account="myaccount",
            container_name="usage-logs",
            blob_name="usage.jsonl"
        )
        writer.write(UsageRecord(...))
        writer.shutdown()
    """
    
    _instance: Optional["UsageWriter"] = None
    _init_lock = threading.Lock()
    
    # Instance attributes (declared for type checker)
    _file_path: Optional[Path]
    _file: Optional[TextIO]
    _lock: threading.RLock
    _initialized: bool
    
    # Azure Blob Storage writer
    _azure_blob_writer: Optional[AzureBlobWriter]
    _logger: logging.Logger
    
    def __new__(
        cls, 
        file_path: Optional[Path] = None,
        storage_account: Optional[str] = None,
        container_name: Optional[str] = None,
        blob_name: Optional[str] = None,
        mode: str = "dev"
    ) -> "UsageWriter":
        """Singleton pattern for global writer instance."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._file_path = file_path
                    instance._file = None
                    instance._lock = threading.RLock()
                    instance._initialized = False
                    instance._logger = logging.getLogger(__name__)
                    
                    # Initialize Azure Blob Writer if configured or auto-detecting in prod
                    if (storage_account or mode != "dev") and container_name and blob_name:
                        instance._azure_blob_writer = AzureBlobWriter(
                            storage_account=storage_account,
                            container_name=container_name,
                            blob_name=blob_name,
                            mode=mode,
                            logger=instance._logger
                        )
                    else:
                        instance._azure_blob_writer = None
                    
                    cls._instance = instance
        return cls._instance
    
    def _ensure_initialized(self) -> None:
        """Lazy initialization of file handle."""
        if not self._initialized and self._file_path is not None:
            try:
                self._file = open(self._file_path, "a", encoding="utf-8")
                self._initialized = True
            except OSError as e:
                raise RuntimeError(f"Failed to open usage log file {self._file_path}: {e}")
    

    @classmethod
    def get_instance(cls) -> Optional["UsageWriter"]:
        """Get the singleton instance without creating a new one."""
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton (primarily for testing)."""
        with cls._init_lock:
            if cls._instance is not None:
                cls._instance.shutdown()
            cls._instance = None

    def write(self, record: UsageRecord) -> None:
        """
        Write a usage record to the JSONL file and Azure Blob Storage (if configured).
        
        Thread-safe and handles errors gracefully.
        
        Args:
            record: The UsageRecord to write
        """
        with self._lock:
            # Initialize blob storage on first write
            if self._azure_blob_writer is not None and not self._azure_blob_writer.is_initialized:
                self._azure_blob_writer.initialize()
            
            # Write to local file
            self._ensure_initialized()
            json_line = record.to_json_line() + '\n'
            
            if self._file is not None:
                try:
                    self._file.write(json_line)
                    self._file.flush()
                except OSError as e:
                    # Log but don't raise - usage logging shouldn't break the app
                    self._logger.error(f"Failed to write usage record to file: {e}")
            
            # Append to Azure blob
            if self._azure_blob_writer is not None:
                self._azure_blob_writer.append(json_line)

    def initialize_remote(self) -> bool:
        """
        Initialize Azure Blob Storage append target early (optional).

        Returns:
            True if initialization succeeds or is not configured, False otherwise.
        """
        if self._azure_blob_writer is None:
            self._logger.info("Azure usage logging disabled (no storage configuration provided)")
            return True
        return self._azure_blob_writer.initialize()

    def shutdown(self) -> None:
        """Close the file handle and blob client."""
        with self._lock:
            if self._file is not None:
                try:
                    self._file.flush()
                    self._file.close()
                except Exception:
                    pass
                finally:
                    self._file = None
                    self._initialized = False
            
            # Close Azure Blob Writer
            if self._azure_blob_writer is not None:
                self._azure_blob_writer.close()


def initialize_quota_tracker(file_path: Path) -> int:
    """
    Initialize the global QuotaTracker by loading historical usage from file.
    
    Should be called once during application startup from the config module,
    before any quota checks are performed.
    
    Args:
        file_path: Path to the usage.jsonl file
        
    Returns:
        Number of usage records restored
    """
    tracker = get_quota_tracker()
    if isinstance(tracker, InMemoryQuotaTracker):
        return tracker.load_from_file(file_path)
    return 0


def initialize_usage_writer(
    file_path: Path,
    storage_account: Optional[str] = None,
    container_name: Optional[str] = None,
    blob_name: Optional[str] = None,
    mode: str = "dev"
) -> UsageWriter:
    """
    Initialize the global UsageWriter instance.
    
    Should be called once during application startup from the config module.
    
    Args:
        file_path: Path to the usage.jsonl file
        storage_account: Azure Storage account name (optional)
        container_name: Azure Blob container name (optional, default: "usage-logs")
        blob_name: Azure Blob name (optional, default: "usage.jsonl")
        
    Returns:
        The initialized UsageWriter instance
    """
    writer = UsageWriter(
        file_path=file_path,
        storage_account=storage_account,
        container_name=container_name,
        blob_name=blob_name,
        mode=mode
    )
    writer.initialize_remote()
    return writer


def get_usage_writer() -> Optional[UsageWriter]:
    """
    Get the global UsageWriter instance.
    
    Returns:
        The UsageWriter instance, or None if not initialized
    """
    return UsageWriter.get_instance()
