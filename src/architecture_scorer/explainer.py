"""Explainer - Phase 6 of the Scoring Engine.

Generates human-readable explanations and summaries for recommendations.
Builds the final output structure with complete transparency.
"""

from typing import Optional

from .config import get_config
from .schema import (
    ArchitectureRecommendation,
    DerivedIntent,
    ExcludedArchitecture,
    RecommendationSummary,
    SignalConfidence,
    ScoringResult,
)


class RecommendationExplainer:
    """Generates explanations and summaries for scoring results.

    Principles:
    - Transparency over brevity
    - Every recommendation must be explainable
    - Assumptions must be visible
    - Unknown is better than wrong

    Configuration:
    - Confidence thresholds can be customized via scorer-config.yaml
    - See docs/configuration.md for details
    """

    def __init__(self):
        """Initialize explainer with configuration."""
        cfg = get_config().confidence_thresholds
        self.high_threshold = cfg.high_score_threshold
        self.medium_threshold = cfg.medium_score_threshold
        self.high_penalty_limit = cfg.high_penalty_limit
        self.medium_penalty_limit = cfg.medium_penalty_limit
        self.high_max_low_signals = cfg.high_max_low_signals
        self.medium_max_low_signals = cfg.medium_max_low_signals
        self.high_max_assumptions = cfg.high_max_assumptions

    def generate_summary(
        self,
        recommendations: list[ArchitectureRecommendation],
        excluded: list[ExcludedArchitecture],
        intent: DerivedIntent,
    ) -> RecommendationSummary:
        """Generate a summary of the recommendation results.

        Args:
            recommendations: Scored and sorted recommendations
            excluded: Excluded architectures with reasons
            intent: Derived intent used for scoring

        Returns:
            Summary with primary recommendation and key drivers
        """
        if not recommendations:
            return RecommendationSummary(
                primary_recommendation=None,
                primary_recommendation_id=None,
                confidence_level="Low",
                key_drivers=["No eligible architectures found"],
                key_risks=["All architectures were excluded based on application characteristics"],
                assumptions_count=0,
                clarifications_needed=self._count_low_confidence_signals(intent),
            )

        primary = recommendations[0]

        # Determine confidence level
        confidence_level = self._determine_confidence_level(primary, intent)

        # Extract key drivers
        key_drivers = self._extract_key_drivers(primary, intent)

        # Extract key risks
        key_risks = self._extract_key_risks(primary, recommendations)

        # Count assumptions
        total_assumptions = sum(len(r.assumptions) for r in recommendations[:3])

        return RecommendationSummary(
            primary_recommendation=primary.name,
            primary_recommendation_id=primary.architecture_id,
            confidence_level=confidence_level,
            key_drivers=key_drivers,
            key_risks=key_risks,
            assumptions_count=total_assumptions,
            clarifications_needed=self._count_low_confidence_signals(intent),
        )

    def _determine_confidence_level(
        self,
        primary: ArchitectureRecommendation,
        intent: DerivedIntent,
    ) -> str:
        """Determine overall confidence level based on config thresholds."""
        score = primary.likelihood_score
        penalty = primary.confidence_penalty
        low_confidence_count = self._count_low_confidence_signals(intent)

        # High confidence: high score, low penalty, few assumptions
        if (score >= self.high_threshold and
            penalty < self.high_penalty_limit and
            low_confidence_count <= self.high_max_low_signals and
            len(primary.assumptions) <= self.high_max_assumptions):
            return "High"

        # Medium confidence: decent score with some uncertainty
        if (score >= self.medium_threshold and
            penalty < self.medium_penalty_limit and
            low_confidence_count <= self.medium_max_low_signals):
            return "Medium"

        return "Low"

    def _count_low_confidence_signals(self, intent: DerivedIntent) -> int:
        """Count signals with low or unknown confidence."""
        count = 0
        signals = [
            intent.treatment,
            intent.time_category,
            intent.availability_requirement,
            intent.security_requirement,
            intent.operational_maturity_estimate,
            intent.likely_runtime_model,
            intent.modernization_depth_feasible,
            intent.cloud_native_feasibility,
            intent.cost_posture,
        ]
        for signal in signals:
            if signal.confidence in (SignalConfidence.LOW, SignalConfidence.UNKNOWN):
                count += 1
        return count

    def _extract_key_drivers(
        self,
        primary: ArchitectureRecommendation,
        intent: DerivedIntent,
    ) -> list[str]:
        """Extract key drivers for the primary recommendation."""
        drivers = []

        # Treatment alignment
        if intent.treatment.confidence == SignalConfidence.HIGH:
            drivers.append(f"Treatment: {intent.treatment.value.value} (confirmed)")
        elif intent.treatment.value:
            drivers.append(f"Treatment: {intent.treatment.value.value} (inferred)")

        # Top matched dimensions
        for match in primary.matched_dimensions[:3]:
            drivers.append(f"{match.dimension}: {match.value}")

        # App Mod recommendations if present
        if primary.fit_summary:
            for fit in primary.fit_summary[:2]:
                if fit not in drivers:
                    drivers.append(fit)

        return drivers[:5]  # Limit to 5 key drivers

    def _extract_key_risks(
        self,
        primary: ArchitectureRecommendation,
        recommendations: list[ArchitectureRecommendation],
    ) -> list[str]:
        """Extract key risks and concerns."""
        risks = []

        # Mismatched dimensions
        for mismatch in primary.mismatched_dimensions[:2]:
            risks.append(f"{mismatch.dimension}: {mismatch.impact}")

        # Assumptions as risks
        for assumption in primary.assumptions[:2]:
            risks.append(f"Assumption: {assumption.assumption}")

        # Score gap with next recommendation
        if len(recommendations) > 1:
            gap = primary.likelihood_score - recommendations[1].likelihood_score
            if gap < 10:
                risks.append(
                    f"Close alternative: {recommendations[1].name} "
                    f"({recommendations[1].likelihood_score:.0f}%)"
                )

        # Catalog quality warning
        if primary.catalog_quality.value in ("ai_suggested", "example_only"):
            risks.append(f"Catalog quality: {primary.catalog_quality.value} (review recommended)")

        return risks[:4]  # Limit to 4 key risks

    def enrich_recommendation(
        self,
        recommendation: ArchitectureRecommendation,
        rank: int,
    ) -> ArchitectureRecommendation:
        """Enrich a recommendation with additional context.

        Adds rank-specific explanations and warnings.
        """
        # Add rank-based context to fit summary
        if rank == 1:
            if recommendation.likelihood_score >= self.high_threshold:
                recommendation.fit_summary.insert(0, "Strong match for application requirements")
            elif recommendation.likelihood_score >= self.medium_threshold:
                recommendation.fit_summary.insert(0, "Good match with some considerations")
            else:
                recommendation.fit_summary.insert(0, "Possible match - review assumptions carefully")

        # Add confidence penalty warning if significant
        if recommendation.confidence_penalty >= 0.15:
            recommendation.struggle_summary.append(
                f"Confidence reduced by {recommendation.confidence_penalty*100:.0f}% due to assumptions"
            )

        return recommendation

    def format_exclusion_summary(
        self,
        excluded: list[ExcludedArchitecture],
    ) -> str:
        """Format a human-readable summary of exclusions."""
        if not excluded:
            return "No architectures were excluded."

        lines = [f"Excluded {len(excluded)} architectures:"]

        # Group by reason type
        reason_counts: dict[str, int] = {}
        for ex in excluded:
            for reason in ex.reasons:
                reason_type = reason.reason_type
                reason_counts[reason_type] = reason_counts.get(reason_type, 0) + 1

        for reason_type, count in sorted(reason_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  - {reason_type}: {count} architectures")

        return "\n".join(lines)


def build_scoring_result(
    application_name: str,
    catalog_version: str,
    catalog_count: int,
    intent: DerivedIntent,
    questions: list,
    recommendations: list[ArchitectureRecommendation],
    excluded: list[ExcludedArchitecture],
    warnings: list[str],
) -> ScoringResult:
    """Build the complete scoring result.

    Args:
        application_name: Name of the scored application
        catalog_version: Version of the architecture catalog
        catalog_count: Total architectures in catalog
        intent: Derived intent used for scoring
        questions: Any pending clarification questions
        recommendations: Scored recommendations
        excluded: Excluded architectures
        warnings: Processing warnings

    Returns:
        Complete ScoringResult ready for output
    """
    explainer = RecommendationExplainer()

    # Enrich recommendations with rank context
    enriched_recommendations = []
    for i, rec in enumerate(recommendations):
        enriched = explainer.enrich_recommendation(rec, rank=i + 1)
        enriched_recommendations.append(enriched)

    # Generate summary
    summary = explainer.generate_summary(enriched_recommendations, excluded, intent)

    return ScoringResult(
        application_name=application_name,
        catalog_version=catalog_version,
        catalog_architecture_count=catalog_count,
        derived_intent=intent,
        clarification_questions=questions,
        questions_pending=len(questions) > 0,
        recommendations=enriched_recommendations,
        excluded=excluded,
        summary=summary,
        eligible_count=len(recommendations),
        excluded_count=len(excluded),
        processing_warnings=warnings,
    )
