"""AI-assisted classification suggestions for architecture entries."""

from typing import Optional

from .config import get_config
from .parser import ParsedDocument
from .schema import (
    ArchitectureEntry,
    ArchitectureFamily,
    AvailabilityModel,
    ClassificationMeta,
    Complexity,
    ComplexityLevel,
    ExtractionConfidence,
    OperatingModel,
    RuntimeModel,
    Treatment,
    TimeCategory,
    WorkloadDomain,
)


# Mapping from Azure categories to workload domains
CATEGORY_TO_DOMAIN = {
    'web': WorkloadDomain.WEB,
    'ai-machine-learning': WorkloadDomain.AI,
    'analytics': WorkloadDomain.DATA,
    'databases': WorkloadDomain.DATA,
    'compute': WorkloadDomain.INFRASTRUCTURE,
    'containers': WorkloadDomain.INFRASTRUCTURE,
    'networking': WorkloadDomain.INFRASTRUCTURE,
    'hybrid': WorkloadDomain.INFRASTRUCTURE,
    'integration': WorkloadDomain.INTEGRATION,
    'security': WorkloadDomain.SECURITY,
    'identity': WorkloadDomain.SECURITY,
    'iot': WorkloadDomain.INFRASTRUCTURE,
    'devops': WorkloadDomain.INFRASTRUCTURE,
    'storage': WorkloadDomain.DATA,
    'migration': WorkloadDomain.INFRASTRUCTURE,
    'management-and-governance': WorkloadDomain.INFRASTRUCTURE,
    'developer-tools': WorkloadDomain.INFRASTRUCTURE,
    'media': WorkloadDomain.WEB,
}


class ArchitectureClassifier:
    """Provides AI-assisted classification suggestions for architectures.

    These suggestions require human review before being considered final.
    """

    def _get_config(self):
        """Get classification config."""
        return get_config().classification

    def suggest_classifications(
        self,
        entry: ArchitectureEntry,
        doc: ParsedDocument
    ) -> ArchitectureEntry:
        """Suggest classifications for an architecture entry.

        All suggestions are marked as AI_SUGGESTED and require human review.
        """
        content = (doc.content + ' ' + doc.description + ' ' + doc.title).lower()

        # First, try to use yml metadata for domain (most reliable)
        domain = self._suggest_workload_domain_from_yml(doc)
        if not domain:
            domain = self._suggest_workload_domain(content)
        if domain:
            entry.workload_domain = domain
            source = "yml_metadata" if doc.arch_metadata.azure_categories else "content_analysis"
            entry.workload_domain_confidence = ClassificationMeta(
                confidence=ExtractionConfidence.AI_SUGGESTED,
                source=source
            )

        # Suggest architecture family
        family = self._suggest_family(content, entry.azure_services_used, doc)
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

        # Suggest operating model based on family and services
        entry.operating_model_required = self._suggest_operating_model(entry, content)

        # Suggest supported treatments based on family
        entry.supported_treatments = self._suggest_treatments(entry)

        # Suggest time categories based on complexity
        entry.supported_time_categories = self._suggest_time_categories(entry)

        return entry

    def _suggest_workload_domain_from_yml(self, doc: ParsedDocument) -> Optional[WorkloadDomain]:
        """Suggest workload domain from yml azure_categories metadata."""
        if not doc.arch_metadata.azure_categories:
            return None

        # Use the first matching category
        for cat in doc.arch_metadata.azure_categories:
            cat_lower = cat.lower().strip()
            if cat_lower in CATEGORY_TO_DOMAIN:
                return CATEGORY_TO_DOMAIN[cat_lower]

        return None

    def _suggest_workload_domain(self, content: str) -> Optional[WorkloadDomain]:
        """Suggest workload domain based on content keywords."""
        config = self._get_config()
        scores: dict[str, int] = {}

        for domain, keywords in config.domain_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[domain] = score

        if scores:
            best = max(scores, key=scores.get)
            try:
                return WorkloadDomain(best)
            except ValueError:
                pass
        return None

    def _suggest_family(
        self,
        content: str,
        services: list[str],
        doc: ParsedDocument
    ) -> Optional[ArchitectureFamily]:
        """Suggest architecture family based on content and services."""
        config = self._get_config()
        scores: dict[str, int] = {}

        # Score based on keywords
        for family, keywords in config.family_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[family] = score

        # Boost based on Azure services
        service_lower = ' '.join(s.lower() for s in services)

        if 'kubernetes' in service_lower or 'container' in service_lower:
            scores['cloud_native'] = scores.get('cloud_native', 0) + 3

        if 'virtual machine' in service_lower:
            scores['iaas'] = scores.get('iaas', 0) + 2

        if 'app service' in service_lower or 'functions' in service_lower:
            scores['paas'] = scores.get('paas', 0) + 2

        if 'synapse' in service_lower or 'data factory' in service_lower:
            scores['data'] = scores.get('data', 0) + 2

        # Boost based on yml products
        for product in doc.arch_metadata.products:
            prod_lower = product.lower()
            if 'kubernetes' in prod_lower or 'container' in prod_lower:
                scores['cloud_native'] = scores.get('cloud_native', 0) + 2
            elif 'virtual-machine' in prod_lower:
                scores['iaas'] = scores.get('iaas', 0) + 2
            elif 'app-service' in prod_lower or 'function' in prod_lower:
                scores['paas'] = scores.get('paas', 0) + 2

        if scores:
            best = max(scores, key=scores.get)
            try:
                return ArchitectureFamily(best)
            except ValueError:
                pass
        return None

    def _suggest_runtime_models(self, content: str) -> list[RuntimeModel]:
        """Suggest runtime models based on content."""
        config = self._get_config()
        models = []

        for model, keywords in config.runtime_keywords.items():
            if any(kw in content for kw in keywords):
                try:
                    models.append(RuntimeModel(model))
                except ValueError:
                    pass

        # Default to unknown if nothing detected
        if not models:
            models = [RuntimeModel.UNKNOWN]

        # Check for mixed if multiple detected
        if len(models) > 2:
            models = [RuntimeModel.MIXED]

        return models

    def _suggest_availability(self, content: str) -> list[AvailabilityModel]:
        """Suggest availability models based on content."""
        config = self._get_config()
        models = []

        for model, keywords in config.availability_keywords.items():
            if any(kw in content for kw in keywords):
                try:
                    models.append(AvailabilityModel(model))
                except ValueError:
                    pass

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

    def _suggest_operating_model(
        self,
        entry: ArchitectureEntry,
        content: str
    ) -> OperatingModel:
        """Suggest operating model based on architecture characteristics."""
        # Cloud-native and containerized architectures require DevOps
        if entry.family == ArchitectureFamily.CLOUD_NATIVE:
            return OperatingModel.DEVOPS

        # Microservices require DevOps or SRE
        if RuntimeModel.MICROSERVICES in entry.expected_runtime_models:
            return OperatingModel.DEVOPS

        # Multi-region active-active typically needs SRE
        if AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE in entry.availability_models:
            return OperatingModel.SRE

        # PaaS can work with transitional
        if entry.family == ArchitectureFamily.PAAS:
            return OperatingModel.TRANSITIONAL

        # IaaS can work with traditional IT
        if entry.family == ArchitectureFamily.IAAS:
            return OperatingModel.TRADITIONAL_IT

        # Check for DevOps keywords in content
        devops_keywords = ['ci/cd', 'cicd', 'devops', 'gitops', 'infrastructure as code', 'iac']
        if any(kw in content for kw in devops_keywords):
            return OperatingModel.DEVOPS

        # Default to transitional for most modern architectures
        return OperatingModel.TRANSITIONAL

    def _suggest_treatments(self, entry: ArchitectureEntry) -> list[Treatment]:
        """Suggest supported treatments based on architecture family."""
        treatments = []

        if entry.family == ArchitectureFamily.IAAS:
            # IaaS supports rehost, replatform
            treatments = [Treatment.REHOST, Treatment.REPLATFORM, Treatment.TOLERATE]

        elif entry.family == ArchitectureFamily.PAAS:
            # PaaS supports replatform, refactor
            treatments = [Treatment.REPLATFORM, Treatment.REFACTOR]

        elif entry.family == ArchitectureFamily.CLOUD_NATIVE:
            # Cloud-native requires refactor or replace
            treatments = [Treatment.REFACTOR, Treatment.REPLACE]

        elif entry.family == ArchitectureFamily.DATA:
            # Data platforms support replatform, refactor
            treatments = [Treatment.REPLATFORM, Treatment.REFACTOR]

        elif entry.family == ArchitectureFamily.INTEGRATION:
            # Integration can support most treatments
            treatments = [Treatment.REPLATFORM, Treatment.REFACTOR, Treatment.REPLACE]

        elif entry.family == ArchitectureFamily.FOUNDATION:
            # Foundation is for new implementations
            treatments = [Treatment.REFACTOR, Treatment.REPLACE]

        else:
            # Default: support common treatments
            treatments = [Treatment.REPLATFORM, Treatment.REFACTOR]

        return treatments

    def _suggest_time_categories(self, entry: ArchitectureEntry) -> list[TimeCategory]:
        """Suggest time categories based on complexity and family."""
        categories = []

        # High complexity = invest
        if (entry.complexity.implementation == ComplexityLevel.HIGH or
                entry.complexity.operations == ComplexityLevel.HIGH):
            categories.append(TimeCategory.INVEST)

        # Medium complexity = migrate
        if (entry.complexity.implementation == ComplexityLevel.MEDIUM or
                entry.complexity.operations == ComplexityLevel.MEDIUM):
            categories.append(TimeCategory.MIGRATE)

        # IaaS can be used for tolerate scenarios
        if entry.family == ArchitectureFamily.IAAS:
            categories.append(TimeCategory.TOLERATE)

        # Cloud-native is usually an invest scenario
        if entry.family == ArchitectureFamily.CLOUD_NATIVE:
            if TimeCategory.INVEST not in categories:
                categories.append(TimeCategory.INVEST)

        # Default
        if not categories:
            categories = [TimeCategory.MIGRATE]

        return categories
