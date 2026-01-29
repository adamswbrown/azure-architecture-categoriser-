"""Markdown parsing utilities for architecture documentation."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .config import get_config


@dataclass
class ParsedDocument:
    """Represents a parsed markdown document."""
    path: Path
    title: str
    description: str
    frontmatter: dict = field(default_factory=dict)
    content: str = ""
    sections: dict[str, str] = field(default_factory=dict)
    headings: list[tuple[int, str]] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    raw_content: str = ""


class MarkdownParser:
    """Parser for Azure Architecture Center markdown documents."""

    # Patterns for extraction
    FRONTMATTER_PATTERN = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
    HEADING_PATTERN = re.compile(r'^(#{1,6})\s+(.+?)(?:\s*{#[\w-]+})?\s*$', re.MULTILINE)
    IMAGE_PATTERN = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
    LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    INCLUDE_PATTERN = re.compile(r'\[!INCLUDE\s*\[([^\]]*)\]\(([^)]+)\)\]')

    def _get_config(self):
        """Get services config."""
        return get_config().services

    def parse_file(self, file_path: Path) -> Optional[ParsedDocument]:
        """Parse a markdown file into a structured document."""
        try:
            content = file_path.read_text(encoding='utf-8')
        except (IOError, UnicodeDecodeError):
            return None

        return self.parse_content(content, file_path)

    def parse_content(self, content: str, file_path: Path) -> ParsedDocument:
        """Parse markdown content into a structured document."""
        raw_content = content
        frontmatter = {}
        body = content

        # Extract frontmatter
        fm_match = self.FRONTMATTER_PATTERN.match(content)
        if fm_match:
            try:
                frontmatter = yaml.safe_load(fm_match.group(1)) or {}
            except yaml.YAMLError:
                frontmatter = {}
            body = content[fm_match.end():]

        # Extract title from frontmatter or first heading
        title = frontmatter.get('title', '')
        if not title:
            first_heading = self.HEADING_PATTERN.search(body)
            if first_heading:
                title = first_heading.group(2).strip()

        # Extract description
        description = frontmatter.get('description', '')
        if not description:
            description = frontmatter.get('summary', '')

        # Extract all headings
        headings = [
            (len(m.group(1)), m.group(2).strip())
            for m in self.HEADING_PATTERN.finditer(body)
        ]

        # Extract sections (content under each heading)
        sections = self._extract_sections(body)

        # Extract images
        images = [m.group(2) for m in self.IMAGE_PATTERN.finditer(body)]

        # Extract links
        links = [m.group(2) for m in self.LINK_PATTERN.finditer(body)]

        return ParsedDocument(
            path=file_path,
            title=title,
            description=description,
            frontmatter=frontmatter,
            content=body,
            sections=sections,
            headings=headings,
            images=images,
            links=links,
            raw_content=raw_content,
        )

    def _extract_sections(self, content: str) -> dict[str, str]:
        """Extract content under each heading as sections."""
        sections: dict[str, str] = {}
        lines = content.split('\n')
        current_heading = None
        current_content: list[str] = []

        for line in lines:
            heading_match = self.HEADING_PATTERN.match(line)
            if heading_match:
                # Save previous section
                if current_heading:
                    sections[current_heading.lower()] = '\n'.join(current_content).strip()

                current_heading = heading_match.group(2).strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_heading:
            sections[current_heading.lower()] = '\n'.join(current_content).strip()

        return sections

    def extract_azure_services(self, doc: ParsedDocument) -> list[str]:
        """Extract Azure service names from document content."""
        config = self._get_config()

        services = set()
        content = doc.content + ' ' + doc.description

        for pattern in config.detection_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                service = match.group(1) if match.lastindex else match.group(0)
                # Normalize service name
                normalized = self._normalize_service_name(service)
                if normalized:
                    services.add(normalized)

        # Also check frontmatter for products/services
        products = doc.frontmatter.get('ms.products', [])
        if isinstance(products, list):
            for product in products:
                if 'azure' in product.lower():
                    services.add(product)

        return sorted(services)

    def _normalize_service_name(self, name: str) -> Optional[str]:
        """Normalize Azure service name."""
        if not name:
            return None

        config = self._get_config()
        lower_name = name.lower().strip()

        if lower_name in config.normalizations:
            return config.normalizations[lower_name]

        # If starts with Azure, keep as is
        if name.lower().startswith('azure'):
            return name.strip()

        return f"Azure {name.strip()}"
