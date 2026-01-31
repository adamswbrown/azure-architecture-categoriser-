"""Main Streamlit application for catalog builder configuration."""

import subprocess
import sys
from pathlib import Path

import streamlit as st

# Add src to path for imports
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from catalog_builder_gui.state import initialize_state, get_state, set_state

from catalog_builder_gui.components.keywords_editor import render_keywords_editor
from catalog_builder_gui.components.filter_presets import render_filter_presets
from catalog_builder_gui.components.preview_panel import render_preview_panel
from catalog_builder_gui.components.config_editor import render_config_editor

# Import path validation utilities
from architecture_recommendations_app.utils.sanitize import (
    safe_path, PathValidationError
)

# Default repository URL
DEFAULT_REPO_URL = "https://github.com/MicrosoftDocs/architecture-center.git"
DEFAULT_CLONE_DIR = str(Path.home() / "architecture-center")


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

    # Check if directory already exists with a valid repo
    if clone_path.exists():
        if (clone_path / '.git').exists() and (clone_path / 'docs').exists():
            # Try to pull latest
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
            return False, f"Directory exists but is not the Azure Architecture Center repo (missing 'docs' folder): {clone_dir}. Try a different path like ~/architecture-center"

    # Create parent directory if needed
    clone_path.parent.mkdir(parents=True, exist_ok=True)

    # Clone the repository
    try:
        result = subprocess.run(
            ['git', 'clone', '--depth', '1', repo_url, str(clone_path)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout for clone
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


def render_sidebar() -> None:
    """Render the sidebar with common controls."""
    st.sidebar.title("Catalog Builder")
    st.sidebar.markdown("---")

    # Repository section
    st.sidebar.subheader("Repository")

    repo_path = get_state('repo_path', '')
    repo_valid = False

    if repo_path:
        repo = Path(repo_path)
        repo_valid = repo.exists() and (repo / 'docs').exists()

    # Show prominent warning if no repo found
    if not repo_path or not repo_valid:
        st.sidebar.error("⚠️ Repository not found!")
        st.sidebar.markdown("Clone the Azure Architecture Center repository to get started.")

        # Clone section (expanded when no repo)
        repo_url = st.sidebar.text_input(
            "Repository URL",
            value=get_state('repo_url', DEFAULT_REPO_URL),
            help="Git URL for the Azure Architecture Center repository"
        )
        set_state('repo_url', repo_url)

        clone_dir = st.sidebar.text_input(
            "Clone Directory",
            value=get_state('clone_dir', DEFAULT_CLONE_DIR),
            help="Where to clone the architecture-center repo (NOT this project's directory)"
        )
        set_state('clone_dir', clone_dir)

        if st.sidebar.button("Clone Repository", type="primary", use_container_width=True):
            with st.spinner("Cloning repository (this may take a few minutes)..."):
                success, message = clone_repository(repo_url, clone_dir)
                if success:
                    st.sidebar.success(message)
                    # Resolve symlinks for consistent paths using validated path
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
        # Repo found - show success and collapse clone options
        doc_count = len(list((Path(repo_path) / 'docs').rglob('*.md')))
        st.sidebar.success(f"✓ Repository found ({doc_count:,} docs)")

        # Clone/update in expander when repo exists
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
                help="Where to clone the architecture-center repo (NOT this project's directory)"
            )
            set_state('clone_dir', clone_dir)

            if st.button("Update Repository (git pull)", use_container_width=True):
                with st.spinner("Updating repository..."):
                    success, message = clone_repository(repo_url, clone_dir)
                    if success:
                        st.success(message)
                        # Resolve symlinks for consistent paths using validated path
                        try:
                            validated_path = safe_path(clone_dir, must_exist=True)
                            set_state('repo_path', str(validated_path))
                        except PathValidationError:
                            set_state('repo_path', '')
                        st.rerun()
                    else:
                        st.error(message)

    # Repository path input (can be set manually or via clone)
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
        from catalog_builder.config import CatalogConfig
        try:
            data = yaml.safe_load(uploaded_file.read())
            config = CatalogConfig.model_validate(data)
            set_state('config', config)
            st.sidebar.success("Config loaded!")
        except Exception as e:
            st.sidebar.error(f"Error loading config: {e}")

    # Reset button
    if st.sidebar.button("Reset to Defaults", type="secondary"):
        from catalog_builder.config import CatalogConfig
        set_state('config', CatalogConfig())
        set_state('active_filters', {'products': [], 'categories': [], 'topics': []})
        st.sidebar.success("Reset complete!")
        st.rerun()


def main() -> None:
    """Main entry point for the Streamlit app."""
    st.set_page_config(
        page_title="Catalog Builder Config",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Initialize session state
    initialize_state()

    # Render sidebar
    render_sidebar()

    # Main content area with tabs
    st.title("Azure Architecture Catalog Builder")

    # Welcome/Overview section
    with st.expander("📖 Getting Started", expanded=not get_state('repo_path')):
        st.markdown("""
        ### What This Tool Does

        The Catalog Builder scans the [Azure Architecture Center](https://learn.microsoft.com/en-us/azure/architecture/)
        repository and creates a structured catalog of architecture patterns. This catalog is used by the
        **Architecture Scorer** to recommend patterns for your applications.

        ### Quick Start

        1. **Clone the Repository** (sidebar) - Get the Azure Architecture Center content
        2. **Generate Catalog** (tab 1) - Build `architecture-catalog.json` with defaults (~170 architectures)

        **Optional customization:**
        - **Preview** - See what will be included before generating
        - **Adjust Filters** (tab 2) - Customize which architectures to include

        ### Default Settings

        The builder uses sensible defaults that work for most use cases:

        | Setting | Default | Effect |
        |---------|---------|--------|
        | **Topic Filter** | reference-architecture, example-scenario, solution-idea | All topic types |
        | **Exclude Examples** | No | All ~170 architectures (curated + examples) |
        | **Product Filter** | None (all) | No product restrictions |
        | **Category Filter** | None (all) | No category restrictions |
        | **Require YML** | No | Includes both YML-tagged and detected architectures |

        **Note:** Example scenarios (marked `example_only`) are learning/POC architectures, not
        production-ready patterns. Check "Exclude Examples" in Filters for production catalogs only.

        ### Workflow

        ```
        Repository → Detection → Filtering → Classification → Catalog JSON
        ```

        1. **Detection**: Identifies architecture documents by folder, metadata, and content signals
        2. **Filtering**: Applies your topic/product/category filters
        3. **Classification**: Assigns workload domain, family, runtime model, etc.
        4. **Output**: Generates `architecture-catalog.json` for the scorer

        ### CLI Usage

        After configuring, use the CLI to build the full catalog:
        ```bash
        catalog-builder build-catalog --repo-path ./architecture-center --out catalog.json --config my-config.yaml
        ```
        """)

    st.markdown("Configure the catalog builder settings through the tabs below.")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🔨 Build Catalog",
        "🎛️ Filter Presets",
        "📚 Keyword Dictionaries",
        "⚙️ Config Editor"
    ])

    with tab1:
        render_preview_panel()

    with tab2:
        render_filter_presets()

    with tab3:
        render_keywords_editor()

    with tab4:
        render_config_editor()


if __name__ == "__main__":
    main()
