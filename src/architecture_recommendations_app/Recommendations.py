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
from architecture_recommendations_app.utils.validation import (
    validate_uploaded_file,
    get_drmigrate_prompt,
    format_validation_error_with_prompt,
)
from architecture_recommendations_app.utils.sanitize import safe_html, secure_temp_file
from architecture_recommendations_app.components.upload_section import render_upload_section
from architecture_recommendations_app.components.results_display import render_results, render_user_answers
from architecture_recommendations_app.components.pdf_generator import generate_pdf_report
from architecture_recommendations_app.components.config_editor import render_config_editor

from architecture_scorer.engine import ScoringEngine
from architecture_scorer.schema import ScoringResult


@st.dialog("Recommendations Help")
def _show_help_dialog():
    """Display help information in a modal dialog."""
    st.markdown("""
    ### How to Use This App

    **1. Upload Context File**
    Upload your Dr. Migrate application context file (JSON) to get started.

    **2. Answer Questions (Optional)**
    Answer clarification questions to improve recommendation accuracy.

    **3. View Results**
    See matched architectures with scores, diagrams, and export options.

    ---

    ### Understanding the Catalog

    **Sources:**
    - **Refresh with Defaults** - Fetches latest Azure Architecture Center (~51 reference architectures)
    - **Catalog Builder** page - Custom filtering (can include examples, solution ideas)

    **Catalog Priority:**
    1. Session state (from Catalog Builder)
    2. `ARCHITECTURE_CATALOG_PATH` env var
    3. `./architecture-catalog.json`
    4. Bundled catalog

    ---

    **Other Pages:**
    - **Catalog Builder** - Create custom catalogs with filters
    - **Catalog Stats** - Browse and explore the catalog
    """)

    if st.button("Got it!", type="primary", use_container_width=True):
        st.rerun()


# Sample files for demo - curated selection showcasing different scenarios
SAMPLE_FILES = [
    {
        "file": "01-java-refactor-aks.json",
        "name": "Java Microservices → AKS",
        "description": "Spring Boot application refactoring to Azure Kubernetes Service",
        "treatment": "Refactor",
        "tech": "Java 11, Spring Boot, PostgreSQL",
        "complexity": "Medium",
    },
    {
        "file": "02-dotnet-replatform-appservice.json",
        "name": ".NET Core → App Service",
        "description": "Modern .NET application replatforming to Azure App Service",
        "treatment": "Replatform",
        "tech": ".NET 6, SQL Server, Redis",
        "complexity": "Low",
    },
    {
        "file": "07-greenfield-cloud-native-perfect.json",
        "name": "Cloud-Native Greenfield",
        "description": "New application built for cloud from the start",
        "treatment": "Rebuild",
        "tech": "Node.js, Cosmos DB, Event Grid",
        "complexity": "Medium",
    },
    {
        "file": "09-rehost-vm-lift-shift.json",
        "name": "VM Lift-and-Shift",
        "description": "Legacy application moving to Azure VMs with minimal changes",
        "treatment": "Rehost",
        "tech": "Windows Server, IIS, SQL Server",
        "complexity": "Low",
    },
    {
        "file": "13-highly-regulated-healthcare.json",
        "name": "Healthcare (HIPAA)",
        "description": "Highly regulated healthcare application requiring compliance",
        "treatment": "Replatform",
        "tech": ".NET, SQL Server, HL7 FHIR",
        "complexity": "High",
    },
    {
        "file": "17-cost-minimized-startup.json",
        "name": "Startup MVP",
        "description": "Cost-optimized startup application prioritizing budget",
        "treatment": "Replatform",
        "tech": "Python, PostgreSQL, Redis",
        "complexity": "Low",
    },
    {
        "file": "18-innovation-first-ai-ml.json",
        "name": "AI/ML Platform",
        "description": "Innovation-focused AI and machine learning workload",
        "treatment": "Rebuild",
        "tech": "Python, TensorFlow, Spark",
        "complexity": "High",
    },
    {
        "file": "14-multi-region-active-active.json",
        "name": "Multi-Region HA",
        "description": "Mission-critical application requiring global availability",
        "treatment": "Refactor",
        "tech": "Java, Cosmos DB, Traffic Manager",
        "complexity": "Very High",
    },
]


def _get_samples_directory() -> Path | None:
    """Find the samples directory with multiple fallback paths.

    Tries several approaches to find the samples directory:
    1. Relative to this file's location
    2. Relative to current working directory
    3. Absolute path from project root environment variable
    4. Docker container standard location
    """
    import sys

    # Approach 1: Relative to this file
    samples_dir = Path(__file__).parent.parent.parent / "examples" / "context_files"
    if samples_dir.exists():
        return samples_dir

    # Approach 2: Relative to current working directory
    samples_dir = Path.cwd() / "examples" / "context_files"
    if samples_dir.exists():
        return samples_dir

    # Approach 3: Check /app (Docker standard)
    samples_dir = Path("/app/examples/context_files")
    if samples_dir.exists():
        return samples_dir

    # Approach 3b: Check /app/examples (without context_files subdirectory)
    samples_dir = Path("/app/examples")
    if samples_dir.exists() and (samples_dir / "context_files").exists():
        return samples_dir / "context_files"

    # Approach 4: Check common development locations
    project_root_candidates = [
        Path(__file__).parent.parent.parent,
        Path.cwd(),
        Path.cwd().parent,
        Path.home() / "Developer" / "azure-architecture-categoriser-",
    ]

    for root in project_root_candidates:
        samples_dir = root / "examples" / "context_files"
        if samples_dir.exists():
            return samples_dir

    # Log what we're looking for (for debugging)
    import logging
    logger = logging.getLogger(__name__)
    logger.debug(f"Could not find samples directory")
    logger.debug(f"  __file__: {__file__}")
    logger.debug(f"  cwd: {Path.cwd()}")
    logger.debug(f"  sys.path: {sys.path[:3]}")

    return None


def _get_all_samples(samples_dir: Path) -> list[dict]:
    """Dynamically discover all sample files and build metadata.

    Scans the samples directory for .json files and extracts metadata.
    Falls back to hardcoded SAMPLE_FILES metadata when available.
    """
    import json

    # Build lookup of hardcoded metadata by filename
    hardcoded_metadata = {sample['file']: sample for sample in SAMPLE_FILES}

    samples = []

    # Find all .json files in samples directory
    json_files = sorted(samples_dir.glob("*.json"))

    for file_path in json_files:
        filename = file_path.name

        # Skip test files
        if 'test' in filename.lower() or 'xss' in filename.lower():
            continue

        # Start with hardcoded metadata if available
        if filename in hardcoded_metadata:
            samples.append(hardcoded_metadata[filename])
            continue

        # Try to extract metadata from the file itself
        try:
            with open(file_path, 'r') as f:
                content = json.load(f)

            # Extract info from app_overview if available
            app_info = {}
            if isinstance(content, list) and len(content) > 0:
                app_overview = content[0].get('app_overview', [])
                if app_overview:
                    app_info = app_overview[0]

            # Generate metadata
            sample = {
                'file': filename,
                'name': app_info.get('application', filename.replace('.json', '').replace('-', ' ').title()),
                'description': f"{app_info.get('app_type', 'Application')} - Treatment: {app_info.get('treatment', 'Unknown')}",
                'treatment': app_info.get('treatment', 'Unknown'),
                'complexity': 'Medium',  # Default
                'tech': ', '.join(content[0].get('detected_technology_running', [])[:3]) if isinstance(content, list) and len(content) > 0 else 'Various',
            }
            samples.append(sample)
        except Exception as e:
            # Fallback: create minimal metadata
            samples.append({
                'file': filename,
                'name': filename.replace('.json', '').replace('-', ' ').title(),
                'description': 'Sample context file',
                'treatment': 'Unknown',
                'complexity': 'Unknown',
                'tech': 'Various',
            })

    return samples


@st.dialog("Sample Context Files", width="large")
def _show_sample_files_dialog():
    """Display sample files available for download."""
    st.markdown("""
    These are **synthetic demo scenarios** created to showcase the recommender's capabilities.
    Each file simulates a different migration scenario with realistic application profiles.
    """)

    st.info("**Tip:** Select a scenario that matches your interests, then upload it to see recommendations.")

    # Get the samples directory path with fallbacks
    samples_dir = _get_samples_directory()

    if not samples_dir:
        import os
        import subprocess

        # Get detailed directory listing for debugging
        app_listing = "❌ Could not list /app"
        try:
            result = subprocess.run(['ls', '-la', '/app'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                app_listing = "```\n" + result.stdout + "\n```"
            else:
                app_listing = f"Error listing: {result.stderr}"
        except Exception as e:
            app_listing = f"Exception: {str(e)}"

        examples_listing = "❌ /app/examples not accessible"
        if os.path.exists('/app/examples'):
            try:
                result = subprocess.run(['ls', '-la', '/app/examples'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    examples_listing = "```\n" + result.stdout + "\n```"
            except:
                pass

        st.error(f"""
        **Sample files directory not found.**

        **Directory Check:**
        - Current working directory: `{os.getcwd()}`
        - Python executable: `{__file__}`
        - /app exists: `{os.path.exists('/app')}`
        - /app/examples exists: `{os.path.exists('/app/examples')}`
        - /app/examples/context_files exists: `{os.path.exists('/app/examples/context_files')}`

        **Contents of /app:**
        {app_listing}

        **Contents of /app/examples:**
        {examples_listing}

        **Workaround:** Generate sample files from the Catalog Builder page or download from [GitHub](https://github.com/adamswbrown/azure-architecture-categoriser/tree/main/examples/context_files).
        """)
        return

    # Show where samples directory was found
    import os
    files_in_dir = os.listdir(str(samples_dir)) if os.path.isdir(str(samples_dir)) else []
    st.info(f"📁 Found samples at: `{samples_dir}` ({len(files_in_dir)} items)")

    # Dynamically discover all samples
    all_samples = _get_all_samples(samples_dir)
    st.caption(f"Displaying {len(all_samples)} sample scenarios")

    for sample in all_samples:
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**{sample['name']}**")
                st.caption(sample['description'])
                st.markdown(f"Treatment: `{sample['treatment']}` · Complexity: `{sample['complexity']}`")
                st.markdown(f"*Tech: {sample['tech']}*")

            with col2:
                try:
                    file_path = samples_dir / sample['file']
                    if file_path.exists():
                        with open(file_path, 'r') as f:
                            file_content = f.read()
                        st.download_button(
                            "Download",
                            data=file_content,
                            file_name=sample['file'],
                            mime="application/json",
                            key=f"download_{sample['file']}",
                            use_container_width=True,
                        )
                    else:
                        st.caption(f"⚠️ Not found: {file_path}")
                except Exception as e:
                    st.caption(f"⚠️ Error: {str(e)}")

    st.markdown("---")
    st.caption("For production use, generate context files using [Dr. Migrate](https://drmigrate.com).")


def _render_title_with_help(key_suffix: str = ""):
    """Render the page title with a help button."""
    title_col, help_col = st.columns([10, 1])
    with title_col:
        st.title("Azure Architecture Recommendations")
    with help_col:
        st.markdown("<br>", unsafe_allow_html=True)  # Align with title
        if st.button("?", help="Show help", key=f"help_button{key_suffix}"):
            _show_help_dialog()


def get_catalog_path() -> str:
    """Get the catalog path from session state, environment, or default locations."""
    # 0. Session state (user-selected catalog) - takes precedence
    session_catalog = get_state('catalog_path')
    session_source = get_state('catalog_source')

    # Debug: Log what we found in session state
    # print(f"DEBUG: session_catalog={session_catalog}, session_source={session_source}")

    if session_catalog and Path(session_catalog).exists():
        return session_catalog

    # 1. Environment variable
    env_path = os.environ.get("ARCHITECTURE_CATALOG_PATH")
    if env_path and Path(env_path).exists():
        set_state('catalog_source', 'environment')
        set_state('catalog_path', env_path)
        return env_path

    # 2. Project root first (more likely to be correct than CWD)
    project_root = Path(__file__).parent.parent.parent
    root_path = project_root / "architecture-catalog.json"
    if root_path.exists():
        resolved = str(root_path.resolve())
        set_state('catalog_source', 'project_root')
        set_state('catalog_path', resolved)
        return resolved

    # 3. Local file in current directory (fallback)
    local_path = Path("architecture-catalog.json")
    if local_path.exists():
        resolved = str(local_path.resolve())
        set_state('catalog_source', 'current_directory')
        set_state('catalog_path', resolved)
        return resolved

    return None


def get_catalog_info(catalog_path: str) -> dict:
    """Get information about the catalog."""
    info = {
        'path': catalog_path,
        'filename': Path(catalog_path).name,
        'size_kb': 0,
        'last_modified': None,
        'age_days': None,
        'architecture_count': 0,
        'source': get_state('catalog_source') or 'unknown',
        'generation_settings': None,
        'generated_at': None,
        'version': None
    }

    try:
        path = Path(catalog_path)
        stat = path.stat()
        info['size_kb'] = round(stat.st_size / 1024, 1)

        modified_dt = datetime.fromtimestamp(stat.st_mtime)
        info['last_modified'] = modified_dt.strftime("%d/%m/%Y")

        # Calculate age in days
        age = datetime.now() - modified_dt
        info['age_days'] = age.days

        # Count architectures and get generation settings
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog_data = json.load(f)
            if isinstance(catalog_data, dict) and 'architectures' in catalog_data:
                info['architecture_count'] = len(catalog_data['architectures'])
                # Extract build parameters
                info['generation_settings'] = catalog_data.get('generation_settings')
                info['generated_at'] = catalog_data.get('generated_at')
                info['version'] = catalog_data.get('version')
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

        **Option 1:** Go to the **Catalog Builder** page (in the sidebar) to generate one.

        **Option 2:** Use the sidebar to upload an existing catalog file.

        **Option 3:** Click "Generate Catalog with Defaults" in the sidebar to build one with default settings (~51 reference architectures).
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

        # Handle deferred refresh request (to avoid button rerun issues)
        if get_state('refresh_catalog_requested'):
            set_state('refresh_catalog_requested', False)
            _refresh_catalog()
            return

        # Catalog section
        st.subheader("Architecture Catalog")

        catalog_path = get_catalog_path()

        if catalog_path:
            info = get_catalog_info(catalog_path)
            age_days = info.get('age_days')

            # Show current catalog info with stale warning if needed
            source = get_state('catalog_source', 'unknown')
            source_label = {'catalog_builder': '(from Catalog Builder)', 'project_root': '', 'current_directory': '', 'environment': '(env)'}.get(source, '')

            if age_days is not None and age_days > 30:
                st.warning(f"**{info['architecture_count']}** architectures ({age_days} days old) {source_label}")
            else:
                st.success(f"**{info['architecture_count']}** architectures loaded {source_label}")

            # Compact catalog details expander
            with st.expander("Catalog Details", expanded=False):
                # File and date on same visual block
                if age_days == 0:
                    age_str = "today"
                elif age_days == 1:
                    age_str = "1 day ago"
                elif age_days is not None:
                    age_str = f"{age_days} days ago"
                else:
                    age_str = "unknown"

                st.caption(f"`{info['filename']}` · Updated {age_str} · {info['size_kb']} KB")

                # Build parameters as compact badges
                gen_settings = info.get('generation_settings')
                if gen_settings:
                    badges = []

                    # Topics badge
                    topics = gen_settings.get('allowed_topics', [])
                    if topics:
                        for topic in topics:
                            # Shorten common topic names
                            short_topic = topic.replace('reference-architecture', 'ref-arch') \
                                               .replace('example-scenario', 'examples') \
                                               .replace('solution-idea', 'solutions')
                            badges.append(f'<span style="background:#e8f4fd;color:#0078D4;padding:2px 6px;border-radius:3px;font-size:0.75rem;margin:2px;">{short_topic}</span>')

                    # Exclude examples badge
                    if gen_settings.get('exclude_examples', False):
                        badges.append('<span style="background:#DFF6DD;color:#107C10;padding:2px 6px;border-radius:3px;font-size:0.75rem;margin:2px;">excl. examples</span>')

                    # Require YML badge
                    if gen_settings.get('require_architecture_yml', False):
                        badges.append('<span style="background:#FFF4CE;color:#797673;padding:2px 6px;border-radius:3px;font-size:0.75rem;margin:2px;">req. yml</span>')

                    # Products filter badge
                    products = gen_settings.get('allowed_products', [])
                    if products:
                        badges.append(f'<span style="background:#E6E6E6;color:#333;padding:2px 6px;border-radius:3px;font-size:0.75rem;margin:2px;">{len(products)} products</span>')

                    # Categories filter badge
                    categories = gen_settings.get('allowed_categories', [])
                    if categories:
                        badges.append(f'<span style="background:#E6E6E6;color:#333;padding:2px 6px;border-radius:3px;font-size:0.75rem;margin:2px;">{len(categories)} categories</span>')

                    if badges:
                        st.markdown(f'<div style="line-height:1.8;">{"".join(badges)}</div>', unsafe_allow_html=True)
                    else:
                        st.caption("All topics, no filters")

                # Copyable path (collapsed by default via small font)
                st.code(info['path'], language=None)

            # Refresh button with confirmation
            with st.expander("Refresh Catalog with Defaults", expanded=get_state('show_refresh_confirm', False)):
                st.warning("This will replace your current catalog with default settings:")
                st.markdown("""
                **Default settings:**
                - **Topics:** Reference Architectures only (~51 patterns)
                - **Products:** No filter (all products)
                - **Categories:** No filter (all categories)
                - **Examples:** Excluded (production-ready only)

                For custom filtering, use the **Catalog Builder** page instead.
                """)
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("Confirm Refresh", type="primary", use_container_width=True, key="confirm_refresh_btn"):
                        set_state('show_refresh_confirm', False)
                        set_state('refresh_catalog_requested', True)
                        st.rerun()
                with col2:
                    if st.button("Cancel", use_container_width=True, key="cancel_refresh_btn"):
                        set_state('show_refresh_confirm', False)
                        st.rerun()

        else:
            st.warning("No catalog found")

            # Offer to generate a catalog when none exists
            st.info("Click below to generate a catalog from the Azure Architecture Center.")
            with st.expander("Generate Catalog with Defaults", expanded=True):
                st.markdown("""
                **Default settings:**
                - **Topics:** Reference Architectures only (~51 patterns)
                - **Products:** No filter (all products)
                - **Categories:** No filter (all categories)
                - **Examples:** Excluded (production-ready only)

                For custom filtering, use the **Catalog Builder** page instead.
                """)
                if st.button("Generate Catalog", type="primary", use_container_width=True,
                            key="generate_catalog_btn"):
                    set_state('refresh_catalog_requested', True)
                    st.rerun()

        st.markdown("---")

        # Scoring configuration section
        render_config_editor()

        # Footer with credits and GitHub link
        st.markdown("---")
        st.markdown(
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
    _render_title_with_help("_step1")
    st.caption("Upload your application context to receive tailored architecture recommendations.")

    _render_step_indicator(1)

    st.markdown("")  # Small spacer

    # Upload section with sample files button
    uploaded_file = render_upload_section(on_sample_click=_show_sample_files_dialog)

    if uploaded_file is not None:
        try:
            file_hash = hash(uploaded_file.getvalue())

            # Check if this is a new file
            if get_state('last_file_hash') != file_hash:
                # New file - validate it
                try:
                    is_valid, error_msg, data, suggestions = validate_uploaded_file(uploaded_file)

                    if not is_valid:
                        st.error(f"**Validation Error:** {error_msg}")
                        if suggestions:
                            with st.expander("How to fix this", expanded=True):
                                for suggestion in suggestions:
                                    st.markdown(f"- {suggestion}")

                        # Show Dr. Migrate LLM prompt for generating correct data
                        with st.expander("Generate data from Dr. Migrate AI Advisor", expanded=False):
                            st.markdown("""
                            **If you're using Dr. Migrate**, copy the prompt below and paste it into
                            the AI Advisor to generate the correct data format:
                            """)
                            prompt = get_drmigrate_prompt("YOUR_APPLICATION_NAME")
                            st.code(prompt, language="text")
                            st.caption("Replace `YOUR_APPLICATION_NAME` with your actual application name before using.")
                        return
                except Exception as e:
                    # Catch any unexpected errors during validation
                    st.error(f"""
                    **Upload Error:** Could not process your file.

                    **Error details:** {str(e)}

                    **Troubleshooting:**
                    - Ensure the file is valid JSON format
                    - Check that the file is not corrupted
                    - Try downloading a sample file first to verify the format
                    """)
                    return

                # Store the validated data
                set_state('context_data', data)
                set_state('last_file_hash', file_hash)
                set_state('scoring_result', None)
                set_state('user_answers', {})
                set_state('questions', None)

        except Exception as e:
            # Catch errors reading the file itself
            st.error(f"""
            **File Read Error:** Could not read your file.

            **Error details:** {str(e)}

            **This could happen if:**
            - The file is too large (max 10MB)
            - The file path contains special characters
            - There's a permissions issue
            - The file is being used by another process

            **Try:** Download and upload a sample file first to verify the upload works correctly.
            """)
            return

        # Get the stored context data
        data = get_state('context_data')
        if not data:
            return

        st.markdown("")  # Spacer

        # Show file summary
        _render_file_summary(data)

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
    _render_title_with_help("_step2")

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
    _render_title_with_help("_step3")

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

    # Get questions and answers for display
    questions = get_state('questions', [])
    user_answers = get_state('user_answers', {})

    # Check if there are unanswered questions
    answered_ids = set(user_answers.keys()) if user_answers else set()
    unanswered_count = sum(1 for q in questions if q.question_id not in answered_ids)
    has_unanswered = unanswered_count > 0

    # Render the results
    render_results(result, has_unanswered_questions=has_unanswered)
    if questions and user_answers:
        render_user_answers(questions, user_answers)

    # Export section
    st.markdown("---")
    st.subheader("Export Your Results")

    col1, col2, col3 = st.columns(3)

    with col1:
        # PDF Download
        try:
            pdf_bytes = generate_pdf_report(result, questions, user_answers)
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
    """Render a compact summary of the uploaded file contents."""
    if not data or not data[0]:
        st.warning("No data found in context file")
        return

    context = data[0]

    # Application overview - compact table style
    if context.get("app_overview"):
        overview = context["app_overview"][0] if context["app_overview"] else {}

        # Escape user-provided values to prevent XSS (Security fix)
        app_name = safe_html(overview.get("application", "Unknown"))
        app_type = safe_html(overview.get("app_type", "Unknown"))
        criticality = safe_html(overview.get("business_crtiticality", overview.get("business_criticality", "Unknown")))
        treatment = overview.get("treatment", "Unknown")
        treatment_display = safe_html(treatment.title() if treatment else "Unknown")
        app_type_truncated = safe_html(str(overview.get("app_type", "Unknown"))[:25])
        app_type_suffix = "..." if len(str(overview.get("app_type", "Unknown"))) > 25 else ""

        # Compact card-style display
        st.markdown(
            f"""
            <div style="background:#f8f9fa; border-radius:8px; padding:1rem; margin-bottom:1rem;">
                <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:1rem; text-align:center;">
                    <div>
                        <div style="color:#666; font-size:0.75rem; text-transform:uppercase; margin-bottom:0.25rem;">Application</div>
                        <div style="font-weight:600; font-size:0.95rem;">{app_name}</div>
                    </div>
                    <div>
                        <div style="color:#666; font-size:0.75rem; text-transform:uppercase; margin-bottom:0.25rem;">Type</div>
                        <div style="font-weight:600; font-size:0.95rem;">{app_type_truncated}{app_type_suffix}</div>
                    </div>
                    <div>
                        <div style="color:#666; font-size:0.75rem; text-transform:uppercase; margin-bottom:0.25rem;">Criticality</div>
                        <div style="font-weight:600; font-size:0.95rem;">{criticality}</div>
                    </div>
                    <div>
                        <div style="color:#666; font-size:0.75rem; text-transform:uppercase; margin-bottom:0.25rem;">Treatment</div>
                        <div style="font-weight:600; font-size:0.95rem; color:#0078D4;">{treatment_display}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Technologies detected - as styled tags (escaped for XSS protection)
    technologies = context.get("detected_technology_running", [])
    if technologies:
        tech_tags = "".join([
            f'<span style="display:inline-block; background:#e8f4fd; color:#0078D4; '
            f'padding:0.2rem 0.5rem; margin:0.15rem; border-radius:4px; font-size:0.8rem;">{safe_html(tech)}</span>'
            for tech in technologies[:12]
        ])
        if len(technologies) > 12:
            tech_tags += f'<span style="display:inline-block; color:#666; padding:0.2rem 0.5rem; font-size:0.8rem;">+{len(technologies) - 12} more</span>'

        st.markdown(
            f"""
            <div style="margin-bottom:1rem;">
                <div style="color:#666; font-size:0.75rem; text-transform:uppercase; margin-bottom:0.5rem;">Detected Technologies</div>
                <div>{tech_tags}</div>
            </div>
            """,
            unsafe_allow_html=True
        )

    # Server summary - inline compact (escaped for XSS protection)
    servers = context.get("server_details", [])
    if servers:
        envs = set(s.get("environment", "Unknown") for s in servers)
        os_list = [s.get("OperatingSystem", "Unknown") for s in servers]
        windows_count = sum(1 for os in os_list if os and "windows" in os.lower())
        linux_count = len(servers) - windows_count

        os_parts = []
        if windows_count:
            os_parts.append(f"{windows_count} Windows")
        if linux_count:
            os_parts.append(f"{linux_count} Linux")

        # Escape environment names for XSS protection
        envs_escaped = ', '.join(safe_html(env) for env in envs)
        os_parts_display = safe_html(', '.join(os_parts) if os_parts else 'Unknown')

        st.markdown(
            f"""
            <div style="display:flex; gap:2rem; color:#666; font-size:0.85rem; margin-bottom:1rem;">
                <span><strong>{len(servers)}</strong> Server{'s' if len(servers) != 1 else ''}</span>
                <span><strong>{envs_escaped}</strong> Environment{'s' if len(envs) != 1 else ''}</span>
                <span><strong>{os_parts_display}</strong></span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # App Mod results summary - collapsible (escaped for XSS protection)
    app_mod = context.get("App Mod results", [])
    if app_mod:
        with st.expander("App Modernization Assessment", expanded=False):
            for result in app_mod:
                tech = safe_html(result.get("technology", "Unknown"))
                summary = result.get("summary", {})
                recommended = result.get("recommended_targets", [])

                container_ready = summary.get("container_ready", False)
                modernization_feasible = summary.get("modernization_feasible", False)

                badges = []
                if container_ready:
                    badges.append('<span style="background:#DFF6DD; color:#107C10; padding:0.15rem 0.4rem; border-radius:3px; font-size:0.75rem; margin-right:0.3rem;">Container Ready</span>')
                if modernization_feasible:
                    badges.append('<span style="background:#DFF6DD; color:#107C10; padding:0.15rem 0.4rem; border-radius:3px; font-size:0.75rem; margin-right:0.3rem;">Modernization Feasible</span>')

                # Escape recommended targets for XSS protection
                targets_escaped = ', '.join(safe_html(t) for t in recommended)
                targets_str = f" &rarr; {targets_escaped}" if recommended else ""

                st.markdown(
                    f"""<div style="margin-bottom:0.5rem;">
                        <strong>{tech}</strong>{targets_str}
                        <div>{''.join(badges)}</div>
                    </div>""",
                    unsafe_allow_html=True
                )


def _get_questions(data: list, catalog_path: str) -> list:
    """Get clarification questions without full scoring."""
    try:
        # Use secure temp file with context manager for automatic cleanup
        with secure_temp_file(suffix='.json', prefix='context_') as (f, temp_path):
            json.dump(data, f)
            f.flush()  # Ensure data is written before reading

            engine = ScoringEngine()
            engine.load_catalog(catalog_path)
            questions = engine.get_questions(str(temp_path))
            return questions

    except Exception as e:
        st.warning(f"Could not load questions: {e}")
        return []


def _score_context(data: list, catalog_path: str, user_answers: dict) -> ScoringResult | None:
    """Score the context data using the scoring engine."""
    try:
        # Use secure temp file with context manager for automatic cleanup
        with secure_temp_file(suffix='.json', prefix='context_') as (f, temp_path):
            json.dump(data, f)
            f.flush()  # Ensure data is written before reading

            engine = ScoringEngine()
            engine.load_catalog(catalog_path)
            result = engine.score(
                str(temp_path),
                user_answers=user_answers if user_answers else None,
                max_recommendations=5
            )
            return result

    except Exception as e:
        st.error(f"Error analyzing context: {e}")
        return None


def _render_placeholder() -> None:
    """Render placeholder content when no file is uploaded."""
    st.info("""
    **Get Started:**
    1. Upload your context file (JSON format)
    2. Review the application summary
    3. Answer optional questions to improve accuracy
    4. Click "Run Analysis" to get recommendations
    5. Download your PDF report
    """)

    with st.expander("What files are supported?", expanded=True):
        st.markdown("""
        This tool accepts **two types of input files**:

        **1. App Cat Context Files** (Java/.NET applications)
        - Generated by the App Mod/App Cat scanning process
        - Contains detailed code analysis and platform compatibility
        - Includes `app_overview`, `server_details`, `App Mod results`

        **2. Dr. Migrate Data Exports** (All applications)
        - Generated from Dr. Migrate AI Advisor
        - Works for **any application** - not just Java/.NET
        - Contains `application_overview`, `server_overviews`, `installed_applications`
        - Automatically converted to context format on upload

        Both formats are auto-detected and processed seamlessly.
        """)

    with st.expander("How to get data from Dr. Migrate AI Advisor", expanded=False):
        st.markdown("""
        If your application **doesn't have an App Cat scan** (not Java/.NET),
        you can still get architecture recommendations using Dr. Migrate data.

        **Copy this prompt** and paste it into the Dr. Migrate AI Advisor:
        """)
        prompt = get_drmigrate_prompt("YOUR_APPLICATION_NAME")
        st.code(prompt, language="text")
        st.caption("Replace `YOUR_APPLICATION_NAME` with your actual application name, then save the JSON response and upload it here.")




if __name__ == "__main__":
    main()
