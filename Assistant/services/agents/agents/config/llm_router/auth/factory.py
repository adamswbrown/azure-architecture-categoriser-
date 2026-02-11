"""
Authenticator factory for creating cloud-specific authenticators.

Provides centralized logic for creating the appropriate authenticator
based on cloud provider, environment, and configuration.
"""

from typing import Dict, Any, Optional

from .aws import AWSAuthenticator
from .azure import AzureAuthenticator
from .gcp import GCPAuthenticator
from .local import AzureLocalAuthenticator, GCPLocalAuthenticator, AWSLocalAuthenticator
from .base import BaseAuthenticator
from ..logger import get_logger

logger = get_logger('auth.factory')


class AuthenticatorFactoryError(Exception):
    """Raised when authenticator creation fails."""
    pass


class AuthenticatorFactory:
    """
    Factory for creating cloud-specific authenticators.

    Handles both local development and production Azure VM environments.
    """

    @staticmethod
    def create(
        cloud: str,
        environment: str,
        auth_config: Dict[str, Any],
        client_id: Optional[str] = None,
        vm_name: Optional[str] = None
    ) -> BaseAuthenticator:
        """
        Create appropriate authenticator based on cloud and environment.

        Args:
            cloud: Cloud provider ('aws', 'azure', 'gcp')
            environment: Execution environment ('local', 'azure_vm')
            auth_config: Authentication configuration from endpoint
            client_id: Optional Azure MI client_id (required for production)
            vm_name: Optional VM name (required for AWS production)

        Returns:
            Configured authenticator instance

        Raises:
            AuthenticatorFactoryError: If creation fails or validation fails
        """
        logger.info(f"Creating authenticator: cloud={cloud}, environment={environment}")

        try:
            if environment == 'local':
                return AuthenticatorFactory._create_local(cloud, auth_config)
            else:
                return AuthenticatorFactory._create_production(
                    cloud, auth_config, client_id, vm_name
                )
        except Exception as e:
            error_msg = f"Failed to create {cloud} authenticator for {environment} environment: {e}"
            logger.error(error_msg)
            raise AuthenticatorFactoryError(error_msg) from e

    @staticmethod
    def _create_local(cloud: str, auth_config: Dict[str, Any]) -> BaseAuthenticator:
        """
        Create local development authenticator.

        Args:
            cloud: Cloud provider
            auth_config: Authentication configuration

        Returns:
            Local authenticator instance

        Raises:
            AuthenticatorFactoryError: If cloud is unsupported
        """
        logger.info(f"Creating local development authenticator for {cloud}")

        if cloud == 'aws':
            region = auth_config.get('region')
            if not region:
                raise AuthenticatorFactoryError("AWS local authenticator requires 'region' in auth_config")
            return AWSLocalAuthenticator(region=region)

        elif cloud == 'azure':
            return AzureLocalAuthenticator()

        elif cloud == 'gcp':
            project_id = auth_config.get('project_id')
            if not project_id:
                raise AuthenticatorFactoryError("GCP local authenticator requires 'project_id' in auth_config")
            return GCPLocalAuthenticator(project_id=project_id)

        else:
            raise AuthenticatorFactoryError(f"Unsupported cloud provider: {cloud}")

    @staticmethod
    def _create_production(
        cloud: str,
        auth_config: Dict[str, Any],
        client_id: Optional[str],
        vm_name: Optional[str]
    ) -> BaseAuthenticator:
        """
        Create production Azure VM authenticator.

        Args:
            cloud: Cloud provider
            auth_config: Authentication configuration
            client_id: Azure MI client_id
            vm_name: VM name

        Returns:
            Production authenticator instance

        Raises:
            AuthenticatorFactoryError: If validation fails or cloud is unsupported
        """
        logger.info(f"Creating production authenticator for {cloud}")

        # Validate required parameters
        if client_id is None:
            raise AuthenticatorFactoryError(
                f"client_id is required for production {cloud} authenticator but is None.\n"
                f"This indicates system-assigned managed identity discovery failed.\n"
                f"Troubleshooting:\n"
                f"  1. Verify VM has system-assigned managed identity enabled:\n"
                f"     az vm identity assign --name <vm-name> --resource-group <rg>\n"
                f"  2. Ensure IMDS endpoint (169.254.169.254) is accessible from VM\n"
                f"  3. Check identity has required permissions assigned\n"
                f"  4. Review logs for identity discovery errors"
            )

        if cloud == 'aws':
            # AWS requires vm_name for WIF session naming
            if vm_name is None:
                raise AuthenticatorFactoryError(
                    "vm_name is required for AWS production authenticator"
                )

            role_arn = auth_config.get('role_arn')
            if not role_arn:
                raise AuthenticatorFactoryError(
                    "AWS production authenticator requires 'role_arn' in auth_config"
                )

            logger.info("Creating AWS authenticator (Azure MI → AWS WIF)")
            return AWSAuthenticator(
                client_id=client_id,
                role_arn=role_arn,
                vm_name=vm_name
            )

        elif cloud == 'azure':
            scope = auth_config.get('scope')
            if not scope:
                raise AuthenticatorFactoryError(
                    "Azure production authenticator requires 'scope' in auth_config"
                )

            logger.info("Creating Azure authenticator (Azure MI)")
            return AzureAuthenticator(
                client_id=client_id,
                scope=scope
            )

        elif cloud == 'gcp':
            # Validate required GCP WIF configuration
            required_keys = ['project_id', 'audience', 'token_url', 'service_account']
            missing_keys = [key for key in required_keys if key not in auth_config]

            if missing_keys:
                raise AuthenticatorFactoryError(
                    f"GCP production authenticator requires {missing_keys} in auth_config"
                )

            logger.info("Creating GCP authenticator (Azure MI → GCP WIF)")
            return GCPAuthenticator(
                client_id=client_id,
                project_id=auth_config['project_id'],
                audience=auth_config['audience'],
                token_url=auth_config['token_url'],
                service_account=auth_config['service_account']
            )

        else:
            raise AuthenticatorFactoryError(f"Unsupported cloud provider: {cloud}")
