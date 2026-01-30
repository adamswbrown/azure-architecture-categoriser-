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

# Mapping from ms.custom arb-* values to architecture families
ARB_TO_FAMILY = {
    'arb-web': ArchitectureFamily.PAAS,
    'arb-data': ArchitectureFamily.DATA,
    'arb-containers': ArchitectureFamily.CLOUD_NATIVE,
    'arb-hybrid': ArchitectureFamily.IAAS,
    'arb-aiml': ArchitectureFamily.DATA,
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
        domain_from_yml = self._suggest_workload_domain_from_yml(doc)
        if domain_from_yml:
            entry.workload_domain = domain_from_yml
            entry.workload_domain_confidence = ClassificationMeta(
                confidence=ExtractionConfidence.CURATED,
                source="yml_metadata"
            )
        else:
            domain = self._suggest_workload_domain(content)
            if domain:
                entry.workload_domain = domain
                entry.workload_domain_confidence = ClassificationMeta(
                    confidence=ExtractionConfidence.AI_SUGGESTED,
                    source="content_analysis"
                )

        # Combine services for classification (core + supporting)
        all_services = entry.core_services + entry.supporting_services

        # Suggest architecture family
        family, family_source = self._suggest_family(content, all_services, doc)
        if family:
            entry.family = family
            # Use CURATED confidence when family comes from yml_metadata (arb-* values)
            confidence = (ExtractionConfidence.CURATED
                         if family_source == "yml_metadata"
                         else ExtractionConfidence.AI_SUGGESTED)
            entry.family_confidence = ClassificationMeta(
                confidence=confidence,
                source=family_source
            )

        # Suggest runtime models (improved - never returns unknown)
        runtime_models, runtime_source = self._suggest_runtime_models(
            content, entry.core_services, family
        )
        entry.expected_runtime_models = runtime_models
        entry.runtime_models_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.AI_SUGGESTED,
            source=runtime_source
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
        entry.operating_model_required, op_source = self._suggest_operating_model_enhanced(
            entry, content, doc
        )
        entry.operating_model_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.AI_SUGGESTED,
            source=op_source
        )

        # Enhanced: Suggest treatments using content-based keyword scoring
        entry.supported_treatments, treat_source = self._suggest_treatments_enhanced(
            entry, content, doc
        )
        entry.treatments_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.AI_SUGGESTED,
            source=treat_source
        )

        # Enhanced: Suggest time categories using content-based scoring
        entry.supported_time_categories, time_source = self._suggest_time_categories_enhanced(
            entry, content
        )
        entry.time_categories_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.AI_SUGGESTED,
            source=time_source
        )

        # New: Suggest security level based on compliance mentions
        entry.security_level, sec_source = self._suggest_security_level(content, doc)
        entry.security_level_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.AI_SUGGESTED,
            source=sec_source
        )

        # New: Suggest cost profile based on content and services
        entry.cost_profile, cost_source = self._suggest_cost_profile(content, entry)
        entry.cost_profile_confidence = ClassificationMeta(
            confidence=ExtractionConfidence.AI_SUGGESTED,
            source=cost_source
        )

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
    ) -> tuple[Optional[ArchitectureFamily], str]:
        """Suggest architecture family based on content and services.

        Returns:
            Tuple of (family, source) where source indicates the primary data source.
        """
        # Priority 1: Check ms.custom arb-* values from yml metadata (most reliable)
        for custom_value in doc.arch_metadata.ms_custom:
            custom_lower = custom_value.lower().strip()
            if custom_lower in ARB_TO_FAMILY:
                return ARB_TO_FAMILY[custom_lower], "yml_metadata"

        config = self._get_config()
        scores: dict[str, int] = {}
        source = "content_analysis"

        # Score based on keywords
        for family, keywords in config.family_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[family] = score

        # Boost based on Azure services
        service_lower = ' '.join(s.lower() for s in services)

        if 'kubernetes' in service_lower or 'container' in service_lower:
            scores['cloud_native'] = scores.get('cloud_native', 0) + 3
            source = "service_inference"

        if 'virtual machine' in service_lower:
            scores['iaas'] = scores.get('iaas', 0) + 2
            source = "service_inference"

        if 'app service' in service_lower or 'functions' in service_lower:
            scores['paas'] = scores.get('paas', 0) + 2
            source = "service_inference"

        if 'synapse' in service_lower or 'data factory' in service_lower:
            scores['data'] = scores.get('data', 0) + 2
            source = "service_inference"

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
                return ArchitectureFamily(best), source
            except ValueError:
                pass
        return None, "none"

    def _suggest_runtime_models(
        self,
        content: str,
        core_services: list[str],
        family: ArchitectureFamily | None = None
    ) -> tuple[list[RuntimeModel], str]:
        """Suggest runtime models with aggressive best-effort classification.

        Never returns 'unknown' - always makes a best-effort guess based on
        services, family, and content patterns.

        Returns:
            Tuple of (runtime_models, inference_source)
        """
        config = self._get_config()
        scores: dict[str, float] = {}
        inference_source = "content_analysis"

        # 1. Score based on content keywords (most reliable)
        for model, keywords in config.runtime_keywords.items():
            score = sum(1.5 for kw in keywords if kw in content)
            if score > 0:
                scores[model] = score

        # 2. Strong inference from core Azure services
        services_lower = ' '.join(s.lower() for s in core_services)

        # Kubernetes/Containers → microservices
        if any(s in services_lower for s in ['kubernetes', 'aks', 'container apps']):
            scores['microservices'] = scores.get('microservices', 0) + 3
            inference_source = "service_inference"

        # Functions, Event Grid, Event Hub → event_driven
        if any(s in services_lower for s in ['functions', 'event grid', 'event hub', 'service bus']):
            scores['event_driven'] = scores.get('event_driven', 0) + 2.5
            inference_source = "service_inference"

        # API Management → api
        if 'api management' in services_lower:
            scores['api'] = scores.get('api', 0) + 2.5
            inference_source = "service_inference"

        # App Service (without containers) → n_tier or api
        if 'app service' in services_lower and 'container' not in services_lower:
            scores['n_tier'] = scores.get('n_tier', 0) + 1.5
            scores['api'] = scores.get('api', 0) + 1

        # Batch, Data Factory → batch
        if any(s in services_lower for s in ['batch', 'data factory', 'synapse']):
            scores['batch'] = scores.get('batch', 0) + 2

        # Virtual Machines alone → monolith or n_tier
        if 'virtual machine' in services_lower:
            scores['monolith'] = scores.get('monolith', 0) + 1
            scores['n_tier'] = scores.get('n_tier', 0) + 1.5

        # Logic Apps → event_driven or api
        if 'logic app' in services_lower:
            scores['event_driven'] = scores.get('event_driven', 0) + 1
            scores['api'] = scores.get('api', 0) + 1

        # 3. Family-based inference (fallback boost)
        if family:
            if family == ArchitectureFamily.CLOUD_NATIVE:
                scores['microservices'] = scores.get('microservices', 0) + 2
            elif family == ArchitectureFamily.IAAS:
                scores['n_tier'] = scores.get('n_tier', 0) + 1.5
                scores['monolith'] = scores.get('monolith', 0) + 1
            elif family == ArchitectureFamily.PAAS:
                scores['n_tier'] = scores.get('n_tier', 0) + 1
                scores['api'] = scores.get('api', 0) + 1
            elif family == ArchitectureFamily.DATA:
                scores['batch'] = scores.get('batch', 0) + 1.5
            elif family == ArchitectureFamily.INTEGRATION:
                scores['event_driven'] = scores.get('event_driven', 0) + 1
                scores['api'] = scores.get('api', 0) + 1.5

        # 4. Content pattern boosts
        if 'rest api' in content or 'restful' in content or 'web api' in content:
            scores['api'] = scores.get('api', 0) + 1.5

        if 'frontend' in content and 'backend' in content:
            scores['n_tier'] = scores.get('n_tier', 0) + 1

        if 'cqrs' in content or 'saga' in content or 'choreography' in content:
            scores['microservices'] = scores.get('microservices', 0) + 1.5

        if 'etl' in content or 'pipeline' in content and 'data' in content:
            scores['batch'] = scores.get('batch', 0) + 1

        # 5. Select best matches (never return unknown)
        if scores:
            # Sort by score descending
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            models = []

            # Take top scoring models above threshold
            threshold = 1.0
            for model, score in sorted_scores:
                if score >= threshold and len(models) < 2:
                    try:
                        models.append(RuntimeModel(model))
                    except ValueError:
                        pass

            if models:
                # If more than 2 distinct patterns, it's mixed
                if len(sorted_scores) > 3 and sorted_scores[2][1] >= threshold:
                    return [RuntimeModel.MIXED], inference_source
                return models, inference_source

        # 6. Last resort: infer from generic patterns (never unknown)
        # Default based on what's most common in Azure Architecture Center
        if 'web' in content or 'website' in content or 'portal' in content:
            return [RuntimeModel.N_TIER], "heuristic_fallback"

        if 'data' in content or 'analytics' in content:
            return [RuntimeModel.BATCH], "heuristic_fallback"

        # Ultimate fallback: n_tier is the most common pattern
        return [RuntimeModel.N_TIER], "heuristic_fallback"

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

        # More services = more complexity (count core + supporting)
        service_count = len(entry.core_services) + len(entry.supporting_services)
        if service_count > 10:
            impl_score += 2
            ops_score += 2
        elif service_count > 5:
            impl_score += 1
            ops_score += 1

        # Core service count matters more for implementation
        if len(entry.core_services) > 5:
            impl_score += 1

        # Supporting service count indicates operational maturity
        if len(entry.supporting_services) > 3:
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
    ) -> tuple[list[Treatment], str]:
        """Suggest treatments using content-based keyword scoring.

        Returns:
            Tuple of (treatments, source) where source indicates the primary data source.
        """
        config = self._get_config()
        scores: dict[str, float] = {}
        source = "content_analysis"

        # Score based on content keywords
        for treatment, keywords in config.treatment_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[treatment] = score

        # Boost based on Azure services (using configurable boost values)
        # Use core services primarily - they represent the pattern
        all_services = entry.core_services + entry.supporting_services
        services_lower = ' '.join(s.lower() for s in all_services)

        # VM presence suggests rehost capability
        if 'virtual machine' in services_lower:
            scores['rehost'] = scores.get('rehost', 0) + config.vm_rehost_boost
            scores['retain'] = scores.get('retain', 0) + 1
            source = "service_inference"

        # AKS/Containers suggest refactor
        if any(s in services_lower for s in ['kubernetes', 'container apps', 'container instance']):
            scores['refactor'] = scores.get('refactor', 0) + config.container_refactor_boost
            scores['rebuild'] = scores.get('rebuild', 0) + 1
            source = "service_inference"

        # Managed services suggest replatform
        if any(s in services_lower for s in ['managed instance', 'sql database', 'cosmos']):
            scores['replatform'] = scores.get('replatform', 0) + config.managed_replatform_boost
            source = "service_inference"

        # ExpressRoute/Arc suggest retain/hybrid
        if any(s in services_lower for s in ['expressroute', 'arc', 'vpn gateway']):
            scores['retain'] = scores.get('retain', 0) + config.hybrid_retain_boost
            source = "service_inference"

        # App Service, Functions suggest replatform
        if any(s in services_lower for s in ['app service', 'functions']):
            scores['replatform'] = scores.get('replatform', 0) + 1.5
            source = "service_inference"

        # Boost from YML metadata (ms.collection values)
        ms_collections = doc.arch_metadata.ms_collection
        collections_lower = [c.lower() for c in ms_collections]

        if 'migration' in collections_lower:
            scores['rehost'] = scores.get('rehost', 0) + 2
            scores['replatform'] = scores.get('replatform', 0) + 2
            source = "yml_metadata"

        if 'onprem-to-azure' in collections_lower:
            scores['rehost'] = scores.get('rehost', 0) + 1.5
            scores['replatform'] = scores.get('replatform', 0) + 1.5
            source = "yml_metadata"

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
            source = "family_heuristic"

        return treatments, source

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
    ) -> tuple[list[TimeCategory], str]:
        """Suggest TIME categories using content-based keyword scoring.

        Returns:
            Tuple of (categories, source) where source indicates the primary data source.
        """
        config = self._get_config()
        scores: dict[str, float] = {}
        source = "content_analysis"

        for category, keywords in config.time_category_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[category] = score

        # Cross-reference with treatments
        if Treatment.REFACTOR in entry.supported_treatments:
            scores['invest'] = scores.get('invest', 0) + 1.5
            scores['migrate'] = scores.get('migrate', 0) + 1
            source = "treatment_inference"

        if Treatment.REBUILD in entry.supported_treatments:
            scores['invest'] = scores.get('invest', 0) + 2
            source = "treatment_inference"

        if Treatment.REHOST in entry.supported_treatments:
            scores['migrate'] = scores.get('migrate', 0) + 1.5
            scores['tolerate'] = scores.get('tolerate', 0) + 1
            source = "treatment_inference"

        if Treatment.REPLACE in entry.supported_treatments:
            scores['eliminate'] = scores.get('eliminate', 0) + 1.5
            source = "treatment_inference"

        if Treatment.RETAIN in entry.supported_treatments:
            scores['tolerate'] = scores.get('tolerate', 0) + 1.5
            source = "treatment_inference"

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
            source = "complexity_heuristic"

        return categories, source

    def _suggest_operating_model_enhanced(
        self,
        entry: ArchitectureEntry,
        content: str,
        doc: ParsedDocument
    ) -> tuple[OperatingModel, str]:
        """Suggest operating model using content-based keyword scoring.

        Returns:
            Tuple of (operating_model, source) where source indicates the primary data source.
        """
        config = self._get_config()
        scores: dict[str, float] = {}
        source = "content_analysis"

        for model, keywords in config.operating_model_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[model] = score

        # YML products boost
        for product in doc.arch_metadata.products:
            prod_lower = product.lower()
            if 'devops' in prod_lower or 'pipeline' in prod_lower:
                scores['devops'] = scores.get('devops', 0) + 2
                source = "yml_metadata"

        # Architecture family influence
        if entry.family == ArchitectureFamily.CLOUD_NATIVE:
            scores['devops'] = scores.get('devops', 0) + 2
            scores['sre'] = scores.get('sre', 0) + 1
            if source == "content_analysis":
                source = "family_inference"
        elif entry.family == ArchitectureFamily.IAAS:
            scores['traditional_it'] = scores.get('traditional_it', 0) + 1
            if source == "content_analysis":
                source = "family_inference"
        elif entry.family == ArchitectureFamily.PAAS:
            scores['transitional'] = scores.get('transitional', 0) + 1
            if source == "content_analysis":
                source = "family_inference"

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
                return OperatingModel(best), source
            except ValueError:
                pass

        # Fallback to existing logic
        return self._suggest_operating_model(entry, content), "family_heuristic"

    def _suggest_security_level(
        self,
        content: str,
        doc: ParsedDocument
    ) -> tuple[SecurityLevel, str]:
        """Suggest security level based on compliance mentions and security patterns.

        Returns:
            Tuple of (security_level, source) where source indicates the primary data source.
        """
        config = self._get_config()
        scores: dict[str, float] = {}
        source = "content_analysis"

        for level, keywords in config.security_level_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[level] = score

        # YML categories boost
        if 'security' in [c.lower() for c in doc.arch_metadata.azure_categories]:
            scores['enterprise'] = scores.get('enterprise', 0) + 1
            source = "yml_metadata"

        # Determine level with priority ordering (most restrictive wins)
        # Uses configurable threshold for regulated levels
        priority_order = ['highly_regulated', 'regulated', 'enterprise', 'basic']
        for level in priority_order:
            if scores.get(level, 0) >= config.security_score_threshold:
                try:
                    return SecurityLevel(level), source
                except ValueError:
                    pass

        # Check for any enterprise-level indicators
        if scores.get('enterprise', 0) >= 1:
            return SecurityLevel.ENTERPRISE, source

        # Default to basic
        return SecurityLevel.BASIC, "default"

    def _suggest_cost_profile(
        self,
        content: str,
        entry: ArchitectureEntry
    ) -> tuple[CostProfile, str]:
        """Suggest cost profile based on content and service patterns.

        Returns:
            Tuple of (cost_profile, source) where source indicates the primary data source.
        """
        config = self._get_config()
        scores: dict[str, float] = {}
        source = "content_analysis"

        for profile, keywords in config.cost_profile_keywords.items():
            score = sum(1 for kw in keywords if kw in content)
            if score > 0:
                scores[profile] = score

        # Service-based inference (using all services)
        all_services = entry.core_services + entry.supporting_services
        services_lower = ' '.join(s.lower() for s in all_services)

        if 'premium' in services_lower:
            scores['scale_optimized'] = scores.get('scale_optimized', 0) + 1
            scores['innovation_first'] = scores.get('innovation_first', 0) + 1
            source = "service_inference"

        if any(s in services_lower for s in ['openai', 'cognitive', 'machine learning']):
            scores['innovation_first'] = scores.get('innovation_first', 0) + 2
            source = "service_inference"

        if any(s in services_lower for s in ['functions', 'container apps']):
            scores['cost_minimized'] = scores.get('cost_minimized', 0) + 1
            source = "service_inference"

        # High availability = scale optimized
        if AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE in entry.availability_models:
            scores['scale_optimized'] = scores.get('scale_optimized', 0) + 2

        # Complexity influence
        if entry.complexity.operations == ComplexityLevel.HIGH:
            scores['scale_optimized'] = scores.get('scale_optimized', 0) + 1

        if scores:
            best = max(scores, key=scores.get)
            try:
                return CostProfile(best), source
            except ValueError:
                pass

        return CostProfile.BALANCED, "default"

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
