"""Session state management for Streamlit app."""

from pathlib import Path
from typing import Any

import streamlit as st

from catalog_builder.config import CatalogConfig

# Default values
DEFAULT_REPO_URL = "https://github.com/MicrosoftDocs/architecture-center.git"
DEFAULT_CLONE_DIR = str(Path.home() / "architecture-center")


def find_local_repo() -> str | None:
    """Search for the architecture-center repo in common locations.

    Checks (in priority order - permanent locations first):
    - Home directory (preferred)
    - Current working directory
    - Parent/sibling directories
    - Temp directory (last resort)

    Returns the resolved path if found, None otherwise.
    """
    cwd = Path.cwd().resolve()

    # Locations to search - permanent locations first, temp last
    search_paths = [
        Path.home() / "architecture-center",            # Home: ~/architecture-center (PREFERRED)
        cwd / "architecture-center",                    # Child: ./architecture-center
        cwd.parent / "architecture-center",             # Sibling: ../architecture-center
        cwd,                                            # Current dir (if it IS the repo)
        cwd.parent,                                     # Parent (if parent IS the repo)
        Path("/tmp") / "architecture-center",           # Temp: /tmp/architecture-center (LAST RESORT)
    ]

    # Also check immediate children of cwd
    if cwd.is_dir():
        for child in cwd.iterdir():
            if child.is_dir() and child.name == "architecture-center":
                search_paths.insert(1, child)  # After home, before others

    for path in search_paths:
        # Resolve symlinks for consistent paths (e.g., /tmp -> /private/tmp on macOS)
        resolved = path.resolve()
        if resolved.exists() and (resolved / 'docs').exists():
            # Verify it looks like the architecture-center repo
            if (resolved / '.git').exists() or (resolved / 'docs' / 'example-scenario').exists():
                return str(resolved)

    return None


def initialize_state() -> None:
    """Initialize session state with defaults."""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.config = CatalogConfig()
        st.session_state.repo_url = DEFAULT_REPO_URL
        st.session_state.clone_dir = DEFAULT_CLONE_DIR
        st.session_state.custom_presets = {}
        st.session_state.active_filters = {
            'products': [],
            'categories': [],
            'topics': [],
        }

        # Auto-detect local repo for repo_path only
        # (clone_dir stays as DEFAULT_CLONE_DIR for new clones)
        local_repo = find_local_repo()
        if local_repo:
            st.session_state.repo_path = local_repo
        else:
            st.session_state.repo_path = ""


def get_state(key: str, default: Any = None) -> Any:
    """Get a value from session state."""
    return getattr(st.session_state, key, default)


def set_state(key: str, value: Any) -> None:
    """Set a value in session state."""
    setattr(st.session_state, key, value)
