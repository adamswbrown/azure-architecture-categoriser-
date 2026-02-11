"""Remote catalog loading for the web app.

Thin wrapper around catalog_builder.catalog_download that resolves
the save path relative to the project root (so the file persists
across Streamlit reruns).
"""

from pathlib import Path
from typing import Optional

from catalog_builder.catalog_download import (
    CATALOG_ALLOWED_DOMAINS,
    MAX_ARCHITECTURE_COUNT,
    MAX_CATALOG_BYTES,
    CatalogDownloadError as CatalogLoadError,
    download_catalog,
)

# Re-export for backwards compatibility with Recommendations.py
__all__ = [
    "CATALOG_ALLOWED_DOMAINS",
    "MAX_ARCHITECTURE_COUNT",
    "MAX_CATALOG_BYTES",
    "CatalogLoadError",
    "fetch_remote_catalog",
]


def fetch_remote_catalog(
    url: str,
    *,
    allowed_domains: Optional[frozenset[str]] = None,
) -> tuple[dict, Path]:
    """Download, validate, and persist a remote catalog.

    Saves to ``<project_root>/remote-catalog.json`` so the file is
    available across Streamlit session restarts.
    """
    project_root = Path(__file__).parent.parent.parent.parent
    dest = project_root / "remote-catalog.json"

    return download_catalog(
        url,
        output=dest,
        allowed_domains=allowed_domains,
    )
