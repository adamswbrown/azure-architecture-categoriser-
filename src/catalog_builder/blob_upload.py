"""Upload architecture catalog JSON to Azure Blob Storage."""

import json
import os
from pathlib import Path
from typing import Optional


def _check_azure_deps():
    """Check that Azure SDK dependencies are installed."""
    try:
        import azure.storage.blob  # noqa: F401
    except ImportError:
        raise ImportError(
            "Azure Blob Storage upload requires the 'azure' extras.\n"
            "Install with: pip install -e '.[azure]'"
        )


def _extract_catalog_metadata(catalog_path: Path) -> dict[str, str]:
    """Extract key metadata from a catalog file for blob metadata.

    Azure Blob metadata values must be strings.
    """
    with open(catalog_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    metadata = {}
    if "version" in data:
        metadata["catalog_version"] = str(data["version"])
    if "total_architectures" in data:
        metadata["total_architectures"] = str(data["total_architectures"])
    if "generated_at" in data:
        metadata["generated_at"] = str(data["generated_at"])
    if "source_commit" in data and data["source_commit"]:
        metadata["source_commit"] = str(data["source_commit"])[:12]
    if "source_repo" in data:
        metadata["source_repo"] = str(data["source_repo"])

    return metadata


def upload_catalog_to_blob(
    catalog_path: Path,
    *,
    blob_url: Optional[str] = None,
    connection_string: Optional[str] = None,
    account_url: Optional[str] = None,
    container_name: str = "catalogs",
    blob_name: Optional[str] = None,
    overwrite: bool = True,
) -> str:
    """Upload a catalog JSON file to Azure Blob Storage.

    Authentication is resolved in priority order:
    1. blob_url - Full SAS URL (blob-level or container-level + blob_name)
    2. connection_string - Azure Storage connection string
    3. account_url - Storage account URL with DefaultAzureCredential

    Args:
        catalog_path: Path to the catalog JSON file.
        blob_url: Full blob SAS URL (e.g. https://account.blob.core.windows.net/container/blob?SAS).
        connection_string: Azure Storage connection string.
        account_url: Storage account URL for DefaultAzureCredential.
        container_name: Blob container name (default: "catalogs").
        blob_name: Blob name (defaults to the catalog filename).
        overwrite: Whether to overwrite an existing blob.

    Returns:
        The URL of the uploaded blob (without SAS token).

    Raises:
        ImportError: If azure-storage-blob is not installed.
        ValueError: If no authentication method is provided.
        azure.core.exceptions.ResourceExistsError: If blob exists and overwrite=False.
    """
    _check_azure_deps()

    if blob_name is None:
        blob_name = catalog_path.name

    metadata = _extract_catalog_metadata(catalog_path)

    with open(catalog_path, "rb") as f:
        catalog_data = f.read()

    if blob_url:
        return _upload_via_sas_url(
            catalog_data, blob_url, blob_name, overwrite, metadata
        )
    elif connection_string:
        return _upload_via_connection_string(
            catalog_data, connection_string, container_name, blob_name, overwrite, metadata
        )
    elif account_url:
        return _upload_via_default_credential(
            catalog_data, account_url, container_name, blob_name, overwrite, metadata
        )
    else:
        raise ValueError(
            "No authentication method provided. Supply one of: "
            "--blob-url, --connection-string, or --account-url"
        )


def _upload_via_sas_url(
    data: bytes,
    blob_url: str,
    blob_name: str,
    overwrite: bool,
    metadata: dict[str, str],
) -> str:
    """Upload using a full SAS URL.

    The URL can be either:
    - A blob-level SAS URL (uploaded directly)
    - A container-level SAS URL (blob_name is appended)
    """
    from azure.storage.blob import BlobClient, ContainerClient

    # Heuristic: if the URL path has only one segment after the container,
    # it's likely a container URL. If it has more, it's a blob URL.
    # More reliably: try to detect if the path ends with just a container name.
    from urllib.parse import urlparse
    parsed = urlparse(blob_url.split("?")[0])
    path_parts = [p for p in parsed.path.split("/") if p]

    if len(path_parts) <= 1:
        # Container-level SAS URL - append blob name
        container_client = ContainerClient.from_container_url(blob_url)
        blob_client = container_client.get_blob_client(blob_name)
    else:
        # Blob-level SAS URL - use directly
        blob_client = BlobClient.from_blob_url(blob_url)

    blob_client.upload_blob(
        data,
        overwrite=overwrite,
        content_settings=_content_settings(),
        metadata=metadata,
    )

    # Return the URL without SAS token
    return blob_client.url.split("?")[0]


def _upload_via_connection_string(
    data: bytes,
    connection_string: str,
    container_name: str,
    blob_name: str,
    overwrite: bool,
    metadata: dict[str, str],
) -> str:
    """Upload using an Azure Storage connection string."""
    from azure.storage.blob import BlobServiceClient

    service_client = BlobServiceClient.from_connection_string(connection_string)
    blob_client = service_client.get_blob_client(
        container=container_name, blob=blob_name
    )

    blob_client.upload_blob(
        data,
        overwrite=overwrite,
        content_settings=_content_settings(),
        metadata=metadata,
    )

    return blob_client.url


def _upload_via_default_credential(
    data: bytes,
    account_url: str,
    container_name: str,
    blob_name: str,
    overwrite: bool,
    metadata: dict[str, str],
) -> str:
    """Upload using DefaultAzureCredential (managed identity, Azure CLI, etc.)."""
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    credential = DefaultAzureCredential()
    service_client = BlobServiceClient(account_url=account_url, credential=credential)
    blob_client = service_client.get_blob_client(
        container=container_name, blob=blob_name
    )

    blob_client.upload_blob(
        data,
        overwrite=overwrite,
        content_settings=_content_settings(),
        metadata=metadata,
    )

    return blob_client.url


def _content_settings():
    """Return ContentSettings for a JSON catalog upload."""
    from azure.storage.blob import ContentSettings

    return ContentSettings(
        content_type="application/json",
        content_encoding="utf-8",
    )
