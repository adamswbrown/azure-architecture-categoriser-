"""Metadata extraction from architecture documents."""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from .parser import MarkdownParser, ParsedDocument
from .schema import ArchitectureEntry, ClassificationMeta, ExtractionConfidence


class MetadataExtractor:
    """Extracts metadata from architecture documents."""

    LEARN_BASE_URL = "https://learn.microsoft.com/en-us/azure/architecture"

    def __init__(self, parser: MarkdownParser):
        self.parser = parser

    def extract(
        self,
        doc: ParsedDocument,
        repo_root: Path,
        last_modified: Optional[datetime] = None
    ) -> ArchitectureEntry:
        """Extract metadata and create an architecture entry."""
        rel_path = str(doc.path.relative_to(repo_root)).replace('\\', '/')

        # Generate architecture ID from path
        arch_id = self._generate_id(rel_path)

        # Extract title and description
        title = self._extract_title(doc)
        description = self._extract_description(doc)

        # Build Learn URL
        learn_url = self._build_learn_url(rel_path)

        # Extract Azure services
        services = self.parser.extract_azure_services(doc)

        # Extract diagram assets
        diagrams = self._extract_diagrams(doc, rel_path)

        # Create entry with extracted values
        entry = ArchitectureEntry(
            architecture_id=arch_id,
            name=title,
            description=description,
            source_repo_path=rel_path,
            learn_url=learn_url,
            azure_services_used=services,
            diagram_assets=diagrams,
            last_repo_update=last_modified,
        )

        # Add extraction warnings
        if not title:
            entry.extraction_warnings.append("Could not extract title")
        if not description:
            entry.extraction_warnings.append("Could not extract description")
        if not services:
            entry.extraction_warnings.append("No Azure services detected")
        if not diagrams:
            entry.extraction_warnings.append("No architecture diagrams found")

        return entry

    def _generate_id(self, rel_path: str) -> str:
        """Generate a unique ID from the file path."""
        # Remove docs/ prefix and .md extension
        path = rel_path
        if path.startswith('docs/'):
            path = path[5:]
        if path.endswith('.md'):
            path = path[:-3]

        # Replace special chars with dashes
        path = re.sub(r'[^a-zA-Z0-9]+', '-', path)
        path = path.strip('-').lower()

        # Ensure uniqueness with hash suffix if path is too long
        if len(path) > 60:
            hash_suffix = hashlib.md5(rel_path.encode()).hexdigest()[:8]
            path = path[:50] + '-' + hash_suffix

        return path

    def _extract_title(self, doc: ParsedDocument) -> str:
        """Extract the title from the document."""
        # Priority: frontmatter title > first H1 > filename
        if doc.title:
            return doc.title

        # Try first H1
        for level, heading in doc.headings:
            if level == 1:
                return heading

        # Fall back to filename
        return doc.path.stem.replace('-', ' ').replace('_', ' ').title()

    def _extract_description(self, doc: ParsedDocument) -> str:
        """Extract description from the document."""
        # Priority: frontmatter description > first paragraph
        if doc.description:
            return doc.description

        # Try to get first substantial paragraph
        content = doc.content.strip()
        paragraphs = re.split(r'\n\s*\n', content)

        for para in paragraphs:
            # Skip headings, images, includes
            para = para.strip()
            if para.startswith('#'):
                continue
            if para.startswith('!'):
                continue
            if para.startswith('[!INCLUDE'):
                continue
            if len(para) > 50:
                # Clean up markdown
                clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', para)
                clean = re.sub(r'[*_`]', '', clean)
                return clean[:500]

        return ""

    def _build_learn_url(self, rel_path: str) -> Optional[str]:
        """Build the Microsoft Learn URL for the document."""
        # Remove docs/ prefix and .md extension
        path = rel_path
        if path.startswith('docs/'):
            path = path[5:]
        if path.endswith('.md'):
            path = path[:-3]
        if path.endswith('/index'):
            path = path[:-6]

        # URL encode the path
        path = quote(path, safe='/')

        return f"{self.LEARN_BASE_URL}/{path}"

    def _extract_diagrams(self, doc: ParsedDocument, rel_path: str) -> list[str]:
        """Extract diagram asset paths."""
        diagrams = []
        doc_dir = Path(rel_path).parent

        for image in doc.images:
            # Normalize path
            if image.startswith('./'):
                image = image[2:]
            if image.startswith('../'):
                # Resolve relative path
                image_path = (doc_dir / image).as_posix()
            elif not image.startswith('http'):
                image_path = (doc_dir / image).as_posix()
            else:
                # Skip external URLs
                continue

            # Check if it looks like a diagram
            lower = image.lower()
            if any(x in lower for x in ['architecture', 'diagram', 'flow', '.svg']):
                diagrams.append(image_path)
            elif lower.endswith(('.svg', '.png')):
                diagrams.append(image_path)

        return diagrams


class GitMetadataExtractor:
    """Extracts metadata from git repository."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self._repo = None

    def _get_repo(self):
        """Lazy load git repo."""
        if self._repo is None:
            try:
                import git
                self._repo = git.Repo(self.repo_root)
            except Exception:
                self._repo = False
        return self._repo if self._repo else None

    def get_last_modified(self, file_path: Path) -> Optional[datetime]:
        """Get the last modified date for a file from git."""
        repo = self._get_repo()
        if not repo:
            return None

        try:
            rel_path = str(file_path.relative_to(self.repo_root))
            commits = list(repo.iter_commits(paths=rel_path, max_count=1))
            if commits:
                return datetime.fromtimestamp(commits[0].committed_date)
        except Exception:
            pass

        return None

    def get_current_commit(self) -> Optional[str]:
        """Get the current commit hash."""
        repo = self._get_repo()
        if not repo:
            return None

        try:
            return repo.head.commit.hexsha
        except Exception:
            return None
