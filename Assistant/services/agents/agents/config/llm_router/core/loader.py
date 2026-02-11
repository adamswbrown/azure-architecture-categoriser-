"""
Configuration file loader supporting local filesystem and Azure Storage.
"""

import json
import ssl
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List
from urllib.parse import urlparse

import certifi

from .constants import HTTP_TIMEOUT, AZURE_STORAGE_RESOURCE, AZURE_STORAGE_API_VERSION
from .imds_client import IMDSClient, IMDSError, IMDSNotAvailableError
from ..logger import get_logger

logger = get_logger('core.loader')


class LoaderError(Exception):
    """Base exception for loader errors."""
    pass


class ConfigLoader:
    """Smart loader for JSON configuration files."""

    AZURE_STORAGE_HOSTS = [
        'blob.core.windows.net',
        'blob.core.usgovcloudapi.net',
        'blob.core.chinacloudapi.cn'
    ]

    STORAGE_RESOURCE = AZURE_STORAGE_RESOURCE  # Azure Storage resource URL
    TIMEOUT = HTTP_TIMEOUT  # HTTP request timeout for Azure Storage operations

    def __init__(self, client_id: Optional[str] = None, environment: Optional[str] = None):
        """
        Initialize config loader.

        Args:
            client_id: Optional Azure UMI client_id for storage authentication (production mode)
            environment: Optional environment type ('azure_vm' or 'local')
        """
        self.client_id = client_id
        self.environment = environment

    @staticmethod
    def _create_ssl_context() -> ssl.SSLContext:
        """
        Create SSL context using certifi certificates.

        This ensures SSL verification works on all platforms (macOS, Linux, Windows)
        without requiring system-level certificate installation.

        Returns:
            SSL context configured with certifi certificate bundle
        """
        context = ssl.create_default_context(cafile=certifi.where())
        return context

    def load(self, source: str) -> Dict[str, Any]:
        """
        Load JSON from local file or Azure Storage URL.

        Args:
            source: File path or Azure Storage URL

        Returns:
            Parsed JSON as dictionary

        Raises:
            LoaderError: If loading fails
        """
        if self.is_azure_storage_url(source):
            logger.info(f"Loading from Azure Storage: {source}")
            return self._load_azure_storage(source)
        else:
            logger.info(f"Loading from local file: {source}")
            return self._load_local(source)

    def _load_local(self, file_path: str) -> Dict[str, Any]:
        """
        Load JSON from local filesystem.

        Args:
            file_path: Path to JSON file

        Returns:
            Parsed JSON

        Raises:
            LoaderError: If file not found or invalid JSON
        """
        try:
            path = Path(file_path).expanduser().resolve()
            logger.debug(f"Reading file: {path}")

            with open(path, 'r') as f:
                data = json.load(f)

            logger.debug(f"Successfully loaded {len(str(data))} bytes")
            return data

        except FileNotFoundError as e:
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in file {file_path}: {e}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to load file {file_path}: {e}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e

    def _load_azure_storage(self, url: str) -> Dict[str, Any]:
        """
        Load JSON from Azure Storage blob with environment-aware authentication.

        Production (Azure VM): Uses IMDS with managed identity
        Development (local): Uses Azure SDK credentials (az login)

        Args:
            url: Azure Storage blob URL

        Returns:
            Parsed JSON

        Raises:
            LoaderError: If download or authentication fails
        """
        logger.debug("Detected Azure Storage URL, getting storage token")

        # Get storage access token using appropriate method
        if self.environment == 'local':
            token = self._get_storage_token_sdk()
        else:
            # Default to IMDS for production or when environment not specified
            token = self._get_storage_token_imds()

        # Download blob
        try:
            logger.debug(f"Downloading blob: {url}")

            req = urllib.request.Request(url)
            req.add_header('Authorization', f'Bearer {token}')
            req.add_header('x-ms-version', AZURE_STORAGE_API_VERSION)

            # Create SSL context with certifi certificates for proper verification
            ssl_context = self._create_ssl_context()

            with urllib.request.urlopen(req, timeout=self.TIMEOUT, context=ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))

            logger.debug(f"Successfully downloaded {len(str(data))} bytes")
            return data

        except urllib.error.HTTPError as e:
            error_msg = f"HTTP error downloading blob: {e.code} {e.reason}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e
        except urllib.error.URLError as e:
            error_msg = f"Failed to download blob: {e}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON in blob: {e}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e

    def _get_storage_token_imds(self) -> str:
        """
        Get Azure Storage access token using IMDS (production mode).

        Returns:
            Access token string

        Raises:
            LoaderError: If token request fails
        """
        if self.client_id:
            logger.debug(f"Requesting storage token with client_id: {self.client_id[:8]}...")
        else:
            logger.debug("Requesting storage token with system-assigned identity")

        try:
            data = IMDSClient.get_token(
                resource=self.STORAGE_RESOURCE,
                client_id=self.client_id,
                timeout=HTTP_TIMEOUT
            )
            token = data['access_token']

            logger.debug(f"Storage token obtained: {token[:8]}...{token[-4:]}")
            return token

        except (IMDSError, IMDSNotAvailableError) as e:
            error_msg = f"Failed to get storage token: {e}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e
        except KeyError as e:
            error_msg = f"Invalid token response: {e}"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e

    def _get_storage_token_sdk(self) -> str:
        """
        Get Azure Storage access token using Azure SDK (local development mode).

        Uses AzureCliCredential which relies on 'az login' credentials.

        Returns:
            Access token string

        Raises:
            LoaderError: If token request fails
        """
        logger.debug("Getting storage token using Azure SDK (az login credentials)")

        try:
            from azure.identity import AzureCliCredential
        except ImportError as e:
            error_msg = "Failed to import azure-identity. Install with: pip install azure-identity"
            logger.error(error_msg)
            raise LoaderError(error_msg) from e

        try:
            credential = AzureCliCredential()
            # Get token for Azure Storage scope
            token_result = credential.get_token("https://storage.azure.com/.default")
            token = token_result.token

            logger.debug(f"Storage token obtained via SDK: {token[:8]}...{token[-4:]}")
            return token

        except Exception as e:
            error_msg = f"Failed to get storage token via Azure SDK: {e}"
            logger.error(error_msg)
            logger.error("Make sure you are logged in with: az login")
            raise LoaderError(error_msg) from e

    @staticmethod
    def is_azure_storage_url(source: str) -> bool:
        """
        Check if source is an Azure Storage URL.

        Args:
            source: File path or URL

        Returns:
            True if Azure Storage URL, False otherwise
        """
        try:
            parsed = urlparse(source)
            return any(host in parsed.netloc for host in ConfigLoader.AZURE_STORAGE_HOSTS)
        except Exception:
            return False

    @staticmethod
    def find_config(filename: str, search_paths: List[str]) -> Optional[str]:
        """
        Search for a config file in multiple paths.

        Args:
            filename: Name of config file (e.g., 'config.json')
            search_paths: List of directory paths to search

        Returns:
            Path to first found config file, or None
        """
        logger.debug(f"Searching for {filename} in: {search_paths}")

        for search_path in search_paths:
            path = Path(search_path).expanduser() / filename

            if path.is_file():
                logger.debug(f"Found config at: {path}")
                return str(path)

        logger.debug(f"Config {filename} not found in any search path")
        return None
