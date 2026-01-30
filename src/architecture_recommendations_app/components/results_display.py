"""Results display component for the recommendations app."""

import streamlit as st

from architecture_scorer.schema import ScoringResult, ArchitectureRecommendation, ClarificationQuestion


# Quality badge colors
QUALITY_LABELS = {
    "curated": ("Curated", "#0078D4", "white"),
    "ai_enriched": ("AI Enriched", "#5C2D91", "white"),
    "ai_suggested": ("AI Suggested", "#FFB900", "black"),
    "example_only": ("Example", "#E6E6E6", "#666"),
}

# Confidence level styling - base descriptions
CONFIDENCE_STYLES = {
    "High": ("#107C10", "Strong match with clear requirements"),
    "Medium": ("#FFB900", "Good match based on available data"),
    "Low": ("#D83B01", "Limited data - answering questions may improve recommendations"),
}


def render_user_answers(
    questions: list[ClarificationQuestion],
    answers: dict[str, str]
) -> None:
    """Render the user's answers to clarification questions.

    Args:
        questions: List of clarification questions
        answers: Dictionary mapping question_id to selected value
    """
    if not answers:
        return

    with st.expander("Your Answers", expanded=False):
        for q in questions:
            if q.question_id in answers:
                answer_value = answers[q.question_id]
                # Find the label for this answer
                answer_label = answer_value
                for opt in q.options:
                    if opt.value == answer_value:
                        answer_label = opt.label
                        break

                st.markdown(
                    f"**{q.question_text}**  \n"
                    f"<span style='color:#0078D4;'>{answer_label}</span>",
                    unsafe_allow_html=True
                )


def render_results(result: ScoringResult, has_unanswered_questions: bool = False) -> None:
    """Render the scoring results.

    Args:
        result: The scoring result to display
        has_unanswered_questions: Whether there are unanswered clarification questions
    """
    # Summary section
    _render_summary(result)

    st.markdown("---")

    # Check if we have recommendations
    if not result.recommendations:
        _render_no_matches(result, has_unanswered_questions)
        return

    # Primary recommendation (highlighted)
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


def _render_no_matches(result: ScoringResult, has_unanswered_questions: bool) -> None:
    """Render a helpful message when no strong matches are found.

    Args:
        result: The scoring result (with empty recommendations)
        has_unanswered_questions: Whether clarification questions remain unanswered
    """
    summary = result.summary

    # Warning banner
    st.markdown(
        """
        <div style="background:#FFF4CE; border-left:4px solid #FFB900; padding:1rem;
                    border-radius:0 8px 8px 0; margin-bottom:1rem;">
            <div style="display:flex; align-items:center; gap:0.5rem;">
                <span style="font-size:1.5rem;">⚠️</span>
                <span style="font-weight:600; font-size:1.1rem;">No Strong Matches Found</span>
            </div>
            <p style="margin:0.5rem 0 0 2rem; color:#5C4813;">
                We couldn't find architectures that strongly match your application's requirements.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Two-column layout for details
    col1, col2 = st.columns(2)

    with col1:
        # What we understood
        st.markdown("**What we understood:**")
        if summary.key_drivers:
            for driver in summary.key_drivers[:5]:
                st.markdown(f"- {driver}")
        else:
            st.caption("_Limited information extracted from context file_")

    with col2:
        # Possible reasons
        st.markdown("**Possible reasons:**")
        reasons = [
            "Unique combination of requirements",
            "Missing details about scale or availability needs",
            "Specialized technology stack not in catalog",
            "Context file may need more detail",
        ]
        for reason in reasons[:4]:
            st.markdown(f"- {reason}")

    st.markdown("")

    # Suggestions section
    with st.container(border=True):
        st.markdown("**💡 Suggestions to improve results:**")

        suggestions = []

        if has_unanswered_questions:
            suggestions.append(
                "**Answer the clarification questions** - "
                "Providing more details can significantly improve matching"
            )

        suggestions.extend([
            "**Review your context file** - Ensure it includes technology stack, "
            "scalability needs, and compliance requirements",
            "**Browse Azure Architecture Center** - Explore patterns manually at "
            "[learn.microsoft.com/azure/architecture](https://learn.microsoft.com/azure/architecture/browse)",
            "**Contact your Azure specialist** - For complex or unique scenarios, "
            "consult with an Azure solutions architect",
        ])

        for suggestion in suggestions:
            st.markdown(f"- {suggestion}")

    # Show key considerations if any
    if summary.key_risks:
        st.markdown("")
        with st.expander("Key Considerations", expanded=False):
            for risk in summary.key_risks[:5]:
                st.markdown(f"- {risk}")


def _render_summary(result: ScoringResult) -> None:
    """Render a compact summary section."""
    summary = result.summary

    # Get confidence styling
    conf_color, _ = CONFIDENCE_STYLES.get(
        summary.confidence_level,
        ("#666", "")
    )

    # Compact metrics row using CSS grid
    st.markdown(
        f"""
        <div style="background:#f8f9fa; border-radius:8px; padding:0.75rem 1rem; margin-bottom:1rem;">
            <div style="display:grid; grid-template-columns:2fr 1fr 1fr 1fr; gap:1rem; align-items:center;">
                <div>
                    <span style="color:#666; font-size:0.7rem; text-transform:uppercase;">Application</span><br/>
                    <span style="font-weight:600; font-size:1.1rem;">{result.application_name}</span>
                </div>
                <div style="text-align:center;">
                    <span style="color:#666; font-size:0.7rem; text-transform:uppercase;">Confidence</span><br/>
                    <span style="font-weight:600; font-size:1.1rem; color:{conf_color};">{summary.confidence_level}</span>
                </div>
                <div style="text-align:center;">
                    <span style="color:#666; font-size:0.7rem; text-transform:uppercase;">Recommendations</span><br/>
                    <span style="font-weight:600; font-size:1.1rem;">{len(result.recommendations)}</span>
                </div>
                <div style="text-align:center;">
                    <span style="color:#666; font-size:0.7rem; text-transform:uppercase;">Evaluated</span><br/>
                    <span style="font-weight:600; font-size:1.1rem;">{result.catalog_architecture_count}</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Key insights as collapsed expanders side by side
    col1, col2 = st.columns(2)

    with col1:
        if summary.key_drivers:
            with st.expander("Key Drivers - Why these recommendations", expanded=False):
                for driver in summary.key_drivers[:4]:
                    st.markdown(f"- {driver}")

    with col2:
        if summary.key_risks:
            with st.expander("Key Considerations - Things to review", expanded=False):
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

            # Architecture diagram (if available) - centered, constrained width for primary
            if rec.diagram_url:
                st.markdown("")  # Spacer
                try:
                    # Use expander with centered image - smaller ratio for more compact display
                    with st.expander("View Architecture Diagram", expanded=True):
                        # Center the image using columns - narrower center for smaller diagram
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col2:
                            st.image(rec.diagram_url, use_container_width=True)
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
                st.markdown(
                    f'<a href="{rec.learn_url}" target="_blank" style="display:inline-block; '
                    f'background:#0078D4; color:white; padding:0.5rem 1rem; border-radius:4px; '
                    f'text-decoration:none; font-weight:500; margin-top:0.5rem;">'
                    f'Learn more on Microsoft Docs &rarr;</a>',
                    unsafe_allow_html=True
                )

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

            # Learn more link - styled as visible button
            if rec.learn_url:
                st.markdown(
                    f'<a href="{rec.learn_url}" target="_blank" style="display:inline-block; '
                    f'background:#0078D4; color:white; padding:0.3rem 0.6rem; border-radius:4px; '
                    f'text-decoration:none; font-size:0.85rem; margin-top:0.3rem;">'
                    f'View details &rarr;</a>',
                    unsafe_allow_html=True
                )
