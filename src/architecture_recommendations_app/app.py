"""Customer-facing Azure Architecture Recommendations Application."""

import json
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from architecture_recommendations_app.state import initialize_state, get_state, set_state, clear_state
from architecture_recommendations_app.utils.validation import validate_uploaded_file
from architecture_recommendations_app.components.upload_section import render_upload_section
from architecture_recommendations_app.components.results_display import render_results
from architecture_recommendations_app.components.pdf_generator import generate_pdf_report

from architecture_scorer.engine import ScoringEngine
from architecture_scorer.schema import ScoringResult


def get_catalog_path() -> str:
    """Get the catalog path from environment or default locations."""
    # 1. Environment variable
    env_path = os.environ.get("ARCHITECTURE_CATALOG_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. Local file in current directory
    local_path = Path("architecture-catalog.json")
    if local_path.exists():
        return str(local_path)

    # 3. Local file in project root
    project_root = Path(__file__).parent.parent.parent
    root_path = project_root / "architecture-catalog.json"
    if root_path.exists():
        return str(root_path)

    return None


def main() -> None:
    """Main entry point for the Streamlit app."""
    st.set_page_config(
        page_title="Azure Architecture Recommendations",
        page_icon=":cloud:",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

    # Apply custom styles
    _apply_custom_styles()

    # Initialize session state
    initialize_state()

    # Check for catalog
    catalog_path = get_catalog_path()
    if not catalog_path:
        st.error("Architecture catalog not found. Please ensure `architecture-catalog.json` exists.")
        st.info("You can generate a catalog using the Catalog Builder GUI or CLI.")
        return

    # Get current step
    current_step = get_state('current_step') or 1

    # Render based on current step
    if current_step == 1:
        _render_step1_upload(catalog_path)
    elif current_step == 2:
        _render_step2_questions(catalog_path)
    elif current_step == 3:
        _render_step3_results()

    # Footer with catalog info
    _render_footer(catalog_path)


def _apply_custom_styles() -> None:
    """Apply custom CSS for professional branding."""
    st.markdown("""
    <style>
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Step indicator styling */
    .step-indicator {
        display: flex;
        justify-content: center;
        margin-bottom: 2rem;
    }
    .step {
        padding: 0.5rem 1rem;
        margin: 0 0.5rem;
        border-radius: 20px;
        font-weight: bold;
    }
    .step-active {
        background: #0078D4;
        color: white;
    }
    .step-complete {
        background: #107C10;
        color: white;
    }
    .step-pending {
        background: #E6E6E6;
        color: #666;
    }

    /* Score badge styling */
    .score-high { background: #DFF6DD; color: #107C10; }
    .score-medium { background: #FFF4CE; color: #797673; }
    .score-low { background: #FDE7E9; color: #D83B01; }
    </style>
    """, unsafe_allow_html=True)


def _render_step_indicator(current: int) -> None:
    """Render the step progress indicator."""
    steps = ["1. Upload & Review", "2. Answer Questions", "3. Results"]

    cols = st.columns([1, 3, 1])
    with cols[1]:
        step_cols = st.columns(3)
        for i, (step_col, label) in enumerate(zip(step_cols, steps), 1):
            with step_col:
                if i < current:
                    st.markdown(f"✅ **{label}**")
                elif i == current:
                    st.markdown(f"🔵 **{label}**")
                else:
                    st.markdown(f"⚪ {label}")


def _render_step1_upload(catalog_path: str) -> None:
    """Step 1: Upload file and review application summary."""
    st.title("Azure Architecture Recommendations")
    st.markdown("Upload your application context to receive tailored architecture recommendations.")

    _render_step_indicator(1)

    st.markdown("---")
    st.subheader("Step 1: Upload Your Context File")

    # Upload section
    uploaded_file = render_upload_section()

    if uploaded_file is not None:
        file_hash = hash(uploaded_file.getvalue())

        # Check if this is a new file
        if get_state('last_file_hash') != file_hash:
            # New file - validate it
            is_valid, error_msg, data, suggestions = validate_uploaded_file(uploaded_file)

            if not is_valid:
                st.error(f"**Validation Error:** {error_msg}")
                if suggestions:
                    with st.expander("How to fix this"):
                        for suggestion in suggestions:
                            st.markdown(f"- {suggestion}")
                return

            # Store the validated data
            set_state('context_data', data)
            set_state('last_file_hash', file_hash)
            set_state('scoring_result', None)
            set_state('user_answers', {})
            set_state('questions', None)

        # Get the stored context data
        data = get_state('context_data')
        if not data:
            return

        st.markdown("---")

        # Show file summary
        _render_file_summary(data)

        st.markdown("---")

        # Get questions for next step (cache them)
        if get_state('questions') is None:
            questions = _get_questions(data, catalog_path)
            set_state('questions', questions)

        # Next step button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("Continue to Questions →", type="primary", use_container_width=True):
                set_state('current_step', 2)
                st.rerun()

    else:
        _render_placeholder()


def _render_step2_questions(catalog_path: str) -> None:
    """Step 2: Answer clarification questions."""
    st.title("Azure Architecture Recommendations")

    _render_step_indicator(2)

    st.markdown("---")
    st.subheader("Step 2: Answer These Questions")
    st.markdown("Providing answers will improve the accuracy of your recommendations. All questions are optional.")

    # Get stored questions
    questions = get_state('questions') or []

    # Collect answers
    user_answers = {}

    if questions:
        with st.container(border=True):
            for q in questions:
                # Build options list for selectbox
                options = ["-- Select (optional) --"] + [opt.value for opt in q.options]
                option_labels = {opt.value: opt.label for opt in q.options}

                # Format the question
                st.markdown(f"**{q.question_text}**")

                # Show current inference if available
                if q.current_inference:
                    confidence_text = q.inference_confidence.value if q.inference_confidence else "unknown"
                    st.caption(f"Current inference: {q.current_inference} ({confidence_text} confidence)")

                # Selectbox for answer
                selected = st.selectbox(
                    q.question_text,
                    options=options,
                    format_func=lambda x, labels=option_labels: labels.get(x, x) if x != "-- Select (optional) --" else x,
                    key=f"question_{q.question_id}",
                    label_visibility="collapsed"
                )

                if selected != "-- Select (optional) --":
                    user_answers[q.question_id] = selected

                    # Show option description if selected
                    for opt in q.options:
                        if opt.value == selected and opt.description:
                            st.caption(f"_{opt.description}_")

                st.markdown("")  # Spacer
    else:
        st.info("No additional questions needed - your context file provides sufficient information.")

    st.markdown("---")

    # Navigation buttons
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("← Back to Upload", use_container_width=True):
            set_state('current_step', 1)
            st.rerun()

    with col3:
        if st.button("Run Analysis →", type="primary", use_container_width=True):
            # Store answers and run analysis
            set_state('user_answers', user_answers)

            # Get context data
            data = get_state('context_data')
            if data:
                with st.spinner("Analyzing your application..."):
                    result = _score_context(data, catalog_path, user_answers)
                    if result:
                        set_state('scoring_result', result)
                        set_state('current_step', 3)
                        st.rerun()
                    else:
                        st.error("Analysis failed. Please try again.")


def _render_step3_results() -> None:
    """Step 3: Show results with export options."""
    st.title("Azure Architecture Recommendations")

    _render_step_indicator(3)

    st.markdown("---")
    st.subheader("Step 3: Your Recommendations")

    # Get results
    result = get_state('scoring_result')

    if not result:
        st.error("No results available. Please start over.")
        if st.button("Start New Analysis"):
            _reset_and_restart()
        return

    # Render the results
    render_results(result)

    # Export section
    st.markdown("---")
    st.subheader("Export Your Results")

    col1, col2, col3 = st.columns(3)

    with col1:
        # PDF Download
        try:
            pdf_bytes = generate_pdf_report(result)
            st.download_button(
                "📄 Download PDF Report",
                data=pdf_bytes,
                file_name=f"{result.application_name}_architecture_recommendations.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary"
            )
        except Exception as e:
            st.error(f"PDF generation error: {e}")

    with col2:
        # JSON Download
        json_str = result.model_dump_json(indent=2)
        st.download_button(
            "📋 Download JSON",
            data=json_str,
            file_name=f"{result.application_name}_recommendations.json",
            mime="application/json",
            use_container_width=True
        )

    with col3:
        # New analysis button
        if st.button("🔄 Start New Analysis", use_container_width=True):
            _reset_and_restart()


def _reset_and_restart() -> None:
    """Clear all state and restart from step 1."""
    clear_state()
    set_state('current_step', 1)
    st.rerun()


def _render_file_summary(data: list) -> None:
    """Render a summary of the uploaded file contents."""
    st.subheader("Application Summary")

    if not data or not data[0]:
        st.warning("No data found in context file")
        return

    context = data[0]

    # Application overview
    if context.get("app_overview"):
        overview = context["app_overview"][0] if context["app_overview"] else {}

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            app_name = overview.get("application", "Unknown")
            st.metric("Application", app_name)

        with col2:
            app_type = overview.get("app_type", "Unknown")
            st.metric("Type", app_type)

        with col3:
            criticality = overview.get("business_crtiticality", overview.get("business_criticality", "Unknown"))
            st.metric("Criticality", criticality)

        with col4:
            treatment = overview.get("treatment", "Unknown")
            st.metric("Treatment", treatment.title() if treatment else "Unknown")

    # Technologies detected
    technologies = context.get("detected_technology_running", [])
    if technologies:
        st.markdown("**Detected Technologies:**")
        # Show as tags/chips
        tech_str = " • ".join(technologies[:10])
        if len(technologies) > 10:
            tech_str += f" • ... and {len(technologies) - 10} more"
        st.markdown(tech_str)

    # Server summary
    servers = context.get("server_details", [])
    if servers:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Servers", len(servers))

        # Count environments
        envs = set(s.get("environment", "Unknown") for s in servers)
        with col2:
            st.metric("Environments", ", ".join(envs) if envs else "Unknown")

        # Count by OS
        os_list = [s.get("OperatingSystem", "Unknown") for s in servers]
        windows_count = sum(1 for os in os_list if os and "windows" in os.lower())
        linux_count = len(servers) - windows_count
        with col3:
            os_summary = []
            if windows_count:
                os_summary.append(f"{windows_count} Windows")
            if linux_count:
                os_summary.append(f"{linux_count} Linux")
            st.metric("Operating Systems", ", ".join(os_summary) if os_summary else "Unknown")

    # App Mod results summary
    app_mod = context.get("App Mod results", [])
    if app_mod:
        with st.expander("App Modernization Assessment"):
            for result in app_mod:
                tech = result.get("technology", "Unknown")
                st.markdown(f"**{tech}**")

                summary = result.get("summary", {})
                if summary:
                    container_ready = summary.get("container_ready", False)
                    modernization_feasible = summary.get("modernization_feasible", False)
                    st.markdown(f"- Container Ready: {'Yes' if container_ready else 'No'}")
                    st.markdown(f"- Modernization Feasible: {'Yes' if modernization_feasible else 'No'}")

                recommended = result.get("recommended_targets", [])
                if recommended:
                    st.markdown(f"- Recommended Targets: {', '.join(recommended)}")


def _get_questions(data: list, catalog_path: str) -> list:
    """Get clarification questions without full scoring."""
    try:
        # Write to temp file for engine
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            engine = ScoringEngine()
            engine.load_catalog(catalog_path)
            questions = engine.get_questions(temp_path)
            return questions
        finally:
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        st.warning(f"Could not load questions: {e}")
        return []


def _score_context(data: list, catalog_path: str, user_answers: dict) -> ScoringResult | None:
    """Score the context data using the scoring engine."""
    try:
        # Write to temp file for engine
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            engine = ScoringEngine()
            engine.load_catalog(catalog_path)
            result = engine.score(
                temp_path,
                user_answers=user_answers if user_answers else None,
                max_recommendations=5
            )
            return result
        finally:
            Path(temp_path).unlink(missing_ok=True)

    except Exception as e:
        st.error(f"Error analyzing context: {e}")
        return None


def _render_placeholder() -> None:
    """Render placeholder content when no file is uploaded."""
    st.info("""
    **Get Started:**
    1. Upload your Dr. Migrate context file (JSON format)
    2. Review the application summary
    3. Answer optional questions to improve accuracy
    4. Click "Run Analysis" to get recommendations
    5. Download your PDF report
    """)

    with st.expander("What is a context file?"):
        st.markdown("""
        A context file contains information about your application gathered by
        Dr. Migrate or similar assessment tools. It includes:

        - **Application Overview**: Name, type, business criticality, migration treatment
        - **Detected Technologies**: Runtime, frameworks, databases, middleware
        - **Server Details**: Infrastructure metrics and Azure readiness
        - **App Modernization Results**: Platform compatibility assessments

        The file should be in JSON format.
        """)


def _render_footer(catalog_path: str) -> None:
    """Render footer with catalog info."""
    try:
        catalog_stat = Path(catalog_path).stat()
        from datetime import datetime
        mod_time = datetime.fromtimestamp(catalog_stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        st.caption(f"Catalog: {Path(catalog_path).name} (Updated: {mod_time})")
    except Exception:
        pass


if __name__ == "__main__":
    main()
