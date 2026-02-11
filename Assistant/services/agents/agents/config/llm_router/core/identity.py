"""
Azure System-assigned Managed Identity (SMI) discovery and management.

Discovers the VM's system-assigned managed identity via IMDS.
"""

from typing import Optional
from dataclasses import dataclass

from .constants import ARM_RESOURCE
from .imds_client import IMDSClient, IMDSError, IMDSNotAvailableError
from ..logger import get_logger

logger = get_logger('core.identity')


class IdentityError(Exception):
    """Base exception for identity-related errors."""
    pass


class IdentityNotFoundError(IdentityError):
    """Raised when system-assigned managed identity is not enabled."""
    pass


@dataclass
class ManagedIdentity:
    """System-assigned Managed Identity information."""
    client_id: str
    principal_id: str
    resource_id: str
    identity_type: str = 'system'  # Always 'system' for system-assigned identity

    @property
    def name(self) -> str:
        """Get identity name (VM name for system identity)."""
        # For system identity, resource_id is just the VM name
        if '/' in self.resource_id:
            return self.resource_id.split('/')[-1]
        return self.resource_id

    def __str__(self) -> str:
        return f"Identity(type={self.identity_type}, name={self.name}, client_id={self.client_id[:8] if self.client_id else 'N/A'}...)"


class IdentityDiscovery:
    """Discovers Azure System-assigned Managed Identity for the VM."""

    def __init__(self, vm_name: str):
        """
        Initialize identity discovery.

        Args:
            vm_name: Name of the VM (used for logging and error messages)
        """
        self.vm_name = vm_name.lower()
        self._identity: Optional[ManagedIdentity] = None
        self._smi_attempted: bool = False  # Track if we tried SMI discovery


    def try_system_identity(self) -> Optional[ManagedIdentity]:
        """
        Try to use system-assigned managed identity.

        Makes a single IMDS request without client_id to check if SMI is enabled.
        If successful, extracts identity information from the token and response.

        Returns:
            ManagedIdentity if SMI is enabled, None otherwise

        Raises:
            IdentityError: If IMDS request fails for reasons other than missing SMI
        """
        if self._smi_attempted:
            return None  # Already tried, didn't work

        self._smi_attempted = True
        logger.info("Attempting to use system-assigned managed identity")

        try:
            # Request token without client_id (SMI mode)
            data = IMDSClient.get_token(resource=ARM_RESOURCE)

            # Extract identity information from IMDS response
            client_id = data.get('client_id')  # Returned in IMDS response for SMI

            if not client_id:
                logger.warning("System identity response missing client_id")
                return None

            # Create ManagedIdentity object
            # For SMI: principal_id = client_id, resource_id = vm_name (name property uses last segment)
            identity = ManagedIdentity(
                client_id=client_id,
                principal_id=client_id,  # For SMI, principal_id equals client_id
                resource_id=self.vm_name,  # Simplified: just use VM name
                identity_type='system'
            )

            logger.info(f"System-assigned identity found: {self.vm_name}")
            logger.info(f"Client ID: {client_id[:8]}...{client_id[-4:]}")

            return identity

        except IMDSNotAvailableError as e:
            # No system-assigned identity enabled
            logger.debug(f"No system-assigned identity enabled: {e}")
            return None

        except IMDSError as e:
            # Other IMDS errors
            logger.warning(f"Error checking system identity: {e}")
            return None

        except KeyError as e:
            # Token parsing errors
            logger.warning(f"Error parsing system identity token: {e}")
            return None

        except Exception as e:
            # Unexpected errors
            logger.warning(f"Unexpected error checking system identity: {e}")
            return None

    def get_identity(self) -> ManagedIdentity:
        """
        Get system-assigned managed identity.

        Returns:
            ManagedIdentity object with system-assigned identity information

        Raises:
            IdentityNotFoundError: If system-assigned identity is not enabled
            IdentityError: If discovery fails
        """
        # Return cached identity if already discovered
        if self._identity is not None:
            logger.debug("Returning cached system identity")
            return self._identity

        logger.info("Discovering system-assigned managed identity")
        identity = self.try_system_identity()

        if identity is None:
            error_msg = (
                f"System-assigned managed identity not enabled on VM '{self.vm_name}'.\n"
                f"To enable:\n"
                f"  az vm identity assign --name {self.vm_name} --resource-group <resource-group>\n"
                f"Then assign required roles to the identity:\n"
                f"  az role assignment create --role <role-name> --assignee <principal-id> --scope <scope>"
            )
            logger.error(error_msg)
            raise IdentityNotFoundError(error_msg)

        self._identity = identity
        logger.info(f"System-assigned managed identity discovered: {self.vm_name}")

        return identity

