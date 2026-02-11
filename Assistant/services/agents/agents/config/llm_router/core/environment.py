"""
Environment detection utilities.

Detects whether the code is running on Azure VM with Managed Identity
or on a local development machine.

Supports manual override via parameter, config, or environment variable.
"""

import os
import urllib.request
import urllib.error
from typing import Literal, Optional
from .constants import IMDS_INSTANCE_URL, IMDS_INSTANCE_API_VERSION, ENVIRONMENT_DETECTION_TIMEOUT
from ..logger import get_logger

logger = get_logger('core.environment')

EnvironmentType = Literal['azure_vm', 'local']


def detect_environment(override: Optional[str] = None) -> EnvironmentType:
    """
    Detect the runtime environment.

    Args:
        override: Optional override value ('auto', 'azure_vm', 'local', or None)
                 If provided and not 'auto', returns the override value.

    Returns:
        'azure_vm' if running on Azure VM with Managed Identity
        'local' if running on local development machine

    Raises:
        ValueError: If override value is invalid
    """
    # If override is provided (check for None explicitly, not truthiness)
    if override is not None:
        # Validate non-empty string
        if not override or not override.strip():
            raise ValueError("Environment override cannot be empty string")
        if override == 'auto':
            # Fall through to auto-detection
            pass
        elif override in ['azure_vm', 'local']:
            logger.info(f"Environment overridden to: {override}")
            return override  # type: ignore
        else:
            raise ValueError(f"Invalid environment override: {override}. Must be 'auto', 'azure_vm', or 'local'")

    # Auto-detect based on IMDS availability
    if _is_azure_vm():
        logger.info("Detected environment: Azure VM (Managed Identity available)")
        return 'azure_vm'
    else:
        logger.info("Detected environment: Local development machine")
        return 'local'


def _is_azure_vm() -> bool:
    """
    Check if code is running on an Azure VM with access to IMDS.

    Attempts to access Azure Instance Metadata Service (IMDS) which is
    only available on Azure VMs.

    Returns:
        True if Azure IMDS is accessible, False otherwise
    """
    imds_url = f"{IMDS_INSTANCE_URL}?api-version={IMDS_INSTANCE_API_VERSION}"

    try:
        req = urllib.request.Request(imds_url)
        req.add_header('Metadata', 'true')

        # Short timeout to avoid blocking on non-Azure environments
        with urllib.request.urlopen(req, timeout=ENVIRONMENT_DETECTION_TIMEOUT) as response:
            if response.status == 200:
                logger.debug("Azure IMDS accessible - running on Azure VM")
                return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
        logger.debug("Azure IMDS not accessible - running on local machine")
        return False
    except Exception as e:
        logger.debug(f"Unexpected error checking Azure IMDS: {e}")
        return False

    return False
