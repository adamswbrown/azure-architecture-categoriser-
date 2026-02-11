"""
Local development authenticators for Azure, GCP, and AWS.

These authenticators use SDK credential chains (DefaultAzureCredential,
Application Default Credentials, boto3 credential chain) which work on
developer laptops with CLI authentication (az login, gcloud auth, aws configure).
"""

from typing import Dict, Any, Optional
from .base import BaseAuthenticator
from .gcp import GCPAuthenticationError
from ..core.constants import GCP_DEFAULT_SCOPES
from ..logger import get_logger

logger = get_logger('auth.local')


class AzureLocalAuthenticator(BaseAuthenticator):
    """
    Azure authenticator for local development using AzureCliCredential.

    Uses AzureCliCredential which only uses 'az login' credentials.
    This ensures the logged-in user's credentials are used, not system
    managed identity (which DefaultAzureCredential would try first on an Azure VM).
    """

    def __init__(self):
        """Initialize Azure local authenticator."""
        self.client_id = None  # Not needed for AzureCliCredential
        logger.info("Azure local authenticator initialized (will use AzureCliCredential)")

    def authenticate(self) -> Dict[str, Any]:
        """
        Perform authentication and return credentials.

        This method is not used for Azure local dev - the actual credential
        is created in the factory using AzureCliCredential directly.

        Returns:
            Empty dictionary (actual auth handled by azure-identity library)
        """
        logger.debug("Azure local auth uses AzureCliCredential in factory")
        return {}

    def get_token(self) -> str:
        """
        Get access token.

        This method is not used for Azure local dev - tokens are obtained
        via the token provider callback in AsyncAzureOpenAI.

        Returns:
            Empty string
        """
        return ""


class GCPLocalAuthenticator(BaseAuthenticator):
    """
    GCP authenticator for local development using Application Default Credentials.

    Uses google-auth credential chain which tries:
    1. GOOGLE_APPLICATION_CREDENTIALS environment variable (service account JSON)
    2. gcloud CLI auth (gcloud auth application-default login)
    3. GCE metadata service (if on Google Cloud)
    """

    def __init__(self, project_id: str):
        """
        Initialize GCP local authenticator.

        Args:
            project_id: GCP project ID
        """
        self.project_id = project_id
        self._credentials: Optional[Any] = None

        logger.info(f"GCP local authenticator initialized for project: {project_id}")

    def authenticate(self) -> Dict[str, Any]:
        """
        Perform authentication and return GCP credentials.

        Uses Application Default Credentials which automatically tries
        multiple credential sources.

        Returns:
            Dictionary with authentication credentials:
            {
                'credentials': google.auth.credentials.Credentials,
                'project_id': str
            }

        Raises:
            Exception: If authentication fails
        """
        # Check if we have cached credentials
        if self._credentials is not None:
            logger.debug("Using cached GCP credentials")
            return {
                'credentials': self._credentials,
                'project_id': self.project_id
            }

        logger.info("Creating GCP credentials using Application Default Credentials")

        try:
            import google.auth

            # Load default credentials (tries ADC, gcloud, GCE metadata)
            creds, detected_project = google.auth.default(
                scopes=GCP_DEFAULT_SCOPES
            )

            # Use detected project if no project_id was provided
            project = self.project_id or detected_project

            # Attach quota project
            if hasattr(creds, 'with_quota_project'):
                creds = creds.with_quota_project(project)

            self._credentials = creds
            logger.info(f"GCP credentials created successfully for project: {project}")

            return {
                'credentials': creds,
                'project_id': project
            }

        except Exception as e:
            error_msg = f"Failed to create GCP credentials: {e}"
            logger.error(error_msg)
            logger.error("Make sure to run: gcloud auth application-default login")
            raise GCPAuthenticationError(error_msg) from e

    def get_token(self) -> str:
        """
        Get or refresh access token.

        Returns:
            Access token string

        Raises:
            Exception: If token request fails
        """
        auth_result = self.authenticate()
        creds = auth_result['credentials']

        # Refresh if needed
        if not creds.valid:
            from google.auth.transport.requests import Request
            creds.refresh(Request())

        return creds.token


class AWSLocalAuthenticator(BaseAuthenticator):
    """
    AWS authenticator for local development using boto3 credential chain.

    Uses boto3's standard credential chain which tries:
    1. Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
    2. AWS CLI credentials (~/.aws/credentials)
    3. AWS CLI config (~/.aws/config)
    4. IAM Identity Center (SSO)
    5. EC2 instance metadata (if on EC2)
    """

    def __init__(self, region: str):
        """
        Initialize AWS local authenticator.

        Args:
            region: AWS region name (e.g., 'us-east-1', 'ap-southeast-2')
        """
        self.region = region
        logger.info(f"AWS local authenticator initialized for region: {region}")

    def authenticate(self) -> Dict[str, Any]:
        """
        Perform authentication and return AWS credentials.

        This method is not typically called for local dev - instead,
        boto3.Session() with no arguments uses the credential chain automatically.

        However, we return the region for RefreshableBedrockProvider to use.

        Returns:
            Dictionary with region information:
            {
                'region': str
            }
        """
        logger.debug("AWS local auth uses boto3 credential chain")
        return {
            'region': self.region
        }

    def get_token(self) -> str:
        """
        Get AWS session token.

        For local dev, this is not used - boto3 handles credentials internally.

        Returns:
            Empty string
        """
        return ""
