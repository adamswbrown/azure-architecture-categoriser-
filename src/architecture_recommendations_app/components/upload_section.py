"""Upload section component for the recommendations app."""

import streamlit as st


def render_upload_section():
    """Render the file upload section.

    Returns:
        Uploaded file object or None
    """
    uploaded_file = st.file_uploader(
        "Upload your context file (JSON)",
        type=['json'],
        help="Upload the JSON context file from Dr. Migrate or similar assessment tool"
    )

    if uploaded_file:
        st.success(f"Loaded: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

    return uploaded_file
