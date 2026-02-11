"""
Standardized error parsing for authentication failures.

Provides consistent error messages and troubleshooting guidance
across all cloud providers.
"""

from typing import Optional, Dict, Any
import re
from ..logger import get_logger

logger = get_logger('auth.error_parser')


class AuthErrorParser:
    """
    Parses authentication errors and provides standardized messages.

    Helps users troubleshoot authentication failures with actionable guidance.
    """

    # Common error patterns
    PATTERNS = {
        'token_expired': [
            r'token.*expired',
            r'expired.*token',
            r'TokenExpiredError',
        ],
        'permission_denied': [
            r'permission.*denied',
            r'access.*denied',
            r'unauthorized',
            r'forbidden',
            r'lacks.*required.*action',
            r'not authorized',
        ],
        'network_timeout': [
            r'timeout',
            r'timed out',
            r'connection.*timeout',
            r'read.*timeout',
        ],
        'network_failure': [
            r'connection.*refused',
            r'connection.*failed',
            r'network.*unreachable',
            r'name resolution failed',
            r'dns.*failed',
        ],
        'invalid_credentials': [
            r'invalid.*credentials',
            r'invalid.*token',
            r'authentication.*failed',
            r'invalid.*client',
        ],
        'missing_config': [
            r'missing.*configuration',
            r'required.*not.*provided',
            r'not.*found',
            r'does not exist',
        ],
        'role_assumption_failed': [
            r'AssumeRoleWithWebIdentity',
            r'assume.*role.*failed',
            r'STS.*error',
        ],
        'managed_identity_failed': [
            r'managed.*identity',
            r'IMDS.*failed',
            r'metadata.*service',
        ],
        'wif_failed': [
            r'workload.*identity',
            r'token.*exchange.*failed',
            r'external.*account',
        ],
    }

    # Troubleshooting guidance for each error type
    GUIDANCE = {
        'token_expired': (
            "Token has expired. This should auto-refresh. "
            "If the error persists, check if managed identity has proper permissions."
        ),
        'permission_denied': (
            "Missing required permissions. Verify:\n"
            "  1. Managed identity has correct RBAC role assignments\n"
            "  2. Role assignments have propagated (can take 5-30 minutes)\n"
            "  3. Resource-level permissions are configured correctly"
        ),
        'network_timeout': (
            "Network timeout while connecting to authentication service. "
            "Check network connectivity and firewall rules."
        ),
        'network_failure': (
            "Network connection failed. Verify:\n"
            "  1. VM has internet connectivity\n"
            "  2. DNS resolution is working\n"
            "  3. No firewall blocking authentication endpoints"
        ),
        'invalid_credentials': (
            "Invalid credentials provided. Check:\n"
            "  1. Managed identity is correctly configured\n"
            "  2. Client ID matches the assigned identity\n"
            "  3. Workload Identity Federation configuration is correct"
        ),
        'missing_config': (
            "Missing required configuration. Verify:\n"
            "  1. endpoints.json has all required auth fields\n"
            "  2. config.json has correct cloud provider settings\n"
            "  3. All WIF configuration parameters are present"
        ),
        'role_assumption_failed': (
            "AWS role assumption failed. Verify:\n"
            "  1. AWS trust policy allows Azure federated identity\n"
            "  2. Role ARN is correct in endpoints.json\n"
            "  3. Azure managed identity is configured in trust policy\n"
            "  4. Trust policy uses StringLike condition (not StringEquals)"
        ),
        'managed_identity_failed': (
            "Azure managed identity access failed. Check:\n"
            "  1. VM has managed identity enabled\n"
            "  2. Identity follows {vm_name}-mi naming pattern\n"
            "  3. IMDS endpoint (169.254.169.254) is accessible"
        ),
        'wif_failed': (
            "Workload Identity Federation failed. Verify:\n"
            "  1. WIF configuration in endpoints.json is correct\n"
            "  2. GCP service account exists and has permissions\n"
            "  3. Workload Identity Pool is properly configured\n"
            "  4. Azure managed identity can exchange tokens"
        ),
    }

    @classmethod
    def parse(cls, error: Exception, cloud: Optional[str] = None) -> Dict[str, Any]:
        """
        Parse error and return standardized error information.

        Args:
            error: The exception that was raised
            cloud: Optional cloud provider context ('aws', 'azure', 'gcp')

        Returns:
            Dictionary with:
                - error_type: Categorized error type
                - original_message: Original error message
                - user_message: User-friendly error message
                - guidance: Troubleshooting steps
                - cloud: Cloud provider (if provided)
        """
        error_str = str(error).lower()
        error_type = cls._categorize_error(error_str)

        # Build user-friendly message
        user_message = cls._build_user_message(error_type, cloud)

        # Get troubleshooting guidance
        guidance = cls.GUIDANCE.get(error_type, "Check logs for more details.")

        result = {
            'error_type': error_type,
            'original_message': str(error),
            'user_message': user_message,
            'guidance': guidance,
        }

        if cloud:
            result['cloud'] = cloud

        logger.debug(f"Parsed error: type={error_type}, cloud={cloud}")
        return result

    @classmethod
    def _categorize_error(cls, error_str: str) -> str:
        """
        Categorize error based on message patterns.

        Args:
            error_str: Lowercase error message

        Returns:
            Error category string
        """
        for category, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_str, re.IGNORECASE):
                    return category

        return 'unknown'

    @classmethod
    def _build_user_message(cls, error_type: str, cloud: Optional[str]) -> str:
        """
        Build user-friendly error message.

        Args:
            error_type: Categorized error type
            cloud: Optional cloud provider

        Returns:
            User-friendly error message
        """
        cloud_str = f" ({cloud.upper()})" if cloud else ""

        messages = {
            'token_expired': f"Authentication token expired{cloud_str}",
            'permission_denied': f"Permission denied{cloud_str}",
            'network_timeout': f"Network timeout while authenticating{cloud_str}",
            'network_failure': f"Network connection failed{cloud_str}",
            'invalid_credentials': f"Invalid credentials{cloud_str}",
            'missing_config': f"Missing authentication configuration{cloud_str}",
            'role_assumption_failed': "AWS role assumption failed (WIF)",
            'managed_identity_failed': "Azure managed identity access failed",
            'wif_failed': f"Workload Identity Federation failed{cloud_str}",
            'unknown': f"Authentication failed{cloud_str}",
        }

        return messages.get(error_type, f"Authentication error{cloud_str}")

    @classmethod
    def format_error(cls, error: Exception, cloud: Optional[str] = None) -> str:
        """
        Format error as user-friendly string with guidance.

        Args:
            error: The exception that was raised
            cloud: Optional cloud provider context

        Returns:
            Formatted error string with troubleshooting steps
        """
        parsed = cls.parse(error, cloud)

        lines = [
            f"❌ {parsed['user_message']}",
            f"",
            f"Original error: {parsed['original_message']}",
            f"",
            f"Troubleshooting:",
            parsed['guidance'],
        ]

        return "\n".join(lines)

    @classmethod
    def log_error(cls, error: Exception, cloud: Optional[str] = None) -> None:
        """
        Log error with parsed details.

        Args:
            error: The exception that was raised
            cloud: Optional cloud provider context
        """
        parsed = cls.parse(error, cloud)

        logger.error(
            f"Authentication error: {parsed['user_message']} "
            f"(type={parsed['error_type']}, cloud={cloud})"
        )
        logger.debug(f"Original error: {parsed['original_message']}")
        logger.debug(f"Guidance: {parsed['guidance']}")


# Convenience functions
def parse_auth_error(error: Exception, cloud: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse authentication error.

    Convenience wrapper for AuthErrorParser.parse().
    """
    return AuthErrorParser.parse(error, cloud)


def format_auth_error(error: Exception, cloud: Optional[str] = None) -> str:
    """
    Format authentication error as user-friendly string.

    Convenience wrapper for AuthErrorParser.format_error().
    """
    return AuthErrorParser.format_error(error, cloud)


def log_auth_error(error: Exception, cloud: Optional[str] = None) -> None:
    """
    Log authentication error with parsed details.

    Convenience wrapper for AuthErrorParser.log_error().
    """
    AuthErrorParser.log_error(error, cloud)
