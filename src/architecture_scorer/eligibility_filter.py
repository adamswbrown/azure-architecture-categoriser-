"""Eligibility Filter - Phase 4 of the Scoring Engine.

Filters out architectures that are definitively not suitable.
Returns eligible architectures for scoring and records exclusion reasons.
"""

from typing import Optional

from catalog_builder.schema import (
    ArchitectureEntry,
    CatalogQuality,
    ExclusionReason,
    OperatingModel,
    SecurityLevel,
    Treatment,
)

from .schema import (
    ApplicationContext,
    CompatibilityStatus,
    DerivedIntent,
    ExcludedArchitecture,
    ExclusionReasonDetail,
)


class EligibilityFilter:
    """Filters architectures based on hard eligibility rules.

    Exclusion is immediate and complete - if any rule fails,
    the architecture is excluded.

    Key principle: App Mod results are authoritative for platform compatibility.
    """

    # Operating model hierarchy (can support this level or below)
    OPERATING_MODEL_HIERARCHY = {
        OperatingModel.TRADITIONAL_IT: 0,
        OperatingModel.TRANSITIONAL: 1,
        OperatingModel.DEVOPS: 2,
        OperatingModel.SRE: 3,
    }

    # Security level hierarchy (can support this level or below)
    SECURITY_LEVEL_HIERARCHY = {
        SecurityLevel.BASIC: 0,
        SecurityLevel.ENTERPRISE: 1,
        SecurityLevel.REGULATED: 2,
        SecurityLevel.HIGHLY_REGULATED: 3,
    }

    # Exclusion reason mapping to app characteristics
    EXCLUSION_MAPPINGS = {
        ExclusionReason.REHOST_ONLY: lambda ctx, intent: intent.treatment.value != Treatment.REHOST,
        ExclusionReason.TOLERATE_ONLY: lambda ctx, intent: intent.treatment.value != Treatment.TOLERATE,
        ExclusionReason.SINGLE_VM_WORKLOADS: lambda ctx, intent: ctx.server_summary.server_count > 1,
        ExclusionReason.GREENFIELD_ONLY: lambda ctx, intent: True,  # Existing apps are not greenfield
        ExclusionReason.SIMPLE_WORKLOADS: lambda ctx, intent: ctx.server_summary.server_count > 2,
        ExclusionReason.WINDOWS_ONLY: lambda ctx, intent: ctx.detected_technology.is_linux and not ctx.detected_technology.is_windows,
        ExclusionReason.LINUX_ONLY: lambda ctx, intent: ctx.detected_technology.is_windows and not ctx.detected_technology.is_linux,
        ExclusionReason.NO_CONTAINER_EXPERIENCE: lambda ctx, intent: _check_no_container_experience(ctx, intent),
        ExclusionReason.STATEFUL_APPS: lambda ctx, intent: False,  # Can't determine statefulness from context alone
    }

    def filter(
        self,
        architectures: list[ArchitectureEntry],
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> tuple[list[ArchitectureEntry], list[ExcludedArchitecture]]:
        """Filter architectures based on eligibility rules.

        Args:
            architectures: All architectures from catalog
            context: Normalized application context
            intent: Derived intent signals

        Returns:
            Tuple of (eligible_architectures, excluded_architectures)
        """
        eligible = []
        excluded = []

        for arch in architectures:
            exclusion_reasons = self._check_eligibility(arch, context, intent)

            if exclusion_reasons:
                excluded.append(ExcludedArchitecture(
                    architecture_id=arch.architecture_id,
                    name=arch.name,
                    reasons=exclusion_reasons,
                ))
            else:
                eligible.append(arch)

        return eligible, excluded

    def _check_eligibility(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ExclusionReasonDetail]:
        """Check all eligibility rules for an architecture.

        Returns list of exclusion reasons (empty if eligible).
        """
        reasons = []

        # Rule 1: Catalog quality check
        quality_reason = self._check_catalog_quality(arch)
        if quality_reason:
            reasons.append(quality_reason)
            return reasons  # Early exit for discard candidates

        # Rule 2: Treatment compatibility
        treatment_reason = self._check_treatment_compatibility(arch, intent)
        if treatment_reason:
            reasons.append(treatment_reason)

        # Rule 3: TIME category compatibility
        time_reason = self._check_time_category_compatibility(arch, intent)
        if time_reason:
            reasons.append(time_reason)

        # Rule 4: Security level compatibility
        security_reason = self._check_security_level_compatibility(arch, intent)
        if security_reason:
            reasons.append(security_reason)

        # Rule 5: Operating model compatibility
        ops_reason = self._check_operating_model_compatibility(arch, intent)
        if ops_reason:
            reasons.append(ops_reason)

        # Rule 6: App Mod platform compatibility (AUTHORITATIVE)
        appmod_reasons = self._check_app_mod_compatibility(arch, context)
        reasons.extend(appmod_reasons)

        # Rule 7: not_suitable_for exclusions
        suitability_reasons = self._check_not_suitable_for(arch, context, intent)
        reasons.extend(suitability_reasons)

        return reasons

    def _check_catalog_quality(
        self, arch: ArchitectureEntry
    ) -> Optional[ExclusionReasonDetail]:
        """Check if catalog quality disqualifies the architecture."""
        # Note: We don't have a "discard_candidate" quality level in the schema
        # but example_only entries should be deprioritized, not excluded
        # If we wanted to exclude them:
        # if arch.catalog_quality == CatalogQuality.EXAMPLE_ONLY:
        #     return ExclusionReasonDetail(
        #         reason_type="catalog_quality",
        #         description="Example-only architecture, not reference pattern",
        #         blocking_value=arch.catalog_quality.value,
        #     )
        return None

    def _check_treatment_compatibility(
        self, arch: ArchitectureEntry, intent: DerivedIntent
    ) -> Optional[ExclusionReasonDetail]:
        """Check if architecture supports the required treatment."""
        required_treatment = intent.treatment.value

        # If architecture has no supported treatments, we can't exclude
        if not arch.supported_treatments:
            return None

        if required_treatment not in arch.supported_treatments:
            return ExclusionReasonDetail(
                reason_type="treatment_mismatch",
                description=f"Architecture does not support {required_treatment.value} treatment",
                blocking_value=required_treatment.value,
                required_value=", ".join(t.value for t in arch.supported_treatments),
            )

        return None

    def _check_time_category_compatibility(
        self, arch: ArchitectureEntry, intent: DerivedIntent
    ) -> Optional[ExclusionReasonDetail]:
        """Check if architecture supports the required TIME category."""
        required_time = intent.time_category.value

        # If architecture has no supported time categories, we can't exclude
        if not arch.supported_time_categories:
            return None

        if required_time not in arch.supported_time_categories:
            return ExclusionReasonDetail(
                reason_type="time_category_mismatch",
                description=f"Architecture does not support {required_time.value} TIME category",
                blocking_value=required_time.value,
                required_value=", ".join(t.value for t in arch.supported_time_categories),
            )

        return None

    def _check_security_level_compatibility(
        self, arch: ArchitectureEntry, intent: DerivedIntent
    ) -> Optional[ExclusionReasonDetail]:
        """Check if architecture meets security requirements."""
        required_security = intent.security_requirement.value
        arch_security = arch.security_level

        required_level = self.SECURITY_LEVEL_HIERARCHY.get(required_security, 0)
        arch_level = self.SECURITY_LEVEL_HIERARCHY.get(arch_security, 0)

        # Architecture must support at least the required level
        if arch_level < required_level:
            return ExclusionReasonDetail(
                reason_type="security_level_insufficient",
                description=f"Architecture security level ({arch_security.value}) below requirement ({required_security.value})",
                blocking_value=arch_security.value,
                required_value=required_security.value,
            )

        return None

    def _check_operating_model_compatibility(
        self, arch: ArchitectureEntry, intent: DerivedIntent
    ) -> Optional[ExclusionReasonDetail]:
        """Check if app's operational maturity can handle architecture requirements.

        We allow a 1-level gap (transitional can access devops) because:
        - Transitional teams are actively modernizing
        - Replatform/refactor projects are part of that journey
        - Better to show options with guidance than no options

        We still exclude 2+ level gaps (traditional_it can't access devops/sre).
        """
        app_maturity = intent.operational_maturity_estimate.value
        arch_required = arch.operating_model_required

        app_level = self.OPERATING_MODEL_HIERARCHY.get(app_maturity, 0)
        arch_level = self.OPERATING_MODEL_HIERARCHY.get(arch_required, 0)

        # Allow 1-level gap (transitional->devops, devops->sre)
        # Exclude only when gap is 2+ levels
        gap = arch_level - app_level
        if gap > 1:
            return ExclusionReasonDetail(
                reason_type="operating_model_gap",
                description=f"App maturity ({app_maturity.value}) significantly below architecture requirement ({arch_required.value})",
                blocking_value=app_maturity.value,
                required_value=arch_required.value,
            )

        return None

    def _check_app_mod_compatibility(
        self, arch: ArchitectureEntry, context: ApplicationContext
    ) -> list[ExclusionReasonDetail]:
        """Check App Mod platform compatibility (AUTHORITATIVE source)."""
        reasons = []

        if not context.app_mod_results:
            return reasons

        mod = context.app_mod_results

        # Check if architecture requires platforms that App Mod marks as unsupported
        arch_services = set(s.lower() for s in arch.core_services + arch.supporting_services)

        # Map services to platforms for compatibility check
        platform_mappings = {
            "azure kubernetes service": ["aks", "kubernetes"],
            "azure container apps": ["container apps", "aca"],
            "azure app service": ["app service"],
        }

        for pc in mod.platform_compatibility:
            if pc.status == CompatibilityStatus.NOT_SUPPORTED:
                platform_lower = pc.platform.lower()

                # Check if architecture uses this platform
                for arch_platform, keywords in platform_mappings.items():
                    if any(kw in platform_lower for kw in keywords):
                        if any(kw in " ".join(arch_services) for kw in keywords + [arch_platform]):
                            reasons.append(ExclusionReasonDetail(
                                reason_type="app_mod_blocker",
                                description=f"App Mod: {pc.platform} not supported",
                                blocking_value="NotSupported",
                                required_value=pc.platform,
                            ))

        # Check explicit blockers
        for blocker in mod.explicit_blockers:
            # Don't create duplicate reasons for the same blocker
            blocker_lower = blocker.lower()
            if "container" in blocker_lower and any(
                svc in arch_services for svc in ["kubernetes", "container", "aks", "aca"]
            ):
                reasons.append(ExclusionReasonDetail(
                    reason_type="app_mod_blocker",
                    description=f"App Mod blocker: {blocker}",
                    blocking_value=blocker,
                ))

        return reasons

    def _check_not_suitable_for(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ExclusionReasonDetail]:
        """Check architecture's not_suitable_for against app characteristics."""
        reasons = []

        for exclusion in arch.not_suitable_for:
            # Check if this exclusion applies to the app
            check_func = self.EXCLUSION_MAPPINGS.get(exclusion)
            if check_func and check_func(context, intent):
                reasons.append(ExclusionReasonDetail(
                    reason_type="not_suitable_for",
                    description=f"Architecture not suitable for: {exclusion.value}",
                    blocking_value=exclusion.value,
                ))

        return reasons


def _check_no_container_experience(
    context: ApplicationContext, intent: DerivedIntent
) -> bool:
    """Check if app context indicates no container experience."""
    # If App Mod says container-ready is false and there's no container tech
    if context.app_mod_results:
        if context.app_mod_results.container_ready is False:
            return True

    # No container technology detected
    tech = context.detected_technology
    if not tech.containerized and "container" not in " ".join(tech.technologies).lower():
        # And traditional IT operating model
        if intent.operational_maturity_estimate.value == OperatingModel.TRADITIONAL_IT:
            return True

    return False
