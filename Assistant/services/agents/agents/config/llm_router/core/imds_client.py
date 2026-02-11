"""
Azure Instance Metadata Service (IMDS) client.

Provides centralized access to Azure IMDS endpoints for:
- OAuth token retrieval (managed identity authentication)
- Instance metadata (VM information, location, etc.)

This abstraction reduces code duplication and provides consistent error handling
across all IMDS operations in the llm_router module.
"""

import json
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .constants import (
    IMDS_TOKEN_URL,
    IMDS_INSTANCE_URL,
    IMDS_API_VERSION,
    IMDS_INSTANCE_API_VERSION,
    IMDS_TIMEOUT,
)
from ..logger import get_logger

logger = get_logger('core.imds_client')


class IMDSError(Exception):
    """Base exception for IMDS-related errors."""
    pass


class IMDSTimeoutError(IMDSError):
    """Raised when IMDS request times out."""
    pass


class IMDSNotAvailableError(IMDSError):
    """Raised when IMDS service is not available (not running on Azure VM)."""
    pass


class IMDSClient:
    """
    Client for Azure Instance Metadata Service (IMDS).

    Provides methods for retrieving OAuth tokens and instance metadata
    from the Azure IMDS endpoint (http://169.254.169.254).

    All methods are static as IMDS is a singleton service on Azure VMs.
    """

    @staticmethod
    def get_token(
        resource: str,
        client_id: Optional[str] = None,
        api_version: str = IMDS_API_VERSION,
        timeout: int = IMDS_TIMEOUT
    ) -> Dict[str, Any]:
        """
        Get OAuth access token from IMDS.

        Args:
            resource: OAuth resource URL (e.g., 'https://management.azure.com/')
            client_id: Optional client ID for user-assigned managed identity.
                      If None, uses system-assigned managed identity.
            api_version: IMDS API version (default: from constants)
            timeout: Request timeout in seconds (default: from constants)

        Returns:
            Dictionary containing:
            - access_token: JWT access token
            - client_id: Client ID of the identity
            - expires_on: Token expiration timestamp (string)
            - expires_in: Seconds until expiration (string)
            - resource: Resource the token is for
            - token_type: Token type (usually "Bearer")

        Raises:
            IMDSError: If token request fails
            IMDSTimeoutError: If request times out
            IMDSNotAvailableError: If IMDS is not accessible (not on Azure VM)
        """
        logger.debug(f"Requesting IMDS token for resource: {resource}")

        # Build URL with required parameters
        url = (
            f"{IMDS_TOKEN_URL}?"
            f"api-version={api_version}&"
            f"resource={urllib.parse.quote(resource, safe='')}"
        )

        # Add client_id for user-assigned managed identity
        if client_id:
            url += f"&client_id={client_id}"
            logger.debug(f"Using user-assigned MI with client_id: {client_id[:8]}...")
        else:
            logger.debug("Using system-assigned managed identity")

        try:
            req = urllib.request.Request(url)
            req.add_header('Metadata', 'true')

            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

            logger.debug(f"Token obtained: {data.get('access_token', '')[:8]}...")
            return data

        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                # 400/404 usually means no managed identity assigned
                error_body = e.read().decode('utf-8')
                error_msg = f"No managed identity available (HTTP {e.code}): {error_body}"
                logger.error(error_msg)
                raise IMDSNotAvailableError(error_msg) from e
            else:
                error_body = e.read().decode('utf-8')
                error_msg = f"HTTP error getting IMDS token ({e.code}): {error_body}"
                logger.error(error_msg)
                raise IMDSError(error_msg) from e

        except urllib.error.URLError as e:
            # Connection refused, timeout, or network error
            error_msg = f"IMDS not accessible: {e}"
            logger.error(error_msg)
            raise IMDSNotAvailableError(error_msg) from e

        except (KeyError, json.JSONDecodeError, ValueError) as e:
            error_msg = f"Invalid IMDS token response: {e}"
            logger.error(error_msg)
            raise IMDSError(error_msg) from e

    @staticmethod
    def get_token_with_expiry(
        resource: str,
        client_id: Optional[str] = None,
        api_version: str = IMDS_API_VERSION,
        timeout: int = IMDS_TIMEOUT
    ) -> tuple[str, datetime]:
        """
        Get OAuth access token with parsed expiration datetime.

        Convenience method that returns the access token and expiration
        as a timezone-aware datetime object.

        Args:
            resource: OAuth resource URL
            client_id: Optional client ID for user-assigned MI
            api_version: IMDS API version
            timeout: Request timeout in seconds

        Returns:
            Tuple of (access_token, expiration_datetime)
            - access_token: JWT token string
            - expiration_datetime: Timezone-aware datetime (UTC)

        Raises:
            IMDSError: If token request fails
        """
        data = IMDSClient.get_token(resource, client_id, api_version, timeout)

        access_token = data['access_token']
        expires_on = int(data['expires_on'])  # Unix timestamp

        # Convert to timezone-aware datetime (UTC)
        expiration = datetime.fromtimestamp(expires_on, tz=timezone.utc)

        return access_token, expiration

    @staticmethod
    def get_instance_metadata(
        api_version: str = IMDS_INSTANCE_API_VERSION,
        timeout: int = IMDS_TIMEOUT
    ) -> Dict[str, Any]:
        """
        Get instance metadata from IMDS.

        Returns information about the current VM including:
        - Compute: VM size, location, name, OS, etc.
        - Network: IP addresses, network interfaces, etc.

        Args:
            api_version: IMDS instance API version (default: from constants)
            timeout: Request timeout in seconds (default: from constants)

        Returns:
            Dictionary containing compute and network metadata

        Raises:
            IMDSError: If metadata request fails
            IMDSNotAvailableError: If IMDS is not accessible
        """
        logger.debug("Requesting IMDS instance metadata")

        url = f"{IMDS_INSTANCE_URL}?api-version={api_version}&format=json"

        try:
            req = urllib.request.Request(url)
            req.add_header('Metadata', 'true')

            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode('utf-8'))

            logger.debug(f"Instance metadata retrieved: VM name={data.get('compute', {}).get('name')}")
            return data

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            error_msg = f"HTTP error getting IMDS metadata ({e.code}): {error_body}"
            logger.error(error_msg)
            raise IMDSError(error_msg) from e

        except urllib.error.URLError as e:
            error_msg = f"IMDS not accessible: {e}"
            logger.error(error_msg)
            raise IMDSNotAvailableError(error_msg) from e

        except (KeyError, json.JSONDecodeError, ValueError) as e:
            error_msg = f"Invalid IMDS metadata response: {e}"
            logger.error(error_msg)
            raise IMDSError(error_msg) from e

    @staticmethod
    def is_available(timeout: int = 2) -> bool:
        """
        Check if IMDS is available (quick check).

        Attempts a minimal IMDS request to determine if the service is accessible.
        Uses a short timeout for quick detection.

        Args:
            timeout: Request timeout in seconds (default: 2 for quick check)

        Returns:
            True if IMDS is accessible, False otherwise
        """
        try:
            IMDSClient.get_instance_metadata(timeout=timeout)
            return True
        except (IMDSError, IMDSNotAvailableError):
            return False

    @staticmethod
    def extract_vm_metadata(instance_metadata: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract common VM metadata fields from IMDS response.

        Args:
            instance_metadata: Full IMDS instance metadata response

        Returns:
            Dictionary with commonly used fields:
            - name: VM name
            - location: Azure region
            - vmId: Unique VM identifier
            - resourceGroupName: Resource group name
            - subscriptionId: Subscription ID
            - tags: VM tags (if any)

        Raises:
            KeyError: If required fields are missing
        """
        compute = instance_metadata.get('compute', {})

        return {
            'name': compute['name'],
            'location': compute['location'],
            'vmId': compute['vmId'],
            'resourceGroupName': compute['resourceGroupName'],
            'subscriptionId': compute['subscriptionId'],
            'tags': compute.get('tags', ''),
        }
