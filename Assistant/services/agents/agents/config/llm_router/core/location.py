"""
Location detection using Instance Metadata Service (IMDS) or environment variables.

Supports both Azure VM production and local development environments.
"""

import json
import os
import urllib.request
import urllib.error
from typing import Dict, Optional
from dataclasses import dataclass

from .constants import IMDS_TIMEOUT
from .imds_client import IMDSClient, IMDSError, IMDSNotAvailableError
from ..logger import get_logger
from .environment import detect_environment

logger = get_logger('core.location')


class LocationDetectionError(Exception):
    """Raised when VM location cannot be detected."""
    pass


@dataclass
class VMInfo:
    """VM metadata information."""
    name: str
    location: str  # Azure region
    vm_id: str
    resource_group: str
    subscription_id: str

    def __str__(self) -> str:
        return f"VM(name={self.name}, location={self.location}, id={self.vm_id[:8]}...)"


class LocationDetector:
    """Detects Azure VM location and metadata via IMDS."""

    def __init__(self):
        """Initialize location detector."""
        self._vm_info: Optional[VMInfo] = None

    def detect(self, environment: Optional[str] = None) -> VMInfo:
        """
        Detect current Azure VM location and metadata or use local defaults.

        For Azure VM: Queries IMDS for VM metadata
        For local dev: Uses environment variables or defaults

        Args:
            environment: Optional environment override ('azure_vm' or 'local').
                        If None, auto-detects.

        Returns:
            VMInfo object with VM metadata

        Raises:
            LocationDetectionError: If detection fails
        """
        if self._vm_info is not None:
            logger.debug("Returning cached VM info")
            return self._vm_info

        # Use provided environment or auto-detect
        env = environment if environment else detect_environment()

        if env == 'azure_vm':
            return self._detect_from_imds()
        else:
            return self._detect_from_environment()

    def _detect_from_imds(self) -> VMInfo:
        """
        Detect VM metadata from Azure IMDS.

        Returns:
            VMInfo object from IMDS

        Raises:
            LocationDetectionError: If IMDS query fails
        """
        logger.info("Querying Azure IMDS for VM metadata")

        try:
            metadata = IMDSClient.get_instance_metadata(timeout=IMDS_TIMEOUT)
            data = metadata.get('compute', {})

            self._vm_info = VMInfo(
                name=data.get('name', '').lower(),
                location=data.get('location', '').lower(),
                vm_id=data.get('vmId', ''),
                resource_group=data.get('resourceGroupName', ''),
                subscription_id=data.get('subscriptionId', '')
            )

            logger.info(
                f"VM detected: name={self._vm_info.name}, "
                f"region={self._vm_info.location}, "
                f"vmId={self._vm_info.vm_id[:13]}..."
            )
            logger.debug(
                f"Full VM info: resourceGroup={self._vm_info.resource_group}, "
                f"subscription={self._vm_info.subscription_id[:8]}..."
            )

            return self._vm_info

        except (IMDSError, IMDSNotAvailableError) as e:
            error_msg = f"Failed to query Azure IMDS: {e}"
            logger.error(error_msg)
            raise LocationDetectionError(error_msg) from e
        except KeyError as e:
            error_msg = f"Failed to parse IMDS response: {e}"
            logger.error(error_msg)
            raise LocationDetectionError(error_msg) from e

    def _detect_from_environment(self) -> VMInfo:
        """
        Detect VM metadata from environment variables for local development.

        Environment variables:
            LLM_ROUTER_VM_NAME: VM name (default: 'local-dev')
            LLM_ROUTER_LOCATION: Azure region (default: 'australiasoutheast')
            LLM_ROUTER_VM_ID: VM ID (default: 'local-dev-id')
            LLM_ROUTER_RESOURCE_GROUP: Resource group (default: 'local')
            LLM_ROUTER_SUBSCRIPTION_ID: Subscription ID (default: 'local')

        Returns:
            VMInfo object from environment variables

        Raises:
            LocationDetectionError: If required environment variables are missing
        """
        logger.info("Using local development environment variables")

        self._vm_info = VMInfo(
            name=os.getenv('LLM_ROUTER_VM_NAME', 'local-dev').lower(),
            location=os.getenv('LLM_ROUTER_LOCATION', 'australiasoutheast').lower(),
            vm_id=os.getenv('LLM_ROUTER_VM_ID', 'local-dev-id'),
            resource_group=os.getenv('LLM_ROUTER_RESOURCE_GROUP', 'local'),
            subscription_id=os.getenv('LLM_ROUTER_SUBSCRIPTION_ID', 'local')
        )

        logger.info(
            f"Local dev environment: name={self._vm_info.name}, "
            f"location={self._vm_info.location}"
        )

        return self._vm_info

    def get_vm_name(self) -> str:
        """
        Get the VM name.

        Returns:
            VM name in lowercase
        """
        vm_info = self.detect()
        return vm_info.name

    def get_region(self) -> str:
        """
        Get the Azure region.

        Returns:
            Azure region in lowercase
        """
        vm_info = self.detect()
        return vm_info.location

    def map_region_to_geo(self, geo_map: Dict[str, str]) -> str:
        """
        Map Azure region to geographic zone using provided mapping.

        Args:
            geo_map: Dictionary mapping regions to geo zones

        Returns:
            Geographic zone (US/EU/APAC)
        """
        region = self.get_region()

        # Try exact match
        if region in geo_map:
            geo = geo_map[region]
            logger.info(f"Mapped region '{region}' to geo zone: {geo}")
            return geo

        # Try partial match
        for mapped_region, geo in geo_map.items():
            if mapped_region in region or region in mapped_region:
                logger.info(f"Mapped region '{region}' to geo zone: {geo} (partial match with '{mapped_region}')")
                return geo

        # Default to US
        logger.warning(f"Region '{region}' not found in geo_map, defaulting to US")
        return "US"
