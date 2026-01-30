"""Tests for the catalog builder."""

import json
import tempfile
from pathlib import Path

import pytest

from catalog_builder.parser import MarkdownParser, ParsedDocument, ArchitectureMetadata
from catalog_builder.detector import ArchitectureDetector, DetectionResult
from catalog_builder.extractor import MetadataExtractor
from catalog_builder.classifier import ArchitectureClassifier
from catalog_builder.schema import (
    ArchitectureEntry,
    ArchitectureCatalog,
    ArchitectureFamily,
    Complexity,
    ComplexityLevel,
    CostProfile,
    ExclusionReason,
    OperatingModel,
    RuntimeModel,
    SecurityLevel,
    TimeCategory,
    Treatment,
    WorkloadDomain,
)


class TestMarkdownParser:
    """Tests for the markdown parser."""

    def test_parse_frontmatter(self):
        """Test parsing YAML frontmatter."""
        parser = MarkdownParser()
        content = """---
title: Test Architecture
description: A test architecture description
ms.topic: architecture
---

# Test Architecture

This is the content.
"""
        doc = parser.parse_content(content, Path("test.md"))

        assert doc.title == "Test Architecture"
        assert doc.description == "A test architecture description"
        assert doc.frontmatter.get("ms.topic") == "architecture"

    def test_parse_headings(self):
        """Test extracting headings."""
        parser = MarkdownParser()
        content = """# Main Title

## Architecture

Some content.

## Components

More content.

### Sub Component

Details.
"""
        doc = parser.parse_content(content, Path("test.md"))

        assert len(doc.headings) == 4
        assert (1, "Main Title") in doc.headings
        assert (2, "Architecture") in doc.headings
        assert (2, "Components") in doc.headings
        assert (3, "Sub Component") in doc.headings

    def test_parse_images(self):
        """Test extracting images."""
        parser = MarkdownParser()
        content = """# Test

![Architecture diagram](./images/architecture.svg)
![Flow](./diagrams/flow.png)
"""
        doc = parser.parse_content(content, Path("test.md"))

        assert len(doc.images) == 2
        assert "./images/architecture.svg" in doc.images
        assert "./diagrams/flow.png" in doc.images

    def test_extract_azure_services(self):
        """Test Azure service extraction."""
        parser = MarkdownParser()
        content = """# Architecture

This solution uses Azure Kubernetes Service (AKS) and Azure Cosmos DB
for data storage. It also leverages Azure Functions for serverless
compute and Azure API Management for the API gateway.
"""
        doc = parser.parse_content(content, Path("test.md"))
        services = parser.extract_azure_services(doc)

        assert "Azure Kubernetes Service" in services
        assert "Azure Cosmos DB" in services
        assert "Azure Functions" in services
        assert "Azure API Management" in services


class TestArchitectureDetector:
    """Tests for architecture detection."""

    def test_detect_by_sections(self):
        """Test detection by architecture sections."""
        parser = MarkdownParser()
        detector = ArchitectureDetector()

        content = """---
title: Web App Architecture
---

# Web App Architecture

## Architecture

The architecture consists of...

## Components

- Azure App Service
- Azure SQL Database

![Architecture](./arch.svg)
"""
        doc = parser.parse_content(content, Path("docs/example-scenario/test.md"))

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "docs/example-scenario").mkdir(parents=True)
            doc.path = repo_root / "docs/example-scenario/test.md"

            result = detector.detect(doc, repo_root)

            assert result.is_architecture
            assert result.confidence > 0.5
            assert len(result.reasons) > 0

    def test_exclude_guide_folder(self):
        """Test that guide folder is excluded."""
        parser = MarkdownParser()
        detector = ArchitectureDetector()

        content = """# Best Practices Guide

This is a guide, not an architecture.
"""
        doc = parser.parse_content(content, Path("docs/guide/test.md"))

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            (repo_root / "docs/guide").mkdir(parents=True)
            doc.path = repo_root / "docs/guide/test.md"

            result = detector.detect(doc, repo_root)

            assert not result.is_architecture
            assert len(result.exclusion_reasons) > 0


class TestMetadataExtractor:
    """Tests for metadata extraction."""

    def test_generate_id(self):
        """Test architecture ID generation."""
        parser = MarkdownParser()
        extractor = MetadataExtractor(parser)

        # Test normal path
        id1 = extractor._generate_id("docs/example-scenario/web-app/index.md")
        assert "example-scenario-web-app" in id1

        # Test path normalization
        id2 = extractor._generate_id("docs/data/analytics/big-data.md")
        assert "data-analytics-big-data" in id2

    def test_build_learn_url(self):
        """Test URL generation uses Microsoft Learn direct paths."""
        parser = MarkdownParser()
        extractor = MetadataExtractor(parser)

        # Learn URL format: https://learn.microsoft.com/en-us/azure/architecture/{path}
        url = extractor._build_learn_url("docs/example-scenario/web-app/index.md")
        assert url == "https://learn.microsoft.com/en-us/azure/architecture/example-scenario/web-app/index"

        # Test a -content file (typical architecture document) - suffix should be stripped
        url2 = extractor._build_learn_url("docs/networking/architecture/azure-dns-private-resolver-content.md")
        assert url2 == "https://learn.microsoft.com/en-us/azure/architecture/networking/architecture/azure-dns-private-resolver"


class TestArchitectureClassifier:
    """Tests for the classifier."""

    def test_suggest_web_domain(self):
        """Test web domain detection."""
        classifier = ArchitectureClassifier()

        content = "This web application uses React frontend with ASP.NET Core backend."
        domain = classifier._suggest_workload_domain(content.lower())

        assert domain == WorkloadDomain.WEB

    def test_suggest_data_domain(self):
        """Test data domain detection."""
        classifier = ArchitectureClassifier()

        content = "The data warehouse uses Synapse Analytics for big data processing."
        domain = classifier._suggest_workload_domain(content.lower())

        assert domain == WorkloadDomain.DATA

    def test_suggest_cloud_native_family(self):
        """Test cloud native family detection."""
        classifier = ArchitectureClassifier()

        content = "kubernetes microservices container"
        services = ["Azure Kubernetes Service", "Azure Container Registry"]
        # Create a mock parsed doc with empty metadata
        from catalog_builder.parser import ParsedDocument, ArchitectureMetadata
        mock_doc = ParsedDocument(
            path=Path("/test.md"),
            title="Test",
            description="Test",
            arch_metadata=ArchitectureMetadata(products=[])
        )
        family = classifier._suggest_family(content, services, mock_doc)

        assert family == ArchitectureFamily.CLOUD_NATIVE


class TestCatalogSchema:
    """Tests for the catalog schema."""

    def test_architecture_entry_defaults(self):
        """Test that defaults are properly set."""
        entry = ArchitectureEntry(
            architecture_id="test-arch",
            name="Test Architecture",
            description="A test",
            source_repo_path="docs/test.md",
        )

        assert entry.architecture_id == "test-arch"
        assert entry.expected_runtime_models == [RuntimeModel.UNKNOWN]
        assert entry.azure_services_used == []

    def test_catalog_serialization(self):
        """Test catalog JSON serialization."""
        entry = ArchitectureEntry(
            architecture_id="test-arch",
            name="Test",
            description="Test desc",
            source_repo_path="docs/test.md",
            core_services=["Azure App Service"],
            supporting_services=["Azure Monitor"],
        )

        catalog = ArchitectureCatalog(
            source_repo="/path/to/repo",
            architectures=[entry],
        )

        # Serialize to JSON
        json_str = catalog.model_dump_json()
        data = json.loads(json_str)

        assert data["total_architectures"] == 1
        assert data["architectures"][0]["architecture_id"] == "test-arch"
        assert "Azure App Service" in data["architectures"][0]["core_services"]
        assert "Azure Monitor" in data["architectures"][0]["supporting_services"]

    def test_catalog_count_update(self):
        """Test that total_architectures updates."""
        entry = ArchitectureEntry(
            architecture_id="test",
            name="Test",
            description="",
            source_repo_path="docs/test.md",
        )

        catalog = ArchitectureCatalog(
            source_repo="/repo",
            architectures=[entry, entry],
        )

        assert catalog.total_architectures == 2


class TestEnhancedClassifier:
    """Tests for enhanced content-based classification features."""

    def test_suggest_rehost_treatment(self):
        """Test rehost treatment detection from lift-and-shift content."""
        from catalog_builder.classifier import ArchitectureClassifier
        from catalog_builder.schema import Treatment, ArchitectureFamily

        classifier = ArchitectureClassifier()
        content = "this lift and shift migration requires no code changes to the existing application."

        mock_doc = ParsedDocument(
            path=Path("/test.md"),
            title="Migration Guide",
            description="Lift and shift to Azure",
            arch_metadata=ArchitectureMetadata(products=[]),
            frontmatter={}
        )

        entry = ArchitectureEntry(
            architecture_id="test",
            name="Test",
            description="",
            source_repo_path="docs/test.md",
            family=ArchitectureFamily.IAAS,
            azure_services_used=["Azure Virtual Machines"]
        )

        treatments, source = classifier._suggest_treatments_enhanced(entry, content, mock_doc)

        assert Treatment.REHOST in treatments

    def test_suggest_refactor_treatment(self):
        """Test refactor treatment detection from microservices content."""
        from catalog_builder.classifier import ArchitectureClassifier
        from catalog_builder.schema import Treatment, ArchitectureFamily

        classifier = ArchitectureClassifier()
        content = "modernize the application by decomposing into cloud-native microservices using containerize approach."

        mock_doc = ParsedDocument(
            path=Path("/test.md"),
            title="Modernization",
            description="Cloud native modernization",
            arch_metadata=ArchitectureMetadata(products=[]),
            frontmatter={}
        )

        entry = ArchitectureEntry(
            architecture_id="test",
            name="Test",
            description="",
            source_repo_path="docs/test.md",
            family=ArchitectureFamily.CLOUD_NATIVE,
            azure_services_used=["Azure Kubernetes Service"]
        )

        treatments, source = classifier._suggest_treatments_enhanced(entry, content, mock_doc)

        assert Treatment.REFACTOR in treatments

    def test_suggest_security_level_regulated(self):
        """Test detection of regulated security level."""
        from catalog_builder.classifier import ArchitectureClassifier
        from catalog_builder.schema import SecurityLevel

        classifier = ArchitectureClassifier()
        content = "this architecture is designed for hipaa compliance and pci-dss requirements."

        mock_doc = ParsedDocument(
            path=Path("/test.md"),
            title="Regulated Workload",
            description="Healthcare compliance",
            arch_metadata=ArchitectureMetadata(azure_categories=[]),
            frontmatter={}
        )

        security_level, source = classifier._suggest_security_level(content, mock_doc)

        assert security_level == SecurityLevel.HIGHLY_REGULATED

    def test_suggest_devops_operating_model(self):
        """Test DevOps operating model detection."""
        from catalog_builder.classifier import ArchitectureClassifier
        from catalog_builder.schema import OperatingModel, ArchitectureFamily, RuntimeModel

        classifier = ArchitectureClassifier()
        content = "uses ci/cd with github actions and terraform infrastructure as code for automated deployment."

        mock_doc = ParsedDocument(
            path=Path("/test.md"),
            title="DevOps Architecture",
            description="CI/CD pipeline",
            arch_metadata=ArchitectureMetadata(products=[]),
            frontmatter={}
        )

        entry = ArchitectureEntry(
            architecture_id="test",
            name="Test",
            description="",
            source_repo_path="docs/test.md",
            family=ArchitectureFamily.CLOUD_NATIVE,
            expected_runtime_models=[RuntimeModel.MICROSERVICES]
        )

        operating_model, source = classifier._suggest_operating_model_enhanced(entry, content, mock_doc)

        assert operating_model == OperatingModel.DEVOPS

    def test_suggest_cost_profile_innovation(self):
        """Test innovation-first cost profile detection."""
        from catalog_builder.classifier import ArchitectureClassifier
        from catalog_builder.schema import CostProfile, ArchitectureFamily

        classifier = ArchitectureClassifier()
        content = "uses azure openai and cognitive services for ai-powered features with machine learning."

        entry = ArchitectureEntry(
            architecture_id="test",
            name="Test",
            description="",
            source_repo_path="docs/test.md",
            family=ArchitectureFamily.CLOUD_NATIVE,
            azure_services_used=["Azure OpenAI Service", "Azure Cognitive Services"]
        )

        cost_profile, source = classifier._suggest_cost_profile(content, entry)

        assert cost_profile == CostProfile.INNOVATION_FIRST

    def test_extract_not_suitable_for(self):
        """Test extraction of explicit exclusions."""
        from catalog_builder.classifier import ArchitectureClassifier
        from catalog_builder.schema import ExclusionReason

        classifier = ArchitectureClassifier()
        content = "this pattern isn't suitable for simple workloads. windows only solution with low maturity teams."

        mock_doc = ParsedDocument(
            path=Path("/test.md"),
            title="Complex Pattern",
            description="Not for beginners",
            arch_metadata=ArchitectureMetadata(products=[]),
            sections={'considerations': 'requires kubernetes experience'}
        )

        exclusions = classifier._extract_not_suitable_for(content, mock_doc)

        assert ExclusionReason.SIMPLE_WORKLOADS in exclusions
        assert ExclusionReason.WINDOWS_ONLY in exclusions

    def test_time_category_invest(self):
        """Test TIME invest category detection."""
        from catalog_builder.classifier import ArchitectureClassifier
        from catalog_builder.schema import TimeCategory, Treatment, ComplexityLevel, Complexity

        classifier = ArchitectureClassifier()
        content = "greenfield cloud-native microservices with serverless and managed service approach for digital transformation."

        entry = ArchitectureEntry(
            architecture_id="test",
            name="Test",
            description="",
            source_repo_path="docs/test.md",
            supported_treatments=[Treatment.REFACTOR, Treatment.REBUILD],
            complexity=Complexity(implementation=ComplexityLevel.HIGH)
        )

        categories, source = classifier._suggest_time_categories_enhanced(entry, content)

        assert TimeCategory.INVEST in categories
