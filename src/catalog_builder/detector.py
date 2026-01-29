"""Architecture candidate detection heuristics."""

import re
from dataclasses import dataclass
from pathlib import Path

from .config import get_config
from .parser import ParsedDocument


@dataclass
class DetectionResult:
    """Result of architecture detection."""
    is_architecture: bool
    confidence: float  # 0.0 to 1.0
    reasons: list[str]
    exclusion_reasons: list[str]
    filtered_out: bool = False  # True if excluded by filters (not detection)


class ArchitectureDetector:
    """Detects architecture candidates using heuristics."""

    def __init__(self):
        self._keyword_patterns = None
        self._diagram_patterns = None

    def _get_config(self):
        """Get detection config."""
        return get_config().detection

    def _get_filters(self):
        """Get filter config."""
        return get_config().filters

    def _compile_patterns(self):
        """Compile regex patterns from config."""
        config = self._get_config()
        if self._keyword_patterns is None:
            self._keyword_patterns = [
                re.compile(kw, re.IGNORECASE) for kw in config.architecture_keywords
            ]
        if self._diagram_patterns is None:
            self._diagram_patterns = [
                re.compile(p, re.IGNORECASE) for p in config.diagram_patterns
            ]

    def detect(self, doc: ParsedDocument, repo_root: Path) -> DetectionResult:
        """Detect if a document is an architecture candidate."""
        self._compile_patterns()
        config = self._get_config()
        filters = self._get_filters()

        reasons = []
        exclusion_reasons = []
        score = 0.0

        rel_path = str(doc.path.relative_to(repo_root)).replace('\\', '/')

        # Check folder exclusions first
        for exclude in config.exclude_folders:
            if rel_path.startswith(exclude):
                exclusion_reasons.append(f"In excluded folder: {exclude}")

        # Check file exclusions
        if doc.path.name.lower() in config.exclude_files:
            exclusion_reasons.append(f"Excluded file type: {doc.path.name}")

        # If excluded by folder/file, return early
        if exclusion_reasons:
            return DetectionResult(
                is_architecture=False,
                confidence=0.0,
                reasons=reasons,
                exclusion_reasons=exclusion_reasons,
            )

        # Check filters (ms.topic, categories, products)
        filter_result = self._check_filters(doc)
        if filter_result:
            return DetectionResult(
                is_architecture=False,
                confidence=0.0,
                reasons=reasons,
                exclusion_reasons=[filter_result],
                filtered_out=True,
            )

        # HIGH CONFIDENCE: Has YamlMime:Architecture metadata
        if doc.arch_metadata.is_architecture_yml:
            reasons.append("Has YamlMime:Architecture metadata")
            score += 0.5  # Strong signal

            # Even higher if it's a reference architecture
            if doc.arch_metadata.ms_topic == 'reference-architecture':
                reasons.append("Is a reference architecture")
                score += 0.3

        # Check if in included folder
        in_included_folder = any(
            rel_path.startswith(folder) for folder in config.include_folders
        )
        if in_included_folder:
            reasons.append("In architecture folder")
            score += config.folder_score

        # Check for architecture diagrams
        diagrams = self._find_diagrams(doc)
        if diagrams:
            reasons.append(f"Contains {len(diagrams)} architecture diagram(s)")
            score += config.diagram_score

        # Check for architecture sections
        arch_sections = self._find_architecture_sections(doc)
        if arch_sections:
            reasons.append(f"Has architecture sections: {', '.join(arch_sections[:3])}")
            score += config.section_score

        # Check for architecture keywords
        keywords_found = self._find_keywords(doc)
        if keywords_found:
            reasons.append("Contains architecture keywords")
            score += config.keyword_score

        # Check frontmatter for architecture indicators
        if self._check_frontmatter(doc):
            reasons.append("Frontmatter indicates architecture content")
            score += config.frontmatter_score

        # Determine if it's an architecture
        # If require_architecture_yml is set, we MUST have the yml file
        if filters.require_architecture_yml and not doc.arch_metadata.is_architecture_yml:
            return DetectionResult(
                is_architecture=False,
                confidence=score,
                reasons=reasons,
                exclusion_reasons=["No YamlMime:Architecture file (required by filter)"],
                filtered_out=True,
            )

        is_architecture = score >= config.min_confidence and len(reasons) >= config.min_signals

        return DetectionResult(
            is_architecture=is_architecture,
            confidence=min(score, 1.0),
            reasons=reasons,
            exclusion_reasons=exclusion_reasons,
        )

    def _check_filters(self, doc: ParsedDocument) -> str | None:
        """Check if document passes filters. Returns exclusion reason or None."""
        filters = self._get_filters()
        ms_topic = doc.arch_metadata.ms_topic or doc.frontmatter.get('ms.topic', '')

        # Check excluded topics first
        if filters.excluded_topics and ms_topic in filters.excluded_topics:
            return f"Excluded topic: {ms_topic}"

        # Check allowed topics (if specified)
        if filters.allowed_topics:
            if ms_topic and ms_topic not in filters.allowed_topics:
                return f"Topic '{ms_topic}' not in allowed list"

        # Check allowed categories (if specified)
        if filters.allowed_categories:
            doc_categories = doc.arch_metadata.azure_categories
            if doc_categories:
                if not any(cat in filters.allowed_categories for cat in doc_categories):
                    return f"Categories {doc_categories} not in allowed list"

        # Check allowed products (if specified) - supports prefix matching
        # e.g., "azure" matches "azure-kubernetes-service", "azure-app-service", etc.
        if filters.allowed_products:
            doc_products = doc.arch_metadata.products
            if doc_products:
                if not self._product_matches_filter(doc_products, filters.allowed_products):
                    return f"Products not in allowed list"

        return None

    def _product_matches_filter(
        self,
        doc_products: list[str],
        allowed_products: list[str]
    ) -> bool:
        """Check if any document product matches allowed products.

        Supports both exact matching and prefix matching:
        - Exact: "azure-app-service" matches "azure-app-service"
        - Prefix: "azure" matches "azure-app-service", "azure-kubernetes-service", etc.
        """
        for doc_product in doc_products:
            for allowed in allowed_products:
                # Exact match
                if doc_product == allowed:
                    return True
                # Prefix match: allowed is a prefix of doc_product
                # e.g., "azure" matches "azure-kubernetes-service"
                if doc_product.startswith(allowed + '-'):
                    return True
                # Also match if allowed is the doc_product prefix
                # e.g., "azure-kubernetes" matches "azure-kubernetes-service"
                if doc_product.startswith(allowed):
                    return True
        return False

    def _find_diagrams(self, doc: ParsedDocument) -> list[str]:
        """Find architecture diagrams in the document."""
        diagrams = []
        for image in doc.images:
            for pattern in self._diagram_patterns:
                if pattern.match(image):
                    diagrams.append(image)
                    break
        return diagrams

    def _find_architecture_sections(self, doc: ParsedDocument) -> list[str]:
        """Find architecture-related sections in the document."""
        config = self._get_config()
        found = []
        for section_name in doc.sections.keys():
            for arch_section in config.architecture_sections:
                if arch_section in section_name.lower():
                    found.append(section_name)
                    break
        return found

    def _find_keywords(self, doc: ParsedDocument) -> list[str]:
        """Find architecture keywords in the document."""
        found = []
        content = doc.content.lower()
        for pattern in self._keyword_patterns:
            if pattern.search(content):
                found.append(pattern.pattern)
        return found

    def _check_frontmatter(self, doc: ParsedDocument) -> bool:
        """Check frontmatter for architecture indicators."""
        fm = doc.frontmatter

        # Check ms.topic or ms.custom
        topic = fm.get('ms.topic', '')
        custom = fm.get('ms.custom', '')
        if any(kw in str(topic).lower() + str(custom).lower()
               for kw in ['architecture', 'reference', 'solution', 'example-scenario']):
            return True

        # Check for architecture in title
        title = fm.get('title', '')
        if 'architecture' in title.lower():
            return True

        return False

    def should_scan_directory(self, dir_path: Path, repo_root: Path) -> bool:
        """Determine if a directory should be scanned."""
        config = self._get_config()

        try:
            rel_path = str(dir_path.relative_to(repo_root)).replace('\\', '/')
        except ValueError:
            return False

        # Check exclusions
        for exclude in config.exclude_folders:
            if rel_path.startswith(exclude) or rel_path == exclude.rstrip('/'):
                return False

        # Check if starts with docs/
        if not rel_path.startswith('docs'):
            return False

        return True
