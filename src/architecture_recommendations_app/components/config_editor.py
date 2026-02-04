"""Configuration editor component for the recommendations app."""

import streamlit as st

from architecture_scorer.config import (
    get_config,
    find_config_file,
)


def render_config_editor() -> None:
    """Render the configuration editor in the sidebar."""
    st.subheader("Scoring Configuration")

    # Find or create config file path
    config_path = find_config_file()
    if config_path:
        st.caption(f"Config: `{config_path.name}`")
    else:
        st.caption("Using default configuration")

    # Get current config
    config = get_config()

    # Main config sections in expanders
    with st.expander("Confidence Thresholds", expanded=False):
        st.caption("Adjust when recommendations are classified as High/Medium/Low confidence")

        conf = config.confidence_thresholds

        high_score = st.slider(
            "High confidence min score",
            min_value=40.0, max_value=90.0,
            value=conf.high_score_threshold,
            step=5.0,
            help="Minimum match score (%) for High confidence"
        )

        medium_score = st.slider(
            "Medium confidence min score",
            min_value=20.0, max_value=70.0,
            value=conf.medium_score_threshold,
            step=5.0,
            help="Minimum match score (%) for Medium confidence"
        )

        # Show Low threshold indicator
        st.caption(f"**Low confidence:** Scores below {medium_score:.0f}%")

        # Validate thresholds
        if high_score <= medium_score:
            st.error("High threshold must be greater than Medium threshold")
        else:
            conf.high_score_threshold = high_score
            conf.medium_score_threshold = medium_score

    with st.expander("Scoring Weights", expanded=False):
        st.caption("Adjust how much each factor contributes to the match score")

        weights = config.scoring_weights

        col1, col2 = st.columns(2)

        with col1:
            weights.treatment_alignment = st.slider(
                "Treatment alignment",
                min_value=0.0, max_value=0.5,
                value=weights.treatment_alignment,
                step=0.05,
                help="Weight for migration treatment match"
            )

            weights.platform_compatibility = st.slider(
                "Platform compatibility",
                min_value=0.0, max_value=0.5,
                value=weights.platform_compatibility,
                step=0.05,
                help="Weight for platform/technology match"
            )

            weights.availability_alignment = st.slider(
                "Availability alignment",
                min_value=0.0, max_value=0.3,
                value=weights.availability_alignment,
                step=0.02,
                help="Weight for availability requirements (boosted when user answers)"
            )

            weights.service_overlap = st.slider(
                "Service overlap",
                min_value=0.0, max_value=0.3,
                value=weights.service_overlap,
                step=0.02,
                help="Weight for Azure service overlap"
            )

        with col2:
            weights.runtime_model_compatibility = st.slider(
                "Runtime model",
                min_value=0.0, max_value=0.3,
                value=weights.runtime_model_compatibility,
                step=0.02,
                help="Weight for runtime model match"
            )

            weights.app_mod_recommended = st.slider(
                "App Mod boost",
                min_value=0.0, max_value=0.3,
                value=weights.app_mod_recommended,
                step=0.02,
                help="Boost when App Mod recommends target"
            )

            weights.operating_model_fit = st.slider(
                "Operating model fit",
                min_value=0.0, max_value=0.2,
                value=weights.operating_model_fit,
                step=0.02,
                help="Weight for operational maturity (boosted when user answers)"
            )

            weights.cost_posture_alignment = st.slider(
                "Cost alignment",
                min_value=0.0, max_value=0.2,
                value=weights.cost_posture_alignment,
                step=0.02,
                help="Weight for cost strategy match (boosted when user answers)"
            )

            weights.security_alignment = st.slider(
                "Security alignment",
                min_value=0.0, max_value=0.2,
                value=weights.security_alignment,
                step=0.02,
                help="Weight for security requirements alignment"
            )

        # Show weight sum
        total = (
            weights.treatment_alignment +
            weights.runtime_model_compatibility +
            weights.platform_compatibility +
            weights.app_mod_recommended +
            weights.service_overlap +
            weights.browse_tag_overlap +
            weights.availability_alignment +
            weights.operating_model_fit +
            weights.complexity_tolerance +
            weights.cost_posture_alignment +
            weights.security_alignment
        )
        if abs(total - 1.0) > 0.1:
            st.warning(f"Weights sum to {total:.2f} (should be ~1.0)")
        else:
            st.success(f"Weights sum: {total:.2f}")

    with st.expander("Quality Weights", expanded=False):
        st.caption("How catalog quality affects match scores")

        quality = config.quality_weights

        quality.curated = st.slider(
            "Curated weight",
            min_value=0.5, max_value=1.0,
            value=quality.curated,
            step=0.05,
            help="Score multiplier for curated architectures"
        )

        quality.ai_enriched = st.slider(
            "AI Enriched weight",
            min_value=0.5, max_value=1.0,
            value=quality.ai_enriched,
            step=0.05,
            help="Score multiplier for AI-enriched architectures"
        )

        quality.ai_suggested = st.slider(
            "AI Suggested weight",
            min_value=0.5, max_value=1.0,
            value=quality.ai_suggested,
            step=0.05,
            help="Score multiplier for AI-suggested architectures"
        )

        quality.example_only = st.slider(
            "Example weight",
            min_value=0.5, max_value=1.0,
            value=quality.example_only,
            step=0.05,
            help="Score multiplier for example-only architectures"
        )

