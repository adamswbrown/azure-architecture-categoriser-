"""AI-assisted classification suggestions for architecture entries."""

import re
from typing import Optional

from .parser import ParsedDocument
from .schema import (
    ArchitectureEntry,
    ArchitectureFamily,
    AvailabilityModel,
    ClassificationMeta,
    Complexity,
    ComplexityLevel,
    ExtractionConfidence,
    RuntimeModel,
    WorkloadDomain,
)


class ArchitectureClassifier:
    """Provides AI-assisted classification suggestions for architectures.

    These suggestions require human review before being considered final.
    """

    # Keywords for workload domain detection
    DOMAIN_KEYWORDS = {
        WorkloadDomain.WEB: [
            'web app', 'website', 'frontend', 'spa', 'single page',
            'web application', 'web service', 'web api', 'blazor',
            'asp.net', 'react', 'angular', 'vue', 'node.js',
        ],
        WorkloadDomain.DATA: [
            'data warehouse', 'data lake', 'analytics', 'big data',
            'etl', 'data pipeline', 'olap', 'reporting', 'bi ',
            'business intelligence', 'data platform', 'synapse',
            'databricks', 'data factory', 'hdinsight',
        ],
        WorkloadDomain.INTEGRATION: [
            'integration', 'api gateway', 'message', 'queue', 'event',
            'service bus', 'event hub', 'event grid', 'logic app',
            'b2b', 'edi', 'middleware', 'esb', 'ipaa',
        ],
        WorkloadDomain.SECURITY: [
            'security', 'identity', 'authentication', 'authorization',
            'zero trust', 'firewall', 'waf', 'ddos', 'encryption',
            'key vault', 'secret', 'certificate', 'compliance',
        ],
        WorkloadDomain.AI: [
            'machine learning', 'ml ', 'ai ', 'artificial intelligence',
            'cognitive', 'nlp', 'computer vision', 'deep learning',
            'neural', 'openai', 'gpt', 'llm', 'chatbot', 'bot ',
        ],
        WorkloadDomain.INFRASTRUCTURE: [
            'infrastructure', 'network', 'hybrid', 'vpn', 'expressroute',
            'virtual network', 'vnet', 'dns', 'load balancer', 'firewall',
            'hub and spoke', 'landing zone', 'governance',
        ],
    }

    # Keywords for architecture family detection
    FAMILY_KEYWORDS = {
        ArchitectureFamily.FOUNDATION: [
            'landing zone', 'foundation', 'baseline', 'governance',
            'enterprise scale', 'caf ', 'cloud adoption',
        ],
        ArchitectureFamily.IAAS: [
            'virtual machine', 'vm ', 'iaas', 'lift and shift',
            'vm scale set', 'vmss', 'availability set',
        ],
        ArchitectureFamily.PAAS: [
            'app service', 'paas', 'platform as a service',
            'azure sql', 'cosmos db', 'managed service',
        ],
        ArchitectureFamily.CLOUD_NATIVE: [
            'kubernetes', 'aks', 'container', 'microservice',
            'cloud native', 'serverless', 'function', 'cloud-native',
        ],
        ArchitectureFamily.DATA: [
            'data platform', 'data warehouse', 'data lake',
            'analytics', 'synapse', 'databricks', 'data mesh',
        ],
        ArchitectureFamily.INTEGRATION: [
            'integration', 'api management', 'logic app',
            'service bus', 'event-driven', 'messaging',
        ],
        ArchitectureFamily.SPECIALIZED: [
            'sap', 'oracle', 'mainframe', 'hpc', 'high performance',
            'gaming', 'media', 'iot', 'digital twin',
        ],
    }

    # Keywords for runtime model detection
    RUNTIME_KEYWORDS = {
        RuntimeModel.MICROSERVICES: [
            'microservice', 'micro-service', 'distributed service',
            'service mesh', 'sidecar', 'dapr',
        ],
        RuntimeModel.EVENT_DRIVEN: [
            'event-driven', 'event driven', 'event sourcing', 'cqrs',
            'pub/sub', 'publish subscribe', 'reactive',
        ],
        RuntimeModel.API: [
            'rest api', 'graphql', 'api-first', 'api gateway',
            'web api', 'api management',
        ],
        RuntimeModel.N_TIER: [
            'n-tier', 'three-tier', '3-tier', 'multi-tier',
            'presentation layer', 'business layer', 'data layer',
        ],
        RuntimeModel.BATCH: [
            'batch processing', 'batch job', 'scheduled job',
            'etl', 'data pipeline', 'nightly job',
        ],
        RuntimeModel.MONOLITH: [
            'monolith', 'single application', 'traditional app',
        ],
    }

    # Availability indicators
    AVAILABILITY_KEYWORDS = {
        AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE: [
            'active-active', 'multi-region active', 'global distribution',
            'geo-replication', 'global load balancing',
        ],
        AvailabilityModel.MULTI_REGION_ACTIVE_PASSIVE: [
            'active-passive', 'disaster recovery', 'dr region',
            'failover region', 'backup region', 'geo-redundant',
        ],
        AvailabilityModel.ZONE_REDUNDANT: [
            'zone redundant', 'availability zone', 'zone-redundant',
            'across zones', 'zonal',
        ],
    }

    def suggest_classifications(
        self,
        entry: ArchitectureEntry,
        doc: ParsedDocument
    ) -> ArchitectureEntry:
        """Suggest classifications for an architecture entry.

        All suggestions are marked as AI_SUGGESTED and require human review.
        """
        content = (doc.content + ' ' + doc.description + ' ' + doc.title).lower()

        # Suggest workload domain
        domain = self._suggest_workload_domain(content)
        if domain:
            entry.workload_domain = domain
            entry.workload_domain_confidence = ClassificationMeta(
                confidence=ExtractionConfidence.AI_SUGGESTED,
                source="content_analysis"
            )

        # Suggest architecture family
        family = self._suggest_family(content, entry.azure_services_used)
        if family:
            entry.family = family
            entry.family_confidence = ClassificationMeta(
                confidence=ExtractionConfidence.AI_SUGGESTED,
                source="content_analysis"
            )

        # Suggest runtime models
        runtime_models = self._suggest_runtime_models(content)
        if runtime_models:
            entry.expected_runtime_models = runtime_models
            entry.runtime_models_confidence = ClassificationMeta(
                confidence=ExtractionConfidence.AI_SUGGESTED,
                source="content_analysis"
            )

        # Suggest availability models
        availability = self._suggest_availability(content)
        if availability:
            entry.availability_models = availability
            entry.availability_confidence = ClassificationMeta(
                confidence=ExtractionConfidence.AI_SUGGESTED,
                source="content_analysis"
            )

        # Suggest complexity
        complexity = self._suggest_complexity(doc, entry)
        entry.complexity = complexity
        entry.complexity_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.AI_SUGGESTED,
            source="heuristic_analysis"
        )

        return entry

    def _suggest_workload_domain(self, content: str) -> Optional[WorkloadDomain]:
        """Suggest workload domain based on content keywords."""
        scores: dict[WorkloadDomain, int] = {}

        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[domain] = score

        if scores:
            return max(scores, key=scores.get)
        return None

    def _suggest_family(
        self,
        content: str,
        services: list[str]
    ) -> Optional[ArchitectureFamily]:
        """Suggest architecture family based on content and services."""
        scores: dict[ArchitectureFamily, int] = {}

        # Score based on keywords
        for family, keywords in self.FAMILY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[family] = score

        # Boost based on Azure services
        service_lower = ' '.join(s.lower() for s in services)

        if 'kubernetes' in service_lower or 'container' in service_lower:
            scores[ArchitectureFamily.CLOUD_NATIVE] = \
                scores.get(ArchitectureFamily.CLOUD_NATIVE, 0) + 3

        if 'virtual machine' in service_lower:
            scores[ArchitectureFamily.IAAS] = \
                scores.get(ArchitectureFamily.IAAS, 0) + 2

        if 'app service' in service_lower or 'functions' in service_lower:
            scores[ArchitectureFamily.PAAS] = \
                scores.get(ArchitectureFamily.PAAS, 0) + 2

        if 'synapse' in service_lower or 'data factory' in service_lower:
            scores[ArchitectureFamily.DATA] = \
                scores.get(ArchitectureFamily.DATA, 0) + 2

        if scores:
            return max(scores, key=scores.get)
        return None

    def _suggest_runtime_models(self, content: str) -> list[RuntimeModel]:
        """Suggest runtime models based on content."""
        models = []

        for model, keywords in self.RUNTIME_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                models.append(model)

        # Default to unknown if nothing detected
        if not models:
            models = [RuntimeModel.UNKNOWN]

        # Check for mixed if multiple detected
        if len(models) > 2:
            models = [RuntimeModel.MIXED]

        return models

    def _suggest_availability(self, content: str) -> list[AvailabilityModel]:
        """Suggest availability models based on content."""
        models = []

        for model, keywords in self.AVAILABILITY_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                models.append(model)

        # Default to single region if nothing detected
        if not models:
            models = [AvailabilityModel.SINGLE_REGION]

        return models

    def _suggest_complexity(
        self,
        doc: ParsedDocument,
        entry: ArchitectureEntry
    ) -> Complexity:
        """Suggest complexity based on various factors."""
        impl_score = 0
        ops_score = 0

        # More services = more complexity
        service_count = len(entry.azure_services_used)
        if service_count > 10:
            impl_score += 2
            ops_score += 2
        elif service_count > 5:
            impl_score += 1
            ops_score += 1

        # More diagrams might indicate more complexity
        if len(entry.diagram_assets) > 3:
            impl_score += 1

        # Content length as proxy for complexity
        if len(doc.content) > 20000:
            impl_score += 1
            ops_score += 1

        # Multi-region is operationally complex
        if any(m in [AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE,
                     AvailabilityModel.MULTI_REGION_ACTIVE_PASSIVE]
               for m in entry.availability_models):
            ops_score += 2

        # Microservices are complex
        if RuntimeModel.MICROSERVICES in entry.expected_runtime_models:
            impl_score += 1
            ops_score += 1

        # Convert scores to levels
        def score_to_level(score: int) -> ComplexityLevel:
            if score >= 3:
                return ComplexityLevel.HIGH
            elif score >= 1:
                return ComplexityLevel.MEDIUM
            return ComplexityLevel.LOW

        return Complexity(
            implementation=score_to_level(impl_score),
            operations=score_to_level(ops_score)
        )
