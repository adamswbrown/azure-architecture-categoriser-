"""Scorer - Phase 5 of the Scoring Engine.

Scores eligible architectures against application context.
Produces a 0-100 score with detailed breakdown by dimension.
"""

from dataclasses import dataclass
from typing import Optional

from catalog_builder.schema import (
    ArchitectureEntry,
    AvailabilityModel,
    CatalogQuality,
    ComplexityLevel,
    CostProfile,
    OperatingModel,
    RuntimeModel,
    SecurityLevel,
)

from .schema import (
    ApplicationContext,
    ArchitectureRecommendation,
    AssumptionMade,
    BusinessCriticality,
    CloudNativeFeasibility,
    CompatibilityStatus,
    DerivedIntent,
    MatchedDimension,
    MismatchedDimension,
    ModernizationDepth,
    ScoringDimension,
    SignalConfidence,
)


@dataclass
class ScoringWeights:
    """Weights for scoring dimensions."""
    treatment_alignment: float = 0.20  # Hard gate + weight
    runtime_model_compatibility: float = 0.10
    platform_compatibility: float = 0.15  # App Mod boost
    app_mod_recommended: float = 0.10  # Boost if recommended
    service_overlap: float = 0.10  # Core service match
    browse_tag_overlap: float = 0.05
    availability_alignment: float = 0.10
    operating_model_fit: float = 0.08
    complexity_tolerance: float = 0.07
    cost_posture_alignment: float = 0.05


class ArchitectureScorer:
    """Scores eligible architectures against application context.

    Scoring principles:
    - Treatment alignment is a hard gate (must pass)
    - App Mod recommended targets get significant boost
    - Scores are weighted by confidence
    - Assumption-heavy matches are penalized
    - Never force a recommendation
    """

    # Catalog quality weights (applied to final score)
    QUALITY_WEIGHTS = {
        CatalogQuality.CURATED: 1.0,
        CatalogQuality.AI_ENRICHED: 0.95,
        CatalogQuality.AI_SUGGESTED: 0.85,
        CatalogQuality.EXAMPLE_ONLY: 0.70,
    }

    # Confidence penalty factors
    CONFIDENCE_PENALTIES = {
        SignalConfidence.HIGH: 0.0,
        SignalConfidence.MEDIUM: 0.05,
        SignalConfidence.LOW: 0.15,
        SignalConfidence.UNKNOWN: 0.25,
    }

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """Initialize scorer with optional custom weights."""
        self.weights = weights or ScoringWeights()

    def score(
        self,
        architectures: list[ArchitectureEntry],
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ArchitectureRecommendation]:
        """Score eligible architectures and return sorted recommendations.

        Args:
            architectures: Eligible architectures (already filtered)
            context: Normalized application context
            intent: Derived intent signals

        Returns:
            Sorted list of recommendations (highest score first)
        """
        recommendations = []

        for arch in architectures:
            recommendation = self._score_architecture(arch, context, intent)
            recommendations.append(recommendation)

        # Sort by likelihood score descending
        recommendations.sort(key=lambda r: r.likelihood_score, reverse=True)

        return recommendations

    def _score_architecture(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> ArchitectureRecommendation:
        """Score a single architecture."""
        dimensions = []
        matched = []
        mismatched = []
        assumptions = []

        # Score each dimension
        dimensions.append(self._score_treatment_alignment(arch, intent, matched, mismatched, assumptions))
        dimensions.append(self._score_runtime_model(arch, intent, matched, mismatched, assumptions))
        dimensions.append(self._score_platform_compatibility(arch, context, matched, mismatched, assumptions))
        dimensions.append(self._score_app_mod_recommended(arch, context, matched, mismatched))
        dimensions.append(self._score_service_overlap(arch, context, matched, mismatched))
        dimensions.append(self._score_browse_tag_overlap(arch, context, matched, mismatched))
        dimensions.append(self._score_availability_alignment(arch, intent, matched, mismatched, assumptions))
        dimensions.append(self._score_operating_model_fit(arch, intent, matched, mismatched, assumptions))
        dimensions.append(self._score_complexity_tolerance(arch, context, intent, matched, mismatched))
        dimensions.append(self._score_cost_posture(arch, intent, matched, mismatched, assumptions))

        # Calculate base score
        total_weighted = sum(d.weighted_score for d in dimensions)
        total_weights = sum(d.weight for d in dimensions)
        base_score = (total_weighted / total_weights * 100) if total_weights > 0 else 0

        # Apply catalog quality weight
        quality_weight = self.QUALITY_WEIGHTS.get(arch.catalog_quality, 0.85)
        quality_adjusted = base_score * quality_weight

        # Calculate confidence penalty
        confidence_penalty = self._calculate_confidence_penalty(intent, assumptions)
        final_score = max(0, quality_adjusted - (confidence_penalty * 100))

        # Generate fit/struggle summaries
        fit_summary = self._generate_fit_summary(matched)
        struggle_summary = self._generate_struggle_summary(mismatched)

        # Construct diagram URL from first diagram asset
        diagram_url = None
        if arch.diagram_assets:
            first_diagram = arch.diagram_assets[0]
            diagram_url = f"https://raw.githubusercontent.com/MicrosoftDocs/architecture-center/main/{first_diagram}"

        return ArchitectureRecommendation(
            architecture_id=arch.architecture_id,
            name=arch.name,
            pattern_name=arch.pattern_name,
            description=arch.description,
            likelihood_score=round(final_score, 1),
            catalog_quality=arch.catalog_quality,
            scoring_dimensions=dimensions,
            matched_dimensions=matched,
            mismatched_dimensions=mismatched,
            assumptions=assumptions,
            fit_summary=fit_summary,
            struggle_summary=struggle_summary,
            core_services=arch.core_services,
            supporting_services=arch.supporting_services,
            learn_url=arch.learn_url,
            diagram_url=diagram_url,
            browse_tags=arch.browse_tags,
            confidence_penalty=confidence_penalty,
        )

    def _score_treatment_alignment(
        self,
        arch: ArchitectureEntry,
        intent: DerivedIntent,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
        assumptions: list[AssumptionMade],
    ) -> ScoringDimension:
        """Score treatment alignment (hard gate + scoring)."""
        required = intent.treatment.value
        supported = arch.supported_treatments

        # Hard gate: must support treatment
        if supported and required not in supported:
            return ScoringDimension(
                dimension="treatment_alignment",
                weight=self.weights.treatment_alignment,
                raw_score=0,
                weighted_score=0,
                reasoning=f"Treatment {required.value} not in supported: {[t.value for t in supported]}",
                is_hard_gate=True,
                passed_gate=False,
            )

        # Treatment is supported or no restrictions
        if supported and required in supported:
            matched.append(MatchedDimension(
                dimension="Treatment",
                value=required.value,
                reasoning=f"Supports {required.value} treatment"
            ))
            score = 1.0
        else:
            # No treatment restrictions - neutral score
            score = 0.7
            if intent.treatment.confidence in (SignalConfidence.LOW, SignalConfidence.UNKNOWN):
                assumptions.append(AssumptionMade(
                    dimension="treatment",
                    assumption=f"Assumed treatment: {required.value}",
                    confidence=intent.treatment.confidence,
                    impact="Treatment affects architecture selection"
                ))

        return ScoringDimension(
            dimension="treatment_alignment",
            weight=self.weights.treatment_alignment,
            raw_score=score * 100,
            weighted_score=score * self.weights.treatment_alignment,
            reasoning=f"Treatment: {required.value}",
            is_hard_gate=True,
            passed_gate=True,
        )

    def _score_runtime_model(
        self,
        arch: ArchitectureEntry,
        intent: DerivedIntent,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
        assumptions: list[AssumptionMade],
    ) -> ScoringDimension:
        """Score runtime model compatibility."""
        app_runtime = intent.likely_runtime_model.value
        arch_runtimes = arch.expected_runtime_models

        # Check for match
        if app_runtime in arch_runtimes:
            matched.append(MatchedDimension(
                dimension="Runtime Model",
                value=app_runtime.value,
                reasoning="Application runtime matches architecture expectation"
            ))
            score = 1.0
        elif RuntimeModel.MIXED in arch_runtimes or RuntimeModel.UNKNOWN in arch_runtimes:
            # Flexible architecture
            score = 0.7
        elif app_runtime == RuntimeModel.UNKNOWN:
            # Unknown app runtime - neutral
            score = 0.5
            assumptions.append(AssumptionMade(
                dimension="runtime_model",
                assumption="Runtime model unknown; assuming compatible",
                confidence=SignalConfidence.UNKNOWN,
                impact="May need validation"
            ))
        else:
            mismatched.append(MismatchedDimension(
                dimension="Runtime Model",
                expected=", ".join(r.value for r in arch_runtimes),
                actual=app_runtime.value,
                impact="Architecture designed for different runtime pattern"
            ))
            score = 0.3

        return ScoringDimension(
            dimension="runtime_model_compatibility",
            weight=self.weights.runtime_model_compatibility,
            raw_score=score * 100,
            weighted_score=score * self.weights.runtime_model_compatibility,
            reasoning=f"App: {app_runtime.value}, Arch: {[r.value for r in arch_runtimes]}",
        )

    def _score_platform_compatibility(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
        assumptions: list[AssumptionMade],
    ) -> ScoringDimension:
        """Score platform compatibility based on App Mod results."""
        if not context.app_mod_results:
            assumptions.append(AssumptionMade(
                dimension="platform_compatibility",
                assumption="No App Mod results; assuming general compatibility",
                confidence=SignalConfidence.UNKNOWN,
                impact="Platform fit not validated"
            ))
            return ScoringDimension(
                dimension="platform_compatibility",
                weight=self.weights.platform_compatibility,
                raw_score=50,
                weighted_score=0.5 * self.weights.platform_compatibility,
                reasoning="No App Mod results available",
            )

        mod = context.app_mod_results
        arch_services = set(s.lower() for s in arch.core_services)

        # Check compatibility for each core service platform
        compatibility_scores = []
        for pc in mod.platform_compatibility:
            platform_lower = pc.platform.lower()
            # Check if architecture uses this platform
            relevant = any(
                kw in platform_lower
                for kw in ["app service", "kubernetes", "container", "aks", "aca"]
                if kw in " ".join(arch_services)
            )
            if relevant:
                if pc.status == CompatibilityStatus.FULLY_SUPPORTED:
                    compatibility_scores.append(1.0)
                    matched.append(MatchedDimension(
                        dimension="Platform Compatibility",
                        value=pc.platform,
                        reasoning=f"Fully supported: {pc.platform}"
                    ))
                elif pc.status == CompatibilityStatus.SUPPORTED:
                    compatibility_scores.append(0.9)
                elif pc.status == CompatibilityStatus.SUPPORTED_WITH_CHANGES:
                    compatibility_scores.append(0.7)
                elif pc.status == CompatibilityStatus.SUPPORTED_WITH_REFACTOR:
                    compatibility_scores.append(0.5)
                    mismatched.append(MismatchedDimension(
                        dimension="Platform Compatibility",
                        expected="Supported",
                        actual=f"{pc.platform}: Requires refactor",
                        impact="Additional effort required"
                    ))

        if compatibility_scores:
            avg_score = sum(compatibility_scores) / len(compatibility_scores)
        else:
            avg_score = 0.6  # Neutral if no relevant platforms found

        return ScoringDimension(
            dimension="platform_compatibility",
            weight=self.weights.platform_compatibility,
            raw_score=avg_score * 100,
            weighted_score=avg_score * self.weights.platform_compatibility,
            reasoning=f"App Mod compatibility: {len(compatibility_scores)} relevant platforms",
        )

    def _score_app_mod_recommended(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
    ) -> ScoringDimension:
        """Score boost for App Mod recommended targets."""
        if not context.app_mod_results:
            return ScoringDimension(
                dimension="app_mod_recommended",
                weight=self.weights.app_mod_recommended,
                raw_score=50,
                weighted_score=0.5 * self.weights.app_mod_recommended,
                reasoning="No App Mod recommendations",
            )

        recommended = context.app_mod_results.recommended_targets
        if not recommended:
            return ScoringDimension(
                dimension="app_mod_recommended",
                weight=self.weights.app_mod_recommended,
                raw_score=50,
                weighted_score=0.5 * self.weights.app_mod_recommended,
                reasoning="No specific recommendations from App Mod",
            )

        # Check if any recommended targets match architecture services
        arch_services = set(s.lower() for s in arch.core_services)
        recommended_lower = [r.lower() for r in recommended]

        match_count = 0
        for rec in recommended_lower:
            for svc in arch_services:
                if rec in svc or svc in rec:
                    match_count += 1
                    matched.append(MatchedDimension(
                        dimension="App Mod Recommended",
                        value=rec,
                        reasoning=f"Recommended target: {rec}"
                    ))
                    break

        if match_count > 0:
            score = min(1.0, 0.7 + (match_count * 0.15))
        else:
            score = 0.4

        return ScoringDimension(
            dimension="app_mod_recommended",
            weight=self.weights.app_mod_recommended,
            raw_score=score * 100,
            weighted_score=score * self.weights.app_mod_recommended,
            reasoning=f"Matches {match_count} of {len(recommended)} recommended targets",
        )

    def _score_service_overlap(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
    ) -> ScoringDimension:
        """Score overlap between approved services and architecture services."""
        approved = context.approved_services.get_all_approved_services()
        if not approved:
            return ScoringDimension(
                dimension="service_overlap",
                weight=self.weights.service_overlap,
                raw_score=50,
                weighted_score=0.5 * self.weights.service_overlap,
                reasoning="No approved services specified",
            )

        approved_lower = [s.lower() for s in approved]
        arch_services = [s.lower() for s in arch.core_services + arch.supporting_services]

        # Calculate overlap
        matches = sum(1 for a in approved_lower for s in arch_services if a in s or s in a)
        total = len(approved_lower)

        if total > 0:
            overlap_ratio = min(1.0, matches / total)
            if overlap_ratio >= 0.5:
                matched.append(MatchedDimension(
                    dimension="Service Overlap",
                    value=f"{matches}/{total} services",
                    reasoning=f"Good alignment with approved services"
                ))
        else:
            overlap_ratio = 0.5

        score = 0.3 + (overlap_ratio * 0.7)  # 30% base + up to 70% for overlap

        return ScoringDimension(
            dimension="service_overlap",
            weight=self.weights.service_overlap,
            raw_score=score * 100,
            weighted_score=score * self.weights.service_overlap,
            reasoning=f"{matches} of {total} approved services match",
        )

    def _score_browse_tag_overlap(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
    ) -> ScoringDimension:
        """Score overlap between app characteristics and browse tags."""
        # Infer relevant tags from context
        relevant_tags = self._infer_relevant_tags(context)
        arch_tags = [t.lower() for t in arch.browse_tags]

        if not relevant_tags:
            return ScoringDimension(
                dimension="browse_tag_overlap",
                weight=self.weights.browse_tag_overlap,
                raw_score=50,
                weighted_score=0.5 * self.weights.browse_tag_overlap,
                reasoning="No relevant tags inferred from context",
            )

        matches = sum(1 for t in relevant_tags if t in arch_tags)
        score = 0.4 + (min(1.0, matches / len(relevant_tags)) * 0.6)

        if matches > 0:
            matched.append(MatchedDimension(
                dimension="Browse Tags",
                value=f"{matches} tags",
                reasoning=f"Matching tags: {[t for t in relevant_tags if t in arch_tags]}"
            ))

        return ScoringDimension(
            dimension="browse_tag_overlap",
            weight=self.weights.browse_tag_overlap,
            raw_score=score * 100,
            weighted_score=score * self.weights.browse_tag_overlap,
            reasoning=f"{matches} relevant browse tags match",
        )

    def _infer_relevant_tags(self, context: ApplicationContext) -> list[str]:
        """Infer relevant browse tags from application context."""
        tags = []
        tech = context.detected_technology

        if tech.primary_runtime == "Java":
            tags.append("java")
        if tech.primary_runtime == ".NET":
            tags.extend(["dotnet", ".net"])
        if tech.database_present:
            tags.append("databases")
        if tech.messaging_present:
            tags.append("messaging")
        if context.app_mod_results and context.app_mod_results.container_ready:
            tags.append("containers")

        # App type hints
        app_type = (context.app_overview.app_type or "").lower()
        if "web" in app_type:
            tags.append("web")
        if "api" in app_type:
            tags.append("api")

        return [t.lower() for t in tags]

    def _score_availability_alignment(
        self,
        arch: ArchitectureEntry,
        intent: DerivedIntent,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
        assumptions: list[AssumptionMade],
    ) -> ScoringDimension:
        """Score availability model alignment."""
        required = intent.availability_requirement.value
        supported = arch.availability_models

        if required in supported:
            matched.append(MatchedDimension(
                dimension="Availability",
                value=required.value,
                reasoning=f"Supports {required.value}"
            ))
            score = 1.0
        elif self._availability_exceeds(supported, required):
            # Architecture supports higher availability than required
            score = 0.9
        else:
            mismatched.append(MismatchedDimension(
                dimension="Availability",
                expected=required.value,
                actual=", ".join(a.value for a in supported),
                impact="May need architecture modifications for required availability"
            ))
            score = 0.4

        if intent.availability_requirement.confidence in (SignalConfidence.LOW, SignalConfidence.UNKNOWN):
            assumptions.append(AssumptionMade(
                dimension="availability",
                assumption=f"Assumed availability requirement: {required.value}",
                confidence=intent.availability_requirement.confidence,
                impact="Availability affects architecture complexity"
            ))

        return ScoringDimension(
            dimension="availability_alignment",
            weight=self.weights.availability_alignment,
            raw_score=score * 100,
            weighted_score=score * self.weights.availability_alignment,
            reasoning=f"Required: {required.value}, Supported: {[a.value for a in supported]}",
        )

    def _availability_exceeds(
        self, supported: list[AvailabilityModel], required: AvailabilityModel
    ) -> bool:
        """Check if supported availability exceeds requirement."""
        hierarchy = {
            AvailabilityModel.SINGLE_REGION: 0,
            AvailabilityModel.ZONE_REDUNDANT: 1,
            AvailabilityModel.MULTI_REGION_ACTIVE_PASSIVE: 2,
            AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE: 3,
        }
        required_level = hierarchy.get(required, 0)
        max_supported = max(hierarchy.get(a, 0) for a in supported) if supported else 0
        return max_supported > required_level

    def _score_operating_model_fit(
        self,
        arch: ArchitectureEntry,
        intent: DerivedIntent,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
        assumptions: list[AssumptionMade],
    ) -> ScoringDimension:
        """Score operating model fit."""
        app_maturity = intent.operational_maturity_estimate.value
        arch_required = arch.operating_model_required

        hierarchy = {
            OperatingModel.TRADITIONAL_IT: 0,
            OperatingModel.TRANSITIONAL: 1,
            OperatingModel.DEVOPS: 2,
            OperatingModel.SRE: 3,
        }

        app_level = hierarchy.get(app_maturity, 0)
        arch_level = hierarchy.get(arch_required, 0)

        if app_level >= arch_level:
            matched.append(MatchedDimension(
                dimension="Operating Model",
                value=app_maturity.value,
                reasoning=f"Meets {arch_required.value} requirement"
            ))
            # Exact match or slight over is ideal
            score = 1.0 if app_level == arch_level else 0.9
        else:
            gap = arch_level - app_level
            mismatched.append(MismatchedDimension(
                dimension="Operating Model",
                expected=arch_required.value,
                actual=app_maturity.value,
                impact=f"Team maturity gap of {gap} level(s)"
            ))
            score = max(0.2, 1.0 - (gap * 0.3))

        if intent.operational_maturity_estimate.confidence in (SignalConfidence.LOW, SignalConfidence.UNKNOWN):
            assumptions.append(AssumptionMade(
                dimension="operating_model",
                assumption=f"Assumed team maturity: {app_maturity.value}",
                confidence=intent.operational_maturity_estimate.confidence,
                impact="May affect implementation success"
            ))

        return ScoringDimension(
            dimension="operating_model_fit",
            weight=self.weights.operating_model_fit,
            raw_score=score * 100,
            weighted_score=score * self.weights.operating_model_fit,
            reasoning=f"App: {app_maturity.value}, Required: {arch_required.value}",
        )

    def _score_complexity_tolerance(
        self,
        arch: ArchitectureEntry,
        context: ApplicationContext,
        intent: DerivedIntent,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
    ) -> ScoringDimension:
        """Score complexity tolerance based on app criticality and team maturity."""
        impl_complexity = arch.complexity.implementation
        ops_complexity = arch.complexity.operations
        criticality = context.app_overview.business_criticality
        maturity = intent.operational_maturity_estimate.value

        # Map criticality to complexity tolerance
        criticality_tolerance = {
            BusinessCriticality.LOW: ComplexityLevel.LOW,
            BusinessCriticality.MEDIUM: ComplexityLevel.MEDIUM,
            BusinessCriticality.HIGH: ComplexityLevel.HIGH,
            BusinessCriticality.MISSION_CRITICAL: ComplexityLevel.HIGH,
        }

        tolerance = criticality_tolerance.get(criticality, ComplexityLevel.MEDIUM)
        complexity_order = {ComplexityLevel.LOW: 0, ComplexityLevel.MEDIUM: 1, ComplexityLevel.HIGH: 2}

        max_arch_complexity = max(
            complexity_order.get(impl_complexity, 1),
            complexity_order.get(ops_complexity, 1)
        )
        tolerance_level = complexity_order.get(tolerance, 1)

        if max_arch_complexity <= tolerance_level:
            matched.append(MatchedDimension(
                dimension="Complexity",
                value=f"{impl_complexity.value}/{ops_complexity.value}",
                reasoning="Complexity within tolerance"
            ))
            score = 1.0
        else:
            gap = max_arch_complexity - tolerance_level
            mismatched.append(MismatchedDimension(
                dimension="Complexity",
                expected=f"≤ {tolerance.value}",
                actual=f"{impl_complexity.value}/{ops_complexity.value}",
                impact="Architecture may be over-engineered for the use case"
            ))
            score = max(0.3, 1.0 - (gap * 0.35))

        return ScoringDimension(
            dimension="complexity_tolerance",
            weight=self.weights.complexity_tolerance,
            raw_score=score * 100,
            weighted_score=score * self.weights.complexity_tolerance,
            reasoning=f"Impl: {impl_complexity.value}, Ops: {ops_complexity.value}, Tolerance: {tolerance.value}",
        )

    def _score_cost_posture(
        self,
        arch: ArchitectureEntry,
        intent: DerivedIntent,
        matched: list[MatchedDimension],
        mismatched: list[MismatchedDimension],
        assumptions: list[AssumptionMade],
    ) -> ScoringDimension:
        """Score cost profile alignment."""
        required = intent.cost_posture.value
        arch_profile = arch.cost_profile

        profile_order = {
            CostProfile.COST_MINIMIZED: 0,
            CostProfile.BALANCED: 1,
            CostProfile.SCALE_OPTIMIZED: 2,
            CostProfile.INNOVATION_FIRST: 3,
        }

        required_level = profile_order.get(required, 1)
        arch_level = profile_order.get(arch_profile, 1)

        diff = abs(arch_level - required_level)
        if diff == 0:
            matched.append(MatchedDimension(
                dimension="Cost Profile",
                value=required.value,
                reasoning="Cost profile aligned"
            ))
            score = 1.0
        elif diff == 1:
            score = 0.8  # Close enough
        else:
            mismatched.append(MismatchedDimension(
                dimension="Cost Profile",
                expected=required.value,
                actual=arch_profile.value,
                impact="Cost characteristics may not align with expectations"
            ))
            score = 0.5

        if intent.cost_posture.confidence in (SignalConfidence.LOW, SignalConfidence.UNKNOWN):
            assumptions.append(AssumptionMade(
                dimension="cost_posture",
                assumption=f"Assumed cost posture: {required.value}",
                confidence=intent.cost_posture.confidence,
                impact="May affect budget planning"
            ))

        return ScoringDimension(
            dimension="cost_posture_alignment",
            weight=self.weights.cost_posture_alignment,
            raw_score=score * 100,
            weighted_score=score * self.weights.cost_posture_alignment,
            reasoning=f"Required: {required.value}, Architecture: {arch_profile.value}",
        )

    def _calculate_confidence_penalty(
        self,
        intent: DerivedIntent,
        assumptions: list[AssumptionMade],
    ) -> float:
        """Calculate confidence penalty based on assumptions and low-confidence signals."""
        penalty = 0.0

        # Penalty for low-confidence signals
        signals = [
            intent.treatment,
            intent.time_category,
            intent.availability_requirement,
            intent.security_requirement,
            intent.operational_maturity_estimate,
            intent.likely_runtime_model,
        ]

        for signal in signals:
            penalty += self.CONFIDENCE_PENALTIES.get(signal.confidence, 0)

        # Additional penalty for assumptions
        penalty += len(assumptions) * 0.02

        return min(0.25, penalty)  # Cap at 25% penalty

    def _generate_fit_summary(self, matched: list[MatchedDimension]) -> list[str]:
        """Generate human-readable fit summary."""
        summaries = []
        for m in matched[:5]:  # Top 5 matches
            summaries.append(f"{m.dimension}: {m.reasoning}")
        return summaries

    def _generate_struggle_summary(self, mismatched: list[MismatchedDimension]) -> list[str]:
        """Generate human-readable struggle summary."""
        summaries = []
        for m in mismatched[:3]:  # Top 3 mismatches
            summaries.append(f"{m.dimension}: {m.impact}")
        return summaries
