"""Architecture candidate detection heuristics."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .parser import ParsedDocument


@dataclass
class DetectionResult:
    """Result of architecture detection."""
    is_architecture: bool
    confidence: float  # 0.0 to 1.0
    reasons: list[str]
    exclusion_reasons: list[str]


class ArchitectureDetector:
    """Detects architecture candidates using heuristics."""

    # Folders to include
    INCLUDE_FOLDERS = [
        'docs/example-scenario',
        'docs/web-apps',
        'docs/data',
        'docs/integration',
        'docs/ai-ml',
        'docs/databases',
        'docs/iot',
        'docs/microservices',
        'docs/mobile',
        'docs/networking',
        'docs/security',
        'docs/solution-ideas',
        'docs/reference-architectures',
        'docs/hybrid',
        'docs/aws-professional',
        'docs/gcp-professional',
        'docs/oracle-azure',
        'docs/sap',
        'docs/high-availability',
        'docs/serverless',
    ]

    # Folders to exclude
    EXCLUDE_FOLDERS = [
        'docs/guide',
        'docs/best-practices',
        'docs/patterns',
        'docs/antipatterns',
        'docs/framework',
        'docs/icons',
        'docs/includes',
        'docs/resources',
        'docs/browse',
        '_themes',
        '_shared',
    ]

    # Files to exclude
    EXCLUDE_FILES = [
        'index.md',
        'toc.yml',
        'toc.md',
        'readme.md',
        'changelog.md',
    ]

    # Section names that indicate architecture content
    ARCHITECTURE_SECTIONS = [
        'architecture',
        'components',
        'diagram',
        'solution architecture',
        'reference architecture',
        'architectural approach',
        'design',
        'workflow',
        'data flow',
        'dataflow',
    ]

    # Keywords indicating architecture content
    ARCHITECTURE_KEYWORDS = [
        r'reference\s+architecture',
        r'baseline\s+architecture',
        r'solution\s+idea',
        r'architecture\s+pattern',
        r'architectural\s+design',
        r'this\s+architecture',
        r'the\s+architecture',
        r'architecture\s+diagram',
        r'components\s+of\s+this',
        r'azure\s+architecture',
    ]

    # Diagram file patterns
    DIAGRAM_PATTERNS = [
        r'.*architecture.*\.(svg|png)$',
        r'.*diagram.*\.(svg|png)$',
        r'.*flow.*\.(svg|png)$',
        r'.*-arch\.(svg|png)$',
        r'.*\.svg$',  # Most SVGs in architecture docs are diagrams
    ]

    def __init__(self):
        self._keyword_patterns = [
            re.compile(kw, re.IGNORECASE) for kw in self.ARCHITECTURE_KEYWORDS
        ]
        self._diagram_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.DIAGRAM_PATTERNS
        ]

    def detect(self, doc: ParsedDocument, repo_root: Path) -> DetectionResult:
        """Detect if a document is an architecture candidate."""
        reasons = []
        exclusion_reasons = []
        score = 0.0

        rel_path = str(doc.path.relative_to(repo_root)).replace('\\', '/')

        # Check folder exclusions first
        for exclude in self.EXCLUDE_FOLDERS:
            if rel_path.startswith(exclude):
                exclusion_reasons.append(f"In excluded folder: {exclude}")

        # Check file exclusions
        if doc.path.name.lower() in self.EXCLUDE_FILES:
            exclusion_reasons.append(f"Excluded file type: {doc.path.name}")

        # If excluded, return early
        if exclusion_reasons:
            return DetectionResult(
                is_architecture=False,
                confidence=0.0,
                reasons=reasons,
                exclusion_reasons=exclusion_reasons,
            )

        # Check if in included folder
        in_included_folder = any(
            rel_path.startswith(folder) for folder in self.INCLUDE_FOLDERS
        )
        if in_included_folder:
            reasons.append("In architecture folder")
            score += 0.3

        # Check for architecture diagrams
        diagrams = self._find_diagrams(doc)
        if diagrams:
            reasons.append(f"Contains {len(diagrams)} architecture diagram(s)")
            score += 0.3

        # Check for architecture sections
        arch_sections = self._find_architecture_sections(doc)
        if arch_sections:
            reasons.append(f"Has architecture sections: {', '.join(arch_sections[:3])}")
            score += 0.2

        # Check for architecture keywords
        keywords_found = self._find_keywords(doc)
        if keywords_found:
            reasons.append(f"Contains architecture keywords")
            score += 0.2

        # Check frontmatter for architecture indicators
        if self._check_frontmatter(doc):
            reasons.append("Frontmatter indicates architecture content")
            score += 0.1

        # Determine if it's an architecture
        is_architecture = score >= 0.4 and len(reasons) >= 2

        return DetectionResult(
            is_architecture=is_architecture,
            confidence=min(score, 1.0),
            reasons=reasons,
            exclusion_reasons=exclusion_reasons,
        )

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
        found = []
        for section_name in doc.sections.keys():
            for arch_section in self.ARCHITECTURE_SECTIONS:
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
        try:
            rel_path = str(dir_path.relative_to(repo_root)).replace('\\', '/')
        except ValueError:
            return False

        # Check exclusions
        for exclude in self.EXCLUDE_FOLDERS:
            if rel_path.startswith(exclude) or rel_path == exclude.rstrip('/'):
                return False

        # Check if starts with docs/
        if not rel_path.startswith('docs'):
            return False

        return True
