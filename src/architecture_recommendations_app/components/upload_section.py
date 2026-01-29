"""Upload section component for the recommendations app."""

import streamlit as st


def render_upload_section():
    """Render the file upload section.

    Returns:
        Uploaded file object or None
    """
    st.markdown("### Upload Application Context")

    uploaded_file = st.file_uploader(
        "Drop your context file here or click to browse",
        type=['json'],
        help="Upload the JSON context file from Dr. Migrate or similar assessment tool",
        label_visibility="collapsed"
    )

    if uploaded_file:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.success(f"Loaded: **{uploaded_file.name}** ({uploaded_file.size / 1024:.1f} KB)")

    return uploaded_file
