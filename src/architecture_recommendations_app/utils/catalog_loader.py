"""Secure remote catalog loading from URLs.

Downloads architecture catalog JSON files from remote URLs (e.g. Azure Blob
Storage) with protections against malicious content:

- URL validation via domain allowlist and SSRF checks
- Response size cap to prevent memory exhaustion
- JSON structure validation via Pydantic model
- Architecture count ceiling to reject implausibly large payloads
- Content-Type verification
- Connection and read timeouts
"""

import json
import logging
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

from architecture_recommendations_app.utils.sanitize import (
    BLOCKED_HOSTNAMES,
    BLOCKED_IP_RANGES,
    _is_ip_blocked,
)

logger = logging.getLogger(__name__)

# ── Limits ──────────────────────────────────────────────────────────────────
MAX_CATALOG_BYTES = 50 * 1024 * 1024  # 50 MB - generous but bounded
MAX_ARCHITECTURE_COUNT = 500  # no real-world catalog should exceed this
REQUEST_TIMEOUT = (10, 30)  # (connect, read) seconds

# Domains allowed for catalog downloads.
# Uses suffix matching: "blob.core.windows.net" matches
# "myaccount.blob.core.windows.net".
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


class CatalogLoadError(Exception):
    """Raised when a remote catalog cannot be loaded."""


def _validate_catalog_url(
    url: str,
    allowed_domains: frozenset[str],
) -> tuple[bool, str]:
    """Validate a catalog URL with proper subdomain matching.

    Unlike the shared validate_url (which uses a 2-part suffix), this
    checks whether the hostname *ends with* any allowed domain, so
    ``myaccount.blob.core.windows.net`` correctly matches
    ``blob.core.windows.net``.
    """
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

    # Block cloud metadata / internal endpoints
    if hostname in BLOCKED_HOSTNAMES:
        return False, "URL hostname is blocked"

    if _is_ip_blocked(hostname):
        return False, "URL points to a private/internal IP address"

    # Subdomain-aware allowlist check
    for domain in allowed_domains:
        if hostname == domain or hostname.endswith("." + domain):
            return True, ""

    return False, f"URL domain '{hostname}' is not in the allowed list"


def fetch_remote_catalog(
    url: str,
    *,
    allowed_domains: Optional[frozenset[str]] = None,
) -> tuple[dict, Path]:
    """Download, validate, and persist a remote catalog.

    Args:
        url: HTTPS URL pointing to a catalog JSON file.
        allowed_domains: Override the domain allowlist (mainly for testing).

    Returns:
        Tuple of (catalog_dict, path_to_saved_file).
        The saved file is written to the project-local directory so it
        persists across Streamlit reruns.

    Raises:
        CatalogLoadError: On any validation or network failure.
    """
    domains = allowed_domains or CATALOG_ALLOWED_DOMAINS

    # ── 1. Validate URL ─────────────────────────────────────────────────
    valid, err = _validate_catalog_url(url, domains)
    if not valid:
        raise CatalogLoadError(f"Invalid URL: {err}")

    # ── 2. Download with size guard ─────────────────────────────────────
    try:
        resp = requests.get(
            url,
            timeout=REQUEST_TIMEOUT,
            stream=True,
            headers={"Accept": "application/json"},
            allow_redirects=False,
        )
    except requests.ConnectionError:
        raise CatalogLoadError("Could not connect to the catalog URL.")
    except requests.Timeout:
        raise CatalogLoadError("Request timed out while downloading the catalog.")
    except requests.RequestException as exc:
        raise CatalogLoadError(f"Network error: {exc}")

    if resp.status_code in (301, 302):
        raise CatalogLoadError(
            "The URL returned a redirect. Please use the direct URL to the catalog file."
        )

    if resp.status_code != 200:
        raise CatalogLoadError(
            f"Server returned HTTP {resp.status_code}. "
            "Check that the URL is correct and the resource is accessible."
        )

    # Verify content type if the server provides one
    content_type = resp.headers.get("Content-Type", "")
    if content_type and "json" not in content_type and "octet-stream" not in content_type:
        raise CatalogLoadError(
            f"Unexpected Content-Type '{content_type}'. Expected a JSON file."
        )

    # Read body in chunks, enforcing the size limit
    chunks: list[bytes] = []
    received = 0
    for chunk in resp.iter_content(chunk_size=64 * 1024):
        received += len(chunk)
        if received > MAX_CATALOG_BYTES:
            raise CatalogLoadError(
                f"Catalog exceeds the maximum allowed size of "
                f"{MAX_CATALOG_BYTES // (1024 * 1024)} MB."
            )
        chunks.append(chunk)

    raw = b"".join(chunks)

    if not raw:
        raise CatalogLoadError("Downloaded file is empty.")

    # ── 3. Parse JSON ───────────────────────────────────────────────────
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CatalogLoadError(f"Downloaded file is not valid JSON: {exc}")

    # ── 4. Structural validation ────────────────────────────────────────
    _validate_catalog_structure(data)

    # ── 5. Persist to local file ────────────────────────────────────────
    project_root = Path(__file__).parent.parent.parent.parent
    dest = project_root / "remote-catalog.json"

    dest.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    logger.info("Remote catalog saved to %s", dest)

    return data, dest


def _validate_catalog_structure(data: dict) -> None:
    """Validate the essential shape of a catalog without importing heavy models.

    Checks performed:
    - Top-level must be a dict
    - Must contain an 'architectures' key with a list value
    - Architecture count must be <= MAX_ARCHITECTURE_COUNT
    - Each entry must have at least 'name' or 'architecture_id'
    - 'version' field should be present
    """
    if not isinstance(data, dict):
        raise CatalogLoadError(
            "Catalog must be a JSON object with an 'architectures' key."
        )

    if "architectures" not in data:
        raise CatalogLoadError(
            "Catalog is missing the required 'architectures' field."
        )

    architectures = data["architectures"]
    if not isinstance(architectures, list):
        raise CatalogLoadError("'architectures' must be a JSON array.")

    if len(architectures) == 0:
        raise CatalogLoadError("Catalog contains no architectures.")

    if len(architectures) > MAX_ARCHITECTURE_COUNT:
        raise CatalogLoadError(
            f"Catalog contains {len(architectures)} architectures, which exceeds "
            f"the maximum of {MAX_ARCHITECTURE_COUNT}. This may not be a valid catalog."
        )

    if "version" not in data:
        raise CatalogLoadError(
            "Catalog is missing the 'version' field. This may not be a valid catalog file."
        )

    # Spot-check a few entries to make sure they look like architectures
    for i, entry in enumerate(architectures[:5]):
        if not isinstance(entry, dict):
            raise CatalogLoadError(
                f"Architecture entry at index {i} is not a JSON object."
            )
        if "name" not in entry and "architecture_id" not in entry:
            raise CatalogLoadError(
                f"Architecture entry at index {i} is missing both 'name' and "
                f"'architecture_id'. This does not look like a valid catalog."
            )

    # Full Pydantic validation to catch schema drift or tampered payloads
    try:
        from catalog_builder.schema import ArchitectureCatalog
        ArchitectureCatalog.model_validate(data)
    except Exception as exc:
        raise CatalogLoadError(
            f"Catalog failed schema validation: {exc}"
        )
