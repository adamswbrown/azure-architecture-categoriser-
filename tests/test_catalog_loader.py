"""Tests for remote catalog loading with security protections."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from architecture_recommendations_app.utils.catalog_loader import (
    CATALOG_ALLOWED_DOMAINS,
    MAX_ARCHITECTURE_COUNT,
    MAX_CATALOG_BYTES,
    CatalogLoadError,
    _validate_catalog_structure,
    fetch_remote_catalog,
)


# --- Minimal valid catalog for tests ---

def _make_catalog(arch_count: int = 3, **overrides) -> dict:
    """Build a minimal valid catalog dict."""
    base = {
        "version": "1.0.0",
        "generated_at": "2025-01-15T10:00:00",
        "source_repo": "https://github.com/MicrosoftDocs/architecture-center",
        "source_commit": "abc123",
        "total_architectures": arch_count,
        "architectures": [
            {
                "architecture_id": f"arch-{i}",
                "name": f"Architecture {i}",
                "description": f"Test architecture {i}",
                "source_repo_path": f"docs/arch-{i}",
                "family": "paas",
                "workload_domain": "web",
            }
            for i in range(arch_count)
        ],
    }
    base.update(overrides)
    return base


VALID_CATALOG = _make_catalog()
VALID_CATALOG_BYTES = json.dumps(VALID_CATALOG).encode("utf-8")

# Patch target for ArchitectureCatalog (imported inside _validate_catalog_structure)
_PYDANTIC_PATCH = "catalog_builder.schema.ArchitectureCatalog"


# === Structure validation tests ===


class TestValidateCatalogStructure:
    """Tests for _validate_catalog_structure."""

    def test_accepts_valid_catalog(self):
        _validate_catalog_structure(VALID_CATALOG)

    def test_rejects_non_dict(self):
        with pytest.raises(CatalogLoadError, match="JSON object"):
            _validate_catalog_structure([1, 2, 3])

    def test_rejects_missing_architectures(self):
        with pytest.raises(CatalogLoadError, match="'architectures' field"):
            _validate_catalog_structure({"version": "1.0.0"})

    def test_rejects_non_list_architectures(self):
        with pytest.raises(CatalogLoadError, match="JSON array"):
            _validate_catalog_structure({"architectures": "not a list", "version": "1"})

    def test_rejects_empty_architectures(self):
        with pytest.raises(CatalogLoadError, match="no architectures"):
            _validate_catalog_structure({"architectures": [], "version": "1"})

    def test_rejects_too_many_architectures(self):
        catalog = _make_catalog(MAX_ARCHITECTURE_COUNT + 1)
        with pytest.raises(CatalogLoadError, match="exceeds the maximum"):
            _validate_catalog_structure(catalog)

    def test_rejects_missing_version(self):
        data = {"architectures": [{"name": "test"}]}
        with pytest.raises(CatalogLoadError, match="'version' field"):
            _validate_catalog_structure(data)

    def test_rejects_entry_without_name_or_id(self):
        data = {
            "version": "1.0.0",
            "architectures": [{"description": "no name or id"}],
        }
        with pytest.raises(CatalogLoadError, match="missing both 'name'"):
            _validate_catalog_structure(data)

    def test_rejects_non_dict_entry(self):
        data = {
            "version": "1.0.0",
            "architectures": ["not a dict"],
        }
        with pytest.raises(CatalogLoadError, match="not a JSON object"):
            _validate_catalog_structure(data)

    def test_accepts_entry_with_only_name(self):
        """Entry with 'name' but no 'architecture_id' passes structural checks."""
        data = _make_catalog()
        for a in data["architectures"]:
            del a["architecture_id"]
        # Patch Pydantic validation to isolate the structural checks
        with patch(_PYDANTIC_PATCH) as mock_model:
            mock_model.model_validate.return_value = MagicMock()
            _validate_catalog_structure(data)


# === URL validation tests ===


class TestFetchRemoteCatalogURLValidation:
    """Tests that URL validation blocks dangerous URLs."""

    def test_rejects_http_url(self):
        with pytest.raises(CatalogLoadError, match="Invalid URL"):
            fetch_remote_catalog("http://example.com/catalog.json")

    def test_rejects_private_ip(self):
        with pytest.raises(CatalogLoadError, match="Invalid URL"):
            fetch_remote_catalog("https://192.168.1.1/catalog.json")

    def test_rejects_loopback(self):
        with pytest.raises(CatalogLoadError, match="Invalid URL"):
            fetch_remote_catalog("https://127.0.0.1/catalog.json")

    def test_rejects_metadata_endpoint(self):
        with pytest.raises(CatalogLoadError, match="Invalid URL"):
            fetch_remote_catalog("https://169.254.169.254/latest/meta-data/")

    def test_rejects_non_allowlisted_domain(self):
        with pytest.raises(CatalogLoadError, match="Invalid URL"):
            fetch_remote_catalog("https://evil.example.com/catalog.json")

    def test_rejects_ftp_scheme(self):
        with pytest.raises(CatalogLoadError, match="Invalid URL"):
            fetch_remote_catalog("ftp://blob.core.windows.net/catalog.json")

    def test_allows_azure_blob_domain(self):
        assert "blob.core.windows.net" in CATALOG_ALLOWED_DOMAINS

    def test_allows_github_domain(self):
        assert "github.com" in CATALOG_ALLOWED_DOMAINS

    def test_allows_microsoft_domain(self):
        assert "microsoft.com" in CATALOG_ALLOWED_DOMAINS


# === Network / response handling tests ===


def _mock_response(
    status_code=200,
    content=VALID_CATALOG_BYTES,
    content_type="application/json",
    headers=None,
):
    """Build a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {"Content-Type": content_type}
    resp.iter_content = MagicMock(return_value=[content])
    return resp


_REQUESTS_GET = "architecture_recommendations_app.utils.catalog_loader.requests.get"
_BLOB_URL = "https://myaccount.blob.core.windows.net/catalogs/catalog.json"


class TestFetchRemoteCatalogNetwork:
    """Tests for network-level behaviour of fetch_remote_catalog."""

    @patch(_REQUESTS_GET)
    @patch(_PYDANTIC_PATCH)
    def test_success_downloads_and_saves(self, mock_model, mock_get):
        mock_get.return_value = _mock_response()
        mock_model.model_validate.return_value = MagicMock()

        data, path = fetch_remote_catalog(_BLOB_URL)

        assert "architectures" in data
        assert len(data["architectures"]) == 3
        mock_get.assert_called_once()

    @patch(_REQUESTS_GET)
    def test_rejects_redirect(self, mock_get):
        mock_get.return_value = _mock_response(status_code=302)
        with pytest.raises(CatalogLoadError, match="redirect"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_rejects_404(self, mock_get):
        mock_get.return_value = _mock_response(status_code=404)
        with pytest.raises(CatalogLoadError, match="HTTP 404"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_rejects_non_json_content_type(self, mock_get):
        mock_get.return_value = _mock_response(content_type="text/html")
        with pytest.raises(CatalogLoadError, match="Content-Type"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_rejects_oversized_response(self, mock_get):
        huge_chunk = b"x" * (MAX_CATALOG_BYTES + 1)
        resp = _mock_response()
        resp.iter_content = MagicMock(return_value=[huge_chunk])
        mock_get.return_value = resp

        with pytest.raises(CatalogLoadError, match="maximum allowed size"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_rejects_empty_response(self, mock_get):
        resp = _mock_response()
        resp.iter_content = MagicMock(return_value=[])
        mock_get.return_value = resp

        with pytest.raises(CatalogLoadError, match="empty"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_rejects_invalid_json(self, mock_get):
        mock_get.return_value = _mock_response(content=b"not json {{{")
        with pytest.raises(CatalogLoadError, match="not valid JSON"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_rejects_json_without_architectures_key(self, mock_get):
        mock_get.return_value = _mock_response(
            content=json.dumps({"version": "1.0.0"}).encode()
        )
        with pytest.raises(CatalogLoadError, match="'architectures' field"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_connection_error_gives_friendly_message(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.ConnectionError("DNS resolution failed")
        with pytest.raises(CatalogLoadError, match="Could not connect"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    def test_timeout_gives_friendly_message(self, mock_get):
        import requests as req_lib
        mock_get.side_effect = req_lib.Timeout("timed out")
        with pytest.raises(CatalogLoadError, match="timed out"):
            fetch_remote_catalog(_BLOB_URL)

    @patch(_REQUESTS_GET)
    @patch(_PYDANTIC_PATCH)
    def test_allows_octet_stream_content_type(self, mock_model, mock_get):
        """Azure Blob Storage may serve as application/octet-stream."""
        mock_get.return_value = _mock_response(
            content_type="application/octet-stream"
        )
        mock_model.model_validate.return_value = MagicMock()

        data, _ = fetch_remote_catalog(_BLOB_URL)
        assert "architectures" in data

    @patch(_REQUESTS_GET)
    @patch(_PYDANTIC_PATCH)
    def test_allows_no_content_type_header(self, mock_model, mock_get):
        """Some servers may omit Content-Type entirely."""
        mock_get.return_value = _mock_response(headers={})
        mock_model.model_validate.return_value = MagicMock()

        data, _ = fetch_remote_catalog(_BLOB_URL)
        assert "architectures" in data

    @patch(_REQUESTS_GET)
    @patch(_PYDANTIC_PATCH)
    def test_disables_redirects(self, mock_model, mock_get):
        """Ensure allow_redirects=False is set."""
        mock_get.return_value = _mock_response()
        mock_model.model_validate.return_value = MagicMock()

        fetch_remote_catalog(_BLOB_URL)

        _, kwargs = mock_get.call_args
        assert kwargs["allow_redirects"] is False

    @patch(_REQUESTS_GET)
    @patch(_PYDANTIC_PATCH)
    def test_sets_timeout(self, mock_model, mock_get):
        """Ensure a timeout is set on the request."""
        mock_get.return_value = _mock_response()
        mock_model.model_validate.return_value = MagicMock()

        fetch_remote_catalog(_BLOB_URL)

        _, kwargs = mock_get.call_args
        assert kwargs["timeout"] is not None

    @patch(_REQUESTS_GET)
    def test_rejects_301_redirect(self, mock_get):
        mock_get.return_value = _mock_response(status_code=301)
        with pytest.raises(CatalogLoadError, match="redirect"):
            fetch_remote_catalog(_BLOB_URL)
