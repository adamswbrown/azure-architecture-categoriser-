"""
Configuration management for LLM Router.
"""

from typing import Literal, Optional
from dataclasses import dataclass

from .loader import ConfigLoader, LoaderError
from .schema import LLM_TIER_TYPE, CLOUD_PROVIDER_TYPE
from ..logger import get_logger

logger = get_logger('core.config')


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass

@dataclass
class Config:
    """LLM Router configuration."""

    llm_cloud: CLOUD_PROVIDER_TYPE  # azure, gcp, aws
    llm_provider: str  # openai, claude, gemini
    tier: Optional[LLM_TIER_TYPE] = None  # Tier name from endpoints.json (optional, defaults to first available)
    endpoints_source: Optional[str] = None  # Path or URL to endpoints.json
    environment: Optional[str] = None  # auto, azure_vm, local (optional, defaults to auto)
    location: Optional[str] = None  # Azure region override (e.g., 'australiaeast', 'eastus')

    # Default search paths for config.json
    DEFAULT_SEARCH_PATHS = [
        ".",  # Current working directory
        "~/.llm_router",  # User home directory (cross-platform via expanduser)
    ]

    # Default endpoints.json location
    DEFAULT_ENDPOINTS_SOURCE = "./endpoints.json"

    @classmethod
    def load(cls, config_path: Optional[str] = None, client_id: Optional[str] = None, environment: Optional[str] = None) -> 'Config':
        """
        Load configuration from file.

        Args:
            config_path: Optional explicit path to config.json.
                        If None, searches default paths.
            client_id: Optional Azure UMI client_id for loading from Azure Storage (production mode)
            environment: Optional environment type ('azure_vm' or 'local')

        Returns:
            Config object

        Raises:
            ConfigurationError: If config not found or invalid
        """
        loader = ConfigLoader(client_id=client_id, environment=environment)

        # If explicit path provided, use it
        if config_path:
            logger.info(f"Loading config from: {config_path}")
            try:
                data = loader.load(config_path)
            except LoaderError as e:
                raise ConfigurationError(f"Failed to load config: {e}") from e
        else:
            # Search default paths
            logger.info("Searching for config.json in default paths")
            found_path = ConfigLoader.find_config("config.json", cls.DEFAULT_SEARCH_PATHS)

            if found_path:
                logger.info(f"Config found at: {found_path}")
                try:
                    data = loader.load(found_path)
                except LoaderError as e:
                    raise ConfigurationError(f"Failed to load config: {e}") from e
            else:
                error_msg = (
                    f"config.json not found in any default path: {cls.DEFAULT_SEARCH_PATHS}. "
                    f"Please provide explicit config_path or create config.json in one of these locations."
                )
                logger.error(error_msg)
                raise ConfigurationError(error_msg)

        # Parse and validate
        try:
            config = cls(
                llm_cloud=data['llm_cloud'],
                llm_provider=data['llm_provider'],
                tier=data.get('tier'),
                endpoints_source=data.get('endpoints_source'),
                environment=data.get('environment'),
                location=data.get('location')
            )

            config.validate()
            logger.info(f"Config loaded: cloud={config.llm_cloud}, provider={config.llm_provider}")
            if config.environment:
                logger.info(f"Environment override from config: {config.environment}")
            if config.location:
                logger.info(f"Location override from config: {config.location}")

            return config

        except KeyError as e:
            error_msg = f"Missing required config field: {e}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg) from e

    @classmethod
    def from_dict(cls, config_dict: dict, environment: Optional[str] = None) -> 'Config':
        """
        Create configuration from a dictionary.

        This method allows passing configuration programmatically instead of
        loading from a file. Useful for integrating with other config systems
        or testing.

        Args:
            config_dict: Dictionary with config values. Required keys:
                        - llm_cloud: str
                        - llm_provider: str
                        Optional keys:
                        - tier: str
                        - endpoints_source: str
                        - environment: str
                        - location: str
            environment: Optional environment override

        Returns:
            Config object

        Raises:
            ConfigurationError: If required fields missing or validation fails

        Example:
            >>> config = Config.from_dict({
            ...     "llm_cloud": "azure",
            ...     "llm_provider": "openai",
            ...     "tier": "gpt-4o-mini"
            ... })
        """
        logger.info("Creating config from dictionary")

        # Parse and validate
        try:
            config = cls(
                llm_cloud=config_dict['llm_cloud'],
                llm_provider=config_dict['llm_provider'],
                tier=config_dict.get('tier'),
                endpoints_source=config_dict.get('endpoints_source'),
                environment=environment or config_dict.get('environment'),
                location=config_dict.get('location')
            )

            config.validate()
            logger.info(f"Config created: cloud={config.llm_cloud}, provider={config.llm_provider}")
            if config.environment:
                logger.info(f"Environment: {config.environment}")
            if config.location:
                logger.info(f"Location: {config.location}")

            return config

        except KeyError as e:
            error_msg = f"Missing required config field in dict: {e}"
            logger.error(error_msg)
            raise ConfigurationError(error_msg) from e

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ConfigurationError: If configuration is invalid
        """
        valid_clouds = ['azure', 'gcp', 'aws']
        valid_providers = ['openai', 'claude', 'gemini']
        valid_environments = ['auto', 'azure_vm', 'local', None]

        if self.llm_cloud not in valid_clouds:
            raise ConfigurationError(
                f"Invalid llm_cloud: {self.llm_cloud}. Must be one of: {valid_clouds}"
            )

        if self.llm_provider not in valid_providers:
            raise ConfigurationError(
                f"Invalid llm_provider: {self.llm_provider}. Must be one of: {valid_providers}"
            )

        # Tier validation: must be a string or None
        # Valid tier names are defined in endpoints.json for each cloud/provider/geo combination
        # Common values: 'gpt-4o-mini', 'claude-opus', 'reasoning', etc.
        if self.tier is not None and not isinstance(self.tier, str):
            raise ConfigurationError(
                f"Invalid tier: {self.tier}. Must be a string (e.g., 'gpt-4o-mini', 'claude-opus', 'reasoning') or None"
            )

        if self.environment not in valid_environments:
            raise ConfigurationError(
                f"Invalid environment: {self.environment}. Must be one of: auto, azure_vm, local, or None"
            )

    def get_endpoints_source(self) -> str:
        """
        Get endpoints source (file or URL).

        Returns:
            Path or URL to endpoints.json
        """
        return self.endpoints_source or self.DEFAULT_ENDPOINTS_SOURCE
