"""Session state management for the recommendations app."""

from typing import Any

import streamlit as st


def initialize_state() -> None:
    """Initialize session state with defaults."""
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.current_step = 1
        st.session_state.scoring_result = None
        st.session_state.last_file_hash = None
        st.session_state.context_data = None
        st.session_state.questions = None
        st.session_state.error_state = None
        st.session_state.user_answers = {}


def get_state(key: str, default: Any = None) -> Any:
    """Get a value from session state."""
    return getattr(st.session_state, key, default)


def set_state(key: str, value: Any) -> None:
    """Set a value in session state."""
    setattr(st.session_state, key, value)


def clear_state() -> None:
    """Clear all session state for a new analysis."""
    st.session_state.current_step = 1
    st.session_state.scoring_result = None
    st.session_state.last_file_hash = None
    st.session_state.context_data = None
    st.session_state.questions = None
    st.session_state.error_state = None
    st.session_state.user_answers = {}
