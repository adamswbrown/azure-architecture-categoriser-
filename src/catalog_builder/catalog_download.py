"""Download architecture catalog JSON from a remote HTTPS URL.

Provides secure remote catalog fetching with protections against
malicious content:

- URL validation via domain allowlist with subdomain matching
- SSRF protection (blocked private IPs, cloud metadata endpoints)
- Response size cap to prevent memory exhaustion
- JSON structure validation and Pydantic schema checks
- Architecture count ceiling to reject implausibly large payloads
- Content-Type verification
- Connection and read timeouts
"""

import ipaddress
import json
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# ── Limits ──────────────────────────────────────────────────────────────────
MAX_CATALOG_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_ARCHITECTURE_COUNT = 500
REQUEST_TIMEOUT = (10, 30)  # (connect, read) seconds

# ── SSRF protection ─────────────────────────────────────────────────────────
BLOCKED_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

BLOCKED_HOSTNAMES = frozenset([
    "metadata.google.internal",
    "metadata.goog",
    "169.254.169.254",
    "100.100.100.200",
])

# Domains allowed for catalog downloads (suffix matching).
CATALOG_ALLOWED_DOMAINS = frozenset([
    # Azure Blob Storage (all clouds)
    "blob.core.windows.net",
    "blob.core.chinacloudapi.cn",
    "blob.core.usgovcloudapi.net",
    # Microsoft docs / CDN
    "microsoft.com",
    "azure.com",
    "azureedge.net",
    "akamaized.net",
    "msecnd.net",
    # GitHub (raw content / releases)
    "github.com",
    "githubusercontent.com",
    "raw.githubusercontent.com",
])


class CatalogDownloadError(Exception):
    """Raised when a remote catalog cannot be downloaded or validated."""


def _is_ip_blocked(hostname: str) -> bool:
    """Check if a hostname is a blocked IP address."""
    try:
        ip = ipaddress.ip_address(hostname)
        return any(ip in network for network in BLOCKED_IP_RANGES)
    except ValueError:
        return False


def _validate_catalog_url(
    url: str,
    allowed_domains: frozenset[str],
) -> tuple[bool, str]:
    """Validate a catalog URL with subdomain matching and SSRF checks."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme.lower() != "https":
        return False, "URL scheme must be HTTPS"

    if not parsed.netloc:
        return False, "URL must have a hostname"

    hostname = parsed.netloc.lower()
    if ":" in hostname:
        hostname = hostname.split(":")[0]

    if hostname in BLOCKED_HOSTNAMES:
        return False, "URL hostname is blocked"

    if _is_ip_blocked(hostname):
        return False, "URL points to a private/internal IP address"

    for domain in allowed_domains:
        if hostname == domain or hostname.endswith("." + domain):
            return True, ""

    return False, f"URL domain '{hostname}' is not in the allowed list"


def _validate_catalog_structure(data: dict) -> None:
    """Validate the essential shape of a catalog dict.

    Checks:
    - Top-level must be a dict with 'architectures' list
    - Architecture count within bounds
    - Each entry has 'name' or 'architecture_id'
    - 'version' field present
    - Full Pydantic schema validation
    """
    if not isinstance(data, dict):
        raise CatalogDownloadError(
            "Catalog must be a JSON object with an 'architectures' key."
        )

    if "architectures" not in data:
        raise CatalogDownloadError(
            "Catalog is missing the required 'architectures' field."
        )

    architectures = data["architectures"]
    if not isinstance(architectures, list):
        raise CatalogDownloadError("'architectures' must be a JSON array.")

    if len(architectures) == 0:
        raise CatalogDownloadError("Catalog contains no architectures.")

    if len(architectures) > MAX_ARCHITECTURE_COUNT:
        raise CatalogDownloadError(
            f"Catalog contains {len(architectures)} architectures, which exceeds "
            f"the maximum of {MAX_ARCHITECTURE_COUNT}. This may not be a valid catalog."
        )

    if "version" not in data:
        raise CatalogDownloadError(
            "Catalog is missing the 'version' field. This may not be a valid catalog file."
        )

    for i, entry in enumerate(architectures[:5]):
        if not isinstance(entry, dict):
            raise CatalogDownloadError(
                f"Architecture entry at index {i} is not a JSON object."
            )
        if "name" not in entry and "architecture_id" not in entry:
            raise CatalogDownloadError(
                f"Architecture entry at index {i} is missing both 'name' and "
                f"'architecture_id'. This does not look like a valid catalog."
            )

    # Full Pydantic validation
    try:
        from catalog_builder.schema import ArchitectureCatalog
        ArchitectureCatalog.model_validate(data)
    except Exception as exc:
        raise CatalogDownloadError(
            f"Catalog failed schema validation: {exc}"
        )


def download_catalog(
    url: str,
    *,
    output: Optional[Path] = None,
    allowed_domains: Optional[frozenset[str]] = None,
) -> tuple[dict, Path]:
    """Download, validate, and save a catalog from a remote URL.

    Args:
        url: HTTPS URL pointing to a catalog JSON file.
        output: Where to save the file. Defaults to ``remote-catalog.json``
            in the current working directory.
        allowed_domains: Override the domain allowlist (for testing).

    Returns:
        Tuple of (catalog_dict, path_to_saved_file).

    Raises:
        CatalogDownloadError: On any validation or network failure.
    """
    domains = allowed_domains or CATALOG_ALLOWED_DOMAINS

    # 1. Validate URL
    valid, err = _validate_catalog_url(url, domains)
    if not valid:
        raise CatalogDownloadError(f"Invalid URL: {err}")

    # 2. Download with size guard
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            stream=True,
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
    except requests.ConnectionError:
        raise CatalogDownloadError("Could not connect to the catalog URL.")
    except requests.Timeout:
        raise CatalogDownloadError("Request timed out while downloading the catalog.")
    except requests.RequestException as exc:
        raise CatalogDownloadError(f"Network error: {exc}")

    if resp.status_code in (301, 302):
        raise CatalogDownloadError(
            "The URL returned a redirect. Please use the direct URL to the catalog file."
        )

    if resp.status_code != 200:
        raise CatalogDownloadError(
            f"Server returned HTTP {resp.status_code}. "
            "Check that the URL is correct and the resource is accessible."
        )

    content_type = resp.headers.get("Content-Type", "")
    if content_type and "json" not in content_type and "octet-stream" not in content_type:
        raise CatalogDownloadError(
            f"Unexpected Content-Type '{content_type}'. Expected a JSON file."
        )

    chunks: list[bytes] = []
    received = 0
    for chunk in resp.iter_content(chunk_size=64 * 1024):
        received += len(chunk)
        if received > MAX_CATALOG_BYTES:
            raise CatalogDownloadError(
                f"Catalog exceeds the maximum allowed size of "
                f"{MAX_CATALOG_BYTES // (1024 * 1024)} MB."
            )
        chunks.append(chunk)

    raw = b"".join(chunks)
    if not raw:
        raise CatalogDownloadError("Downloaded file is empty.")

    # 3. Parse JSON
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CatalogDownloadError(f"Downloaded file is not valid JSON: {exc}")

    # 4. Structural + schema validation
    _validate_catalog_structure(data)

    # 5. Persist
    dest = output or Path("remote-catalog.json")
    dest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Remote catalog saved to %s", dest)

    return data, dest
