"""Catalog Builder page - Build and customize architecture catalogs."""

import subprocess
import sys
from pathlib import Path

import streamlit as st

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from catalog_builder.config import CatalogConfig
from architecture_recommendations_app.state import (
    initialize_state, get_state, set_state, get_config,
    DEFAULT_REPO_URL, DEFAULT_CLONE_DIR
)
from architecture_recommendations_app.utils.sanitize import (
    safe_path, PathValidationError
)

# Import catalog builder components
from catalog_builder_gui.components.keywords_editor import render_keywords_editor
from catalog_builder_gui.components.filter_presets import render_filter_presets
from catalog_builder_gui.components.preview_panel import render_preview_panel
from catalog_builder_gui.components.config_editor import render_config_editor
from catalog_builder_gui.components.modernization_editor import render_modernization_editor


def clone_repository(repo_url: str, clone_dir: str) -> tuple[bool, str]:
    """Clone the repository to the specified directory.

    Args:
        repo_url: Git URL to clone from.
        clone_dir: User-provided directory path to clone into.

    Returns:
        Tuple of (success, message).
    """
    # Validate the clone directory path to prevent path injection
    try:
        clone_path = safe_path(clone_dir, allow_creation=True)
    except PathValidationError as e:
        return False, f"Invalid clone directory: {e}"

    if clone_path.exists():
        if (clone_path / '.git').exists() and (clone_path / 'docs').exists():
            try:
                result = subprocess.run(
                    ['git', 'pull'],
                    cwd=str(clone_path),
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                if result.returncode == 0:
                    return True, "Repository updated (git pull)"
                else:
                    return False, f"Git pull failed: {result.stderr}"
            except subprocess.TimeoutExpired:
                return False, "Git pull timed out"
            except Exception as e:
                return False, f"Error updating repo: {e}"
        else:
            return False, "Directory exists but is not the Azure Architecture Center repo"

    clone_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, str(clone_path)],
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


def ensure_config_initialized() -> None:
    """Ensure config is initialized in session state."""
    if get_state('config') is None:
        set_state('config', CatalogConfig())


@st.dialog("Catalog Builder Help")
def show_help_dialog():
    """Display help information in a modal dialog."""
    st.markdown("""
    ### How to Use the Catalog Builder

    **1. Clone the Repository**
    Use the sidebar to clone the Azure Architecture Center repository,
    or specify an existing local path.

    **2. Build Your Catalog**
    - **Quick Build**: ~51 production-ready reference architectures
    - **Full Build**: ~171 architectures including examples and solution ideas
    - **Custom Build**: Fine-tune filters and content types

    **3. Use Your Catalog**
    After generating a catalog, navigate to:
    - **Recommendations** - Analyze your applications and get architecture matches
    - **Catalog Stats** - Explore and browse the catalog contents

    ---

    **Tips:**
    - The catalog is automatically shared across all pages
    - Use "Update Repository" periodically to get the latest patterns
    - Custom configs can be saved and loaded via YAML files
    """)

    if st.button("Got it!", type="primary", use_container_width=True):
        st.rerun()


def render_sidebar() -> None:
    """Render the sidebar with repository controls."""
    st.sidebar.title("Catalog Builder")
    st.sidebar.markdown("---")

    st.sidebar.subheader("Repository")

    repo_path = get_state('repo_path', '')
    repo_valid = False

    if repo_path:
        repo = Path(repo_path)
        repo_valid = repo.exists() and (repo / 'docs').exists()

    if not repo_path or not repo_valid:
        st.sidebar.error("Repository not found!")
        st.sidebar.markdown("Clone the Azure Architecture Center repository to get started.")

        repo_url = st.sidebar.text_input(
            "Repository URL",
            value=get_state('repo_url', DEFAULT_REPO_URL),
            help="Git URL for the Azure Architecture Center repository"
        )
        set_state('repo_url', repo_url)

        clone_dir = st.sidebar.text_input(
            "Clone Directory",
            value=get_state('clone_dir', DEFAULT_CLONE_DIR),
            help="Where to clone the architecture-center repo"
        )
        set_state('clone_dir', clone_dir)

        if st.sidebar.button("Clone Repository", type="primary", use_container_width=True):
            with st.spinner("Cloning repository (this may take a few minutes)..."):
                success, message = clone_repository(repo_url, clone_dir)
                if success:
                    st.sidebar.success(message)
                    try:
                        validated_path = safe_path(clone_dir, must_exist=True)
                        set_state('repo_path', str(validated_path))
                    except PathValidationError:
                        set_state('repo_path', '')
                    st.rerun()
                else:
                    st.sidebar.error(message)

        st.sidebar.markdown("---")
        st.sidebar.markdown("**Or specify an existing path:**")

    else:
        doc_count = len(list((Path(repo_path) / 'docs').rglob('*.md')))
        st.sidebar.success(f"Repository found ({doc_count:,} docs)")

        with st.sidebar.expander("Update or Change Repository"):
            repo_url = st.text_input(
                "Repository URL",
                value=get_state('repo_url', DEFAULT_REPO_URL),
                help="Git URL for the Azure Architecture Center repository"
            )
            set_state('repo_url', repo_url)

            clone_dir = st.text_input(
                "Clone Directory",
                value=get_state('clone_dir', DEFAULT_CLONE_DIR),
                help="Where to clone the architecture-center repo"
            )
            set_state('clone_dir', clone_dir)

            if st.button("Update Repository (git pull)", use_container_width=True):
                with st.spinner("Updating repository..."):
                    success, message = clone_repository(repo_url, clone_dir)
                    if success:
                        st.success(message)
                        try:
                            validated_path = safe_path(clone_dir, must_exist=True)
                            set_state('repo_path', str(validated_path))
                        except PathValidationError:
                            set_state('repo_path', '')
                        st.rerun()
                    else:
                        st.error(message)

    new_repo_path = st.sidebar.text_input(
        "Repository Path",
        value=repo_path,
        placeholder="/path/to/architecture-center",
        help="Path to the cloned Azure Architecture Center repository"
    )
    if new_repo_path != repo_path:
        set_state('repo_path', new_repo_path)
        st.rerun()

    st.sidebar.markdown("---")

    # Config file upload
    st.sidebar.subheader("Configuration")
    uploaded_file = st.sidebar.file_uploader(
        "Load Config File",
        type=['yaml', 'yml'],
        help="Upload an existing catalog-config.yaml file"
    )

    if uploaded_file is not None:
        import yaml
        try:
            data = yaml.safe_load(uploaded_file.read())
            config = CatalogConfig.model_validate(data)
            set_state('config', config)
            st.sidebar.success("Config loaded!")
        except Exception as e:
            st.sidebar.error(f"Error loading config: {e}")

    # Reset button
    if st.sidebar.button("Reset to Defaults", type="secondary"):
        set_state('config', CatalogConfig())
        set_state('active_filters', {'products': [], 'categories': [], 'topics': []})
        st.sidebar.success("Reset complete!")
        st.rerun()

    # Footer with credits and GitHub link
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="text-align: center; padding: 1rem 0; color: #666; font-size: 0.85rem;">
            <p style="margin-bottom: 0.5rem;">
                Built by <a href="https://askadam.cloud/#about" target="_blank"><strong>Adam Brown</strong></a><br/>
                with help from Claude & Copilot 😉
            </p>
            <a href="https://github.com/adamswbrown/azure-architecture-categoriser" target="_blank">
                <img src="https://img.shields.io/badge/View_on-GitHub-181717?style=for-the-badge&logo=github" alt="View on GitHub"/>
            </a>
        </div>
        """,
        unsafe_allow_html=True
    )


def main():
    st.set_page_config(
        page_title="Catalog Builder - Azure Architecture Recommendations",
        page_icon=":wrench:",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize shared state (includes catalog builder state)
    initialize_state()

    # Ensure config is initialized
    ensure_config_initialized()

    # Render sidebar
    render_sidebar()

    # Main content - title with help button
    title_col, help_col = st.columns([10, 1])
    with title_col:
        st.title("Azure Architecture Catalog Builder")
    with help_col:
        st.markdown("<br>", unsafe_allow_html=True)  # Align with title
        if st.button("?", help="Show help", key="help_button"):
            show_help_dialog()

    # Compact intro
    if not get_state('repo_path'):
        st.info("**Step 1:** Clone the Azure Architecture Center repository using the sidebar to get started.")

    st.caption(
        "Scans the [Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/) "
        "to create a catalog of architecture patterns for the **Recommendations** page. "
        "**Quick Start:** Clone repo (sidebar) → Generate catalog (Build tab)"
    )

    # Tabs for different functionality
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Build Catalog",
        "Filter Presets",
        "Keyword Dictionaries",
        "Config Editor",
        "Modernization Options"
    ])

    with tab1:
        render_preview_panel()

    with tab2:
        render_filter_presets()

    with tab3:
        render_keywords_editor()

    with tab4:
        render_config_editor()

    with tab5:
        render_modernization_editor()


if __name__ == "__main__":
    main()
