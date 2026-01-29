"""Markdown parsing utilities for architecture documentation."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .config import get_config


@dataclass
class ArchitectureMetadata:
    """Metadata from YamlMime:Architecture files."""
    ms_topic: str = ""  # reference-architecture, example-scenario, solution-idea, etc.
    azure_categories: list[str] = field(default_factory=list)  # web, ai-machine-learning, etc.
    products: list[str] = field(default_factory=list)  # azure-app-service, azure-kubernetes-service
    thumbnail_url: str = ""
    is_architecture_yml: bool = False  # True if we found a YamlMime:Architecture file


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
    # New: Architecture-specific metadata from .yml files
    arch_metadata: ArchitectureMetadata = field(default_factory=ArchitectureMetadata)


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

        doc = self.parse_content(content, file_path)

        # Try to find and parse paired .yml architecture file
        arch_metadata = self._find_architecture_yml(file_path)
        if arch_metadata:
            doc.arch_metadata = arch_metadata
            # Merge yml metadata into frontmatter for backwards compatibility
            if arch_metadata.ms_topic:
                doc.frontmatter['ms.topic'] = arch_metadata.ms_topic
            if arch_metadata.azure_categories:
                doc.frontmatter['azure_categories'] = arch_metadata.azure_categories
            if arch_metadata.products:
                doc.frontmatter['products'] = arch_metadata.products

        return doc

    def _find_architecture_yml(self, md_path: Path) -> Optional[ArchitectureMetadata]:
        """Find and parse a paired YamlMime:Architecture file.

        Architecture yml files can be:
        1. Same name as md file: foo.yml for foo.md
        2. Same name without -content suffix: foo.yml for foo-content.md
        3. In the same directory with matching base name
        """
        # Try common yml file patterns
        base_name = md_path.stem
        parent = md_path.parent

        # Pattern 1: exact match (basic-web-app.yml for basic-web-app.md)
        yml_candidates = [
            parent / f"{base_name}.yml",
        ]

        # Pattern 2: content file pattern (basic-web-app.yml for basic-web-app-content.md)
        if base_name.endswith('-content'):
            yml_candidates.insert(0, parent / f"{base_name[:-8]}.yml")

        # Pattern 3: index pattern (architectures/basic-web-app.yml for architectures/basic-web-app/index.md)
        if base_name == 'index':
            yml_candidates.insert(0, parent.with_suffix('.yml'))

        for yml_path in yml_candidates:
            if yml_path.exists():
                metadata = self._parse_architecture_yml(yml_path)
                if metadata and metadata.is_architecture_yml:
                    return metadata

        return None

    def _parse_architecture_yml(self, yml_path: Path) -> Optional[ArchitectureMetadata]:
        """Parse a YamlMime:Architecture YAML file."""
        try:
            content = yml_path.read_text(encoding='utf-8')
        except (IOError, UnicodeDecodeError):
            return None

        # Check if it's a YamlMime:Architecture file
        if not content.strip().startswith('### YamlMime:Architecture'):
            return None

        # Remove the YamlMime header before parsing
        yaml_content = '\n'.join(content.split('\n')[1:])

        try:
            data = yaml.safe_load(yaml_content)
            if not data:
                return None
        except yaml.YAMLError:
            return None

        metadata = data.get('metadata', {})

        # Extract ms.topic
        ms_topic = metadata.get('ms.topic', '')

        # Extract azure categories (can be list or single value)
        azure_cats = data.get('azureCategories', [])
        if isinstance(azure_cats, str):
            azure_cats = [azure_cats]
        # Also check metadata.ms.category
        ms_category = metadata.get('ms.category', [])
        if isinstance(ms_category, str):
            ms_category = [ms_category]
        azure_cats = list(set(azure_cats + ms_category))

        # Extract products
        products = data.get('products', [])
        if isinstance(products, str):
            products = [products]

        # Get thumbnail
        thumbnail = data.get('thumbnailUrl', '')

        return ArchitectureMetadata(
            ms_topic=ms_topic,
            azure_categories=azure_cats,
            products=products,
            thumbnail_url=thumbnail,
            is_architecture_yml=True,
        )

    def parse_yml_file(self, yml_path: Path) -> Optional[ParsedDocument]:
        """Parse a YamlMime:Architecture YAML file directly.

        This is for when we want to process .yml files as the primary source.
        """
        metadata = self._parse_architecture_yml(yml_path)
        if not metadata or not metadata.is_architecture_yml:
            return None

        try:
            content = yml_path.read_text(encoding='utf-8')
            yaml_content = '\n'.join(content.split('\n')[1:])
            data = yaml.safe_load(yaml_content)
        except Exception:
            return None

        yml_metadata = data.get('metadata', {})

        # Find the referenced content file
        content_ref = data.get('content', '')
        content_body = ""
        images = []

        # Try to load the included content file
        include_match = re.search(r'\[!INCLUDE\[.*?\]\((.*?)\)\]', content_ref)
        if include_match:
            content_file = yml_path.parent / include_match.group(1)
            if content_file.exists():
                try:
                    content_body = content_file.read_text(encoding='utf-8')
                    images = [m.group(2) for m in self.IMAGE_PATTERN.finditer(content_body)]
                except Exception:
                    pass

        return ParsedDocument(
            path=yml_path,
            title=data.get('name', yml_metadata.get('title', '')),
            description=data.get('summary', yml_metadata.get('description', '')),
            frontmatter=yml_metadata,
            content=content_body,
            sections={},
            headings=[],
            images=images,
            links=[],
            raw_content=content,
            arch_metadata=metadata,
        )

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

        # Extract ms.topic from frontmatter if available
        arch_metadata = ArchitectureMetadata()
        if 'ms.topic' in frontmatter:
            arch_metadata.ms_topic = frontmatter['ms.topic']

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
            arch_metadata=arch_metadata,
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

        # Add products from architecture metadata
        for product in doc.arch_metadata.products:
            normalized = self._normalize_product_id(product)
            if normalized:
                services.add(normalized)

        return sorted(services)

    def _normalize_product_id(self, product_id: str) -> Optional[str]:
        """Normalize a product ID like 'azure-app-service' to a display name."""
        if not product_id:
            return None

        # Common product ID mappings
        product_mappings = {
            'azure-app-service': 'Azure App Service',
            'azure-kubernetes-service': 'Azure Kubernetes Service',
            'azure-virtual-machines': 'Azure Virtual Machines',
            'azure-sql-database': 'Azure SQL Database',
            'azure-cosmos-db': 'Azure Cosmos DB',
            'azure-functions': 'Azure Functions',
            'azure-monitor': 'Azure Monitor',
            'azure-storage': 'Azure Storage',
            'azure-blob-storage': 'Azure Blob Storage',
            'azure-virtual-network': 'Azure Virtual Network',
            'azure-expressroute': 'Azure ExpressRoute',
            'azure-front-door': 'Azure Front Door',
            'azure-application-gateway': 'Azure Application Gateway',
            'azure-load-balancer': 'Azure Load Balancer',
            'azure-firewall': 'Azure Firewall',
            'azure-key-vault': 'Azure Key Vault',
            'azure-event-hubs': 'Azure Event Hubs',
            'azure-service-bus': 'Azure Service Bus',
            'azure-logic-apps': 'Azure Logic Apps',
            'azure-data-factory': 'Azure Data Factory',
            'azure-databricks': 'Azure Databricks',
            'azure-synapse-analytics': 'Azure Synapse Analytics',
            'azure-api-management': 'Azure API Management',
            'azure-container-apps': 'Azure Container Apps',
            'azure-container-instances': 'Azure Container Instances',
            'azure-private-link': 'Azure Private Link',
            'azure-vpn-gateway': 'Azure VPN Gateway',
            'azure-files': 'Azure Files',
            'azure-netapp-files': 'Azure NetApp Files',
            'entra-id': 'Microsoft Entra ID',
            'ai-services': 'Azure AI Services',
            'azure-openai': 'Azure OpenAI Service',
            'azure-machine-learning': 'Azure Machine Learning',
            'fabric': 'Microsoft Fabric',
            'azure': 'Azure',
        }

        if product_id in product_mappings:
            return product_mappings[product_id]

        # Convert kebab-case to Title Case and prepend Azure
        if product_id.startswith('azure-'):
            name = product_id[6:].replace('-', ' ').title()
            return f"Azure {name}"

        return product_id.replace('-', ' ').title()

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
