"""
Azure OpenAI authenticator using User Managed Identity.

Gets access token from Azure IMDS for Cognitive Services.
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .base import BaseAuthenticator
from ..core.constants import HTTP_TIMEOUT, TOKEN_EXPIRY_BUFFER
from ..core.imds_client import IMDSClient, IMDSError, IMDSNotAvailableError
from ..logger import get_logger

logger = get_logger('auth.azure')


class AzureAuthenticationError(Exception):
    """Raised when Azure authentication fails."""
    pass


class AzureAuthenticator(BaseAuthenticator):
    """Authenticates to Azure OpenAI using Managed Identity (system or user-assigned)."""

    def __init__(self, client_id: Optional[str], scope: str):
        """
        Initialize Azure authenticator.

        Args:
            client_id: Optional Azure MI client_id. If None, uses system-assigned managed identity.
                      For user-assigned MI, provide the client_id.
            scope: OAuth scope (e.g., 'https://cognitiveservices.azure.com/.default')
        """
        self.client_id = client_id
        self.scope = scope
        self._token: Optional[str] = None
        self._expiration: Optional[datetime] = None

        identity_type = "system-assigned" if client_id is None else "user-assigned"
        logger.info(f"Azure authenticator initialized for scope: {scope}")
        logger.info(f"Using {identity_type} managed identity")
        if client_id:
            logger.debug(f"Client ID: {client_id[:8]}...")

    def authenticate(self) -> Dict[str, Any]:
        """
        Perform authentication and return credentials.

        Returns:
            Dictionary with authentication credentials:
            {
                'access_token': str,
                'token_type': 'Bearer',
                'expires_on': datetime
            }

        Raises:
            AzureAuthenticationError: If authentication fails
        """
        # Check if we have cached token that is still valid
        if self._token and self._is_token_valid():
            logger.debug("Using cached Azure token")
            return {
                'access_token': self._token,
                'token_type': 'Bearer',
                'expires_on': self._expiration
            }

        logger.info("Obtaining new Azure access token")

        # Get new token from IMDS
        token, expiration = self._get_token_from_imds()

        # Cache token
        self._token = token
        self._expiration = expiration

        logger.info(f"Azure token obtained, valid until {expiration.isoformat()}")

        return {
            'access_token': token,
            'token_type': 'Bearer',
            'expires_on': expiration
        }

    def get_token(self) -> str:
        """
        Get or refresh access token.

        Returns:
            Access token string

        Raises:
            AzureAuthenticationError: If token request fails
        """
        credentials = self.authenticate()
        return credentials['access_token']

    def _is_token_valid(self) -> bool:
        """
        Check if cached token is still valid.

        Returns:
            True if token is valid, False otherwise
        """
        if not self._expiration:
            return False

        # Consider token invalid if it expires within the buffer period
        return datetime.now(timezone.utc) + TOKEN_EXPIRY_BUFFER < self._expiration

    def _get_token_from_imds(self) -> tuple[str, datetime]:
        """
        Get access token from Azure IMDS.

        Returns:
            Tuple of (access_token, expiration_datetime)

        Raises:
            AzureAuthenticationError: If token request fails
        """
        logger.debug(f"Requesting Azure token for scope: {self.scope}")

        # IMDS resource parameter should be without the .default suffix
        # e.g., "https://cognitiveservices.azure.com/.default" -> "https://cognitiveservices.azure.com"
        resource = self.scope.replace('/.default', '')

        try:
            access_token, expiration = IMDSClient.get_token_with_expiry(
                resource=resource,
                client_id=self.client_id,
                timeout=HTTP_TIMEOUT
            )

            logger.debug(f"Token obtained: {access_token[:8]}...{access_token[-4:]}")
            logger.debug(f"Token expires at: {expiration.isoformat()}")

            return access_token, expiration

        except (IMDSError, IMDSNotAvailableError) as e:
            error_msg = f"Failed to get Azure token: {e}"
            logger.error(error_msg)
            raise AzureAuthenticationError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error getting Azure token: {e}"
            logger.error(error_msg)
            raise AzureAuthenticationError(error_msg) from e

    def get_authorization_header(self) -> str:
        """
        Get Authorization header value for API requests.

        Returns:
            Authorization header value (e.g., 'Bearer {token}')

        Raises:
            AzureAuthenticationError: If token request fails
        """
        token = self.get_token()
        return f"Bearer {token}"
