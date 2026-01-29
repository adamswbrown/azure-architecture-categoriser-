"""Results display component for the recommendations app."""

import streamlit as st

from architecture_scorer.schema import ScoringResult, ArchitectureRecommendation


# Quality badge colors
QUALITY_LABELS = {
    "curated": ("Curated", "#0078D4", "white"),
    "ai_enriched": ("AI Enriched", "#5C2D91", "white"),
    "ai_suggested": ("AI Suggested", "#FFB900", "black"),
    "example_only": ("Example", "#E6E6E6", "#666"),
}

# Confidence level styling
CONFIDENCE_STYLES = {
    "High": ("#107C10", "Strong match with clear requirements"),
    "Medium": ("#FFB900", "Good match - consider answering questions for better accuracy"),
    "Low": ("#D83B01", "Limited data - answering questions will improve recommendations"),
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
        # Show alternatives in a more compact grid
        cols = st.columns(2)
        for i, rec in enumerate(result.recommendations[1:5]):  # Max 4 alternatives
            with cols[i % 2]:
                _render_recommendation_card(rec, is_primary=False)


def _render_summary(result: ScoringResult) -> None:
    """Render the summary section with metrics."""
    summary = result.summary

    st.subheader("Analysis Summary")

    # Get confidence styling
    conf_color, conf_help = CONFIDENCE_STYLES.get(
        summary.confidence_level,
        ("#666", "Confidence level based on data quality")
    )

    # Primary metrics - larger, cleaner display
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"**Application**")
        st.markdown(f"### {result.application_name}")

    with col2:
        st.markdown(f"**Match Confidence**")
        st.markdown(
            f'<h3 style="color:{conf_color}; margin:0;">{summary.confidence_level}</h3>',
            unsafe_allow_html=True
        )
        st.caption(conf_help)

    with col3:
        st.markdown("**Recommendations**")
        st.markdown(f"### {len(result.recommendations)}")

    with col4:
        st.markdown("**Architectures Evaluated**")
        st.markdown(f"### {result.catalog_architecture_count}")

    st.markdown("")  # Spacer

    # Key insights in expanders for cleaner look
    col1, col2 = st.columns(2)

    with col1:
        if summary.key_drivers:
            with st.expander("**Key Drivers** - Why these recommendations", expanded=True):
                for driver in summary.key_drivers[:4]:
                    st.markdown(f"- {driver}")

    with col2:
        if summary.key_risks:
            with st.expander("**Key Considerations** - Things to review", expanded=True):
                for risk in summary.key_risks[:4]:
                    st.markdown(f"- {risk}")


def _render_recommendation_card(rec: ArchitectureRecommendation, is_primary: bool) -> None:
    """Render a single recommendation as a card."""
    with st.container(border=True):
        # Score badge with appropriate color
        score = rec.likelihood_score
        if score >= 60:
            score_color = "#107C10"  # Green
            score_bg = "#DFF6DD"
        elif score >= 40:
            score_color = "#797673"  # Dark gray
            score_bg = "#FFF4CE"
        else:
            score_color = "#D83B01"  # Red/orange
            score_bg = "#FDE7E9"

        # Quality badge
        quality_key = rec.catalog_quality.value
        quality_label, quality_bg, quality_text = QUALITY_LABELS.get(
            quality_key, ("Unknown", "#E6E6E6", "#666")
        )

        if is_primary:
            # Primary recommendation - full width, prominent display
            # Header with title and badges
            header_col, badge_col = st.columns([3, 1])

            with header_col:
                st.markdown(f"### {rec.name}")
                st.caption(f"Pattern: {rec.pattern_name}")

            with badge_col:
                # Score and quality badges stacked
                st.markdown(
                    f'<div style="text-align:right;">'
                    f'<span style="background:{score_bg}; color:{score_color}; '
                    f'padding:0.5rem 1rem; border-radius:8px; font-size:1.2rem; font-weight:bold;">'
                    f'{score:.0f}% Match</span><br/><br/>'
                    f'<span style="background:{quality_bg}; color:{quality_text}; '
                    f'padding:0.25rem 0.75rem; border-radius:4px; font-size:0.85rem;">'
                    f'{quality_label}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            # Architecture diagram (if available) - constrained width for primary
            if rec.diagram_url:
                st.markdown("")  # Spacer
                try:
                    # Use expander to keep diagram accessible but not dominating
                    with st.expander("View Architecture Diagram", expanded=True):
                        st.image(rec.diagram_url, width=500)
                except Exception:
                    st.caption("_Architecture diagram unavailable_")

            # Description
            if rec.description:
                st.markdown("")
                desc = rec.description[:500] + "..." if len(rec.description) > 500 else rec.description
                st.markdown(desc)

            # Why it fits / Challenges in columns
            st.markdown("")
            fit_col, challenge_col = st.columns(2)

            with fit_col:
                if rec.fit_summary:
                    st.markdown("**Why it fits:**")
                    for fit in rec.fit_summary[:4]:
                        st.markdown(f"- {fit}")

            with challenge_col:
                if rec.struggle_summary:
                    st.markdown("**Potential challenges:**")
                    for struggle in rec.struggle_summary[:4]:
                        st.markdown(f"- {struggle}")

            # Services and Learn more
            st.markdown("")
            if rec.core_services or rec.supporting_services:
                with st.expander("Azure Services"):
                    if rec.core_services:
                        st.markdown(f"**Core:** {', '.join(rec.core_services[:10])}")
                    if rec.supporting_services:
                        st.markdown(f"**Supporting:** {', '.join(rec.supporting_services[:8])}")

            if rec.learn_url:
                st.link_button("Learn more on Microsoft Docs", rec.learn_url)

        else:
            # Alternative recommendation - compact card
            # Header with score badge
            st.markdown(
                f'<div style="display:flex; justify-content:space-between; align-items:flex-start;">'
                f'<div><strong>{rec.name}</strong><br/>'
                f'<span style="color:#666; font-size:0.85rem;">{rec.pattern_name}</span></div>'
                f'<span style="background:{score_bg}; color:{score_color}; '
                f'padding:0.25rem 0.5rem; border-radius:4px; font-size:0.9rem; font-weight:bold;">'
                f'{score:.0f}%</span>'
                f'</div>',
                unsafe_allow_html=True
            )

            # Small thumbnail image (constrained height)
            if rec.diagram_url:
                try:
                    st.image(rec.diagram_url, width=280)
                except Exception:
                    pass  # Silently skip if unavailable

            # Brief description
            if rec.description:
                desc = rec.description[:150] + "..." if len(rec.description) > 150 else rec.description
                st.caption(desc)

            # Key fit point
            if rec.fit_summary:
                st.markdown(f"**Fits:** {rec.fit_summary[0]}")

            # Compact services list
            if rec.core_services:
                services = ", ".join(rec.core_services[:4])
                if len(rec.core_services) > 4:
                    services += f" +{len(rec.core_services) - 4} more"
                st.caption(f"Services: {services}")

            # Learn more link
            if rec.learn_url:
                st.markdown(f"[View details]({rec.learn_url})")
