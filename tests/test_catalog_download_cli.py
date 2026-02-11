"""Tests for the catalog download CLI command and --catalog-url option."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from catalog_builder.cli import main as catalog_builder_cli
from architecture_scorer.cli import main as scorer_cli

# Reuse the catalog factory from the download tests
VALID_CATALOG = {
    "version": "1.0.0",
    "generated_at": "2025-01-15T10:00:00",
    "source_repo": "https://github.com/MicrosoftDocs/architecture-center",
    "source_commit": "abc123",
    "total_architectures": 2,
    "architectures": [
        {
            "architecture_id": f"arch-{i}",
            "name": f"Architecture {i}",
            "description": f"Test architecture {i}",
            "source_repo_path": f"docs/arch-{i}",
            "family": "paas",
            "workload_domain": "web",
        }
        for i in range(2)
    ],
}

_DOWNLOAD_PATCH = "catalog_builder.catalog_download.download_catalog"
_BLOB_URL = "https://myaccount.blob.core.windows.net/catalogs/catalog.json"


# === catalog-builder download ===


class TestCatalogBuilderDownloadCLI:
    """Tests for the 'catalog-builder download' command."""

    def test_download_help(self):
        runner = CliRunner()
        result = runner.invoke(catalog_builder_cli, ["download", "--help"])
        assert result.exit_code == 0
        assert "Download a catalog from a remote URL" in result.output

    @patch("catalog_builder.cli.download_catalog")
    def test_download_success(self, mock_download, tmp_path):
        dest = tmp_path / "catalog.json"
        mock_download.return_value = (VALID_CATALOG, dest)

        runner = CliRunner()
        result = runner.invoke(catalog_builder_cli, [
            "download",
            "--url", _BLOB_URL,
            "--out", str(dest),
        ])

        assert result.exit_code == 0
        assert "2 architectures" in result.output
        mock_download.assert_called_once_with(_BLOB_URL, output=dest)

    @patch("catalog_builder.cli.download_catalog")
    def test_download_verbose_shows_settings(self, mock_download, tmp_path):
        dest = tmp_path / "catalog.json"
        catalog_with_settings = {
            **VALID_CATALOG,
            "generation_settings": {
                "allowed_topics": ["reference-architecture"],
                "exclude_examples": True,
            },
        }
        mock_download.return_value = (catalog_with_settings, dest)

        runner = CliRunner()
        result = runner.invoke(catalog_builder_cli, [
            "download",
            "--url", _BLOB_URL,
            "--out", str(dest),
            "--verbose",
        ])

        assert result.exit_code == 0
        assert "reference-architecture" in result.output

    @patch("catalog_builder.cli.download_catalog")
    def test_download_failure_exits_with_error(self, mock_download):
        from catalog_builder.catalog_download import CatalogDownloadError
        mock_download.side_effect = CatalogDownloadError("Connection refused")

        runner = CliRunner()
        result = runner.invoke(catalog_builder_cli, [
            "download",
            "--url", _BLOB_URL,
        ])

        assert result.exit_code != 0
        assert "Connection refused" in result.output

    def test_download_requires_url(self):
        runner = CliRunner()
        result = runner.invoke(catalog_builder_cli, ["download"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()


# === architecture-scorer score --catalog-url ===


class TestScorerCatalogURL:
    """Tests for --catalog-url on the scorer CLI."""

    def test_score_help_shows_catalog_url(self):
        runner = CliRunner()
        result = runner.invoke(scorer_cli, ["score", "--help"])
        assert result.exit_code == 0
        assert "--catalog-url" in result.output

    def test_questions_help_shows_catalog_url(self):
        runner = CliRunner()
        result = runner.invoke(scorer_cli, ["questions", "--help"])
        assert result.exit_code == 0
        assert "--catalog-url" in result.output

    def test_score_requires_catalog_or_url(self):
        """Should fail when neither --catalog nor --catalog-url is given."""
        runner = CliRunner()
        result = runner.invoke(scorer_cli, [
            "score",
            "--context", "/dev/null",
            "--no-interactive",
        ])
        # The _resolve_catalog helper prints an error and exits
        assert result.exit_code != 0

    @patch("architecture_scorer.cli.download_catalog")
    @patch("architecture_scorer.cli.ScoringEngine")
    def test_score_with_catalog_url(self, mock_engine_cls, mock_download, tmp_path):
        """--catalog-url downloads, then passes the local path to the engine."""
        # Setup: create a fake context file
        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text(json.dumps({"app_overview": []}))

        dest = tmp_path / "remote-catalog.json"
        mock_download.return_value = (VALID_CATALOG, dest)

        mock_engine = MagicMock()
        mock_engine_cls.return_value = mock_engine
        # Make score() return a result with the minimum fields
        mock_result = MagicMock()
        mock_result.clarification_questions = []
        mock_result.recommendations = []
        mock_result.processing_warnings = []
        mock_result.summary.primary_recommendation = "Test"
        mock_result.summary.confidence_level = "High"
        mock_result.summary.key_drivers = []
        mock_result.summary.key_risks = []
        mock_result.eligible_count = 1
        mock_result.excluded_count = 0
        mock_result.application_name = "Test"
        mock_engine.score.return_value = mock_result

        runner = CliRunner()
        result = runner.invoke(scorer_cli, [
            "score",
            "--catalog-url", _BLOB_URL,
            "--context", str(ctx_file),
            "--no-interactive",
        ])

        mock_download.assert_called_once_with(_BLOB_URL)
        mock_engine.load_catalog.assert_called_once_with(str(dest))

    @patch("architecture_scorer.cli.download_catalog")
    def test_score_catalog_url_download_failure(self, mock_download, tmp_path):
        from catalog_builder.catalog_download import CatalogDownloadError
        mock_download.side_effect = CatalogDownloadError("Invalid URL: blocked")

        ctx_file = tmp_path / "ctx.json"
        ctx_file.write_text(json.dumps({"app_overview": []}))

        runner = CliRunner()
        result = runner.invoke(scorer_cli, [
            "score",
            "--catalog-url", "https://evil.com/bad.json",
            "--context", str(ctx_file),
            "--no-interactive",
        ])

        assert result.exit_code != 0
        assert "Download failed" in result.output
