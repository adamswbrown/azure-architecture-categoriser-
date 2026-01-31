"""Catalog Stats page - Analytics dashboard for the architecture catalog."""

import json
import sys
from collections import Counter
from pathlib import Path

import streamlit as st

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from architecture_recommendations_app.state import get_state, set_state


def get_catalog_path() -> str | None:
    """Get the catalog path from session state, environment, or default locations."""
    import os

    # 0. Session state (user-selected catalog)
    session_catalog = get_state('catalog_path')
    if session_catalog and Path(session_catalog).exists():
        return session_catalog

    # 1. Environment variable
    env_path = os.environ.get("ARCHITECTURE_CATALOG_PATH")
    if env_path and Path(env_path).exists():
        return env_path

    # 2. Local file in current directory
    local_path = Path("architecture-catalog.json")
    if local_path.exists():
        return str(local_path.resolve())

    # 3. Local file in project root
    project_root = Path(__file__).parent.parent.parent.parent
    root_path = project_root / "architecture-catalog.json"
    if root_path.exists():
        return str(root_path.resolve())

    return None


def load_catalog(catalog_path: str) -> dict | None:
    """Load the catalog JSON file."""
    try:
        with open(catalog_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading catalog: {e}")
        return None


def main():
    st.set_page_config(
        page_title="Catalog Stats - Azure Architecture Recommendations",
        page_icon=":bar_chart:",
        layout="wide",
    )

    st.title("Catalog Statistics")
    st.caption("Analytics dashboard for the architecture catalog")

    # Get catalog path
    catalog_path = get_catalog_path()

    if not catalog_path:
        st.warning("No catalog found. Please load a catalog from the main page.")
        st.info("Go to the **Recommendations** page to load or generate a catalog.")
        return

    # Load catalog
    catalog_data = load_catalog(catalog_path)
    if not catalog_data:
        return

    # Extract architectures
    if isinstance(catalog_data, dict) and 'architectures' in catalog_data:
        architectures = catalog_data['architectures']
        generation_settings = catalog_data.get('generation_settings', {})
        generated_at = catalog_data.get('generated_at', 'Unknown')
    elif isinstance(catalog_data, list):
        architectures = catalog_data
        generation_settings = {}
        generated_at = 'Unknown'
    else:
        st.error("Invalid catalog format")
        return

    # Show catalog info
    catalog_info = Path(catalog_path)
    st.caption(f"`{catalog_info.name}` | {len(architectures)} architectures | Generated: {generated_at}")

    st.markdown("---")

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)

    # Count unique services
    all_services = set()
    for arch in architectures:
        if arch.get('core_services'):
            all_services.update(arch['core_services'])
        if arch.get('supporting_services'):
            all_services.update(arch['supporting_services'])

    # Count unique categories
    all_categories = set()
    for arch in architectures:
        if arch.get('browse_categories'):
            all_categories.update(arch['browse_categories'])

    col1.metric("Total Architectures", len(architectures))
    col2.metric("Azure Services", len(all_services))
    col3.metric("Categories", len(all_categories))
    col4.metric("Catalog Size", f"{catalog_info.stat().st_size / 1024:.1f} KB")

    st.markdown("---")

    # Charts section
    tab1, tab2, tab3, tab4 = st.tabs([
        "By Family",
        "By Operating Model",
        "Top Services",
        "Quality Breakdown"
    ])

    with tab1:
        st.subheader("Architectures by Family")

        family_counts = Counter()
        for arch in architectures:
            family = arch.get('family', 'unknown')
            family_counts[family] += 1

        if family_counts:
            # Create bar chart data
            chart_data = dict(family_counts.most_common())
            st.bar_chart(chart_data)

            # Show breakdown
            st.markdown("**Breakdown:**")
            cols = st.columns(len(family_counts))
            for i, (family, count) in enumerate(family_counts.most_common()):
                with cols[i % len(cols)]:
                    pct = (count / len(architectures)) * 100
                    st.metric(family.replace('_', ' ').title(), f"{count} ({pct:.0f}%)")
        else:
            st.info("No family data available")

    with tab2:
        st.subheader("Operating Model Distribution")

        op_model_counts = Counter()
        for arch in architectures:
            op_model = arch.get('operating_model_required', 'unknown')
            op_model_counts[op_model] += 1

        if op_model_counts:
            chart_data = dict(op_model_counts.most_common())
            st.bar_chart(chart_data)

            st.markdown("**What this means:**")
            st.markdown("""
            - **DevOps**: Requires CI/CD, automation, GitOps practices
            - **SRE**: Site Reliability Engineering maturity (error budgets, SLOs)
            - **Transitional**: Moving from traditional to cloud-native operations
            - **Traditional IT**: Classic ops model with change management
            """)
        else:
            st.info("No operating model data available")

    with tab3:
        st.subheader("Top Azure Services")

        service_counts = Counter()
        for arch in architectures:
            for svc in arch.get('core_services', []):
                service_counts[svc] += 1
            for svc in arch.get('supporting_services', []):
                service_counts[svc] += 1

        if service_counts:
            top_20 = dict(service_counts.most_common(20))
            st.bar_chart(top_20)

            # Show exact counts
            with st.expander("All Services (sorted by frequency)"):
                for svc, count in service_counts.most_common():
                    st.write(f"- **{svc}**: {count} architectures")
        else:
            st.info("No service data available")

    with tab4:
        st.subheader("Quality Breakdown")

        # Count by quality indicators
        quality_counts = Counter()
        for arch in architectures:
            # Check for quality indicators
            if arch.get('example_only', False):
                quality_counts['Example/POC'] += 1
            elif arch.get('ai_enriched', False):
                quality_counts['AI-Enriched'] += 1
            else:
                quality_counts['Curated'] += 1

        if quality_counts:
            chart_data = dict(quality_counts.most_common())
            st.bar_chart(chart_data)

            st.markdown("**Quality Levels:**")
            col1, col2, col3 = st.columns(3)

            with col1:
                count = quality_counts.get('Curated', 0)
                st.metric("Curated", count)
                st.caption("Production-ready, reviewed patterns")

            with col2:
                count = quality_counts.get('AI-Enriched', 0)
                st.metric("AI-Enriched", count)
                st.caption("Auto-classified with AI assistance")

            with col3:
                count = quality_counts.get('Example/POC', 0)
                st.metric("Example/POC", count)
                st.caption("Learning scenarios, not production-ready")
        else:
            st.info("No quality data available")

    st.markdown("---")

    # Additional analytics
    st.subheader("Additional Insights")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**By Category**")
        category_counts = Counter()
        for arch in architectures:
            for cat in arch.get('browse_categories', []):
                category_counts[cat] += 1

        if category_counts:
            top_10 = dict(category_counts.most_common(10))
            st.bar_chart(top_10)
        else:
            st.info("No category data")

    with col2:
        st.markdown("**By Runtime Model**")
        runtime_counts = Counter()
        for arch in architectures:
            for rt in arch.get('expected_runtime_models', []):
                runtime_counts[rt] += 1

        if runtime_counts:
            st.bar_chart(dict(runtime_counts.most_common()))
        else:
            st.info("No runtime model data")

    # Generation settings
    if generation_settings:
        st.markdown("---")
        with st.expander("Catalog Generation Settings"):
            st.json(generation_settings)

    # Browse architectures
    st.markdown("---")
    st.subheader("Browse Architectures")

    # Filter options
    col1, col2, col3 = st.columns(3)

    with col1:
        families = sorted(set(arch.get('family', 'unknown') for arch in architectures))
        selected_family = st.selectbox("Filter by Family", ["All"] + families)

    with col2:
        op_models = sorted(set(arch.get('operating_model_required', 'unknown') for arch in architectures))
        selected_op_model = st.selectbox("Filter by Operating Model", ["All"] + op_models)

    with col3:
        search_term = st.text_input("Search by name", placeholder="e.g., kubernetes")

    # Apply filters
    filtered = architectures
    if selected_family != "All":
        filtered = [a for a in filtered if a.get('family') == selected_family]
    if selected_op_model != "All":
        filtered = [a for a in filtered if a.get('operating_model_required') == selected_op_model]
    if search_term:
        filtered = [a for a in filtered if search_term.lower() in a.get('name', '').lower()]

    st.caption(f"Showing {len(filtered)} of {len(architectures)} architectures")

    # Display filtered architectures
    for arch in filtered[:20]:
        with st.expander(f"**{arch.get('name', 'Unknown')}** ({arch.get('family', 'unknown')})"):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**Description:** {arch.get('description', 'N/A')[:200]}...")
                st.markdown(f"**Family:** {arch.get('family', 'N/A')}")
                st.markdown(f"**Operating Model:** {arch.get('operating_model_required', 'N/A')}")
                st.markdown(f"**Security Level:** {arch.get('security_level', 'N/A')}")

            with col2:
                if arch.get('core_services'):
                    st.markdown(f"**Core Services:** {', '.join(arch['core_services'][:5])}")
                if arch.get('browse_categories'):
                    st.markdown(f"**Categories:** {', '.join(arch['browse_categories'][:5])}")
                if arch.get('learn_url'):
                    st.markdown(f"[View on Microsoft Learn]({arch['learn_url']})")

    if len(filtered) > 20:
        st.info(f"Showing first 20 of {len(filtered)} matching architectures")


if __name__ == "__main__":
    main()
