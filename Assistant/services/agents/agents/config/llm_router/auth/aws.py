"""
AWS Bedrock authenticator using AssumeRoleWithWebIdentity.

Uses Azure UMI token to obtain temporary AWS credentials via STS.
"""

import json
import ssl
import urllib.request
import urllib.error
import urllib.parse
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from xml.etree import ElementTree as ET

import certifi

from .base import BaseAuthenticator
from ..core.constants import (
    ARM_RESOURCE,
    HTTP_TIMEOUT,
    TOKEN_EXPIRY_BUFFER,
    AWS_STS_URL,
)
from ..core.imds_client import IMDSClient, IMDSError, IMDSNotAvailableError
from ..logger import get_logger

logger = get_logger('auth.aws')


class AWSAuthenticationError(Exception):
    """Raised when AWS authentication fails."""
    pass


class AWSAuthenticator(BaseAuthenticator):
    """Authenticates to AWS Bedrock using Azure Managed Identity and Web Identity Federation."""

    def __init__(self, client_id: Optional[str], role_arn: str, vm_name: Optional[str] = None):
        """
        Initialize AWS authenticator.

        Args:
            client_id: Optional Azure MI client_id. If None, uses system-assigned managed identity.
                      For user-assigned MI, provide the client_id.
            role_arn: AWS IAM role ARN to assume
            vm_name: Optional VM name for session identification (used in RoleSessionName)
        """
        self.client_id = client_id
        self.role_arn = role_arn
        self.vm_name = vm_name or "unknown"
        self._credentials: Optional[Dict[str, Any]] = None
        self._expiration: Optional[datetime] = None

        identity_type = "system-assigned" if client_id is None else "user-assigned"
        logger.info(f"AWS authenticator initialized for role: {role_arn}")
        logger.info(f"Using {identity_type} Azure managed identity")
        if client_id:
            logger.debug(f"Azure client_id: {client_id[:8]}...")
        logger.debug(f"VM name for session: {self.vm_name}")

    def authenticate(self) -> Dict[str, Any]:
        """
        Perform authentication and return AWS credentials.

        Returns:
            Dictionary with AWS credentials:
            {
                'AccessKeyId': str,
                'SecretAccessKey': str,
                'SessionToken': str,
                'Expiration': datetime
            }

        Raises:
            AWSAuthenticationError: If authentication fails
        """
        # Check if we have cached credentials that are still valid
        if self._credentials and self._is_token_valid():
            logger.debug("Using cached AWS credentials")
            return self._credentials

        logger.info("Obtaining new AWS credentials")

        # Get Azure UMI token
        azure_token = self._get_azure_token()

        # Exchange for AWS credentials
        credentials = self._assume_role_with_web_identity(azure_token)

        # Cache credentials
        self._credentials = credentials
        self._expiration = credentials['Expiration']

        logger.info(f"AWS credentials obtained, valid until {self._expiration.isoformat()}")
        return credentials

    def get_token(self) -> str:
        """
        Get AWS session token.

        Returns:
            AWS session token string

        Raises:
            AWSAuthenticationError: If authentication fails
        """
        credentials = self.authenticate()
        return credentials['SessionToken']

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

    def _get_azure_token(self) -> str:
        """
        Get Azure managed identity access token from IMDS.

        The token is requested with default Azure AD resource and will be
        used as a web identity token for AWS STS.

        Returns:
            Azure access token

        Raises:
            AWSAuthenticationError: If token request fails
        """
        logger.debug("Requesting Azure token for AWS authentication")

        try:
            data = IMDSClient.get_token(
                resource=ARM_RESOURCE,
                client_id=self.client_id,
                timeout=HTTP_TIMEOUT
            )
            token = data['access_token']

            logger.debug(f"Azure token obtained: {token[:8]}...{token[-4:]}")
            return token

        except (IMDSError, IMDSNotAvailableError) as e:
            error_msg = f"Failed to get Azure token: {e}"
            logger.error(error_msg)
            raise AWSAuthenticationError(error_msg) from e
        except KeyError as e:
            error_msg = f"Invalid Azure token response: {e}"
            logger.error(error_msg)
            raise AWSAuthenticationError(error_msg) from e

    def _assume_role_with_web_identity(self, web_identity_token: str) -> Dict[str, Any]:
        """
        Assume AWS role using web identity token.

        Args:
            web_identity_token: Azure access token

        Returns:
            AWS credentials dictionary

        Raises:
            AWSAuthenticationError: If role assumption fails
        """
        logger.debug(f"Assuming AWS role: {self.role_arn}")

        # Build STS AssumeRoleWithWebIdentity request
        # Include VM name in session for CloudTrail auditing
        session_name = f'llm-router-{self.vm_name}-{datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")}'

        params = {
            'Action': 'AssumeRoleWithWebIdentity',
            'RoleArn': self.role_arn,
            'RoleSessionName': session_name,
            'WebIdentityToken': web_identity_token,
            'Version': '2011-06-15'
        }

        logger.debug(f"AWS session name: {session_name}")

        # Encode parameters
        param_string = '&'.join(f'{k}={urllib.parse.quote(str(v), safe="")}' for k, v in params.items())
        url = f"{AWS_STS_URL}?{param_string}"

        try:
            req = urllib.request.Request(url)

            # Create SSL context with certifi certificate bundle (fixes Windows SSL issues)
            ssl_context = ssl.create_default_context(cafile=certifi.where())

            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ssl_context) as response:
                xml_response = response.read().decode('utf-8')

            # Parse XML response
            credentials = self._parse_sts_response(xml_response)

            logger.info(f"Successfully assumed role: {self.role_arn}")
            logger.debug(f"Access Key ID: {credentials['AccessKeyId'][:8]}...")
            return credentials

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            error_msg = f"AWS STS error ({e.code}): {self._extract_sts_error(error_body)}"
            logger.error(error_msg)
            raise AWSAuthenticationError(error_msg) from e
        except urllib.error.URLError as e:
            error_msg = f"Failed to call AWS STS: {e}"
            logger.error(error_msg)
            raise AWSAuthenticationError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to assume AWS role: {e}"
            logger.error(error_msg)
            raise AWSAuthenticationError(error_msg) from e

    def _parse_sts_response(self, xml_response: str) -> Dict[str, Any]:
        """
        Parse AWS STS XML response.

        Args:
            xml_response: XML response from STS

        Returns:
            Credentials dictionary

        Raises:
            AWSAuthenticationError: If parsing fails
        """
        try:
            root = ET.fromstring(xml_response)

            # Define namespace
            ns = {'aws': 'https://sts.amazonaws.com/doc/2011-06-15/'}

            # Extract credentials
            creds_elem = root.find('.//aws:Credentials', ns)
            if creds_elem is None:
                raise AWSAuthenticationError("Credentials not found in STS response")

            access_key_id = creds_elem.find('aws:AccessKeyId', ns).text
            secret_access_key = creds_elem.find('aws:SecretAccessKey', ns).text
            session_token = creds_elem.find('aws:SessionToken', ns).text
            expiration_str = creds_elem.find('aws:Expiration', ns).text

            # Parse expiration timestamp as timezone-aware UTC datetime
            expiration = datetime.strptime(expiration_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)

            return {
                'AccessKeyId': access_key_id,
                'SecretAccessKey': secret_access_key,
                'SessionToken': session_token,
                'Expiration': expiration
            }

        except (ET.ParseError, AttributeError, ValueError) as e:
            error_msg = f"Failed to parse STS response: {e}"
            logger.error(error_msg)
            raise AWSAuthenticationError(error_msg) from e

    def _extract_sts_error(self, xml_response: str) -> str:
        """
        Extract error message from STS error response.

        Args:
            xml_response: XML error response from STS

        Returns:
            Error message string
        """
        try:
            root = ET.fromstring(xml_response)
            ns = {'aws': 'https://sts.amazonaws.com/doc/2011-06-15/'}

            error_elem = root.find('.//aws:Error', ns)
            if error_elem is not None:
                code = error_elem.find('aws:Code', ns)
                message = error_elem.find('aws:Message', ns)

                if code is not None and message is not None:
                    return f"{code.text}: {message.text}"

            return xml_response

        except Exception:
            return xml_response
