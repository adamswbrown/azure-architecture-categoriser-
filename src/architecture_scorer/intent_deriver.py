"""Intent Deriver - Phase 2 of the Scoring Engine.

Derives architectural intent from normalized application context.
Produces signals with confidence levels for downstream scoring.
"""

from typing import Optional

from catalog_builder.schema import (
    AvailabilityModel,
    CostProfile,
    OperatingModel,
    RuntimeModel,
    SecurityLevel,
    TimeCategory,
    Treatment,
)

from .schema import (
    ApplicationContext,
    BusinessCriticality,
    CloudNativeFeasibility,
    CompatibilityStatus,
    DerivedIntent,
    DerivedSignal,
    ModernizationDepth,
    NetworkExposure,
    SignalConfidence,
)


class IntentDeriver:
    """Derives architectural intent from application context.

    Key principle: App Mod results override inference when they conflict.
    """

    def derive(self, context: ApplicationContext) -> DerivedIntent:
        """Derive all architectural intent signals from context."""
        return DerivedIntent(
            treatment=self._derive_treatment(context),
            time_category=self._derive_time_category(context),
            likely_runtime_model=self._derive_runtime_model(context),
            modernization_depth_feasible=self._derive_modernization_depth(context),
            cloud_native_feasibility=self._derive_cloud_native_feasibility(context),
            operational_maturity_estimate=self._derive_operational_maturity(context),
            availability_requirement=self._derive_availability_requirement(context),
            security_requirement=self._derive_security_requirement(context),
            cost_posture=self._derive_cost_posture(context),
            network_exposure=self._derive_network_exposure(context),
        )

    def _derive_treatment(self, context: ApplicationContext) -> DerivedSignal:
        """Derive the migration treatment."""
        app = context.app_overview

        # Declared treatment is authoritative
        if app.declared_treatment:
            return DerivedSignal(
                value=app.declared_treatment,
                confidence=SignalConfidence.HIGH,
                source="declared_treatment",
                reasoning=f"Explicitly declared treatment: {app.declared_treatment.value}"
            )

        # Infer from App Mod results
        if context.app_mod_results:
            mod = context.app_mod_results

            # Check if modernization is blocked
            if mod.modernization_feasible is False:
                return DerivedSignal(
                    value=Treatment.TOLERATE,
                    confidence=SignalConfidence.HIGH,
                    source="app_mod_results",
                    reasoning="App Mod indicates modernization is not feasible"
                )

            # Check for container readiness
            if mod.container_ready:
                # Container-ready suggests refactor/rebuild potential
                if "Azure Kubernetes Service" in mod.recommended_targets:
                    return DerivedSignal(
                        value=Treatment.REFACTOR,
                        confidence=SignalConfidence.MEDIUM,
                        source="app_mod_results",
                        reasoning="Container-ready with AKS recommended"
                    )

            # Check recommended targets
            if mod.recommended_targets:
                if any("App Service" in t for t in mod.recommended_targets):
                    return DerivedSignal(
                        value=Treatment.REPLATFORM,
                        confidence=SignalConfidence.MEDIUM,
                        source="app_mod_results",
                        reasoning=f"App Mod recommends: {', '.join(mod.recommended_targets)}"
                    )

        # Infer from server migration strategy
        if context.server_summary.servers:
            strategies = [
                s.migration_strategy
                for s in context.server_summary.servers
                if s.migration_strategy
            ]
            if strategies:
                most_common = max(set(strategies), key=strategies.count)
                if most_common.lower() in ["rehost", "replatform", "refactor"]:
                    treatment = Treatment(most_common.lower())
                    return DerivedSignal(
                        value=treatment,
                        confidence=SignalConfidence.MEDIUM,
                        source="server_migration_strategy",
                        reasoning=f"Server migration strategy: {most_common}"
                    )

        # Default fallback
        return DerivedSignal(
            value=Treatment.REHOST,
            confidence=SignalConfidence.LOW,
            source="default",
            reasoning="No explicit treatment signal; defaulting to rehost"
        )

    def _derive_time_category(self, context: ApplicationContext) -> DerivedSignal:
        """Derive TIME category from treatment and other signals."""
        app = context.app_overview

        # Declared TIME category is authoritative
        if app.declared_time_category:
            return DerivedSignal(
                value=app.declared_time_category,
                confidence=SignalConfidence.HIGH,
                source="declared_time_category",
                reasoning=f"Explicitly declared TIME category: {app.declared_time_category.value}"
            )

        # Infer from treatment
        treatment = self._derive_treatment(context).value
        treatment_to_time = {
            Treatment.RETIRE: TimeCategory.ELIMINATE,
            Treatment.TOLERATE: TimeCategory.TOLERATE,
            Treatment.REHOST: TimeCategory.MIGRATE,
            Treatment.REPLATFORM: TimeCategory.MIGRATE,
            Treatment.REFACTOR: TimeCategory.INVEST,
            Treatment.REPLACE: TimeCategory.ELIMINATE,
            Treatment.REBUILD: TimeCategory.INVEST,
            Treatment.RETAIN: TimeCategory.TOLERATE,
        }

        time_category = treatment_to_time.get(treatment, TimeCategory.MIGRATE)
        return DerivedSignal(
            value=time_category,
            confidence=SignalConfidence.MEDIUM,
            source="treatment_inference",
            reasoning=f"Inferred from treatment: {treatment.value} → {time_category.value}"
        )

    def _derive_runtime_model(self, context: ApplicationContext) -> DerivedSignal:
        """Derive likely runtime model from technology and architecture signals."""
        tech = context.detected_technology
        app = context.app_overview

        # Check app type hints
        app_type_lower = (app.app_type or "").lower()

        # Microservices indicators
        if context.app_mod_results:
            mod = context.app_mod_results
            # Multiple Spring Boot apps suggest microservices
            if hasattr(mod, 'findings'):
                services_count = getattr(mod, '_services_scanned', 1)
                if mod.container_ready and services_count > 3:
                    return DerivedSignal(
                        value=RuntimeModel.MICROSERVICES,
                        confidence=SignalConfidence.MEDIUM,
                        source="app_mod_results",
                        reasoning="Multiple services detected, container-ready"
                    )

        # Check for messaging (suggests event-driven or microservices)
        if tech.messaging_present:
            if "distributed" in app_type_lower:
                return DerivedSignal(
                    value=RuntimeModel.MICROSERVICES,
                    confidence=SignalConfidence.MEDIUM,
                    source="technology_detection",
                    reasoning="Distributed application with messaging"
                )
            return DerivedSignal(
                value=RuntimeModel.EVENT_DRIVEN,
                confidence=SignalConfidence.MEDIUM,
                source="technology_detection",
                reasoning="Message queue detected suggests event-driven"
            )

        # Check server count and structure
        server_count = context.server_summary.server_count

        if server_count == 1:
            # Single server could be monolith or simple n-tier
            if tech.database_present:
                return DerivedSignal(
                    value=RuntimeModel.N_TIER,
                    confidence=SignalConfidence.MEDIUM,
                    source="server_structure",
                    reasoning="Single server with database suggests n-tier"
                )
            return DerivedSignal(
                value=RuntimeModel.MONOLITH,
                confidence=SignalConfidence.LOW,
                source="server_structure",
                reasoning="Single server suggests monolith"
            )

        elif server_count <= 3:
            return DerivedSignal(
                value=RuntimeModel.N_TIER,
                confidence=SignalConfidence.MEDIUM,
                source="server_structure",
                reasoning=f"{server_count} servers suggests n-tier architecture"
            )

        # Multiple servers might be n-tier or microservices
        if "api" in app_type_lower:
            return DerivedSignal(
                value=RuntimeModel.API,
                confidence=SignalConfidence.MEDIUM,
                source="app_type",
                reasoning="API application type detected"
            )

        # Default for complex deployments
        return DerivedSignal(
            value=RuntimeModel.N_TIER,
            confidence=SignalConfidence.LOW,
            source="default",
            reasoning="Multiple servers with unknown structure"
        )

    def _derive_modernization_depth(self, context: ApplicationContext) -> DerivedSignal:
        """Derive maximum feasible modernization depth."""
        # App Mod results are authoritative
        if context.app_mod_results:
            mod = context.app_mod_results

            # Blocked from modernization
            if mod.modernization_feasible is False or mod.explicit_blockers:
                return DerivedSignal(
                    value=ModernizationDepth.TOLERATE,
                    confidence=SignalConfidence.HIGH,
                    source="app_mod_results",
                    reasoning=f"Blocked: {', '.join(mod.explicit_blockers) if mod.explicit_blockers else 'modernization not feasible'}"
                )

            # Check highest supported level
            if mod.container_ready:
                # Container-ready means refactor/rebuild is possible
                for pc in mod.platform_compatibility:
                    if "kubernetes" in pc.platform.lower():
                        if pc.status == CompatibilityStatus.FULLY_SUPPORTED:
                            return DerivedSignal(
                                value=ModernizationDepth.REFACTOR,
                                confidence=SignalConfidence.HIGH,
                                source="app_mod_results",
                                reasoning="Fully supported on Kubernetes"
                            )

            # Check platform compatibility
            max_depth = ModernizationDepth.REHOST
            for pc in mod.platform_compatibility:
                if pc.status.is_supported():
                    if "container" in pc.platform.lower() or "kubernetes" in pc.platform.lower():
                        max_depth = ModernizationDepth.REFACTOR
                    elif "app service" in pc.platform.lower():
                        if max_depth == ModernizationDepth.REHOST:
                            max_depth = ModernizationDepth.REPLATFORM

            return DerivedSignal(
                value=max_depth,
                confidence=SignalConfidence.MEDIUM,
                source="app_mod_results",
                reasoning=f"Based on platform compatibility analysis"
            )

        # Infer from technology
        tech = context.detected_technology

        # Legacy technology limits modernization
        if "Access" in tech.database_types:
            return DerivedSignal(
                value=ModernizationDepth.TOLERATE,
                confidence=SignalConfidence.MEDIUM,
                source="technology_detection",
                reasoning="Microsoft Access detected - limited modernization options"
            )

        # Modern frameworks suggest higher potential
        if tech.primary_runtime in ["Java", "Node.js", "Python", "Go"]:
            return DerivedSignal(
                value=ModernizationDepth.REFACTOR,
                confidence=SignalConfidence.LOW,
                source="technology_detection",
                reasoning=f"{tech.primary_runtime} typically supports containerization"
            )

        if tech.primary_runtime == ".NET":
            # Check if Framework or Core
            if "Framework" in " ".join(tech.technologies):
                return DerivedSignal(
                    value=ModernizationDepth.REPLATFORM,
                    confidence=SignalConfidence.LOW,
                    source="technology_detection",
                    reasoning=".NET Framework may have containerization limitations"
                )
            return DerivedSignal(
                value=ModernizationDepth.REFACTOR,
                confidence=SignalConfidence.LOW,
                source="technology_detection",
                reasoning=".NET typically supports modernization"
            )

        # Default
        return DerivedSignal(
            value=ModernizationDepth.REHOST,
            confidence=SignalConfidence.LOW,
            source="default",
            reasoning="Unknown technology stack; conservative estimate"
        )

    def _derive_cloud_native_feasibility(self, context: ApplicationContext) -> DerivedSignal:
        """Derive cloud-native transformation feasibility."""
        # Check App Mod container readiness
        if context.app_mod_results:
            mod = context.app_mod_results

            if mod.container_ready:
                # Check for blockers even if container-ready
                if mod.explicit_blockers:
                    return DerivedSignal(
                        value=CloudNativeFeasibility.MEDIUM,
                        confidence=SignalConfidence.HIGH,
                        source="app_mod_results",
                        reasoning=f"Container-ready but with blockers: {len(mod.explicit_blockers)}"
                    )
                return DerivedSignal(
                    value=CloudNativeFeasibility.HIGH,
                    confidence=SignalConfidence.HIGH,
                    source="app_mod_results",
                    reasoning="App Mod confirms container-ready"
                )

            if mod.container_ready is False:
                return DerivedSignal(
                    value=CloudNativeFeasibility.LOW,
                    confidence=SignalConfidence.HIGH,
                    source="app_mod_results",
                    reasoning="App Mod indicates not container-ready"
                )

        # Infer from technology
        tech = context.detected_technology

        # Modern cloud-native friendly stacks
        cloud_native_stacks = ["Java", "Node.js", "Python", "Go"]
        if tech.primary_runtime in cloud_native_stacks:
            if tech.messaging_present:
                return DerivedSignal(
                    value=CloudNativeFeasibility.HIGH,
                    confidence=SignalConfidence.MEDIUM,
                    source="technology_detection",
                    reasoning=f"{tech.primary_runtime} with messaging is cloud-native friendly"
                )
            return DerivedSignal(
                value=CloudNativeFeasibility.MEDIUM,
                confidence=SignalConfidence.MEDIUM,
                source="technology_detection",
                reasoning=f"{tech.primary_runtime} typically supports cloud-native"
            )

        # .NET has varied support
        if tech.primary_runtime == ".NET":
            if "Framework" in " ".join(tech.technologies):
                return DerivedSignal(
                    value=CloudNativeFeasibility.LOW,
                    confidence=SignalConfidence.MEDIUM,
                    source="technology_detection",
                    reasoning=".NET Framework has limited container support"
                )
            return DerivedSignal(
                value=CloudNativeFeasibility.MEDIUM,
                confidence=SignalConfidence.MEDIUM,
                source="technology_detection",
                reasoning=".NET Core/.NET 5+ supports containers"
            )

        # Default conservative
        return DerivedSignal(
            value=CloudNativeFeasibility.LOW,
            confidence=SignalConfidence.LOW,
            source="default",
            reasoning="Unknown stack; conservative cloud-native estimate"
        )

    def _derive_operational_maturity(self, context: ApplicationContext) -> DerivedSignal:
        """Derive operational maturity estimate."""
        tech = context.detected_technology
        app = context.app_overview
        app_mod = context.app_mod_results

        # Check for DevOps indicators
        if tech.has_ci_cd:
            return DerivedSignal(
                value=OperatingModel.DEVOPS,
                confidence=SignalConfidence.HIGH,
                source="technology_detection",
                reasoning="CI/CD detected indicates DevOps maturity"
            )

        # Containerized apps typically require DevOps
        if tech.containerized:
            return DerivedSignal(
                value=OperatingModel.DEVOPS,
                confidence=SignalConfidence.MEDIUM,
                source="technology_detection",
                reasoning="Containerized workload suggests DevOps practices"
            )

        # App Mod container_ready is a strong DevOps indicator
        # Container-ready apps require CI/CD, image registries, orchestration
        if app_mod and app_mod.container_ready:
            return DerivedSignal(
                value=OperatingModel.DEVOPS,
                confidence=SignalConfidence.MEDIUM,
                source="app_mod_results",
                reasoning="Container-ready application indicates DevOps maturity"
            )

        # Full AKS support in App Mod suggests DevOps capability
        if app_mod:
            for pc in app_mod.platform_compatibility:
                if "kubernetes" in pc.platform.lower() or "aks" in pc.platform.lower():
                    if pc.status == CompatibilityStatus.FULLY_SUPPORTED:
                        return DerivedSignal(
                            value=OperatingModel.DEVOPS,
                            confidence=SignalConfidence.MEDIUM,
                            source="app_mod_results",
                            reasoning="Full Kubernetes support indicates DevOps readiness"
                        )

        # Modern frameworks often correlate with DevOps
        if tech.primary_runtime in ["Go", "Node.js"] or tech.messaging_present:
            return DerivedSignal(
                value=OperatingModel.TRANSITIONAL,
                confidence=SignalConfidence.LOW,
                source="technology_detection",
                reasoning="Modern stack suggests at least transitional maturity"
            )

        # Replatform/refactor treatments imply modernization intent
        # Teams choosing these paths are moving toward more modern operations
        treatment = app.declared_treatment
        if treatment and treatment in [Treatment.REPLATFORM, Treatment.REFACTOR, Treatment.REBUILD]:
            return DerivedSignal(
                value=OperatingModel.TRANSITIONAL,
                confidence=SignalConfidence.LOW,
                source="treatment_inference",
                reasoning=f"{treatment.value.title()} treatment implies modernization and operational maturity growth"
            )

        # Business criticality might indicate maturity
        if app.business_criticality == BusinessCriticality.MISSION_CRITICAL:
            return DerivedSignal(
                value=OperatingModel.TRANSITIONAL,
                confidence=SignalConfidence.LOW,
                source="business_criticality",
                reasoning="Mission-critical apps often have better operations"
            )

        # Default to traditional IT
        return DerivedSignal(
            value=OperatingModel.TRADITIONAL_IT,
            confidence=SignalConfidence.LOW,
            source="default",
            reasoning="No DevOps indicators detected"
        )

    def _derive_availability_requirement(self, context: ApplicationContext) -> DerivedSignal:
        """Derive availability requirements from business criticality."""
        app = context.app_overview

        # Explicit requirement overrides
        if app.availability_requirement:
            return DerivedSignal(
                value=app.availability_requirement,
                confidence=SignalConfidence.HIGH,
                source="explicit_requirement",
                reasoning="Explicitly specified availability requirement"
            )

        # Infer from business criticality
        criticality_to_availability = {
            BusinessCriticality.LOW: AvailabilityModel.SINGLE_REGION,
            BusinessCriticality.MEDIUM: AvailabilityModel.ZONE_REDUNDANT,
            BusinessCriticality.HIGH: AvailabilityModel.ZONE_REDUNDANT,
            BusinessCriticality.MISSION_CRITICAL: AvailabilityModel.MULTI_REGION_ACTIVE_PASSIVE,
        }

        availability = criticality_to_availability.get(
            app.business_criticality,
            AvailabilityModel.SINGLE_REGION
        )

        return DerivedSignal(
            value=availability,
            confidence=SignalConfidence.MEDIUM,
            source="business_criticality",
            reasoning=f"Inferred from {app.business_criticality.value} criticality"
        )

    def _derive_security_requirement(self, context: ApplicationContext) -> DerivedSignal:
        """Derive security requirements from compliance and criticality."""
        app = context.app_overview

        # Check for compliance requirements
        if app.compliance_requirements:
            compliance_lower = [c.lower() for c in app.compliance_requirements]

            # Highly regulated
            if any(c in compliance_lower for c in ["hipaa", "pci-dss", "pci dss", "fedramp", "itar"]):
                return DerivedSignal(
                    value=SecurityLevel.HIGHLY_REGULATED,
                    confidence=SignalConfidence.HIGH,
                    source="compliance_requirements",
                    reasoning=f"Compliance: {', '.join(app.compliance_requirements)}"
                )

            # Regulated
            if any(c in compliance_lower for c in ["soc2", "soc 2", "iso27001", "iso 27001", "gdpr"]):
                return DerivedSignal(
                    value=SecurityLevel.REGULATED,
                    confidence=SignalConfidence.HIGH,
                    source="compliance_requirements",
                    reasoning=f"Compliance: {', '.join(app.compliance_requirements)}"
                )

        # Infer from business criticality
        if app.business_criticality == BusinessCriticality.MISSION_CRITICAL:
            return DerivedSignal(
                value=SecurityLevel.ENTERPRISE,
                confidence=SignalConfidence.MEDIUM,
                source="business_criticality",
                reasoning="Mission-critical apps typically need enterprise security"
            )

        if app.business_criticality == BusinessCriticality.HIGH:
            return DerivedSignal(
                value=SecurityLevel.ENTERPRISE,
                confidence=SignalConfidence.LOW,
                source="business_criticality",
                reasoning="High criticality suggests enterprise security"
            )

        # Default
        return DerivedSignal(
            value=SecurityLevel.BASIC,
            confidence=SignalConfidence.LOW,
            source="default",
            reasoning="No specific security requirements detected"
        )

    def _derive_cost_posture(self, context: ApplicationContext) -> DerivedSignal:
        """Derive cost optimization posture."""
        app = context.app_overview
        server_summary = context.server_summary

        # Mission-critical prioritizes performance over cost
        if app.business_criticality == BusinessCriticality.MISSION_CRITICAL:
            return DerivedSignal(
                value=CostProfile.SCALE_OPTIMIZED,
                confidence=SignalConfidence.MEDIUM,
                source="business_criticality",
                reasoning="Mission-critical apps prioritize scale over cost"
            )

        # Low criticality suggests cost sensitivity
        if app.business_criticality == BusinessCriticality.LOW:
            return DerivedSignal(
                value=CostProfile.COST_MINIMIZED,
                confidence=SignalConfidence.MEDIUM,
                source="business_criticality",
                reasoning="Low criticality suggests cost sensitivity"
            )

        # Low utilization suggests right-sizing opportunity
        if server_summary.utilization_profile == "low":
            return DerivedSignal(
                value=CostProfile.COST_MINIMIZED,
                confidence=SignalConfidence.LOW,
                source="utilization_profile",
                reasoning="Low utilization suggests cost optimization opportunity"
            )

        # Default balanced
        return DerivedSignal(
            value=CostProfile.BALANCED,
            confidence=SignalConfidence.LOW,
            source="default",
            reasoning="Default balanced cost profile"
        )

    def _derive_network_exposure(self, context: ApplicationContext) -> DerivedSignal:
        """Derive network exposure from app type and technology.

        This affects architecture selection significantly:
        - External: Needs WAF, DDoS protection, CDN, public endpoints
        - Internal: Private endpoints, simpler security model
        - Mixed: Both patterns needed (most complex)
        """
        app = context.app_overview
        tech = context.detected_technology

        # Check app_type for hints
        app_type = (app.app_type or "").lower()

        # External-facing indicators
        external_indicators = [
            "web application", "web app", "website", "portal",
            "customer", "public", "e-commerce", "ecommerce",
            "mobile backend", "api", "b2c", "consumer"
        ]
        if any(ind in app_type for ind in external_indicators):
            return DerivedSignal(
                value=NetworkExposure.EXTERNAL,
                confidence=SignalConfidence.LOW,
                source="app_type",
                reasoning=f"App type '{app.app_type}' suggests external-facing"
            )

        # Internal-facing indicators
        internal_indicators = [
            "internal", "intranet", "back-office", "backoffice",
            "admin", "management", "employee", "corporate",
            "batch", "etl", "data pipeline"
        ]
        if any(ind in app_type for ind in internal_indicators):
            return DerivedSignal(
                value=NetworkExposure.INTERNAL,
                confidence=SignalConfidence.LOW,
                source="app_type",
                reasoning=f"App type '{app.app_type}' suggests internal-only"
            )

        # Check for web technology (suggests possibly external)
        web_tech = ["IIS", "Apache", "Nginx", "ASP.NET", "React", "Angular", "Vue"]
        if any(t in tech.technologies for t in web_tech):
            return DerivedSignal(
                value=NetworkExposure.EXTERNAL,
                confidence=SignalConfidence.LOW,
                source="technology_detection",
                reasoning="Web server technology detected, possibly external-facing"
            )

        # Default to internal (safer assumption)
        return DerivedSignal(
            value=NetworkExposure.INTERNAL,
            confidence=SignalConfidence.UNKNOWN,
            source="default",
            reasoning="No clear external indicators; defaulting to internal"
        )
