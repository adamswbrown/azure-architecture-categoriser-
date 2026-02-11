"""
Configuration for the agents module reading in vars from config.toml at root level.

This module provides configuration classes for:
- agents: LLM router configuration, model creation, and agent settings
- db: SQL Server database connection settings
- postgres: Postgres connection settings
- server: ASGI server configuration
- logging: Logging/telemetry directory and OTEL file path configuration
- quota: Daily usage limits for tokens
"""
from pathlib import Path
import tomllib
from typing import Literal, Optional

from pydantic_ai import ModelSettings

from ..telemetry import (
    initialize, initialize_usage_writer,
    initialize_quota_tracker, get_quota_tracker, QuotaLimits
)
from ..app_logging import get_logger, setup_logging

# Path to the config.toml file at the root level
CONFIG_PATH = (Path(".") / "config.toml").resolve()
assert CONFIG_PATH.exists(), f"Config file not found in expected location ({CONFIG_PATH})"
with open(CONFIG_PATH, "rb") as f:
        config: dict[str, dict] = tomllib.load(f)
_logging_config: dict = config.get("logging") or {}
_telemetry_config: dict = config.get("telemetry") or {}

class logging:
    """Configuration for application logging from config.toml."""
    LOG_LEVEL: str = _logging_config.get("LOG_LEVEL", "INFO")


class telemetry:
    """Configuration for telemetry output from config.toml."""
    TELEMETRY_DIR: Path = Path(
        _telemetry_config.get("TELEMETRY_DIR", "./.telemetry")
    ).resolve()
    ENABLE_OTEL_SPANS: bool = _telemetry_config.get("ENABLE_OTEL_SPANS", False)
    OTEL_LOG_FILE: Path = TELEMETRY_DIR / "otel_spans.jsonl"
    USAGE_LOG_FILE: Path = TELEMETRY_DIR / _telemetry_config.get("AZURE_BLOB_NAME", "usage.jsonl")

    # Azure Blob Storage configuration (optional)
    AZURE_STORAGE_ACCOUNT: Optional[str] = _telemetry_config.get("AZURE_STORAGE_ACCOUNT")
    AZURE_CONTAINER_NAME: Optional[str] = _telemetry_config.get("AZURE_CONTAINER_NAME", "llm")
    AZURE_BLOB_NAME: str = _telemetry_config.get("AZURE_BLOB_NAME", "usage.jsonl")
    USAGE_LOG_FILE: Path = TELEMETRY_DIR / AZURE_BLOB_NAME

    if not TELEMETRY_DIR.exists():
        TELEMETRY_DIR.mkdir(parents=True, exist_ok=True)


class quota:
    """
    Configuration for daily usage quotas from config.toml.
    
    Quotas use a 24-hour rolling window based on token limits.
    
    Set DAILY_TOKEN_LIMIT to null/omit for unlimited usage.
    """
    # Daily limits (None = unlimited)
    DAILY_TOKEN_LIMIT: Optional[int] = config.get("quota", {}).get("DAILY_TOKEN_LIMIT")
    QUOTA_WINDOW_HOURS: int = config.get("quota", {}).get("QUOTA_WINDOW_HOURS", 24)
    
    # Whether to enforce quotas (can be disabled for testing)
    ENFORCE_QUOTA: bool = config.get("quota", {}).get("ENFORCE_QUOTA", False)


# Initialize logging and usage tracking
initialize(
    otel_log_file=telemetry.OTEL_LOG_FILE if telemetry.ENABLE_OTEL_SPANS else None,
    service_name="agents"
)
setup_logging(
    level=logging.LOG_LEVEL,
    dev_mode=(config["agents"].get("MODE", "dev") == "dev"),
    include_logfire=False,
)
initialize_usage_writer(
    file_path=telemetry.USAGE_LOG_FILE,
    storage_account=telemetry.AZURE_STORAGE_ACCOUNT,
    container_name=telemetry.AZURE_CONTAINER_NAME,
    blob_name=telemetry.AZURE_BLOB_NAME,
    mode=config["agents"].get("MODE", "dev")
)

from .sqlserver import db
from .postgres import postgres

# Load historical usage records into quota tracker
records_restored = initialize_quota_tracker(file_path=telemetry.USAGE_LOG_FILE)

# Configure default quota limits from config
_default_limits = QuotaLimits(
    daily_token_limit=quota.DAILY_TOKEN_LIMIT,
    window_hours=quota.QUOTA_WINDOW_HOURS
)
# Set default limits on the quota tracker
# The InMemoryQuotaTracker is a singleton, so get_quota_tracker() returns the same instance
_tracker = get_quota_tracker()
_tracker.set_default_limits(_default_limits)

logger = get_logger("config")
logger.info(f"Loading configuration from: {CONFIG_PATH}")
logger.info(f"Telemetry directory: {telemetry.TELEMETRY_DIR}")
if records_restored > 0:
    logger.info(f"Restored {records_restored} usage records from {telemetry.USAGE_LOG_FILE}")
if quota.DAILY_TOKEN_LIMIT:
    logger.info(
        f"Quota limits: tokens={quota.DAILY_TOKEN_LIMIT}, "
        f"window={quota.QUOTA_WINDOW_HOURS}h, "
        f"enforce={quota.ENFORCE_QUOTA}"
    )


class server:
    """Configuration for OpenAI / Azure OpenAI from config.toml"""
    PORT: int = int(config["server"].get("PORT", 8002))


class agents:
    """
    Configuration for agents from config.toml.

    Attributes:
        MODE: Environment mode - "dev" (CLI credentials) or "prod" (Azure UMI)
        CLOUD_PROVIDER: Cloud platform for model hosting - "AZURE" | "AWS" | "GCP"
        LLM_PROVIDER: LLM provider for prompt customization - "openai" | "claude" | "gemini"
        DEFAULT_TIER: Default model tier for agent creation - "light" | "heavy"
        MIGRATION_TARGET: Target cloud for migration (used in prompt variables like {{MIGRATION_TARGET}})
    """
    # Model configuration
    MODE: str = config["agents"].get("MODE", "dev")  # One of: "dev" | "prod"
    CLOUD_PROVIDER: Literal["AZURE", "GCP", "AWS"] = config["agents"].get("CLOUD_PROVIDER", "AZURE")  # One of: "AZURE" | "GCP" | "AWS"
    LLM_PROVIDER: Literal["openai", "gemini", "claude"] = config["agents"].get("LLM_PROVIDER", "openai")  # One of: "openai" | "gemini" | "claude"
    DEFAULT_TIER: Literal["light", "heavy"] = config["agents"].get("DEFAULT_TIER", "light")  # One of: "light" | "heavy"
    TURBO: bool = config["agents"].get("TURBO", False)  # Request lowest possible latency models

    # Variables for prompt injection
    ## These values can be used in prompt files as {{MIGRATION_TARGET}}, etc.
    MIGRATION_TARGET: str = config["agents"].get("MIGRATION_TARGET", CLOUD_PROVIDER)

    # Architecture catalog URL (Azure Blob Storage HTTPS URL)
    CATALOG_URL: Optional[str] = config["agents"].get("CATALOG_URL")

    # LLM Router integration (lazy initialization)
    _llm_integration = None

    @classmethod
    def _get_llm_integration(cls):
        """Get or create LLM Router integration instance."""
        if cls._llm_integration is None:
            from .llm_integration import create_llm_integration
            cls._llm_integration = create_llm_integration(str(CONFIG_PATH))
        return cls._llm_integration

    @classmethod
    def create_model(cls, tier: Optional[str] = None, model_settings: dict | None = None):
        """
        Create a Pydantic AI model using llm_router.

        This is the NEW recommended way to create models for agents.
        It supports multi-cloud (Azure/AWS/GCP) with identity-based authentication.

        Args:
            tier: Model tier name as defined in endpoints.json.
                  Common values: "light" (cost-effective), "heavy" (capable), "reasoning" (deep thinking)
                  The tier must exist for your configured cloud/provider/geo combination.
                  Defaults to config.agents.DEFAULT_TIER if not specified (changed in feat/prompts-per-model).
            model_settings: Optional provider-specific model settings dict (OpenAI only).
                          Example: {'openai_reasoning_effort': 'low', 'openai_max_completion_tokens': 100}
                          Ignored for non-OpenAI providers (Claude, Gemini).

        Returns:
            Pydantic AI compatible model instance

        Raises:
            EndpointNotFoundError: If the specified tier doesn't exist in endpoints.json
        """
        integration = cls._get_llm_integration()
        return integration.create_model(tier=tier if tier else cls.DEFAULT_TIER, model_settings=model_settings)

    @classmethod
    def build_model_settings(cls, tier: Optional[str] = None) -> ModelSettings | None:
        """
        Docstring for build_model_settings
        """
        tier = tier if tier else cls.DEFAULT_TIER
        # Provide model-specific settings based on LLM provider
        match cls.LLM_PROVIDER:
            case "openai":
                from pydantic_ai.models.openai import OpenAIResponsesModelSettings
                if cls.TURBO:
                    logger.info("TURBO mode activated")
                    logger.warning("TURBO mode uses the priority service tier for OpenAI models, which will incur higher costs per token.")
                return OpenAIResponsesModelSettings(
                    openai_previous_response_id="auto",
                    openai_reasoning_effort= None if tier == "reasoning" else "minimal", 
                    openai_service_tier="priority" if cls.TURBO else "auto"
                )

            case "gemini":
                from pydantic_ai.models.google import GoogleModelSettings
                from google.genai.types import ThinkingConfigDict
                if cls.TURBO:
                    logger.warning("TURBO mode not supported by gemini models.")
                # Set thinking to zero for light/nano tiers to reduce latency
                # Set thinking to -1 (dynamic) for other models
                thinking_config = ThinkingConfigDict(
                    thinking_budget=0 if tier in ("light", "nano") else -1
                )
                return GoogleModelSettings(
                    google_thinking_config=thinking_config
                )

            case "claude":
                from pydantic_ai.models.bedrock import BedrockModelSettings
                # Currently no specific settings for Claude models
                if cls.TURBO:
                    logger.info("TURBO mode activated")
                    logger.warning("TURBO mode uses the priority service tier for OpenAI models, which will incur higher costs per token.")
                return BedrockModelSettings(
                    bedrock_cache_instructions=True,       # Cache system instructions
                    bedrock_cache_tool_definitions=True,   # Cache tool definitions
                    bedrock_cache_messages=True,           # Also cache the last message
                    bedrock_service_tier={"type": "priority" if cls.TURBO else "default"}
                )

        
        # Fallback
        logger.warning(f"Unknown LLM_PROVIDER '{cls.LLM_PROVIDER}' - using default ModelSettings")
        return None


__all__ = [
    "agents",
    "db",
    "postgres",
    "server",
    "logging",
    "telemetry",
    "quota",
    "get_logger",
    "setup_logging",
]
