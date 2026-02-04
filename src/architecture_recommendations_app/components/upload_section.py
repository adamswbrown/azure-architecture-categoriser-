"""Upload section component for the recommendations app."""

import streamlit as st


def render_upload_section(on_sample_click=None):
    """Render the file upload section.

    Args:
        on_sample_click: Optional callback function to show sample files dialog

    Returns:
        Uploaded file object or None
    """
    col1, col2 = st.columns([4, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload your context file (JSON)",
            type=['json'],
            help=(
                "Supports both App Cat context files (Java/.NET) and Dr. Migrate data exports (all applications). "
                "Dr. Migrate format is automatically detected and converted."
            )
        )

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)  # Align with uploader
        if on_sample_click:
            if st.button("Try a Sample", type="secondary", use_container_width=True):
                on_sample_click()

    if uploaded_file:
        st.success(f"Loaded: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

    return uploaded_file
