"""Tests for Azure Blob Storage upload functionality."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from catalog_builder.blob_upload import (
    _check_azure_deps,
    _extract_catalog_metadata,
    upload_catalog_to_blob,
)


# --- Sample catalog fixture ---

SAMPLE_CATALOG = {
    "version": "1.0.0",
    "generated_at": "2025-01-15T10:00:00Z",
    "source_repo": "https://github.com/MicrosoftDocs/architecture-center",
    "source_commit": "abc123def456789",
    "total_architectures": 50,
    "architectures": [],
}


@pytest.fixture
def catalog_file(tmp_path):
    """Create a temporary catalog JSON file."""
    path = tmp_path / "architecture-catalog.json"
    path.write_text(json.dumps(SAMPLE_CATALOG), encoding="utf-8")
    return path


# --- Metadata extraction tests ---


class TestExtractCatalogMetadata:
    """Tests for _extract_catalog_metadata."""

    def test_extracts_all_fields(self, catalog_file):
        metadata = _extract_catalog_metadata(catalog_file)
        assert metadata["catalog_version"] == "1.0.0"
        assert metadata["total_architectures"] == "50"
        assert metadata["generated_at"] == "2025-01-15T10:00:00Z"
        assert metadata["source_commit"] == "abc123def456"
        assert metadata["source_repo"] == "https://github.com/MicrosoftDocs/architecture-center"

    def test_handles_missing_optional_fields(self, tmp_path):
        path = tmp_path / "minimal.json"
        path.write_text(json.dumps({"architectures": []}), encoding="utf-8")
        metadata = _extract_catalog_metadata(path)
        assert "source_commit" not in metadata
        assert "catalog_version" not in metadata

    def test_truncates_long_commit(self, tmp_path):
        path = tmp_path / "long_commit.json"
        data = {**SAMPLE_CATALOG, "source_commit": "a" * 40}
        path.write_text(json.dumps(data), encoding="utf-8")
        metadata = _extract_catalog_metadata(path)
        assert len(metadata["source_commit"]) == 12

    def test_handles_null_commit(self, tmp_path):
        path = tmp_path / "null_commit.json"
        data = {**SAMPLE_CATALOG, "source_commit": None}
        path.write_text(json.dumps(data), encoding="utf-8")
        metadata = _extract_catalog_metadata(path)
        assert "source_commit" not in metadata


# --- Dependency check tests ---


class TestCheckAzureDeps:
    """Tests for _check_azure_deps."""

    def test_raises_when_azure_not_installed(self):
        """Missing azure-storage-blob raises ImportError with install hint."""
        import importlib
        import sys

        # Temporarily remove azure.storage.blob from importable modules
        with patch.dict(sys.modules, {"azure.storage.blob": None, "azure": None}):
            with patch("builtins.__import__", side_effect=ImportError("No module")):
                with pytest.raises(ImportError, match="pip install"):
                    _check_azure_deps()


# --- Upload function tests ---


class TestUploadCatalogToBlob:
    """Tests for upload_catalog_to_blob."""

    @patch("catalog_builder.blob_upload._check_azure_deps")
    def test_raises_without_auth(self, mock_deps, catalog_file):
        """Must provide at least one auth method."""
        with pytest.raises(ValueError, match="No authentication method"):
            upload_catalog_to_blob(catalog_file)

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_sas_url")
    def test_sas_url_takes_priority(self, mock_sas, mock_deps, catalog_file):
        mock_sas.return_value = "https://acct.blob.core.windows.net/c/b"

        result = upload_catalog_to_blob(
            catalog_file,
            blob_url="https://acct.blob.core.windows.net/c/b?sv=2021",
            connection_string="DefaultEndpointsProtocol=https;...",
        )

        mock_sas.assert_called_once()
        assert result == "https://acct.blob.core.windows.net/c/b"

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_connection_string")
    def test_connection_string_used_when_no_sas(self, mock_conn, mock_deps, catalog_file):
        mock_conn.return_value = "https://acct.blob.core.windows.net/catalogs/architecture-catalog.json"

        upload_catalog_to_blob(
            catalog_file,
            connection_string="DefaultEndpointsProtocol=https;AccountName=acct;...",
            container_name="catalogs",
        )

        mock_conn.assert_called_once()
        args = mock_conn.call_args
        assert args[0][1] == "DefaultEndpointsProtocol=https;AccountName=acct;..."
        assert args[0][2] == "catalogs"

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_default_credential")
    def test_default_credential_used_as_fallback(self, mock_dc, mock_deps, catalog_file):
        mock_dc.return_value = "https://acct.blob.core.windows.net/catalogs/architecture-catalog.json"

        upload_catalog_to_blob(
            catalog_file,
            account_url="https://acct.blob.core.windows.net",
            container_name="mycontainer",
        )

        mock_dc.assert_called_once()
        args = mock_dc.call_args
        assert args[0][1] == "https://acct.blob.core.windows.net"
        assert args[0][2] == "mycontainer"

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_sas_url")
    def test_default_blob_name_is_filename(self, mock_sas, mock_deps, catalog_file):
        mock_sas.return_value = "https://acct.blob.core.windows.net/c/architecture-catalog.json"

        upload_catalog_to_blob(catalog_file, blob_url="https://acct.blob.core.windows.net/c/b?sv=2021")

        args = mock_sas.call_args
        # blob_name should be the catalog filename
        assert args[0][2] == "architecture-catalog.json"

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_sas_url")
    def test_custom_blob_name(self, mock_sas, mock_deps, catalog_file):
        mock_sas.return_value = "https://acct.blob.core.windows.net/c/custom.json"

        upload_catalog_to_blob(
            catalog_file,
            blob_url="https://acct.blob.core.windows.net/c/b?sv=2021",
            blob_name="custom.json",
        )

        args = mock_sas.call_args
        assert args[0][2] == "custom.json"

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_connection_string")
    def test_overwrite_flag_passed_through(self, mock_conn, mock_deps, catalog_file):
        mock_conn.return_value = "https://acct.blob.core.windows.net/c/b"

        upload_catalog_to_blob(
            catalog_file,
            connection_string="conn",
            overwrite=False,
        )

        args = mock_conn.call_args
        assert args[0][4] is False  # overwrite parameter

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_connection_string")
    def test_default_container_name(self, mock_conn, mock_deps, catalog_file):
        mock_conn.return_value = "https://acct.blob.core.windows.net/catalogs/b"

        upload_catalog_to_blob(catalog_file, connection_string="conn")

        args = mock_conn.call_args
        assert args[0][2] == "catalogs"  # default container name

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_sas_url")
    def test_metadata_passed_to_upload(self, mock_sas, mock_deps, catalog_file):
        mock_sas.return_value = "https://acct.blob.core.windows.net/c/b"

        upload_catalog_to_blob(catalog_file, blob_url="https://acct.blob.core.windows.net/c/b?sv=2021")

        args = mock_sas.call_args
        metadata = args[0][4]  # metadata parameter
        assert "catalog_version" in metadata
        assert metadata["total_architectures"] == "50"


# --- SAS URL path parsing tests ---


class TestSasUrlParsing:
    """Tests that SAS URL parsing correctly distinguishes blob vs container URLs.

    These tests exercise the public upload_catalog_to_blob function with
    _upload_via_sas_url mocked, since the Azure SDK is not installed in tests.
    """

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_sas_url")
    def test_blob_level_url_passes_full_url(self, mock_sas, mock_deps, catalog_file):
        """A blob-level SAS URL (multi-segment path) is passed through."""
        mock_sas.return_value = "https://acct.blob.core.windows.net/container/blob.json"

        result = upload_catalog_to_blob(
            catalog_file,
            blob_url="https://acct.blob.core.windows.net/container/blob.json?sv=2021",
        )

        mock_sas.assert_called_once()
        assert result == "https://acct.blob.core.windows.net/container/blob.json"

    @patch("catalog_builder.blob_upload._check_azure_deps")
    @patch("catalog_builder.blob_upload._upload_via_sas_url")
    def test_container_level_url_passes_through(self, mock_sas, mock_deps, catalog_file):
        """A container-level SAS URL (single-segment path) is passed through."""
        mock_sas.return_value = "https://acct.blob.core.windows.net/container/architecture-catalog.json"

        result = upload_catalog_to_blob(
            catalog_file,
            blob_url="https://acct.blob.core.windows.net/container?sv=2021",
        )

        mock_sas.assert_called_once()
        # blob_name defaults to the filename
        args = mock_sas.call_args[0]
        assert args[2] == "architecture-catalog.json"  # blob_name


# --- CLI integration tests ---


class TestUploadCLI:
    """Tests for the upload CLI command."""

    def test_upload_command_exists(self):
        """The upload command is registered."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["upload", "--help"])
        assert result.exit_code == 0
        assert "Azure Blob Storage" in result.output

    def test_upload_requires_auth(self, catalog_file):
        """Upload fails without any auth option."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["upload", "--catalog", str(catalog_file)])
        assert result.exit_code != 0
        assert "Provide one of" in result.output

    def test_build_catalog_has_upload_url_option(self):
        """The build-catalog command has --upload-url option."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()
        result = runner.invoke(main, ["build-catalog", "--help"])
        assert result.exit_code == 0
        assert "--upload-url" in result.output

    def test_upload_shows_auth_method(self, catalog_file):
        """Upload displays which auth method is being used."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()

        with patch("catalog_builder.cli.upload_catalog_to_blob") as mock_upload:
            mock_upload.return_value = "https://acct.blob.core.windows.net/c/b"
            result = runner.invoke(main, [
                "upload",
                "--catalog", str(catalog_file),
                "--blob-url", "https://acct.blob.core.windows.net/c/b?sv=2021",
            ])

        assert "SAS URL" in result.output
        assert result.exit_code == 0

    def test_upload_handles_import_error(self, catalog_file):
        """Upload shows helpful error when azure SDK is missing."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()

        with patch("catalog_builder.cli.upload_catalog_to_blob") as mock_upload:
            mock_upload.side_effect = ImportError(
                "Azure Blob Storage upload requires the 'azure' extras.\n"
                "Install with: pip install -e '.[azure]'"
            )
            result = runner.invoke(main, [
                "upload",
                "--catalog", str(catalog_file),
                "--blob-url", "https://acct.blob.core.windows.net/c/b?sv=2021",
            ])

        assert result.exit_code != 0
        assert "pip install" in result.output

    def test_upload_with_connection_string(self, catalog_file):
        """Upload works with connection string auth."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()

        with patch("catalog_builder.cli.upload_catalog_to_blob") as mock_upload:
            mock_upload.return_value = "https://acct.blob.core.windows.net/catalogs/b"
            result = runner.invoke(main, [
                "upload",
                "--catalog", str(catalog_file),
                "--connection-string", "DefaultEndpointsProtocol=https;AccountName=acct;...",
                "--container-name", "mycontainer",
            ])

        assert "Connection String" in result.output
        assert result.exit_code == 0
        mock_upload.assert_called_once()
        kwargs = mock_upload.call_args.kwargs
        assert kwargs["connection_string"] == "DefaultEndpointsProtocol=https;AccountName=acct;..."
        assert kwargs["container_name"] == "mycontainer"

    def test_upload_with_account_url(self, catalog_file):
        """Upload works with DefaultAzureCredential auth."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()

        with patch("catalog_builder.cli.upload_catalog_to_blob") as mock_upload:
            mock_upload.return_value = "https://acct.blob.core.windows.net/catalogs/b"
            result = runner.invoke(main, [
                "upload",
                "--catalog", str(catalog_file),
                "--account-url", "https://acct.blob.core.windows.net",
            ])

        assert "DefaultAzureCredential" in result.output
        assert result.exit_code == 0

    def test_upload_no_overwrite(self, catalog_file):
        """Upload passes --no-overwrite flag correctly."""
        from click.testing import CliRunner
        from catalog_builder.cli import main

        runner = CliRunner()

        with patch("catalog_builder.cli.upload_catalog_to_blob") as mock_upload:
            mock_upload.return_value = "https://acct.blob.core.windows.net/c/b"
            result = runner.invoke(main, [
                "upload",
                "--catalog", str(catalog_file),
                "--blob-url", "https://acct.blob.core.windows.net/c/b?sv=2021",
                "--no-overwrite",
            ])

        kwargs = mock_upload.call_args.kwargs
        assert kwargs["overwrite"] is False
