"""Results display component for the recommendations app."""

import streamlit as st

from architecture_scorer.schema import ScoringResult, ArchitectureRecommendation


# Quality badge colors (CSS classes defined in app.py)
QUALITY_LABELS = {
    "curated": ("Curated", "#0078D4", "white"),
    "ai_enriched": ("AI Enriched", "#5C2D91", "white"),
    "ai_suggested": ("AI Suggested", "#FFB900", "black"),
    "example_only": ("Example", "#E6E6E6", "#666"),
}


def render_results(result: ScoringResult) -> None:
    """Render the scoring results."""
    # Summary section
    _render_summary(result)

    st.markdown("---")

    # Primary recommendation (highlighted)
    if result.recommendations:
        st.subheader("Primary Recommendation")
        _render_recommendation_card(result.recommendations[0], is_primary=True)

    # Additional recommendations
    if len(result.recommendations) > 1:
        st.markdown("---")
        st.subheader("Alternative Recommendations")
        for rec in result.recommendations[1:]:
            _render_recommendation_card(rec, is_primary=False)


def _render_summary(result: ScoringResult) -> None:
    """Render the summary section with metrics."""
    summary = result.summary

    st.subheader("Analysis Summary")

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Application", result.application_name)

    with col2:
        st.metric(
            "Confidence",
            summary.confidence_level,
            help="Based on data quality and clarity of requirements"
        )

    with col3:
        st.metric("Recommendations", len(result.recommendations))

    with col4:
        st.metric("Architectures Evaluated", result.catalog_architecture_count)

    # Key insights
    col1, col2 = st.columns(2)

    with col1:
        if summary.key_drivers:
            st.markdown("**Key Drivers:**")
            for driver in summary.key_drivers[:4]:
                st.markdown(f"- {driver}")

    with col2:
        if summary.key_risks:
            st.markdown("**Key Considerations:**")
            for risk in summary.key_risks[:4]:
                st.markdown(f"- {risk}")


def _render_recommendation_card(rec: ArchitectureRecommendation, is_primary: bool) -> None:
    """Render a single recommendation as a card."""
    # Container with border
    with st.container(border=True):
        # Header row with title and badges
        col1, col2, col3 = st.columns([3, 1, 1])

        with col1:
            if is_primary:
                st.markdown(f"#### :green[{rec.name}]")
            else:
                st.markdown(f"#### {rec.name}")
            st.caption(f"Pattern: {rec.pattern_name}")

        with col2:
            # Score badge
            score = rec.likelihood_score
            if score >= 60:
                st.success(f"{score:.0f}% Match")
            elif score >= 40:
                st.warning(f"{score:.0f}% Match")
            else:
                st.error(f"{score:.0f}% Match")

        with col3:
            # Quality badge
            quality_key = rec.catalog_quality.value
            label, bg_color, text_color = QUALITY_LABELS.get(
                quality_key, ("Unknown", "#E6E6E6", "#666")
            )
            st.markdown(
                f'<span style="background:{bg_color}; color:{text_color}; '
                f'padding:0.25rem 0.5rem; border-radius:4px; font-size:0.8rem;">'
                f'{label}</span>',
                unsafe_allow_html=True
            )

        # Layout depends on whether this is primary or alternative
        if is_primary:
            # Primary: larger image above content
            if rec.diagram_url:
                try:
                    st.image(rec.diagram_url, width=450)
                except Exception:
                    pass

            # Description
            if rec.description:
                desc = rec.description[:400] + "..." if len(rec.description) > 400 else rec.description
                st.markdown(desc)

            # Details in columns
            col1, col2 = st.columns(2)

            with col1:
                if rec.fit_summary:
                    st.markdown("**Why it fits:**")
                    for fit in rec.fit_summary[:3]:
                        st.markdown(f"- {fit}")

            with col2:
                if rec.struggle_summary:
                    st.markdown("**Potential challenges:**")
                    for struggle in rec.struggle_summary[:3]:
                        st.markdown(f"- {struggle}")
        else:
            # Alternative: smaller image on left, content on right
            img_col, content_col = st.columns([1, 2])

            with img_col:
                if rec.diagram_url:
                    try:
                        st.image(rec.diagram_url, width=200)
                    except Exception:
                        pass

            with content_col:
                # Description (shorter for alternatives)
                if rec.description:
                    desc = rec.description[:200] + "..." if len(rec.description) > 200 else rec.description
                    st.markdown(desc)

                # Fit summary only (condensed)
                if rec.fit_summary:
                    st.markdown("**Why it fits:** " + "; ".join(rec.fit_summary[:2]))

        # Services expander (both primary and alternative)
        if rec.core_services or rec.supporting_services:
            with st.expander("Azure Services"):
                if rec.core_services:
                    st.markdown(f"**Core:** {', '.join(rec.core_services[:8])}")
                if rec.supporting_services:
                    st.markdown(f"**Supporting:** {', '.join(rec.supporting_services[:5])}")

        # Learn more link
        if rec.learn_url:
            st.markdown(f"[Learn more on Microsoft Docs]({rec.learn_url})")
