"""
Azure Blob Storage writer for usage logs.

Provides a clean interface for writing usage records to Azure Blob Storage
using AppendBlob with identity-based authentication.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional
import json
import urllib.request

# Azure Storage imports (optional)
try:
    from azure.core.exceptions import HttpResponseError, ResourceNotFoundError, ResourceExistsError  # noqa: F401
    from azure.identity import ManagedIdentityCredential, AzureCliCredential  # noqa: F401
    from azure.mgmt.storage import StorageManagementClient  # noqa: F401
    from azure.storage.blob import BlobServiceClient, BlobType, ContentSettings  # noqa: F401
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

IMDS_URL = "http://169.254.169.254/metadata/instance?api-version=2021-02-01"
IMDS_HEADERS = {"Metadata": "true"}


@dataclass
class AzureVmContext:
    on_azure_vm: bool
    subscription_id: Optional[str] = None
    resource_group: Optional[str] = None


class AzureBlobWriter:
    """
    Handles writing to Azure Blob Storage append blobs.
    
    Features:
    - Automatic container and append blob creation
    - Identity-based authentication (Managed Identity or Azure CLI)
    - Graceful error handling
    - Thread-safe operations (when used with external locking)
    
    Usage:
        writer = AzureBlobWriter(
            storage_account="myaccount",
            container_name="usage-logs",
            blob_name="usage.jsonl"
        )
        writer.initialize()
        writer.append("log line\\n")
        writer.close()
    """
    
    def __init__(
        self,
        storage_account: Optional[str],
        container_name: str,
        blob_name: str,
        mode: str = "dev",
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize the Azure Blob writer.
        
        Args:
            storage_account: Azure Storage account name
            container_name: Container name for the blob
            blob_name: Name of the append blob
            logger: Optional logger instance (creates new one if None)
        """
        self.storage_account = storage_account
        self.container_name = container_name
        self.blob_name = blob_name
        self.mode = mode
        self._logger = logger or logging.getLogger(__name__)
        
        self._blob_service_client: Optional[object] = None
        self._append_blob_client: Optional[object] = None
        self._initialized = False

    def _get_vm_context(self, timeout_sec: float = 0.5) -> AzureVmContext:
        req = urllib.request.Request(IMDS_URL, headers=IMDS_HEADERS, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                imds = json.loads(raw)
            compute = (imds or {}).get("compute", {}) or {}
            return AzureVmContext(
                on_azure_vm=True,
                subscription_id=compute.get("subscriptionId"),
                resource_group=compute.get("resourceGroupName"),
            )
        except Exception:
            return AzureVmContext(on_azure_vm=False)

    def _get_storage_mgmt_client(self, credential, subscription_id: str):
        return StorageManagementClient(credential, subscription_id)

    def _discover_storage_account(self, mgmt_client, resource_group: str) -> str:
        accounts = list(mgmt_client.storage_accounts.list_by_resource_group(resource_group))
        if not accounts:
            raise RuntimeError(f"No storage accounts found in resource group '{resource_group}'.")
        if len(accounts) != 1:
            names = ", ".join(a.name for a in accounts if a and a.name)
            raise RuntimeError(
                f"Expected exactly 1 storage account in RG '{resource_group}', found {len(accounts)}: {names}"
            )
        return accounts[0].name

    def _make_blob_service(self, storage_account: str, credential_or_key):
        account_url = f"https://{storage_account}.blob.core.windows.net"
        return BlobServiceClient(account_url=account_url, credential=credential_or_key)

    def _ensure_container_and_append_blob(self, blob_service) -> None:
        container_client = blob_service.get_container_client(self.container_name)
        try:
            container_client.create_container()
            self._logger.info("Created container '%s'", self.container_name)
        except ResourceExistsError:
            self._logger.info("Container '%s' already exists", self.container_name)

        self._append_blob_client = blob_service.get_blob_client(
            container=self.container_name,
            blob=self.blob_name
        )
        try:
            props = self._append_blob_client.get_blob_properties()
            self._logger.info(
                "Existing blob '%s' type: %s",
                self.blob_name,
                getattr(props, "blob_type", None)
            )
            if props.blob_type != BlobType.AppendBlob:
                self._logger.error(
                    f"Blob '{self.blob_name}' exists but is not an AppendBlob (type: {props.blob_type}). "
                    "Blob storage logging will be disabled."
                )
                self._append_blob_client = None
                raise RuntimeError("Existing blob is not AppendBlob.")
            self._logger.debug(f"Append blob '{self.blob_name}' already exists")
        except ResourceNotFoundError:
            self._append_blob_client.create_append_blob(  # type: ignore
                content_settings=ContentSettings(content_type="application/jsonl")
            )
            self._logger.info(f"Created append blob '{self.blob_name}'")

    def _is_authz_mismatch(self, err: HttpResponseError) -> bool:
        msg = getattr(err, "message", "") or str(err)
        code = getattr(err, "error_code", None)
        return (code == "AuthorizationPermissionMismatch") or ("AuthorizationPermissionMismatch" in msg)

    def _get_storage_account_key(self, mgmt_client, resource_group: str, storage_account: str) -> str:
        keys = mgmt_client.storage_accounts.list_keys(resource_group, storage_account)
        values = [k.value for k in (keys.keys or []) if k.value]
        if not values:
            raise RuntimeError("No storage account keys returned (key access may be disabled).")
        return values[0]
    
    @property
    def is_available(self) -> bool:
        """Check if Azure SDK is available."""
        return AZURE_AVAILABLE
    
    @property
    def is_initialized(self) -> bool:
        """Check if blob writer has been successfully initialized."""
        return self._initialized
    
    def initialize(self) -> bool:
        """
        Initialize the blob client and ensure container/blob exist.
        
        Returns:
            True if initialization successful, False otherwise
        """
        if self._initialized:
            return True
        
        if not AZURE_AVAILABLE:
            self._logger.debug("Azure SDK not available")
            return False
        
        try:
            vm_context = self._get_vm_context()
            on_azure_vm = vm_context.on_azure_vm
            self._logger.info(
                "Azure usage logging init: mode=%s, on_azure_vm=%s",
                self.mode,
                on_azure_vm
            )
            if on_azure_vm:
                self._logger.debug(
                    "Azure VM context: subscription=%s, resource_group=%s",
                    vm_context.subscription_id,
                    vm_context.resource_group
                )

            # Choose credential based on environment
            if self.mode == "dev":
                credential = AzureCliCredential()
            else:
                credential = ManagedIdentityCredential() if on_azure_vm else AzureCliCredential()
            self._logger.debug("Azure credential selected: %s", type(credential).__name__)

            # Determine storage account
            storage_account = self.storage_account
            if not storage_account:
                if not on_azure_vm or not vm_context.subscription_id or not vm_context.resource_group:
                    raise RuntimeError(
                        "Azure storage account not configured and Azure VM context not available. "
                        "Provide AZURE_STORAGE_ACCOUNT in config.toml for dev mode."
                    )
                mgmt_client = self._get_storage_mgmt_client(credential, vm_context.subscription_id)
                storage_account = self._discover_storage_account(mgmt_client, vm_context.resource_group)
                self._logger.info(f"Auto-discovered storage account '{storage_account}' from VM resource group")
            self.storage_account = storage_account
            self._logger.info(
                "Azure usage logging target: %s/%s/%s",
                storage_account,
                self.container_name,
                self.blob_name
            )

            # Create blob service client
            self._blob_service_client = self._make_blob_service(storage_account, credential)

            try:
                self._ensure_container_and_append_blob(self._blob_service_client)
            except HttpResponseError as e:
                if self._is_authz_mismatch(e) and on_azure_vm and vm_context.subscription_id and vm_context.resource_group:
                    self._logger.warning(
                        "RBAC authorization mismatch when accessing blob. Falling back to account key."
                    )
                    mgmt_client = self._get_storage_mgmt_client(credential, vm_context.subscription_id)
                    account_key = self._get_storage_account_key(
                        mgmt_client, vm_context.resource_group, storage_account
                    )
                    self._blob_service_client = self._make_blob_service(storage_account, account_key)
                    self._ensure_container_and_append_blob(self._blob_service_client)
                else:
                    raise

            self._initialized = True
            self._logger.info(
                "Azure usage logging initialized: %s/%s/%s",
                self.storage_account,
                self.container_name,
                self.blob_name
            )
            return True
            
        except Exception as e:
            self._logger.warning(f"Failed to initialize Azure Blob Storage: {e}", exc_info=True)
            self._append_blob_client = None
            return False
    
    def append(self, data: str) -> bool:
        """
        Append data to the blob.
        
        Args:
            data: String data to append (should include newline if needed)
            
        Returns:
            True if append successful, False otherwise
        """
        if not self._initialized or self._append_blob_client is None:
            return False
        
        try:
            self._append_blob_client.append_block(data.encode('utf-8'))  # type: ignore
            return True
        except Exception as e:
            self._logger.warning(f"Failed to append to blob: {e}")
            return False
    
    def close(self) -> None:
        """Close the blob service client."""
        if self._blob_service_client is not None:
            try:
                self._blob_service_client.close()  # type: ignore
            except Exception:
                pass
            finally:
                self._blob_service_client = None
                self._append_blob_client = None
                self._initialized = False
