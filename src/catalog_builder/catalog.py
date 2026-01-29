"""Catalog generation orchestration."""

import json
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .classifier import ArchitectureClassifier
from .detector import ArchitectureDetector
from .extractor import GitMetadataExtractor, MetadataExtractor
from .parser import MarkdownParser
from .schema import ArchitectureCatalog, ArchitectureEntry


class CatalogBuilder:
    """Builds the architecture catalog from source documentation."""

    def __init__(
        self,
        repo_path: Path,
        progress_callback: Optional[Callable[[str], None]] = None
    ):
        self.repo_path = repo_path
        self.progress = progress_callback or (lambda x: None)

        # Initialize components
        self.parser = MarkdownParser()
        self.detector = ArchitectureDetector()
        self.extractor = MetadataExtractor(self.parser)
        self.classifier = ArchitectureClassifier()
        self.git_extractor = GitMetadataExtractor(repo_path)

    def build(self) -> ArchitectureCatalog:
        """Build the complete architecture catalog."""
        self.progress("Starting catalog build...")

        # Find all markdown files
        md_files = self._find_markdown_files()
        self.progress(f"Found {len(md_files)} markdown files to scan")

        # Process each file
        entries: list[ArchitectureEntry] = []
        processed = 0
        detected = 0

        for md_file in md_files:
            processed += 1
            if processed % 100 == 0:
                self.progress(f"Processed {processed}/{len(md_files)} files...")

            entry = self._process_file(md_file)
            if entry:
                entries.append(entry)
                detected += 1

        self.progress(f"Detected {detected} architecture candidates")

        # Build catalog
        catalog = ArchitectureCatalog(
            source_repo=str(self.repo_path),
            source_commit=self.git_extractor.get_current_commit(),
            architectures=entries,
        )

        self.progress(f"Catalog built with {catalog.total_architectures} architectures")
        return catalog

    def _find_markdown_files(self) -> list[Path]:
        """Find all markdown files in the docs directory."""
        docs_path = self.repo_path / "docs"
        if not docs_path.exists():
            self.progress("Warning: docs/ directory not found")
            return []

        md_files = []
        for md_file in docs_path.rglob("*.md"):
            # Check if directory should be scanned
            if self.detector.should_scan_directory(md_file.parent, self.repo_path):
                md_files.append(md_file)

        return sorted(md_files)

    def _process_file(self, file_path: Path) -> Optional[ArchitectureEntry]:
        """Process a single markdown file."""
        # Parse the document
        doc = self.parser.parse_file(file_path)
        if not doc:
            return None

        # Detect if it's an architecture
        detection = self.detector.detect(doc, self.repo_path)
        if not detection.is_architecture:
            return None

        # Get git metadata
        last_modified = self.git_extractor.get_last_modified(file_path)

        # Extract metadata
        entry = self.extractor.extract(doc, self.repo_path, last_modified)

        # Add AI-suggested classifications
        entry = self.classifier.suggest_classifications(entry, doc)

        return entry

    def save_catalog(
        self,
        catalog: ArchitectureCatalog,
        output_path: Path
    ) -> None:
        """Save the catalog to a JSON file."""
        self.progress(f"Saving catalog to {output_path}")

        # Convert to dict with proper serialization
        catalog_dict = catalog.model_dump(mode='json')

        # Write with pretty formatting
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(catalog_dict, f, indent=2, ensure_ascii=False, default=str)

        self.progress(f"Catalog saved successfully")


class CatalogValidator:
    """Validates catalog entries and reports issues."""

    def validate(self, catalog: ArchitectureCatalog) -> list[str]:
        """Validate the catalog and return a list of issues."""
        issues = []

        # Check for duplicate IDs
        ids = [a.architecture_id for a in catalog.architectures]
        duplicates = set(id for id in ids if ids.count(id) > 1)
        if duplicates:
            issues.append(f"Duplicate architecture IDs: {duplicates}")

        # Check each entry
        for entry in catalog.architectures:
            entry_issues = self._validate_entry(entry)
            issues.extend(entry_issues)

        return issues

    def _validate_entry(self, entry: ArchitectureEntry) -> list[str]:
        """Validate a single entry."""
        issues = []
        prefix = f"[{entry.architecture_id}]"

        if not entry.name:
            issues.append(f"{prefix} Missing name")

        if not entry.description:
            issues.append(f"{prefix} Missing description")

        if not entry.azure_services_used:
            issues.append(f"{prefix} No Azure services detected")

        if entry.extraction_warnings:
            for warning in entry.extraction_warnings:
                issues.append(f"{prefix} {warning}")

        return issues


def build_catalog(
    repo_path: Path,
    output_path: Path,
    progress_callback: Optional[Callable[[str], None]] = None
) -> tuple[ArchitectureCatalog, list[str]]:
    """Build and save the architecture catalog.

    Returns the catalog and a list of validation issues.
    """
    builder = CatalogBuilder(repo_path, progress_callback)
    catalog = builder.build()

    validator = CatalogValidator()
    issues = validator.validate(catalog)

    builder.save_catalog(catalog, output_path)

    return catalog, issues
