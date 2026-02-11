"""
GCP Vertex AI authenticator using Workload Identity Federation.

Uses google-auth library with external account credentials to automatically
handle Azure token exchange and service account impersonation.
"""

import json
import tempfile
from typing import Dict, Any, Optional
from datetime import datetime

from .base import BaseAuthenticator
from ..core.constants import (
    IMDS_TOKEN_URL,
    IMDS_API_VERSION,
    ARM_RESOURCE,
    GCP_DEFAULT_SCOPES,
    GCP_IAM_CREDENTIALS_BASE_URL,
    GCP_SA_IMPERSONATION_URL_PATTERN,
)
from ..logger import get_logger

logger = get_logger('auth.gcp')


class GCPAuthenticationError(Exception):
    """Raised when GCP authentication fails."""
    pass


class GCPAuthenticator(BaseAuthenticator):
    """Authenticates to GCP Vertex AI using Workload Identity Federation."""

    def __init__(
        self,
        client_id: Optional[str],
        project_id: str,
        audience: str,
        token_url: str,
        service_account: str
    ):
        """
        Initialize GCP authenticator.

        Args:
            client_id: Optional Azure MI client_id. If None, uses system-assigned managed identity.
                      For user-assigned MI, provide the client_id.
            project_id: GCP project ID
            audience: Workload Identity Pool audience
            token_url: GCP STS token exchange URL
            service_account: GCP service account email to impersonate
        """
        self.client_id = client_id
        self.project_id = project_id
        self.audience = audience
        self.token_url = token_url
        self.service_account = service_account
        self._credentials: Optional[Any] = None
        self._expiration: Optional[datetime] = None

        identity_type = "system-assigned" if client_id is None else "user-assigned"
        logger.info(f"GCP authenticator initialized for project: {project_id}")
        logger.info(f"Using {identity_type} Azure managed identity")
        logger.debug(f"Service account: {service_account}")
        if client_id:
            logger.debug(f"Azure client_id: {client_id[:8]}...")

    def authenticate(self) -> Dict[str, Any]:
        """
        Perform authentication and return GCP credentials.

        Returns:
            Dictionary with authentication credentials and google-auth credentials object:
            {
                'credentials': google.auth.credentials.Credentials,
                'project_id': str
            }

        Raises:
            GCPAuthenticationError: If authentication fails
        """
        # Check if we have cached credentials
        if self._credentials is not None:
            logger.debug("Using cached GCP credentials")
            return {
                'credentials': self._credentials,
                'project_id': self.project_id
            }

        logger.info("Creating GCP external account credentials")

        try:
            from google.auth import external_account_authorized_user

            # Create WIF configuration
            wif_config = self._create_wif_config()

            # Load credentials using google-auth
            from google.auth import load_credentials_from_dict

            creds, _ = load_credentials_from_dict(
                wif_config,
                scopes=GCP_DEFAULT_SCOPES
            )

            # Attach quota project
            if hasattr(creds, 'with_quota_project'):
                creds = creds.with_quota_project(self.project_id)

            self._credentials = creds
            logger.info("GCP credentials created successfully")

            return {
                'credentials': creds,
                'project_id': self.project_id
            }

        except Exception as e:
            error_msg = f"Failed to create GCP credentials: {e}"
            logger.error(error_msg)
            raise GCPAuthenticationError(error_msg) from e

    def get_token(self) -> str:
        """
        Get or refresh access token.

        Returns:
            Access token string

        Raises:
            GCPAuthenticationError: If token request fails
        """
        auth_result = self.authenticate()
        creds = auth_result['credentials']

        # Refresh if needed
        if not creds.valid:
            from google.auth.transport.requests import Request
            creds.refresh(Request())

        return creds.token

    def _create_wif_config(self) -> Dict[str, Any]:
        """
        Create Workload Identity Federation configuration.

        Returns:
            WIF configuration dictionary

        Raises:
            GCPAuthenticationError: If configuration creation fails
        """
        logger.debug("Creating WIF configuration")

        # Build IMDS URL for Azure token with optional client_id
        imds_url = (
            f"{IMDS_TOKEN_URL}?"
            f"api-version={IMDS_API_VERSION}&"
            f"resource={ARM_RESOURCE}"
        )

        # Only add client_id for user-assigned managed identity
        if self.client_id:
            imds_url += f"&client_id={self.client_id}"

        wif_config = {
            "universe_domain": "googleapis.com",
            "type": "external_account",
            "audience": self.audience,
            "subject_token_type": "urn:ietf:params:oauth:token-type:jwt",
            "token_url": self.token_url,
            "credential_source": {
                "url": imds_url,
                "headers": {
                    "Metadata": "True"
                },
                "format": {
                    "type": "json",
                    "subject_token_field_name": "access_token"
                }
            },
            "service_account_impersonation_url": GCP_SA_IMPERSONATION_URL_PATTERN.format(
                base=GCP_IAM_CREDENTIALS_BASE_URL,
                sa=self.service_account
            )
        }

        logger.debug("WIF configuration created")
        return wif_config

    def get_project_id(self) -> str:
        """
        Get GCP project ID.

        Returns:
            Project ID string
        """
        return self.project_id
