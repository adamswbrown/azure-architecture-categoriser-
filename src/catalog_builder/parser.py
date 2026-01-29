"""Markdown parsing utilities for architecture documentation."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from .config import get_config


# Canonical Azure service names (whitelist)
# Only services in this list will be included in the catalog
KNOWN_AZURE_SERVICES = {
    # Compute
    'Azure App Service',
    'Azure Functions',
    'Azure Kubernetes Service',
    'Azure Container Apps',
    'Azure Container Instances',
    'Azure Virtual Machines',
    'Azure Batch',
    'Azure Service Fabric',
    'Azure Spring Apps',
    'Azure Static Web Apps',
    'Azure VM Scale Sets',
    'Azure Dedicated Host',
    'Azure VMware Solution',

    # Containers
    'Azure Container Registry',

    # Databases
    'Azure SQL Database',
    'Azure SQL Managed Instance',
    'Azure Cosmos DB',
    'Azure Database for PostgreSQL',
    'Azure Database for MySQL',
    'Azure Database for MariaDB',
    'Azure Cache for Redis',
    'Azure SQL Server',
    'Azure Table Storage',

    # Storage
    'Azure Storage',
    'Azure Blob Storage',
    'Azure Files',
    'Azure Queue Storage',
    'Azure Data Lake Storage',
    'Azure NetApp Files',
    'Azure Managed Disks',
    'Azure HPC Cache',

    # Networking
    'Azure Virtual Network',
    'Azure Load Balancer',
    'Azure Application Gateway',
    'Azure Front Door',
    'Azure Traffic Manager',
    'Azure CDN',
    'Azure DNS',
    'Azure Firewall',
    'Azure DDoS Protection',
    'Azure ExpressRoute',
    'Azure VPN Gateway',
    'Azure Bastion',
    'Azure Private Link',
    'Azure Private Endpoint',
    'Azure NAT Gateway',
    'Azure Route Server',
    'Azure Virtual WAN',
    'Azure Peering Service',
    'Azure Network Watcher',

    # Integration
    'Azure API Management',
    'Azure Logic Apps',
    'Azure Service Bus',
    'Azure Event Hubs',
    'Azure Event Grid',
    'Azure Relay',

    # Identity
    'Microsoft Entra ID',
    'Azure Active Directory',
    'Azure Active Directory B2C',
    'Azure Active Directory Domain Services',

    # Security
    'Azure Key Vault',
    'Azure Firewall',
    'Azure DDoS Protection',
    'Microsoft Defender for Cloud',
    'Microsoft Sentinel',
    'Azure Information Protection',
    'Azure Confidential Computing',

    # Management & Monitoring
    'Azure Monitor',
    'Application Insights',
    'Azure Log Analytics',
    'Azure Advisor',
    'Azure Policy',
    'Azure Automation',
    'Azure Backup',
    'Azure Site Recovery',
    'Azure Cost Management',
    'Azure Resource Manager',
    'Azure Arc',
    'Azure Lighthouse',
    'Azure Managed Grafana',

    # Analytics & Data
    'Azure Synapse Analytics',
    'Azure Databricks',
    'Azure Data Factory',
    'Azure Data Explorer',
    'Azure Stream Analytics',
    'Azure HDInsight',
    'Azure Analysis Services',
    'Azure Purview',
    'Microsoft Fabric',
    'Power BI Embedded',

    # AI & ML
    'Azure OpenAI Service',
    'Azure Machine Learning',
    'Azure Cognitive Services',
    'Azure AI Services',
    'Azure Bot Service',
    'Azure Cognitive Search',
    'Azure AI Search',
    'Azure Form Recognizer',
    'Azure Computer Vision',
    'Azure Speech Services',
    'Azure Translator',
    'Azure Personalizer',
    'Azure Content Moderator',
    'Azure Anomaly Detector',
    'Azure Metrics Advisor',

    # IoT
    'Azure IoT Hub',
    'Azure IoT Central',
    'Azure IoT Edge',
    'Azure Digital Twins',
    'Azure Time Series Insights',
    'Azure Sphere',

    # DevOps & Developer Tools
    'Azure DevOps',
    'Azure Repos',
    'Azure Pipelines',
    'Azure Boards',
    'Azure Artifacts',
    'Azure Test Plans',
    'Azure DevTest Labs',
    'GitHub',
    'GitHub Actions',

    # Media
    'Azure Media Services',
    'Azure Content Delivery Network',

    # Migration
    'Azure Migrate',
    'Azure Database Migration Service',

    # Messaging
    'Azure SignalR Service',
    'Azure Notification Hubs',
    'Azure Communication Services',

    # Blockchain
    'Azure Confidential Ledger',

    # SAP & Specialized
    'Azure SAP HANA',
    'Azure Large Instances',
}

# Lowercase lookup for matching
_KNOWN_SERVICES_LOWER = {s.lower(): s for s in KNOWN_AZURE_SERVICES}


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
        """Extract Azure service names from document content.

        Returns only clean, validated Azure service names from the known services list.
        Uses hard allow-list matching - anything that doesn't exactly match is dropped.
        """
        services = set()

        # Priority 1: Products from architecture metadata (most reliable - from YML)
        for product in doc.arch_metadata.products:
            normalized = self._normalize_product_id(product)
            if normalized and normalized in KNOWN_AZURE_SERVICES:
                services.add(normalized)

        # Priority 2: Products from frontmatter
        products = doc.frontmatter.get('ms.products', [])
        if isinstance(products, list):
            for product in products:
                normalized = self._normalize_product_id(product)
                if normalized and normalized in KNOWN_AZURE_SERVICES:
                    services.add(normalized)

        # Priority 3: Content extraction (most risky - apply strict filtering)
        content_services = self._extract_services_from_content(doc.content + ' ' + doc.description)
        services.update(content_services)

        return sorted(services)

    def _extract_services_from_content(self, content: str) -> set[str]:
        """Extract services from content with strict allow-list matching.

        Only returns services that EXACTLY match the known services list.
        Any prose, sentences, or unrecognized text is dropped.
        """
        config = self._get_config()
        services = set()

        for pattern in config.detection_patterns:
            for match in re.finditer(pattern, content, re.IGNORECASE):
                raw = match.group(1) if match.lastindex else match.group(0)
                normalized = self._strict_service_match(raw)
                if normalized:
                    services.add(normalized)

        return services

    def _strict_service_match(self, raw: str) -> Optional[str]:
        """Strict matching against known Azure services.

        Rules:
        1. Must not contain verbs or sentence patterns
        2. Must exactly match a known service (after normalization)
        3. Drop anything with more than 5 words
        4. Drop anything that looks like a sentence
        """
        if not raw:
            return None

        # Quick rejection: contains obvious sentence patterns
        sentence_indicators = [
            ' is ', ' are ', ' was ', ' were ', ' has ', ' have ', ' does ', ' do ',
            ' can ', ' will ', ' should ', ' would ', ' could ', ' might ',
            ' automatically ', ' executes ', ' removes ', ' provides ', ' supports ',
            ' enables ', ' allows ', ' handles ', ' processes ', ' manages ',
            ' creates ', ' deploys ', ' runs ', ' scales ', ' hosts ', ' serves ',
            ' based on ', ' before ', ' after ', ' when ', ' while ', ' during ',
        ]
        raw_lower = raw.lower()
        for indicator in sentence_indicators:
            if indicator in raw_lower:
                return None

        # Strip everything after first newline
        text = raw.split('\n')[0].strip()

        # Strip everything after common clause starters
        for marker in [' that ', ' which ', ' where ', ' when ', ' and ', ' or ', ' to ', ' for ', ' with ']:
            if marker in text.lower():
                idx = text.lower().find(marker)
                text = text[:idx].strip()

        # Reject if still too long (> 5 words)
        if len(text.split()) > 5:
            return None

        # Reject if ends with common non-service words
        if text.lower().endswith((' it', ' them', ' this', ' that', ' data', ' based')):
            return None

        # Try to match against known services
        return self._match_known_service(text)

    def _match_known_service(self, text: str) -> Optional[str]:
        """Match text against known Azure services with exact matching.

        Returns the canonical service name or None.
        """
        if not text:
            return None

        text_lower = text.lower().strip()
        config = self._get_config()

        # Direct match in known services
        if text_lower in _KNOWN_SERVICES_LOWER:
            return _KNOWN_SERVICES_LOWER[text_lower]

        # Try with Azure prefix
        azure_prefixed = f"azure {text_lower}"
        if azure_prefixed in _KNOWN_SERVICES_LOWER:
            return _KNOWN_SERVICES_LOWER[azure_prefixed]

        # Check config normalizations
        if text_lower in config.normalizations:
            canonical = config.normalizations[text_lower]
            if canonical in KNOWN_AZURE_SERVICES:
                return canonical

        # No match - drop it
        return None


    def _normalize_product_id(self, product_id: str) -> Optional[str]:
        """Normalize a product ID like 'azure-app-service' to a canonical service name.

        Returns None if the product ID doesn't map to a known Azure service.
        Always returns the exact canonical name from KNOWN_AZURE_SERVICES.
        """
        if not product_id:
            return None

        # Skip generic entries
        if product_id.lower() in ('azure', 'microsoft'):
            return None

        # Product ID to canonical name mappings (must match KNOWN_AZURE_SERVICES exactly)
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
            'azure-event-grid': 'Azure Event Grid',
            'azure-logic-apps': 'Azure Logic Apps',
            'azure-data-factory': 'Azure Data Factory',
            'azure-databricks': 'Azure Databricks',
            'azure-synapse-analytics': 'Azure Synapse Analytics',
            'azure-api-management': 'Azure API Management',
            'azure-container-apps': 'Azure Container Apps',
            'azure-container-instances': 'Azure Container Instances',
            'azure-container-registry': 'Azure Container Registry',
            'azure-private-link': 'Azure Private Link',
            'azure-vpn-gateway': 'Azure VPN Gateway',
            'azure-files': 'Azure Files',
            'azure-netapp-files': 'Azure NetApp Files',
            'azure-cache-redis': 'Azure Cache for Redis',
            'azure-redis-cache': 'Azure Cache for Redis',
            'azure-sql-managed-instance': 'Azure SQL Managed Instance',
            'azure-database-postgresql': 'Azure Database for PostgreSQL',
            'azure-database-mysql': 'Azure Database for MySQL',
            'azure-iot-hub': 'Azure IoT Hub',
            'azure-iot-central': 'Azure IoT Central',
            'azure-digital-twins': 'Azure Digital Twins',
            'azure-stream-analytics': 'Azure Stream Analytics',
            'azure-hdinsight': 'Azure HDInsight',
            'azure-data-explorer': 'Azure Data Explorer',
            'azure-data-lake-storage': 'Azure Data Lake Storage',
            'azure-signalr-service': 'Azure SignalR Service',
            'azure-notification-hubs': 'Azure Notification Hubs',
            'azure-cognitive-search': 'Azure Cognitive Search',
            'azure-ai-search': 'Azure AI Search',
            'azure-bot-service': 'Azure Bot Service',
            'azure-devops': 'Azure DevOps',
            'azure-backup': 'Azure Backup',
            'azure-site-recovery': 'Azure Site Recovery',
            'azure-bastion': 'Azure Bastion',
            'azure-ddos-protection': 'Azure DDoS Protection',
            'azure-dns': 'Azure DNS',
            'azure-traffic-manager': 'Azure Traffic Manager',
            'azure-cdn': 'Azure CDN',
            'azure-nat-gateway': 'Azure NAT Gateway',
            'azure-batch': 'Azure Batch',
            'azure-service-fabric': 'Azure Service Fabric',
            'azure-spring-apps': 'Azure Spring Apps',
            'azure-static-web-apps': 'Azure Static Web Apps',
            'azure-devtest-labs': 'Azure DevTest Labs',
            'azure-automation': 'Azure Automation',
            'azure-policy': 'Azure Policy',
            'azure-advisor': 'Azure Advisor',
            'azure-arc': 'Azure Arc',
            'azure-migrate': 'Azure Migrate',
            'azure-machine-learning': 'Azure Machine Learning',
            'azure-cognitive-services': 'Azure Cognitive Services',
            'azure-openai': 'Azure OpenAI Service',
            'entra-id': 'Microsoft Entra ID',
            'entra': 'Microsoft Entra ID',
            'ai-services': 'Azure AI Services',
            'fabric': 'Microsoft Fabric',
            'power-bi-embedded': 'Power BI Embedded',
            'microsoft-sentinel': 'Microsoft Sentinel',
            'microsoft-defender-cloud': 'Microsoft Defender for Cloud',
            'application-insights': 'Application Insights',
            'log-analytics': 'Azure Log Analytics',
            'github': 'GitHub',
            'github-actions': 'GitHub Actions',
        }

        # Direct lookup
        if product_id in product_mappings:
            canonical = product_mappings[product_id]
            # Verify it exists in KNOWN_AZURE_SERVICES
            if canonical in KNOWN_AZURE_SERVICES:
                return canonical
            return None

        # Try kebab-case conversion for azure-* products
        if product_id.startswith('azure-'):
            name = product_id[6:].replace('-', ' ').title()
            candidate = f"Azure {name}"
            if candidate in KNOWN_AZURE_SERVICES:
                return candidate

        # No match - drop it
        return None

