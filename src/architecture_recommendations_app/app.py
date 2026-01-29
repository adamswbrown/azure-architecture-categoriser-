"""Customer-facing Azure Architecture Recommendations Application."""

import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
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
from architecture_recommendations_app.components.config_editor import render_config_editor

from architecture_scorer.engine import ScoringEngine
from architecture_scorer.schema import ScoringResult


def get_catalog_path() -> str:
    """Get the catalog path from session state, environment, or default locations."""
    # 0. Session state (user-selected catalog)
    session_catalog = get_state('catalog_path')
    if session_catalog and Path(session_catalog).exists():
        return session_catalog

    # 1. Environment variable
    env_path = os.environ.get("ARCHITECTURE_CATALOG_PATH")
    if env_path and Path(env_path).exists():
        set_state('catalog_source', 'environment')
        return env_path

    # 2. Local file in current directory
    local_path = Path("architecture-catalog.json")
    if local_path.exists():
        set_state('catalog_source', 'current_directory')
        return str(local_path.resolve())

    # 3. Local file in project root
    project_root = Path(__file__).parent.parent.parent
    root_path = project_root / "architecture-catalog.json"
    if root_path.exists():
        set_state('catalog_source', 'project_root')
        return str(root_path.resolve())

    return None


def get_catalog_info(catalog_path: str) -> dict:
    """Get information about the catalog."""
    info = {
        'path': catalog_path,
        'filename': Path(catalog_path).name,
        'size_kb': 0,
        'last_modified': None,
        'architecture_count': 0,
        'source': get_state('catalog_source') or 'unknown'
    }

    try:
        path = Path(catalog_path)
        stat = path.stat()
        info['size_kb'] = round(stat.st_size / 1024, 1)

        from datetime import datetime
        info['last_modified'] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

        # Count architectures
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog_data = json.load(f)
            if isinstance(catalog_data, dict) and 'architectures' in catalog_data:
                info['architecture_count'] = len(catalog_data['architectures'])
            elif isinstance(catalog_data, list):
                info['architecture_count'] = len(catalog_data)

    except Exception:
        pass

    return info


def get_catalog_age_days(catalog_path: str) -> int | None:
    """Get the age of the catalog in days."""
    try:
        path = Path(catalog_path)
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime)
        age = datetime.now() - modified
        return age.days
    except Exception:
        return None


def is_catalog_stale(catalog_path: str, threshold_days: int = 30) -> bool:
    """Check if catalog is older than threshold."""
    age = get_catalog_age_days(catalog_path)
    if age is None:
        return False
    return age > threshold_days


def get_default_repo_path() -> Path:
    """Get the default path for the architecture-center repo."""
    return Path.home() / "architecture-center"


def clone_or_update_repo(repo_path: Path, progress_callback=None) -> tuple[bool, str]:
    """Clone or update the architecture-center repository.

    Returns (success, message) tuple.
    """
    repo_url = "https://github.com/MicrosoftDocs/architecture-center.git"

    if progress_callback:
        progress_callback("Checking repository...")

    # Check if repo already exists
    if repo_path.exists():
        if (repo_path / '.git').exists() and (repo_path / 'docs').exists():
            # Try to pull latest
            if progress_callback:
                progress_callback("Updating repository (git pull)...")
            try:
                result = subprocess.run(
                    ['git', 'pull'],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    return True, "Repository updated"
                else:
                    return False, f"Git pull failed: {result.stderr}"
            except subprocess.TimeoutExpired:
                return False, "Git pull timed out"
            except Exception as e:
                return False, f"Error updating repo: {e}"
        else:
            return False, f"Directory exists but is not the architecture-center repo: {repo_path}"

    # Clone the repository
    if progress_callback:
        progress_callback("Cloning repository (this may take a few minutes)...")

    repo_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=300
        )
        if result.returncode == 0:
            return True, "Repository cloned successfully"
        else:
            return False, f"Git clone failed: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, "Git clone timed out (>5 minutes)"
    except FileNotFoundError:
        return False, "Git is not installed or not in PATH"
    except Exception as e:
        return False, f"Error cloning repo: {e}"


def build_catalog_from_repo(repo_path: Path, output_path: Path, progress_callback=None) -> tuple[bool, str, int]:
    """Build the catalog from the repository.

    Returns (success, message, architecture_count) tuple.
    """
    try:
        from catalog_builder.catalog import CatalogBuilder

        if progress_callback:
            progress_callback("Initializing catalog builder...")

        builder = CatalogBuilder(repo_path)

        if progress_callback:
            progress_callback("Scanning repository and building catalog...")

        catalog = builder.build()

        if progress_callback:
            progress_callback("Saving catalog...")

        # Save the catalog
        import json
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(catalog.model_dump(), f, indent=2, default=str)

        return True, "Catalog built successfully", catalog.total_architectures

    except ImportError:
        return False, "Catalog builder not installed. Run: pip install -e .", 0
    except Exception as e:
        return False, f"Error building catalog: {e}", 0


def main() -> None:
    """Main entry point for the Streamlit app."""
    st.set_page_config(
        page_title="Azure Architecture Recommendations",
        page_icon=":cloud:",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Apply custom styles
    _apply_custom_styles()

    # Initialize session state
    initialize_state()

    # Render sidebar with catalog configuration
    _render_sidebar()

    # Check for catalog
    catalog_path = get_catalog_path()
    if not catalog_path:
        st.error("Architecture catalog not found.")
        st.info("""
        **To get started, you need an architecture catalog.**

        **Option 1:** Generate one using the Catalog Builder:
        ```bash
        ./bin/start-catalog-builder-gui.sh
        ```

        **Option 2:** Use the sidebar to select an existing catalog file.

        **Option 3:** Set the environment variable:
        ```bash
        export ARCHITECTURE_CATALOG_PATH=/path/to/catalog.json
        ```
        """)
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


def _render_sidebar() -> None:
    """Render sidebar with catalog configuration and information."""
    with st.sidebar:
        st.title("Configuration")

        # Catalog section
        st.subheader("Architecture Catalog")

        catalog_path = get_catalog_path()

        if catalog_path:
            info = get_catalog_info(catalog_path)

            # Show current catalog info
            st.success(f"**{info['architecture_count']}** architectures loaded")

            with st.expander("Catalog Details", expanded=True):
                st.markdown(f"**File:** `{info['filename']}`")

                # Show source
                source_labels = {
                    'environment': '`ARCHITECTURE_CATALOG_PATH` env var',
                    'current_directory': 'Current directory',
                    'project_root': 'Project root',
                    'user_selected': 'User selected',
                    'unknown': 'Auto-detected'
                }
                source = info.get('source', 'unknown')
                st.markdown(f"**Source:** {source_labels.get(source, source)}")

                st.markdown(f"**Last Updated:** {info['last_modified'] or 'Unknown'}")
                st.markdown(f"**Size:** {info['size_kb']} KB")

                # Show full path in a copyable format
                st.code(info['path'], language=None)

            # Check catalog freshness and show warning if stale
            age_days = get_catalog_age_days(catalog_path)
            if age_days is not None and age_days > 30:
                st.warning(f"**Catalog is {age_days} days old.** Azure architectures may have been updated.")

                if st.button("Refresh Catalog", type="primary", use_container_width=True,
                           help="Update from Azure Architecture Center"):
                    _refresh_catalog()

        else:
            st.warning("No catalog found")

            # Offer to generate a catalog when none exists
            st.info("Click below to generate a catalog from the Azure Architecture Center.")
            if st.button("Generate Catalog", type="primary", use_container_width=True):
                _refresh_catalog()

        st.markdown("---")

        # Custom catalog selection
        st.subheader("Load Different Catalog")

        uploaded_catalog = st.file_uploader(
            "Upload catalog JSON",
            type=['json'],
            key="catalog_upload",
            help="Upload a custom architecture-catalog.json file"
        )

        if uploaded_catalog is not None:
            try:
                # Validate it's a valid catalog
                catalog_data = json.load(uploaded_catalog)
                if isinstance(catalog_data, dict) and 'architectures' in catalog_data:
                    arch_count = len(catalog_data['architectures'])
                elif isinstance(catalog_data, list):
                    arch_count = len(catalog_data)
                else:
                    st.error("Invalid catalog format")
                    return

                # Save to temp location
                temp_dir = Path(tempfile.gettempdir())
                temp_catalog = temp_dir / "uploaded-architecture-catalog.json"

                # Reset file position and save
                uploaded_catalog.seek(0)
                with open(temp_catalog, 'w', encoding='utf-8') as f:
                    json.dump(catalog_data, f, indent=2)

                set_state('catalog_path', str(temp_catalog))
                set_state('catalog_source', 'user_selected')
                st.success(f"Loaded catalog with {arch_count} architectures")

                # Clear any existing results since catalog changed
                set_state('scoring_result', None)
                set_state('questions', None)

                st.rerun()

            except json.JSONDecodeError:
                st.error("Invalid JSON file")
            except Exception as e:
                st.error(f"Error loading catalog: {e}")

        # Or specify a path
        catalog_input = st.text_input(
            "Or enter catalog path",
            placeholder="/path/to/architecture-catalog.json",
            key="catalog_path_input",
            help="Full path to an architecture catalog JSON file"
        )

        if catalog_input and st.button("Load Catalog", use_container_width=True):
            if Path(catalog_input).exists():
                set_state('catalog_path', catalog_input)
                set_state('catalog_source', 'user_selected')
                set_state('scoring_result', None)
                set_state('questions', None)
                st.success("Catalog loaded!")
                st.rerun()
            else:
                st.error("File not found")

        # Reset to auto-detect
        if get_state('catalog_source') == 'user_selected':
            if st.button("Reset to Auto-detect", use_container_width=True):
                set_state('catalog_path', None)
                set_state('catalog_source', None)
                set_state('scoring_result', None)
                set_state('questions', None)
                st.rerun()

        st.markdown("---")

        # Custom Catalog Builder section
        st.subheader("Build Custom Catalog")
        st.caption("Create a filtered catalog with specific products, categories, or topics.")

        if st.button("Open Catalog Builder", use_container_width=True,
                    help="Launch the Catalog Builder GUI for advanced filtering"):
            _launch_catalog_builder()

        st.markdown("---")

        # Scoring configuration section
        render_config_editor()

        st.markdown("---")

        # Help section
        with st.expander("Help"):
            st.markdown("""
            **Where does the catalog come from?**

            The app looks for a catalog in this order:
            1. User-selected (upload or path)
            2. `ARCHITECTURE_CATALOG_PATH` env var
            3. `./architecture-catalog.json`
            4. Project root `architecture-catalog.json`

            **Quick Refresh vs Custom Catalog:**

            - **Refresh Catalog** - Downloads latest Azure Architecture Center and rebuilds with default settings
            - **Build Custom Catalog** - Opens the Catalog Builder GUI for advanced filtering by product, category, or topic

            **Manual CLI options:**
            ```bash
            # GUI with full filtering options
            ./bin/start-catalog-builder-gui.sh

            # CLI for scripting
            catalog-builder build-catalog \\
              --repo-path ./architecture-center \\
              --product azure-kubernetes-service \\
              --out my-catalog.json
            ```
            """)


def _refresh_catalog() -> None:
    """Refresh the catalog by cloning/updating repo and rebuilding."""
    # Determine paths
    repo_path = get_default_repo_path()
    # Output to project root
    project_root = Path(__file__).parent.parent.parent
    output_path = project_root / "architecture-catalog.json"

    # Create a status container
    status_container = st.container()

    with status_container:
        st.subheader("Refreshing Catalog")
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Step 1: Clone or update repo (0-40%)
        status_text.text("Step 1/2: Updating Azure Architecture Center repository...")
        progress_bar.progress(5)

        success, message = clone_or_update_repo(
            repo_path,
            progress_callback=lambda msg: status_text.text(f"Step 1/2: {msg}")
        )

        if not success:
            st.error(f"Repository update failed: {message}")
            st.info("Make sure Git is installed and you have internet access.")
            return

        progress_bar.progress(40)
        st.success(f"Repository: {message}")

        # Step 2: Build catalog (40-100%)
        status_text.text("Step 2/2: Building catalog from repository...")
        progress_bar.progress(50)

        success, message, arch_count = build_catalog_from_repo(
            repo_path,
            output_path,
            progress_callback=lambda msg: status_text.text(f"Step 2/2: {msg}")
        )

        if not success:
            st.error(f"Catalog build failed: {message}")
            return

        progress_bar.progress(100)
        status_text.text("Complete!")

        st.success(f"Catalog updated: **{arch_count}** architectures from Azure Architecture Center")
        st.info(f"Saved to: `{output_path}`")

        # Clear cached state and reload
        set_state('catalog_path', str(output_path))
        set_state('catalog_source', 'project_root')
        set_state('scoring_result', None)
        set_state('questions', None)

        if st.button("Continue", type="primary"):
            st.rerun()


def _launch_catalog_builder() -> None:
    """Launch the Catalog Builder GUI in a new process."""
    project_root = Path(__file__).parent.parent.parent

    # Try to find the launch script
    launch_script = project_root / "bin" / "start-catalog-builder-gui.sh"
    launch_script_ps = project_root / "bin" / "start-catalog-builder-gui.ps1"

    st.info("**Launching Catalog Builder GUI...**")
    st.caption("The Catalog Builder will open in a new browser tab at http://localhost:8502")

    try:
        import platform
        import subprocess

        if platform.system() == "Windows":
            if launch_script_ps.exists():
                subprocess.Popen(
                    ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(launch_script_ps)],
                    cwd=project_root,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            else:
                # Fallback to direct streamlit command
                subprocess.Popen(
                    ["streamlit", "run", "src/catalog_builder_gui/app.py", "--server.port", "8502"],
                    cwd=project_root,
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
        else:
            # macOS/Linux
            if launch_script.exists():
                subprocess.Popen(
                    ["bash", str(launch_script)],
                    cwd=project_root,
                    start_new_session=True
                )
            else:
                # Fallback to direct streamlit command
                subprocess.Popen(
                    ["streamlit", "run", "src/catalog_builder_gui/app.py", "--server.port", "8502"],
                    cwd=project_root,
                    start_new_session=True
                )

        st.success("Catalog Builder launched! Check your browser for a new tab at http://localhost:8502")
        st.markdown("[Open Catalog Builder](http://localhost:8502)")

    except FileNotFoundError:
        st.error("Could not launch Catalog Builder. Streamlit may not be installed correctly.")
        st.markdown("""
        **Try launching manually:**
        ```bash
        ./bin/start-catalog-builder-gui.sh
        ```
        """)
    except Exception as e:
        st.error(f"Error launching Catalog Builder: {e}")


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




if __name__ == "__main__":
    main()
