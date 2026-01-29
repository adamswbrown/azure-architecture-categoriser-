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
    RuntimeModel,
    WorkloadDomain,
)


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
        services: list[str]
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
