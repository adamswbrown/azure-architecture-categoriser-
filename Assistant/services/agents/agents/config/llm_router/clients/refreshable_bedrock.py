"""
Refreshable Bedrock Provider for auto-refreshing AWS temporary credentials.

Wraps PydanticAI's BedrockProvider to automatically refresh credentials when they expire,
enabling long-running chat sessions (>1 hour) with AWS Bedrock.

Supports both production (Azure MI → AWS WIF) and local development (boto3 credential chain).

Update notes:
- Preserved original structure and behavior.
- Added a configured boto3 Bedrock Runtime client (timeouts, keep-alive) and pass it to BedrockProvider.
- Added idle-based client recycle to avoid reusing stale TCP connections after long idle periods (e.g., Azure/NAT idle timeouts).
- Still refreshes STS credentials 5 minutes before expiry (unchanged).
"""

from typing import Optional, Any, Callable
from datetime import datetime, timedelta, timezone
import threading

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from pydantic_ai.providers import Provider
from pydantic_ai.providers.bedrock import BedrockProvider

from ..auth.base import BaseAuthenticator
from ..auth.local import AWSLocalAuthenticator
from ..logger import get_logger

logger = get_logger('clients.refreshable_bedrock')


class RefreshableBedrockClient:
    """
    Proxy wrapper for boto3 BedrockRuntimeClient that auto-refreshes credentials.

    This solves the issue where BedrockConverseModel caches the client reference
    and never re-checks it. By intercepting method calls, we can refresh credentials
    before each API request.

    NOTE (updated):
    - The proxy still ensures we consult the latest provider client before each call.
    - The provider now also recycles the underlying HTTP pool after long idle to avoid
      stale sockets, and uses short connect timeouts to fail fast if a socket is bad.
    """

    def __init__(self, get_client_func: Callable[[], Any]):
        """
        Initialize proxy client.

        Args:
            get_client_func: Function that returns current boto3 client (with fresh credentials)
        """
        self._get_client = get_client_func
        logger.debug("RefreshableBedrockClient proxy initialized")

    def __getattr__(self, name: str) -> Any:
        """
        Intercept attribute access to refresh credentials before method calls.

        Args:
            name: Attribute/method name being accessed

        Returns:
            Attribute from current (possibly refreshed) client
        """
        # Get current client (will refresh/recycle if expired/idle)
        client = self._get_client()

        # Return attribute from client
        return getattr(client, name)


class RefreshableBedrockProvider(Provider[BaseClient]):
    """
    Provider wrapper that auto-refreshes AWS Bedrock credentials.

    Explicitly inherits from pydantic-ai's Provider base class for type safety
    and interface compliance.

    This wrapper solves the boto3 limitation where static temporary credentials
    cannot auto-refresh. It recreates the BedrockProvider when credentials expire,
    matching the auto-refresh behavior of Azure and GCP providers.

    UPDATE (behavioral):
    - In addition to STS refresh, we now also rebuild the boto3 Bedrock Runtime client
      after a configurable idle interval to avoid reusing stale TCP connections that
      may have been closed by NAT/LB devices (common ~4–5 min idle timeouts).
    - We construct the boto3 client with explicit timeouts/keep-alive so the first call
      after idle fails fast (e.g., 3s) rather than hanging for minutes.
    """

    TOKEN_EXPIRY_BUFFER = timedelta(minutes=5)      # Refresh 5 minutes before expiry (unchanged)
    IDLE_REFRESH_INTERVAL = timedelta(seconds=180)  # Recycle HTTP client after 3 min idle (prevents stale sockets)

    def __init__(self, authenticator: BaseAuthenticator, region: str):
        """
        Initialize refreshable Bedrock provider.

        Args:
            authenticator: AWS authenticator instance
            region: AWS region name (e.g., 'ap-southeast-2')
        """
        self.authenticator = authenticator
        self.region = region
        self._provider: Optional[BedrockProvider] = None
        self._expiration: Optional[datetime] = None
        self._proxy_client: Optional[RefreshableBedrockClient] = None

        # Updated: track last client usage to decide when to recycle idle connections.
        self._last_used: Optional[datetime] = None

        # Guard provider/client rebuilds when used by multiple threads.
        self._lock = threading.RLock()

        logger.info(f"RefreshableBedrockProvider initialized for region: {region}")

    # ---------- internal helpers ----------

    def _now(self) -> datetime:
        """UTC 'now' helper (centralized for clarity & testing)."""
        return datetime.now(timezone.utc)

    def _mk_runtime_client(self, credentials: Optional[dict] = None) -> BaseClient:
        """
        Build a boto3 bedrock-runtime client with sane timeouts and keep-alive.

        Args:
            credentials: Optional AWS credentials dict with AccessKeyId, SecretAccessKey, SessionToken

        Returns:
            Configured boto3 bedrock-runtime client

        Rationale:
        - Short connect_timeout ensures we fail fast if a kept-alive socket was silently
          closed by an upstream NAT/LB during idle.
        - Keep-alive stays enabled so active sessions avoid unnecessary TCP/TLS handshakes.
        - We do NOT need to re-authenticate when a TCP connection is dropped; we just rebuild
          the HTTP pool (via new client) unless STS is actually expiring.
        """
        cfg = Config(
            retries={"max_attempts": 3, "mode": "standard"},
            connect_timeout=3,     # fail fast on stale TCP
            read_timeout=60,       # typical Bedrock runtime read window
            tcp_keepalive=True,
            max_pool_connections=50,
        )
        if credentials:
            return boto3.client(
                "bedrock-runtime",
                region_name=self.region,
                aws_access_key_id=credentials["AccessKeyId"],
                aws_secret_access_key=credentials["SecretAccessKey"],
                aws_session_token=credentials["SessionToken"],
                config=cfg,
            )
        # Local/dev path: rely on default credential chain.
        return boto3.client("bedrock-runtime", region_name=self.region, config=cfg)

    def _maybe_recycle_runtime_client(self):
        """
        After an idle window, recycle the underlying HTTP connection pool to avoid
        reusing stale sockets closed by NAT/LB (e.g., ~4–5 min Azure outbound idle).

        NOTE:
        - This does not force re-authentication. We recreate the provider with the
          current or refreshed STS creds as needed.
        - This keeps steady-state overhead at ~zero (only triggers after idle).
        """
        if not self._provider or not self._last_used:
            if not self._provider:
                logger.warning("_maybe_recycle_runtime_client called before provider initialized")
            return
        idle = self._now() - self._last_used
        if idle > self.IDLE_REFRESH_INTERVAL:
            logger.info(
                "Idle %.0fs > threshold; recycling bedrock-runtime client",
                idle.total_seconds(),
            )
            # Recreate provider with same auth, without touching STS unless expired.
            self._refresh_provider()
    
    @property
    def provider(self) -> BedrockProvider:
        """
        Get BedrockProvider with auto-refreshing credentials.
        Handles both expiry-based refresh and idle-based connection recycling.

        Returns:
            BedrockProvider instance with refreshable credentials
        """
        with self._lock:
            if self._provider is None or self._is_expired():
                logger.info("Provider expired or not initialized, refreshing provider")
                self._refresh_provider()
            else:
                # Credentials are valid; ensure we don't reuse stale TCP connections after idle
                self._maybe_recycle_runtime_client()

            # Update last used timestamp for idle detection
            self._last_used = self._now()

            if self._provider is None:
                raise RuntimeError("Provider must not be None after refresh")

        return self._provider

    def _get_current_client(self):
        """
        Get current boto3 client, refreshing if needed.

        Returns:
            boto3 BedrockRuntimeClient with fresh credentials and a fresh HTTP pool if idle
        """
        # Must hold lock for entire operation to prevent race condition:
        # Another thread could refresh provider between checking and accessing .client
        with self._lock:
            if self._provider is None or self._is_expired():
                logger.info("Credentials expired or not initialized, refreshing provider")
                self._refresh_provider()
            else:
                # Credentials are valid; ensure we don't reuse stale TCP connections after idle
                self._maybe_recycle_runtime_client()

            self._last_used = self._now()

            if self._provider is None:
                raise RuntimeError("Provider must not be None after refresh")

            # Cache client reference while under lock to prevent race condition
            return self._provider.client

    @property
    def client(self):
        """
        Get boto3 Bedrock Runtime client proxy that auto-refreshes credentials.

        Returns:
            RefreshableBedrockClient proxy that checks expiration/idle before each API call
        """
        # Create proxy once and reuse it
        if self._proxy_client is None:
            self._proxy_client = RefreshableBedrockClient(self._get_current_client)
            logger.debug("Created RefreshableBedrockClient proxy")

        return self._proxy_client

    @property
    def name(self) -> str:
        """Get provider name."""
        return 'bedrock'

    @property
    def base_url(self) -> str:
        """
        Get base URL for Bedrock API.

        Returns:
            Bedrock endpoint URL
        """
        return self.provider.base_url

    def model_profile(self, model_name: str):
        """
        Get model profile for the given model name.

        Args:
            model_name: Model name (e.g., 'anthropic.claude-3-5-sonnet-20240620-v1:0')

        Returns:
            Model profile or None
        """
        return self.provider.model_profile(model_name)

    def _is_expired(self) -> bool:
        """
        Check if credentials are expired or about to expire.

        Returns:
            True if credentials need refresh, False otherwise
        """
        if not self._expiration:
            return True

        # Consider expired if within buffer period
        return self._now() + self.TOKEN_EXPIRY_BUFFER >= self._expiration

    def _refresh_provider(self) -> None:
        """
        Refresh AWS credentials and recreate BedrockProvider.

        For production (Azure MI → AWS WIF):
        1. Calls authenticator to get fresh temporary credentials
        2. Creates new BedrockProvider with those credentials
        3. Updates expiration time for next refresh check

        For local development (boto3 credential chain):
        1. Creates BedrockProvider with a configured boto3 bedrock-runtime client
           (uses boto3 credential chain: env vars, AWS CLI, IAM roles, etc.)
        2. Sets a distant expiration since boto3/IMDS/role can refresh automatically

        NOTE (updated):
        - We now pass a pre-configured boto3 client (with timeouts/keep-alive) into
          BedrockProvider so we control connection behavior. This does not change
          your federation logic; it only improves networking resilience.

        Raises:
            Exception: If credential refresh fails (authenticator errors, etc.)
        """

        try:
            # Check if this is local development
            if isinstance(self.authenticator, AWSLocalAuthenticator):
                logger.info("Creating AWS Bedrock provider using boto3 credential chain (local dev)")

                # Create provider with configured boto3 client - boto3 will use credential chain
                # (env vars, AWS CLI, IAM roles, etc.)
                br_client = self._mk_runtime_client()
                self._provider = BedrockProvider(bedrock_client=br_client)

                # Set expiration far in the future since boto3 handles refresh automatically
                self._expiration = self._now() + timedelta(days=365)

                logger.info("Bedrock provider created with boto3 credential chain")
                logger.info("Credentials will be auto-managed by boto3 (AWS CLI, env vars, or IAM roles)")

            else:
                # Production: Azure MI → AWS WIF
                logger.info("Refreshing AWS Bedrock credentials (Azure MI → AWS WIF)")

                # Get fresh credentials from authenticator
                credentials = self.authenticator.authenticate()

                # Build configured boto3 runtime client using those temporary creds
                br_client = self._mk_runtime_client(credentials)

                # Create new provider with pre-configured client (so our timeouts apply)
                self._provider = BedrockProvider(bedrock_client=br_client)

                # Update expiration time
                self._expiration = credentials.get('Expiration')
                if self._expiration is None:
                    raise ValueError("Authenticator must return 'Expiration' in credentials")
                if not isinstance(self._expiration, datetime):
                    raise TypeError(f"Expiration must be datetime, got {type(self._expiration).__name__}")
                logger.info(f"Bedrock provider refreshed, credentials valid until {self._expiration.isoformat()}")
                logger.debug(f"Access Key ID: {credentials['AccessKeyId'][:8]}...")
        except Exception as e:
            logger.error(f"Failed to refresh provider: {e}")
            # Don't update _provider or _expiration on failure - keep existing state
            raise

        # Reset last-used timestamp after (re)creation
        self._last_used = self._now()

