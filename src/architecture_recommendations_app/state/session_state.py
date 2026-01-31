"""Session state management for the recommendations app.

This module manages shared state across all pages in the multi-page app:
- Recommendations (main page)
- Catalog Stats
- Catalog Builder
"""

from pathlib import Path
from typing import Any

import streamlit as st


# Default values for catalog builder
DEFAULT_REPO_URL = "https://github.com/MicrosoftDocs/architecture-center.git"
DEFAULT_CLONE_DIR = str(Path.home() / "architecture-center")


def find_local_repo() -> str | None:
    """Search for the architecture-center repo in common locations."""
    cwd = Path.cwd().resolve()

    search_paths = [
        Path.home() / "architecture-center",
        cwd / "architecture-center",
        cwd.parent / "architecture-center",
        cwd,
        cwd.parent,
        Path("/tmp") / "architecture-center",
    ]

    if cwd.is_dir():
        for child in cwd.iterdir():
            if child.is_dir() and child.name == "architecture-center":
                search_paths.insert(1, child)

    for path in search_paths:
        resolved = path.resolve()
        if resolved.exists() and (resolved / 'docs').exists():
            if (resolved / '.git').exists() or (resolved / 'docs' / 'example-scenario').exists():
                return str(resolved)

    return None


def initialize_state() -> None:
    """Initialize session state with defaults for all pages."""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True

        # === Recommendations page state ===
        st.session_state.current_step = 1
        st.session_state.scoring_result = None
        st.session_state.last_file_hash = None
        st.session_state.context_data = None
        st.session_state.questions = None
        st.session_state.error_state = None
        st.session_state.user_answers = {}

        # === Shared catalog state (used by all pages) ===
        st.session_state.catalog_path = None
        st.session_state.catalog_source = None

        # === Catalog Builder state ===
        st.session_state.builder_initialized = True
        st.session_state.repo_url = DEFAULT_REPO_URL
        st.session_state.clone_dir = DEFAULT_CLONE_DIR
        st.session_state.custom_presets = {}
        st.session_state.active_filters = {
            'products': [],
            'categories': [],
            'topics': [],
        }

        # Auto-detect local repo for catalog builder
        local_repo = find_local_repo()
        if local_repo:
            st.session_state.repo_path = local_repo
        else:
            st.session_state.repo_path = ""

        # Initialize config lazily (avoid import at module level)
        st.session_state.config = None


def get_state(key: str, default: Any = None) -> Any:
    """Get a value from session state."""
    return getattr(st.session_state, key, default)


def set_state(key: str, value: Any) -> None:
    """Set a value in session state."""
    setattr(st.session_state, key, value)


def clear_state() -> None:
    """Clear all session state for a new analysis.

    Note: This only clears recommendation-related state, not catalog builder state.
    """
    st.session_state.current_step = 1
    st.session_state.scoring_result = None
    st.session_state.last_file_hash = None
    st.session_state.context_data = None
    st.session_state.questions = None
    st.session_state.error_state = None
    st.session_state.user_answers = {}


def get_config():
    """Get or initialize the catalog builder config.

    Lazily imports CatalogConfig to avoid circular imports.
    """
    if st.session_state.config is None:
        from catalog_builder.config import CatalogConfig
        st.session_state.config = CatalogConfig()
    return st.session_state.config
