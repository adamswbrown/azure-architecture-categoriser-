"""AI-assisted classification suggestions for architecture entries."""

import re
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
    CostProfile,
    ExclusionReason,
    ExtractionConfidence,
    OperatingModel,
    RuntimeModel,
    SecurityLevel,
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
        Uses enhanced content-based keyword scoring for better accuracy.
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

        # Enhanced: Suggest operating model using content-based scoring
        entry.operating_model_required = self._suggest_operating_model_enhanced(
            entry, content, doc
        )

        # Enhanced: Suggest treatments using content-based keyword scoring
        entry.supported_treatments = self._suggest_treatments_enhanced(
            entry, content, doc
        )

        # Enhanced: Suggest time categories using content-based scoring
        entry.supported_time_categories = self._suggest_time_categories_enhanced(
            entry, content
        )

        # New: Suggest security level based on compliance mentions
        entry.security_level = self._suggest_security_level(content, doc)

        # New: Suggest cost profile based on content and services
        entry.cost_profile = self._suggest_cost_profile(content, entry)

        # New: Extract not suitable for exclusions
        entry.not_suitable_for = self._extract_not_suitable_for(content, doc)

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

    # ========== Enhanced Classification Methods (Content-Based) ==========

    def _suggest_treatments_enhanced(
        self,
        entry: ArchitectureEntry,
        content: str,
        doc: ParsedDocument
    ) -> list[Treatment]:
        """Suggest treatments using content-based keyword scoring."""
        config = self._get_config()
        scores: dict[str, float] = {}

        # Score based on content keywords
        for treatment, keywords in config.treatment_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[treatment] = score

        # Boost based on Azure services (using configurable boost values)
        services_lower = ' '.join(s.lower() for s in entry.azure_services_used)

        # VM presence suggests rehost capability
        if 'virtual machine' in services_lower:
            scores['rehost'] = scores.get('rehost', 0) + config.vm_rehost_boost
            scores['retain'] = scores.get('retain', 0) + 1

        # AKS/Containers suggest refactor
        if any(s in services_lower for s in ['kubernetes', 'container apps', 'container instance']):
            scores['refactor'] = scores.get('refactor', 0) + config.container_refactor_boost
            scores['rebuild'] = scores.get('rebuild', 0) + 1

        # Managed services suggest replatform
        if any(s in services_lower for s in ['managed instance', 'sql database', 'cosmos']):
            scores['replatform'] = scores.get('replatform', 0) + config.managed_replatform_boost

        # ExpressRoute/Arc suggest retain/hybrid
        if any(s in services_lower for s in ['expressroute', 'arc', 'vpn gateway']):
            scores['retain'] = scores.get('retain', 0) + config.hybrid_retain_boost

        # App Service, Functions suggest replatform
        if any(s in services_lower for s in ['app service', 'functions']):
            scores['replatform'] = scores.get('replatform', 0) + 1.5

        # Boost from YML metadata (ms.collection: migration)
        ms_collections = doc.frontmatter.get('ms.collection', [])
        if isinstance(ms_collections, str):
            ms_collections = [ms_collections]
        if 'migration' in [c.lower() for c in ms_collections]:
            scores['rehost'] = scores.get('rehost', 0) + 1
            scores['replatform'] = scores.get('replatform', 0) + 1

        # Include architecture family hints
        family_treatments = self._get_family_treatment_hints(entry.family)
        for t in family_treatments:
            scores[t] = scores.get(t, 0) + 0.5

        # Select treatments above threshold (configurable)
        threshold = config.treatment_threshold
        treatments = []
        for t, score in scores.items():
            if score >= threshold:
                try:
                    treatments.append(Treatment(t))
                except ValueError:
                    pass

        # Fallback to family-based if nothing found
        if not treatments:
            treatments = self._suggest_treatments(entry)

        return treatments

    def _get_family_treatment_hints(self, family: ArchitectureFamily) -> list[str]:
        """Get treatment hints based on architecture family."""
        hints = {
            ArchitectureFamily.IAAS: ['rehost', 'replatform', 'retain'],
            ArchitectureFamily.PAAS: ['replatform', 'refactor'],
            ArchitectureFamily.CLOUD_NATIVE: ['refactor', 'rebuild'],
            ArchitectureFamily.DATA: ['replatform', 'refactor'],
            ArchitectureFamily.INTEGRATION: ['replatform', 'refactor', 'replace'],
            ArchitectureFamily.FOUNDATION: ['rebuild'],
            ArchitectureFamily.SPECIALIZED: ['replatform', 'refactor'],
        }
        return hints.get(family, ['replatform', 'refactor'])

    def _suggest_time_categories_enhanced(
        self,
        entry: ArchitectureEntry,
        content: str
    ) -> list[TimeCategory]:
        """Suggest TIME categories using content-based keyword scoring."""
        config = self._get_config()
        scores: dict[str, float] = {}

        for category, keywords in config.time_category_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[category] = score

        # Cross-reference with treatments
        if Treatment.REFACTOR in entry.supported_treatments:
            scores['invest'] = scores.get('invest', 0) + 1.5
            scores['migrate'] = scores.get('migrate', 0) + 1

        if Treatment.REBUILD in entry.supported_treatments:
            scores['invest'] = scores.get('invest', 0) + 2

        if Treatment.REHOST in entry.supported_treatments:
            scores['migrate'] = scores.get('migrate', 0) + 1.5
            scores['tolerate'] = scores.get('tolerate', 0) + 1

        if Treatment.REPLACE in entry.supported_treatments:
            scores['eliminate'] = scores.get('eliminate', 0) + 1.5

        if Treatment.RETAIN in entry.supported_treatments:
            scores['tolerate'] = scores.get('tolerate', 0) + 1.5

        # Complexity influence
        if entry.complexity.implementation == ComplexityLevel.HIGH:
            scores['invest'] = scores.get('invest', 0) + 1

        if entry.complexity.implementation == ComplexityLevel.LOW:
            scores['migrate'] = scores.get('migrate', 0) + 0.5

        # Select categories above threshold (configurable)
        threshold = config.time_category_threshold
        categories = []
        for c, score in scores.items():
            if score >= threshold:
                try:
                    categories.append(TimeCategory(c))
                except ValueError:
                    pass

        # Fallback
        if not categories:
            categories = self._suggest_time_categories(entry)

        return categories

    def _suggest_operating_model_enhanced(
        self,
        entry: ArchitectureEntry,
        content: str,
        doc: ParsedDocument
    ) -> OperatingModel:
        """Suggest operating model using content-based keyword scoring."""
        config = self._get_config()
        scores: dict[str, float] = {}

        for model, keywords in config.operating_model_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[model] = score

        # YML products boost
        for product in doc.arch_metadata.products:
            prod_lower = product.lower()
            if 'devops' in prod_lower or 'pipeline' in prod_lower:
                scores['devops'] = scores.get('devops', 0) + 2

        # Architecture family influence
        if entry.family == ArchitectureFamily.CLOUD_NATIVE:
            scores['devops'] = scores.get('devops', 0) + 2
            scores['sre'] = scores.get('sre', 0) + 1
        elif entry.family == ArchitectureFamily.IAAS:
            scores['traditional_it'] = scores.get('traditional_it', 0) + 1
        elif entry.family == ArchitectureFamily.PAAS:
            scores['transitional'] = scores.get('transitional', 0) + 1

        # Availability model influence
        if AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE in entry.availability_models:
            scores['sre'] = scores.get('sre', 0) + 2

        # Microservices influence
        if RuntimeModel.MICROSERVICES in entry.expected_runtime_models:
            scores['devops'] = scores.get('devops', 0) + 1.5

        # Select highest scoring model
        if scores:
            best = max(scores, key=scores.get)
            try:
                return OperatingModel(best)
            except ValueError:
                pass

        # Fallback to existing logic
        return self._suggest_operating_model(entry, content)

    def _suggest_security_level(
        self,
        content: str,
        doc: ParsedDocument
    ) -> SecurityLevel:
        """Suggest security level based on compliance mentions and security patterns."""
        config = self._get_config()
        scores: dict[str, float] = {}

        for level, keywords in config.security_level_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[level] = score

        # YML categories boost
        if 'security' in [c.lower() for c in doc.arch_metadata.azure_categories]:
            scores['enterprise'] = scores.get('enterprise', 0) + 1

        # Determine level with priority ordering (most restrictive wins)
        # Uses configurable threshold for regulated levels
        priority_order = ['highly_regulated', 'regulated', 'enterprise', 'basic']
        for level in priority_order:
            if scores.get(level, 0) >= config.security_score_threshold:
                try:
                    return SecurityLevel(level)
                except ValueError:
                    pass

        # Check for any enterprise-level indicators
        if scores.get('enterprise', 0) >= 1:
            return SecurityLevel.ENTERPRISE

        # Default to basic
        return SecurityLevel.BASIC

    def _suggest_cost_profile(
        self,
        content: str,
        entry: ArchitectureEntry
    ) -> CostProfile:
        """Suggest cost profile based on content and service patterns."""
        config = self._get_config()
        scores: dict[str, float] = {}

        for profile, keywords in config.cost_profile_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[profile] = score

        # Service-based inference
        services_lower = ' '.join(s.lower() for s in entry.azure_services_used)

        if 'premium' in services_lower:
            scores['scale_optimized'] = scores.get('scale_optimized', 0) + 1
            scores['innovation_first'] = scores.get('innovation_first', 0) + 1

        if any(s in services_lower for s in ['openai', 'cognitive', 'machine learning']):
            scores['innovation_first'] = scores.get('innovation_first', 0) + 2

        if any(s in services_lower for s in ['functions', 'container apps']):
            scores['cost_minimized'] = scores.get('cost_minimized', 0) + 1

        # High availability = scale optimized
        if AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE in entry.availability_models:
            scores['scale_optimized'] = scores.get('scale_optimized', 0) + 2

        # Complexity influence
        if entry.complexity.operations == ComplexityLevel.HIGH:
            scores['scale_optimized'] = scores.get('scale_optimized', 0) + 1

        if scores:
            best = max(scores, key=scores.get)
            try:
                return CostProfile(best)
            except ValueError:
                pass

        return CostProfile.BALANCED

    def _extract_not_suitable_for(
        self,
        content: str,
        doc: ParsedDocument
    ) -> list[ExclusionReason]:
        """Extract explicit exclusions from document content."""
        config = self._get_config()
        exclusions: set[ExclusionReason] = set()

        # Extract explicit statements using regex patterns
        for pattern in config.not_suitable_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                exclusions.update(self._map_exclusion_text_to_reasons(match))

        # Check sections for exclusion patterns
        considerations = doc.sections.get('considerations', '')
        alternatives = doc.sections.get('alternatives', '')
        combined = (considerations + ' ' + alternatives).lower()

        # Infer exclusions from content patterns
        if 'simple workload' in combined or 'basic application' in combined:
            exclusions.add(ExclusionReason.SIMPLE_WORKLOADS)

        if 'greenfield' in combined and 'only' in combined:
            exclusions.add(ExclusionReason.GREENFIELD_ONLY)

        if 'windows only' in content or 'windows-only' in content:
            exclusions.add(ExclusionReason.WINDOWS_ONLY)

        if 'linux only' in content or 'linux-only' in content:
            exclusions.add(ExclusionReason.LINUX_ONLY)

        # Check for skill requirements
        if 'kubernetes experience' in content or 'container expertise' in content:
            exclusions.add(ExclusionReason.LOW_MATURITY_TEAMS)

        return list(exclusions)

    def _map_exclusion_text_to_reasons(self, text: str) -> list[ExclusionReason]:
        """Map extracted exclusion text to ExclusionReason enum values."""
        text_lower = text.lower()
        reasons = []

        mapping = {
            'rehost': ExclusionReason.REHOST_ONLY,
            'lift and shift': ExclusionReason.REHOST_ONLY,
            'vm only': ExclusionReason.VM_ONLY_APPS,
            'virtual machine only': ExclusionReason.VM_ONLY_APPS,
            'low maturity': ExclusionReason.LOW_MATURITY_TEAMS,
            'inexperienced team': ExclusionReason.LOW_MATURITY_TEAMS,
            'regulated': ExclusionReason.REGULATED_WORKLOADS,
            'compliance': ExclusionReason.REGULATED_WORKLOADS,
            'budget': ExclusionReason.LOW_BUDGET,
            'cost constrain': ExclusionReason.LOW_BUDGET,
            'skill': ExclusionReason.SKILL_CONSTRAINED,
            'simple': ExclusionReason.SIMPLE_WORKLOADS,
            'basic workload': ExclusionReason.SIMPLE_WORKLOADS,
            'greenfield': ExclusionReason.GREENFIELD_ONLY,
            'legacy': ExclusionReason.LEGACY_SYSTEMS,
        }

        for keyword, reason in mapping.items():
            if keyword in text_lower:
                reasons.append(reason)

        return reasons
