"""Keywords editor component for modifying classification dictionaries."""

import streamlit as st

from catalog_builder_gui.state import get_state, set_state


# Dictionary metadata for display
DICTIONARIES = {
    'domain_keywords': {
        'name': 'Workload Domain',
        'description': 'Keywords to classify architectures by domain (web, data, integration, etc.)',
        'categories': ['web', 'data', 'integration', 'security', 'ai', 'infrastructure'],
    },
    'family_keywords': {
        'name': 'Architecture Family',
        'description': 'Keywords to classify architectures by family (foundation, iaas, paas, etc.)',
        'categories': ['foundation', 'iaas', 'paas', 'cloud_native', 'data', 'integration', 'specialized'],
    },
    'runtime_keywords': {
        'name': 'Runtime Model',
        'description': 'Keywords to identify runtime patterns (microservices, event_driven, api, etc.)',
        'categories': ['microservices', 'event_driven', 'api', 'n_tier', 'batch', 'monolith'],
    },
    'availability_keywords': {
        'name': 'Availability Model',
        'description': 'Keywords to identify availability requirements',
        'categories': ['multi_region_active_active', 'multi_region_active_passive', 'zone_redundant'],
    },
    'treatment_keywords': {
        'name': 'Gartner 8R Treatment',
        'description': 'Keywords for migration treatment classification (rehost, replatform, etc.)',
        'categories': ['rehost', 'replatform', 'refactor', 'rebuild', 'replace', 'retain', 'tolerate', 'retire'],
    },
    'time_category_keywords': {
        'name': 'TIME Category',
        'description': 'Keywords for strategic investment posture (invest, migrate, tolerate, eliminate)',
        'categories': ['invest', 'migrate', 'tolerate', 'eliminate'],
    },
    'operating_model_keywords': {
        'name': 'Operating Model',
        'description': 'Keywords for operational maturity level',
        'categories': ['devops', 'sre', 'transitional', 'traditional_it'],
    },
    'security_level_keywords': {
        'name': 'Security Level',
        'description': 'Keywords for security/compliance requirements',
        'categories': ['highly_regulated', 'regulated', 'enterprise', 'basic'],
    },
    'cost_profile_keywords': {
        'name': 'Cost Profile',
        'description': 'Keywords for cost optimization posture',
        'categories': ['cost_minimized', 'balanced', 'scale_optimized', 'innovation_first'],
    },
}


def render_keywords_editor() -> None:
    """Render the keywords editor tab."""
    st.header("Keyword Dictionaries")
    st.markdown("""
    Edit the keyword dictionaries used for automatic classification.
    Each dictionary maps categories to lists of keywords used to detect that classification.
    """)

    config = get_state('config')
    classification = config.classification

    # Dictionary selector
    selected_dict = st.selectbox(
        "Select Dictionary",
        options=list(DICTIONARIES.keys()),
        format_func=lambda x: f"{DICTIONARIES[x]['name']} ({x})"
    )

    if selected_dict:
        dict_info = DICTIONARIES[selected_dict]
        st.info(dict_info['description'])

        # Get the current dictionary values
        current_dict = getattr(classification, selected_dict)

        st.markdown("---")
        st.subheader(f"Edit: {dict_info['name']}")

        # Track if any changes were made
        changes_made = False
        updated_dict = {}

        # Render each category as an expander with a text area
        for category in dict_info['categories']:
            with st.expander(f"**{category}** ({len(current_dict.get(category, []))} keywords)"):
                current_keywords = current_dict.get(category, [])
                keywords_text = '\n'.join(current_keywords)

                new_keywords_text = st.text_area(
                    f"Keywords for {category}",
                    value=keywords_text,
                    height=150,
                    key=f"{selected_dict}_{category}",
                    help="One keyword or phrase per line"
                )

                # Parse the new keywords
                new_keywords = [k.strip() for k in new_keywords_text.strip().split('\n') if k.strip()]
                updated_dict[category] = new_keywords

                if new_keywords != current_keywords:
                    changes_made = True

        # Apply changes button
        col1, col2 = st.columns([1, 3])
        with col1:
            if st.button("Apply Changes", disabled=not changes_made, type="primary"):
                # Update the config
                setattr(classification, selected_dict, updated_dict)
                set_state('config', config)
                st.success(f"Updated {dict_info['name']} keywords!")
                st.rerun()

        with col2:
            if changes_made:
                st.warning("You have unsaved changes")

        # Show statistics
        st.markdown("---")
        st.subheader("Dictionary Statistics")

        cols = st.columns(3)
        total_keywords = sum(len(v) for v in current_dict.values())
        cols[0].metric("Total Keywords", total_keywords)
        cols[1].metric("Categories", len(current_dict))
        cols[2].metric("Avg per Category", f"{total_keywords / len(current_dict):.1f}" if current_dict else "0")
