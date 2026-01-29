"""Metadata extraction from architecture documents."""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from .config import get_config
from .parser import MarkdownParser, ParsedDocument
from .schema import (
    ArchitectureEntry,
    CatalogQuality,
    ClassificationMeta,
    ExpectedCharacteristics,
    ExtractionConfidence,
    TrinaryOption,
)


# Services that are typically supporting (observability, security, operations)
SUPPORTING_SERVICE_PATTERNS = [
    'monitor', 'log analytics', 'application insights', 'sentinel',
    'key vault', 'defender', 'security center',
    'policy', 'advisor', 'cost management', 'automation',
    'backup', 'site recovery', 'bastion',
    'dns', 'traffic manager', 'ddos',
]

# Core service categories that realize the pattern
CORE_SERVICE_CATEGORIES = [
    # Compute
    'app service', 'functions', 'kubernetes', 'container', 'virtual machine',
    'batch', 'service fabric', 'spring', 'web app',
    # Data
    'sql', 'cosmos', 'storage', 'redis', 'postgresql', 'mysql', 'synapse',
    'data factory', 'databricks', 'data lake', 'event hub', 'stream analytics',
    # Integration
    'api management', 'logic app', 'service bus', 'event grid',
    # Networking (core)
    'application gateway', 'front door', 'load balancer', 'firewall',
    'virtual network', 'expressroute', 'vpn', 'private link',
    # AI
    'openai', 'cognitive', 'machine learning', 'search',
]


class MetadataExtractor:
    """Extracts metadata from architecture documents."""

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
        raw_title = self._extract_title(doc)
        description = self._extract_description(doc)

        # Build Learn URL
        learn_url = self._build_learn_url(rel_path)

        # Extract and classify Azure services
        all_services = self.parser.extract_azure_services(doc)
        core_services, supporting_services = self._classify_services(all_services)

        # Infer pattern name from title and services
        pattern_name_raw = self._infer_pattern_name(raw_title, core_services, doc)
        pattern_name = self._truncate_name(pattern_name_raw)

        # Name should use pattern_name (never raw "Architecture" titles)
        name = self._derive_display_name(pattern_name, raw_title)

        # Extract diagram assets
        diagrams = self._extract_diagrams(doc, rel_path)

        # Extract browse metadata from YML (authoritative source)
        browse_tags = self._extract_browse_tags(doc)
        browse_categories = self._extract_browse_categories(doc)

        # Determine catalog quality based on metadata source
        catalog_quality = self._determine_catalog_quality(doc)

        # Determine pattern_name confidence based on source
        has_yml = doc.arch_metadata.is_architecture_yml
        pattern_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.CURATED if has_yml else ExtractionConfidence.AI_SUGGESTED,
            source="yml_metadata" if has_yml else "title_and_services"
        )

        # Infer expected characteristics
        expected_characteristics = self._infer_expected_characteristics(
            core_services, doc
        )

        # Create entry with extracted values
        entry = ArchitectureEntry(
            architecture_id=arch_id,
            name=name,
            pattern_name=pattern_name,
            pattern_name_confidence=pattern_confidence,
            description=description,
            source_repo_path=rel_path,
            learn_url=learn_url,
            browse_tags=browse_tags,
            browse_categories=browse_categories,
            catalog_quality=catalog_quality,
            core_services=core_services,
            supporting_services=supporting_services,
            services_confidence=ClassificationMeta(
                confidence=ExtractionConfidence.CURATED if has_yml else ExtractionConfidence.AI_SUGGESTED,
                source="yml_products" if has_yml else "content_analysis"
            ),
            expected_characteristics=expected_characteristics,
            diagram_assets=diagrams,
            last_repo_update=last_modified,
        )

        # Add extraction warnings
        if not name or name == "Architecture":
            entry.extraction_warnings.append("Could not extract meaningful name")
        if self._is_junk_name(name):
            entry.extraction_warnings.append(f"Junk pattern name detected: '{name}'")
            # Downgrade quality for junk names - they're not useful for scoring
            if entry.catalog_quality != CatalogQuality.EXAMPLE_ONLY:
                entry.catalog_quality = CatalogQuality.EXAMPLE_ONLY
        if not description:
            entry.extraction_warnings.append("Could not extract description")
        if not core_services:
            entry.extraction_warnings.append("No core Azure services detected")
        if not diagrams:
            entry.extraction_warnings.append("No architecture diagrams found")
        if not browse_tags:
            entry.extraction_warnings.append("No browse tags from YML metadata")

        return entry

    def _get_classification_config(self):
        """Get classification config."""
        from .config import get_config
        return get_config().classification

    def _is_junk_name(self, name: str) -> bool:
        """Check if a name is or contains a junk pattern.

        Catches both exact matches and embedded junk patterns like
        'Zone-redundant Potential Use Cases With Ingress'.

        Uses configurable lists from classification config.
        """
        if not name:
            return True
        name_lower = name.lower().strip()

        config = self._get_classification_config()

        # Exact match against junk_pattern_names
        junk_names = {n.lower() for n in config.junk_pattern_names}
        if name_lower in junk_names:
            return True

        # Contains junk pattern phrase
        for phrase in config.junk_pattern_phrases:
            if phrase.lower() in name_lower:
                return True

        return False

    def _derive_display_name(self, pattern_name: str, raw_title: str) -> str:
        """Derive a human-readable display name.

        The name should never be just 'Architecture' - use pattern_name
        or enhance the raw title to be meaningful.

        Post-processing rules:
        - If name is in junk blacklist → try alternatives
        - If name contains 'that', 'which', 'to' (clause markers) → truncate before
        - If name has more than 8 words → truncate to primary identifier
        """
        # If pattern_name is good and not junk, use it
        if pattern_name and not self._is_junk_name(pattern_name):
            name = self._truncate_name(pattern_name)
            if name and not self._is_junk_name(name):
                return name

        # If raw_title is meaningful and not junk, clean it up
        if raw_title and not self._is_junk_name(raw_title):
            # Remove generic suffixes
            name = raw_title
            for suffix in [' Architecture', ' - Azure Architecture Center', ' on Azure']:
                if name.endswith(suffix):
                    name = name[:-len(suffix)]
            name = self._truncate_name(name.strip())
            if name and not self._is_junk_name(name):
                return name

        # Last resort: return truncated pattern_name even if not ideal
        # But mark it clearly if it's junk
        result = self._truncate_name(pattern_name) or self._truncate_name(raw_title) or "Unnamed Architecture"
        return result

    def _truncate_name(self, name: str) -> str:
        """Truncate a name that contains prose or is too long.

        Rules:
        1. Truncate before clause markers ('that', 'which', 'to', 'for')
           but only when they appear as connectors, not as part of service names
        2. Truncate if more than 8 words
        3. Remove trailing punctuation and incomplete phrases
        """
        if not name:
            return ""

        # Rule 1: Truncate before clause markers (word boundary match)
        # Be careful with 'to' - it's part of "back to" which is fine in names
        clause_markers = [
            ' that ', ' which ', ' where ', ' when ',
            ' so that ', ' in order to ', ' designed to ',
            ' used to ', ' intended to ',
        ]
        name_lower = name.lower()
        for marker in clause_markers:
            if marker in name_lower:
                idx = name_lower.find(marker)
                name = name[:idx].strip()
                name_lower = name.lower()

        # Special handling for standalone 'to' - only truncate if followed by verb-like word
        # e.g., "Web App to handle traffic" → "Web App"
        # but keep "API Management with Path to Production" → keep as is
        to_pattern = re.compile(r'\s+to\s+(?:handle|manage|process|support|enable|provide|create|deploy|run|scale|host|serve)\b', re.IGNORECASE)
        match = to_pattern.search(name)
        if match:
            name = name[:match.start()].strip()

        # Rule 2: Truncate if more than 8 words - be aggressive
        words = name.split()
        if len(words) > 8:
            # Try to find a natural break point (prepositions that indicate secondary clause)
            # Look for break words starting from position 3 (0-indexed)
            break_words = ['and', 'or', 'for', 'using', 'through', 'across', 'with']
            best_break = None
            for i, word in enumerate(words):
                if i >= 3 and word.lower() in break_words:
                    # Only break if result would be 4-8 words
                    if 4 <= i <= 8:
                        best_break = i
                        # Prefer breaks at positions 6-8 for more descriptive names
                        if i >= 6:
                            break

            if best_break:
                name = ' '.join(words[:best_break])
            else:
                # No natural break, just truncate to 8 words
                name = ' '.join(words[:8])

        # Rule 3: Clean up trailing punctuation and incomplete phrases
        name = re.sub(r'[.,;:\-–—]+$', '', name).strip()
        name = re.sub(r'\s+(with|and|or|for|using)$', '', name, flags=re.IGNORECASE).strip()

        return name

    def _extract_browse_tags(self, doc: ParsedDocument) -> list[str]:
        """Extract browse tags from YML products metadata.

        Products like 'azure-kubernetes-service' become tags like 'Containers'.
        """
        tags = []

        # Map product IDs to human-readable browse tags
        product_to_tag = {
            'azure-kubernetes-service': 'Containers',
            'azure-container-apps': 'Containers',
            'azure-container-instances': 'Containers',
            'azure-app-service': 'Web',
            'azure-functions': 'Serverless',
            'azure-virtual-machines': 'Compute',
            'azure-sql-database': 'Databases',
            'azure-cosmos-db': 'Databases',
            'azure-storage': 'Storage',
            'azure-openai': 'AI',
            'azure-machine-learning': 'AI',
            'ai-services': 'AI',
            'azure-synapse-analytics': 'Analytics',
            'azure-databricks': 'Analytics',
            'azure-data-factory': 'Data',
            'azure-event-hubs': 'Messaging',
            'azure-service-bus': 'Messaging',
            'azure-api-management': 'Integration',
            'azure-logic-apps': 'Integration',
            'azure-monitor': 'Monitoring',
            'azure-key-vault': 'Security',
            'entra-id': 'Identity',
            'azure-virtual-network': 'Networking',
            'azure-front-door': 'Networking',
            'azure-application-gateway': 'Networking',
            'azure-firewall': 'Security',
            'azure-private-link': 'Networking',
        }

        # Add 'Azure' as base tag if we have any Azure products
        if doc.arch_metadata.products:
            tags.append('Azure')

        # Map products to tags
        seen_tags = {'Azure'}
        for product in doc.arch_metadata.products:
            tag = product_to_tag.get(product)
            if tag and tag not in seen_tags:
                tags.append(tag)
                seen_tags.add(tag)

        return tags

    def _extract_browse_categories(self, doc: ParsedDocument) -> list[str]:
        """Extract browse categories from YML azure_categories metadata."""
        categories = []

        # Map azure category IDs to display names
        category_to_display = {
            'web': 'Web',
            'ai-machine-learning': 'AI + Machine Learning',
            'analytics': 'Analytics',
            'compute': 'Compute',
            'containers': 'Containers',
            'databases': 'Databases',
            'devops': 'DevOps',
            'hybrid': 'Hybrid',
            'identity': 'Identity',
            'integration': 'Integration',
            'iot': 'IoT',
            'management-and-governance': 'Management',
            'media': 'Media',
            'migration': 'Migration',
            'networking': 'Networking',
            'security': 'Security',
            'storage': 'Storage',
        }

        # Add 'Architecture' as base category for all entries
        categories.append('Architecture')

        # Add ms.topic based categories
        topic = doc.arch_metadata.ms_topic
        if topic == 'reference-architecture':
            categories.append('Reference')
        elif topic == 'example-scenario':
            categories.append('Example Scenario')
        elif topic == 'solution-idea':
            categories.append('Solution Idea')

        # Map azure categories
        for cat in doc.arch_metadata.azure_categories:
            display = category_to_display.get(cat, cat.replace('-', ' ').title())
            if display not in categories:
                categories.append(display)

        return categories

    def _determine_catalog_quality(self, doc: ParsedDocument) -> CatalogQuality:
        """Determine the catalog quality level based on metadata source.

        Quality levels (highest to lowest):
        - curated: Reference architectures with authoritative YML metadata
        - ai_enriched: Has YML but incomplete metadata
        - ai_suggested: No YML, purely AI-extracted
        - example_only: Example scenarios (not reference architectures)

        Example scenarios are marked as 'example_only' because they are
        illustrative implementations, not prescriptive reference patterns.
        """
        ms_topic = doc.arch_metadata.ms_topic or doc.frontmatter.get('ms.topic', '')

        # Example scenarios get their own quality level
        # They are illustrative, not prescriptive reference architectures
        if ms_topic == 'example-scenario':
            return CatalogQuality.EXAMPLE_ONLY

        # Solution ideas are also example-level (not reference architectures)
        if ms_topic == 'solution-idea':
            return CatalogQuality.EXAMPLE_ONLY

        if doc.arch_metadata.is_architecture_yml:
            # Reference architectures with authoritative YML metadata
            if doc.arch_metadata.azure_categories and doc.arch_metadata.products:
                return CatalogQuality.CURATED
            else:
                return CatalogQuality.AI_ENRICHED

        # No YML metadata, purely AI-extracted
        return CatalogQuality.AI_SUGGESTED

    def _infer_expected_characteristics(
        self,
        core_services: list[str],
        doc: ParsedDocument
    ) -> ExpectedCharacteristics:
        """Infer expected architectural characteristics from services and content."""
        content_lower = doc.content.lower()
        services_lower = ' '.join(s.lower() for s in core_services)

        # Container-based services require DevOps/CI/CD
        container_services = ['kubernetes', 'container', 'aks']
        has_containers = any(svc in services_lower for svc in container_services)

        # Serverless and PaaS services typically require CI/CD
        cicd_services = ['functions', 'app service', 'container apps', 'logic apps']
        has_cicd_services = any(svc in services_lower for svc in cicd_services)

        # Check content for DevOps/CI/CD mentions
        devops_keywords = ['ci/cd', 'cicd', 'pipeline', 'github actions', 'azure devops',
                          'deployment', 'gitops', 'terraform', 'infrastructure as code']
        has_devops_content = any(kw in content_lower for kw in devops_keywords)

        # Private networking detection
        private_keywords = ['private endpoint', 'private link', 'vnet integration',
                           'private network', 'private subnet', 'no public']
        has_private_networking = any(kw in content_lower for kw in private_keywords)

        # Stateless detection
        stateless_keywords = ['stateless', 'scale out', 'horizontal scaling', 'load balanc']
        stateful_keywords = ['stateful', 'session affinity', 'sticky session', 'local storage']
        is_stateless = any(kw in content_lower for kw in stateless_keywords)
        is_stateful = any(kw in content_lower for kw in stateful_keywords)

        # Determine characteristics
        devops_required = has_containers or has_devops_content
        ci_cd_required = has_containers or has_cicd_services or has_devops_content
        private_networking_required = has_private_networking

        # Container determination
        if has_containers:
            containers = TrinaryOption.TRUE
        elif 'virtual machine' in services_lower or 'vm' in services_lower:
            containers = TrinaryOption.FALSE
        else:
            containers = TrinaryOption.OPTIONAL

        # Stateless determination
        if is_stateless and not is_stateful:
            stateless = TrinaryOption.TRUE
        elif is_stateful and not is_stateless:
            stateless = TrinaryOption.FALSE
        else:
            stateless = TrinaryOption.OPTIONAL

        return ExpectedCharacteristics(
            containers=containers,
            stateless=stateless,
            devops_required=devops_required,
            ci_cd_required=ci_cd_required,
            private_networking_required=private_networking_required,
        )

    def _classify_services(self, services: list[str]) -> tuple[list[str], list[str]]:
        """Classify services into core and supporting categories."""
        core = []
        supporting = []

        for service in services:
            service_lower = service.lower()

            # Check if it's a supporting service
            is_supporting = any(
                pattern in service_lower
                for pattern in SUPPORTING_SERVICE_PATTERNS
            )

            if is_supporting:
                supporting.append(service)
            else:
                # Check if it matches core service patterns
                is_core = any(
                    pattern in service_lower
                    for pattern in CORE_SERVICE_CATEGORIES
                )
                if is_core:
                    core.append(service)
                else:
                    # Default to supporting if unrecognized
                    supporting.append(service)

        return core, supporting

    def _infer_pattern_name(
        self,
        title: str,
        core_services: list[str],
        doc: ParsedDocument
    ) -> str:
        """Infer a workload-intent pattern name.

        Pattern names should describe architectural INTENT, not just services.
        Format: [Quality/Tier] [Workload Type] with [Key Features]

        Good examples:
        - "Enterprise-grade AKS cluster with private networking and ingress"
        - "Highly available web application with geo-redundancy"
        - "Event-driven microservices for order processing"

        Bad examples (avoid):
        - "Azure App Service with Azure SQL Database"
        - "AKS with Cosmos DB with Redis"
        """
        content_lower = doc.content.lower()
        services_lower = ' '.join(s.lower() for s in core_services)

        # Step 1: Extract workload type/intent from content
        workload_intent = self._extract_workload_intent(title, content_lower, services_lower)

        # Step 2: Extract quality/tier qualifiers
        quality_prefix = self._extract_quality_prefix(content_lower)

        # Step 3: Extract key architectural features
        features = self._extract_key_features(content_lower)

        # Step 4: Compose the pattern name
        parts = []

        if quality_prefix:
            parts.append(quality_prefix)

        parts.append(workload_intent)

        if features:
            parts.append(f"with {' and '.join(features[:2])}")

        pattern = ' '.join(parts)

        # Final cleanup - title case but preserve acronyms
        pattern = self._title_case_preserve_acronyms(pattern)

        return pattern

    def _extract_workload_intent(
        self,
        title: str,
        content_lower: str,
        services_lower: str
    ) -> str:
        """Extract the core workload intent from the document."""
        # Clean up title first
        intent = title

        # Remove common prefixes/suffixes
        prefixes = [
            'architecture for ', 'reference architecture for ', 'baseline architecture for ',
            'example: ', 'tutorial: ', 'how to ', 'azure ', 'microsoft ',
        ]
        suffixes = [
            ' - azure architecture center', ' on azure', ' architecture',
            ' pattern', ' reference', ' baseline',
        ]

        intent_lower = intent.lower()
        for prefix in prefixes:
            if intent_lower.startswith(prefix):
                intent = intent[len(prefix):]
                intent_lower = intent.lower()

        for suffix in suffixes:
            if intent_lower.endswith(suffix):
                intent = intent[:-len(suffix)]
                intent_lower = intent.lower()

        # If still too generic, try to identify the primary workload type
        generic_terms = ['architecture', 'overview', 'introduction', 'guide', 'baseline']
        if intent_lower in generic_terms or len(intent) < 10:
            # Try to infer from primary compute service
            if 'kubernetes' in services_lower or 'aks' in services_lower:
                intent = 'AKS cluster'
            elif 'container apps' in services_lower:
                intent = 'Container Apps deployment'
            elif 'app service' in services_lower:
                intent = 'App Service web application'
            elif 'functions' in services_lower:
                intent = 'Serverless application'
            elif 'virtual machine' in services_lower:
                intent = 'VM-based workload'
            elif 'data factory' in services_lower or 'synapse' in services_lower:
                intent = 'Data pipeline'
            elif 'openai' in services_lower or 'machine learning' in services_lower:
                intent = 'AI/ML workload'
            elif 'event hub' in services_lower or 'service bus' in services_lower:
                intent = 'Event-driven system'
            else:
                # Try content-based workload detection
                if 'e-commerce' in content_lower or 'shopping' in content_lower:
                    intent = 'E-commerce platform'
                elif 'api gateway' in content_lower or 'api management' in content_lower:
                    intent = 'API platform'
                elif 'data warehouse' in content_lower:
                    intent = 'Data warehouse'
                elif 'iot' in content_lower:
                    intent = 'IoT solution'
                elif 'chatbot' in content_lower or 'conversational' in content_lower:
                    intent = 'Conversational AI'
                else:
                    intent = 'Cloud workload'

        return intent.strip()

    def _extract_quality_prefix(self, content_lower: str) -> str:
        """Extract quality/tier prefix from content."""
        # Check for quality indicators in priority order
        if 'mission-critical' in content_lower or 'mission critical' in content_lower:
            return 'Mission-critical'
        elif 'enterprise-grade' in content_lower or 'enterprise grade' in content_lower:
            return 'Enterprise-grade'
        elif 'production-ready' in content_lower or 'production ready' in content_lower:
            return 'Production-ready'
        elif 'highly available' in content_lower or 'high availability' in content_lower:
            return 'Highly available'
        elif 'multi-region' in content_lower or 'multiple regions' in content_lower:
            return 'Multi-region'
        elif 'zone-redundant' in content_lower or 'availability zone' in content_lower:
            return 'Zone-redundant'
        elif 'baseline' in content_lower:
            return 'Baseline'

        return ''

    def _extract_key_features(self, content_lower: str) -> list[str]:
        """Extract key architectural features from content."""
        features = []

        # Security/networking features
        if 'private endpoint' in content_lower or 'private link' in content_lower:
            features.append('private networking')
        if 'zero trust' in content_lower:
            features.append('zero trust')
        if 'web application firewall' in content_lower or 'waf' in content_lower:
            features.append('WAF')

        # Traffic/routing features
        if 'ingress controller' in content_lower or 'nginx' in content_lower:
            features.append('ingress')
        if 'traffic manager' in content_lower or 'front door' in content_lower:
            features.append('global load balancing')
        if 'active-active' in content_lower:
            features.append('active-active')
        elif 'active-passive' in content_lower:
            features.append('active-passive failover')

        # Data features
        if 'geo-replication' in content_lower or 'geo-redundant' in content_lower:
            features.append('geo-redundancy')
        if 'caching' in content_lower or 'redis' in content_lower:
            features.append('caching')

        # DevOps features
        if 'gitops' in content_lower:
            features.append('GitOps')
        if 'blue-green' in content_lower or 'blue/green' in content_lower:
            features.append('blue-green deployment')
        if 'canary' in content_lower:
            features.append('canary deployment')

        return features

    def _title_case_preserve_acronyms(self, text: str) -> str:
        """Title case text but preserve acronyms like AKS, API, WAF."""
        acronyms = {
            'aks', 'api', 'waf', 'cdn', 'dns', 'sql', 'vm', 'vms', 'iot',
            'ai', 'ml', 'ci', 'cd', 'cicd', 'saas', 'paas', 'iaas',
        }

        words = text.split()
        result = []
        for word in words:
            lower = word.lower().rstrip('.,;:')
            if lower in acronyms:
                result.append(word.upper())
            elif word.isupper() and len(word) > 1:
                result.append(word)  # Keep existing acronyms
            else:
                result.append(word.capitalize())

        return ' '.join(result)

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
        """Build the GitHub source URL for the document.

        Uses GitHub direct links which are guaranteed to work since we parse from this repo.
        Format: https://github.com/MicrosoftDocs/architecture-center/blob/main/docs/...
        """
        config = get_config().urls

        # GitHub URL is straightforward - just append the relative path
        return f"{config.github_base_url}{rel_path}"

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
