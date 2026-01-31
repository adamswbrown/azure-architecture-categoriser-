"""End-to-End Test Suite for Azure Architecture Recommender.

This comprehensive test suite validates the complete application pipeline from
security utilities through to recommendation generation.

Test Categories:
================

1. Security Utilities (TestSafePathUtility, TestValidateRepoPath, TestValidateOutputPath)
   - Path injection prevention
   - Path traversal attack protection
   - Input validation for file operations

2. Scoring Pipeline (TestEndToEndScoringPipeline)
   - Context file processing
   - Intent derivation
   - Recommendation generation
   - Result serialization

3. Component Integration (TestIntegrationWithModifiedFiles)
   - Import verification for all modified modules
   - Cross-component functionality

4. Scenario Testing (TestSyntheticScenarios)
   - Real-world migration scenario validation
   - Example context file processing

Running Tests:
=============

    # Run all end-to-end tests
    pytest tests/test_e2e.py -v

    # Run specific test class
    pytest tests/test_e2e.py::TestEndToEndScoringPipeline -v

    # Run with coverage
    pytest tests/test_e2e.py --cov=src/ --cov-report=html

Prerequisites:
=============

    - architecture-catalog.json must exist in project root
    - All dependencies installed: pip install -e ".[dev]"

Synthetic Test Data:
===================

This suite includes synthetic context data representing:
    - Cloud-native Java application (Spring Boot, PostgreSQL, Redis)
    - Legacy .NET application (.NET Framework 4.8, SQL Server, IIS)

These contexts exercise the full scoring pipeline without requiring
external data sources.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Optional

import pytest

# Import the new security utilities
from architecture_recommendations_app.utils.sanitize import (
    safe_path,
    PathValidationError,
    validate_repo_path,
    validate_output_path,
)

# Import scoring engine components
from architecture_scorer.engine import ScoringEngine
from architecture_scorer.schema import ScoringResult


# Path to catalog
CATALOG_PATH = Path(__file__).parent.parent / "architecture-catalog.json"


class TestSafePathUtility:
    """Tests for the safe_path() security utility."""

    def test_valid_absolute_path(self):
        """Test that valid absolute paths work."""
        result = safe_path("/tmp/test.json")
        assert result.is_absolute()
        assert str(result).endswith("test.json")

    def test_valid_relative_path(self):
        """Test that valid relative paths are resolved to absolute."""
        result = safe_path("test.json")
        assert result.is_absolute()

    def test_home_expansion(self):
        """Test that ~ is expanded correctly."""
        result = safe_path("~/test.json")
        assert result.is_absolute()
        assert "~" not in str(result)

    def test_rejects_null_bytes(self):
        """Test that paths with null bytes are rejected."""
        with pytest.raises(PathValidationError, match="null bytes"):
            safe_path("/tmp/test\x00.json")

    def test_rejects_path_traversal_without_base(self):
        """Test that path traversal is rejected when no base is set."""
        with pytest.raises(PathValidationError, match="traversal"):
            safe_path("../../../etc/passwd")

    def test_rejects_path_traversal_with_dots(self):
        """Test various path traversal patterns."""
        traversal_patterns = [
            "../secret.txt",
            "foo/../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/tmp/../../etc/passwd",
        ]
        for pattern in traversal_patterns:
            with pytest.raises(PathValidationError):
                safe_path(pattern)

    def test_allowed_base_containment(self):
        """Test that paths must stay within allowed_base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Valid path within base
            result = safe_path(
                str(base / "subdir" / "file.txt"),
                allowed_base=base
            )
            assert str(base) in str(result)

    def test_allowed_base_rejects_escape(self):
        """Test that escaping allowed_base is rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Try to escape the base
            with pytest.raises(PathValidationError, match="must be within"):
                safe_path("/etc/passwd", allowed_base=base)

    def test_must_exist_validation(self):
        """Test that must_exist validates path existence."""
        with pytest.raises(PathValidationError):
            safe_path("/nonexistent/path/file.json", must_exist=True)

    def test_must_exist_succeeds_for_existing(self):
        """Test that must_exist succeeds for existing files."""
        result = safe_path(str(CATALOG_PATH), must_exist=True)
        assert result.exists()

    def test_empty_path_rejected(self):
        """Test that empty paths are rejected."""
        with pytest.raises(PathValidationError, match="non-empty"):
            safe_path("")

    def test_none_path_rejected(self):
        """Test that None paths are rejected."""
        with pytest.raises(PathValidationError, match="non-empty"):
            safe_path(None)  # type: ignore


class TestValidateRepoPath:
    """Tests for validate_repo_path() utility."""

    def test_rejects_empty_path(self):
        """Test that empty paths are rejected."""
        is_valid, message, path = validate_repo_path("")
        assert not is_valid
        assert "required" in message.lower()
        assert path is None

    def test_rejects_nonexistent_path(self):
        """Test that nonexistent paths are rejected."""
        is_valid, message, path = validate_repo_path("/nonexistent/repo")
        assert not is_valid
        assert path is None

    def test_rejects_file_path(self):
        """Test that file paths (not directories) are rejected."""
        is_valid, message, path = validate_repo_path(str(CATALOG_PATH))
        assert not is_valid
        assert "not a directory" in message.lower()

    def test_rejects_directory_without_docs(self):
        """Test that directories without 'docs' folder are rejected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            is_valid, message, path = validate_repo_path(tmpdir)
            assert not is_valid
            assert "docs" in message.lower()


class TestValidateOutputPath:
    """Tests for validate_output_path() utility."""

    def test_valid_output_path(self):
        """Test that valid output paths work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "output.json")
            is_valid, message, path = validate_output_path(output)
            assert is_valid
            assert path is not None
            assert path.parent.exists()

    def test_creates_parent_directory(self):
        """Test that parent directories are created if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output = str(Path(tmpdir) / "subdir" / "output.json")
            is_valid, message, path = validate_output_path(output)
            assert is_valid
            assert path is not None
            assert path.parent.exists()

    def test_rejects_path_traversal(self):
        """Test that path traversal is rejected in output paths."""
        is_valid, message, path = validate_output_path("../../../etc/output.json")
        assert not is_valid
        assert "traversal" in message.lower()

    def test_respects_base_dir_constraint(self):
        """Test that output stays within base_dir if specified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Valid within base
            is_valid, _, path = validate_output_path(
                str(base / "output.json"),
                base_dir=base
            )
            assert is_valid

            # Invalid outside base
            is_valid, message, _ = validate_output_path(
                "/tmp/output.json",
                base_dir=base
            )
            assert not is_valid


class TestEndToEndScoringPipeline:
    """End-to-end tests for the full scoring pipeline."""

    @pytest.fixture
    def scoring_engine(self):
        """Create a scoring engine with the catalog loaded."""
        if not CATALOG_PATH.exists():
            pytest.skip(f"Catalog not found at {CATALOG_PATH}")
        engine = ScoringEngine()
        engine.load_catalog(str(CATALOG_PATH))
        return engine

    def _create_context_file(self, context_data: dict) -> Path:
        """Create a temporary context file from dict data."""
        # The scorer expects a list containing one application
        context_list = [context_data]
        fd, path = tempfile.mkstemp(suffix='.json', prefix='test_context_')
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(context_list, f)
        except Exception:
            os.close(fd)
            raise
        return Path(path)

    @pytest.fixture
    def synthetic_context_cloud_native(self):
        """Synthetic context for a cloud-native Java application."""
        return {
            "app_overview": [{
                "application": "E2ETestApp",
                "app_type": "Cloud Native Application",
                "business_crtiticality": "High",
                "treatment": "Refactor"
            }],
            "detected_technology_running": [
                "Java 17",
                "Spring Boot",
                "PostgreSQL",
                "Redis"
            ],
            "server_details": [{
                "machine": "TEST-VM-01",
                "environment": "Production",
                "OperatingSystem": "Ubuntu 22.04",
                "ip_address": ["10.0.0.10"],
                "StorageGB": 100.0,
                "MemoryGB": 16.0,
                "Cores": 4.0,
                "CPUUsage": 50.0,
                "MemoryUsage": 60.0,
                "AzureVMReadiness": "Ready",
                "migration_strategy": "Refactor",
                "treatment_option": "Cloud-native"
            }],
            "App Mod results": [{
                "technology": "Java",
                "summary": {
                    "container_ready": True,
                    "microservices_detected": True
                },
                "findings": [],
                "compatibility": {
                    "azure_kubernetes_service": "FullySupported",
                    "azure_container_apps": "Supported"
                },
                "recommended_targets": [
                    "Azure Kubernetes Service",
                    "Azure Container Apps"
                ],
                "blockers": []
            }]
        }

    @pytest.fixture
    def synthetic_context_legacy(self):
        """Synthetic context for a legacy .NET application."""
        return {
            "app_overview": [{
                "application": "LegacyERPApp",
                "app_type": "Enterprise Application",
                "business_crtiticality": "Critical",
                "treatment": "Replatform"
            }],
            "detected_technology_running": [
                ".NET Framework 4.8",
                "SQL Server 2019",
                "IIS",
                "Windows Server 2019"
            ],
            "server_details": [{
                "machine": "LEGACY-VM-01",
                "environment": "Production",
                "OperatingSystem": "Windows Server 2019",
                "ip_address": ["10.0.0.20"],
                "StorageGB": 500.0,
                "MemoryGB": 64.0,
                "Cores": 16.0,
                "CPUUsage": 70.0,
                "MemoryUsage": 80.0,
                "AzureVMReadiness": "Ready with conditions",
                "migration_strategy": "Replatform",
                "treatment_option": "PaaS"
            }],
            "App Mod results": [{
                "technology": ".NET",
                "summary": {
                    "container_ready": False,
                    "requires_windows": True
                },
                "findings": [
                    {
                        "type": "Compatibility",
                        "severity": "Medium",
                        "description": "Uses Windows-specific APIs"
                    }
                ],
                "compatibility": {
                    "azure_app_service": "Supported",
                    "azure_sql": "Supported"
                },
                "recommended_targets": [
                    "Azure App Service",
                    "Azure SQL Database"
                ],
                "blockers": []
            }]
        }

    @pytest.fixture
    def synthetic_answers(self):
        """Synthetic answers for clarification questions."""
        return {
            # Common question answer mappings
            "primary_workload_type": "web_application",
            "scaling_requirements": "auto_scaling",
            "compliance_requirements": "standard",
            "availability_requirements": "high_availability",
            "budget_priority": "balanced",
            "team_expertise": "containers",
            "deployment_preference": "managed_kubernetes",
        }

    def test_pipeline_processes_cloud_native_context(
        self, scoring_engine, synthetic_context_cloud_native
    ):
        """Test that cloud-native context is processed correctly."""
        context_file = self._create_context_file(synthetic_context_cloud_native)
        try:
            result = scoring_engine.score(str(context_file), max_recommendations=5)

            # Validate the result structure
            assert isinstance(result, ScoringResult)
            assert result.application_name == "E2ETestApp"
            assert result.derived_intent is not None
            # Check that treatment was derived
            assert result.derived_intent.treatment is not None
        finally:
            context_file.unlink()

    def test_pipeline_processes_legacy_context(
        self, scoring_engine, synthetic_context_legacy
    ):
        """Test that legacy context is processed correctly."""
        context_file = self._create_context_file(synthetic_context_legacy)
        try:
            result = scoring_engine.score(str(context_file), max_recommendations=5)

            assert isinstance(result, ScoringResult)
            assert result.application_name == "LegacyERPApp"
            assert result.derived_intent is not None
            # Check that treatment was derived
            assert result.derived_intent.treatment is not None
        finally:
            context_file.unlink()

    def test_pipeline_generates_recommendations(
        self, scoring_engine, synthetic_context_cloud_native
    ):
        """Test that recommendations are generated."""
        context_file = self._create_context_file(synthetic_context_cloud_native)
        try:
            result = scoring_engine.score(str(context_file), max_recommendations=5)

            # Should have recommendations
            assert result is not None
            assert hasattr(result, 'recommendations')
            # Refactor treatment should produce recommendations
            assert len(result.recommendations) > 0
        finally:
            context_file.unlink()

    def test_pipeline_result_structure(
        self, scoring_engine, synthetic_context_cloud_native
    ):
        """Test that results have expected structure."""
        context_file = self._create_context_file(synthetic_context_cloud_native)
        try:
            result = scoring_engine.score(str(context_file), max_recommendations=5)

            # Check result structure
            assert result.summary is not None
            assert result.summary.confidence_level in ["High", "Medium", "Low"]
            assert isinstance(result.recommendations, list)
            assert isinstance(result.excluded, list)
        finally:
            context_file.unlink()

    def test_pipeline_result_serializable(
        self, scoring_engine, synthetic_context_cloud_native
    ):
        """Test that results can be serialized to JSON."""
        context_file = self._create_context_file(synthetic_context_cloud_native)
        try:
            result = scoring_engine.score(str(context_file), max_recommendations=5)

            # Should be serializable
            result_dict = result.model_dump(mode='json')
            json_str = json.dumps(result_dict, default=str)
            assert len(json_str) > 0

            # Should be deserializable
            parsed = json.loads(json_str)
            assert isinstance(parsed, dict)
            assert 'recommendations' in parsed
        finally:
            context_file.unlink()

    def test_recommendations_have_scores(
        self, scoring_engine, synthetic_context_cloud_native
    ):
        """Test that recommendations include scores."""
        context_file = self._create_context_file(synthetic_context_cloud_native)
        try:
            result = scoring_engine.score(str(context_file), max_recommendations=5)

            for rec in result.recommendations[:3]:
                # Each recommendation should have a score and ID
                assert hasattr(rec, 'likelihood_score')
                assert rec.likelihood_score >= 0
                assert hasattr(rec, 'architecture_id')
                assert rec.architecture_id is not None
        finally:
            context_file.unlink()


class TestIntegrationWithModifiedFiles:
    """Test that all modified files work together correctly."""

    def test_sanitize_imports_work(self):
        """Test that all imports from sanitize.py work."""
        from architecture_recommendations_app.utils.sanitize import (
            safe_path,
            PathValidationError,
            validate_repo_path,
            validate_output_path,
            safe_html,
            validate_url,
            safe_url,
            sanitize_filename,
            secure_temp_file,
            secure_temp_directory,
        )

        # All should be callable
        assert callable(safe_path)
        assert callable(validate_repo_path)
        assert callable(validate_output_path)
        assert callable(safe_html)
        assert callable(validate_url)
        assert callable(safe_url)
        assert callable(sanitize_filename)

    def test_preview_panel_imports_work(self):
        """Test that preview_panel.py imports work."""
        from catalog_builder_gui.components.preview_panel import render_preview_panel
        assert callable(render_preview_panel)

    def test_config_editor_imports_work(self):
        """Test that config_editor.py imports work."""
        from catalog_builder_gui.components.config_editor import render_config_editor
        assert callable(render_config_editor)

    def test_catalog_builder_gui_imports_work(self):
        """Test that catalog_builder_gui/app.py imports work."""
        from catalog_builder_gui.app import clone_repository
        assert callable(clone_repository)

    def test_combined_security_utilities(self):
        """Test security utilities work together."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)

            # Create a test structure
            docs_dir = base / "docs"
            docs_dir.mkdir()
            (docs_dir / "test.md").write_text("# Test")

            # Validate as repo path
            is_valid, message, path = validate_repo_path(str(base))
            assert is_valid, f"Should be valid: {message}"

            # Create output path within the validated repo
            output_file = base / "output" / "catalog.json"
            is_valid, message, output_path = validate_output_path(str(output_file))
            assert is_valid, f"Should be valid: {message}"
            assert output_path.parent.exists()


class TestSyntheticScenarios:
    """Test various synthetic migration scenarios using example files."""

    @pytest.fixture
    def engine(self):
        """Create scoring engine."""
        if not CATALOG_PATH.exists():
            pytest.skip("Catalog not found")
        engine = ScoringEngine()
        engine.load_catalog(str(CATALOG_PATH))
        return engine

    @pytest.mark.parametrize("scenario_file", [
        "01-java-refactor-aks.json",
        "02-dotnet-replatform-appservice.json",
        "07-greenfield-cloud-native-perfect.json",
        "09-rehost-vm-lift-shift.json",
        "13-highly-regulated-healthcare.json",
    ])
    def test_scenario_from_examples(self, engine, scenario_file):
        """Test scoring against example scenario files."""
        context_path = Path(__file__).parent.parent / "examples" / "context_files" / scenario_file

        if not context_path.exists():
            pytest.skip(f"Example file not found: {scenario_file}")

        # Use the score() method which takes a file path
        result = engine.score(str(context_path), max_recommendations=5)

        assert result is not None
        assert isinstance(result, ScoringResult)
        assert result.application_name is not None
        assert result.derived_intent is not None
        assert result.summary is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
