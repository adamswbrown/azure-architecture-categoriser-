"""Filter presets component for quick filter selection."""

import streamlit as st

from catalog_builder_gui.state import get_state, set_state


# Product-focused presets matching the web UI
PRODUCT_PRESETS = {
    'Show All (No Filter)': {
        'products': [],
        'categories': [],
        'description': 'Complete catalog, no restrictions (~289 architectures)',
        'icon': '🌐',
    },
    'Azure (All)': {
        'products': ['azure'],
        'categories': [],
        'description': 'All Azure services (~280 architectures)',
        'icon': '☁️',
    },
    'Azure Kubernetes (AKS)': {
        'products': ['azure-kubernetes-service'],
        'categories': [],
        'description': 'AKS container orchestration architectures',
        'icon': '🚢',
    },
    'Azure App Service': {
        'products': ['azure-app-service'],
        'categories': [],
        'description': 'Web app hosting architectures',
        'icon': '🌐',
    },
    'Azure Functions': {
        'products': ['azure-functions'],
        'categories': [],
        'description': 'Serverless function architectures',
        'icon': '⚡',
    },
    'Azure Containers': {
        'products': ['azure-container'],
        'categories': [],
        'description': 'Container Apps, Instances, Registry',
        'icon': '📦',
    },
    'Azure SQL': {
        'products': ['azure-sql'],
        'categories': [],
        'description': 'SQL Database, Managed Instance, VMs',
        'icon': '🗄️',
    },
    'Azure Cosmos DB': {
        'products': ['azure-cosmos-db'],
        'categories': [],
        'description': 'Globally distributed database',
        'icon': '🌍',
    },
    'Azure AI / OpenAI': {
        'products': ['azure-openai', 'azure-machine-learning', 'azure-cognitive-services'],
        'categories': [],
        'description': 'AI & ML workloads',
        'icon': '🤖',
    },
    'Microsoft Entra': {
        'products': ['entra'],
        'categories': [],
        'description': 'Identity & access management',
        'icon': '🔐',
    },
    'Microsoft Fabric': {
        'products': ['fabric'],
        'categories': [],
        'description': 'Data platform architectures',
        'icon': '🧵',
    },
    'Power Platform': {
        'products': ['power'],
        'categories': [],
        'description': 'Power Apps, Automate, BI',
        'icon': '⚙️',
    },
    'Microsoft Defender': {
        'products': ['defender'],
        'categories': [],
        'description': 'Security solutions',
        'icon': '🛡️',
    },
    'Azure Networking': {
        'products': ['azure-virtual-network', 'azure-front-door', 'azure-application-gateway', 'azure-load-balancer'],
        'categories': [],
        'description': 'Network architectures',
        'icon': '🔗',
    },
    'Azure Security': {
        'products': ['azure-key-vault', 'azure-firewall', 'defender'],
        'categories': [],
        'description': 'Security & compliance',
        'icon': '🔒',
    },
}

CATEGORY_PRESETS = {
    'Web Apps': {
        'products': [],
        'categories': ['web'],
        'description': 'Web application architectures',
        'icon': '🕸️',
    },
    'Containers': {
        'products': [],
        'categories': ['containers'],
        'description': 'Container workloads',
        'icon': '📦',
    },
    'Databases': {
        'products': [],
        'categories': ['databases'],
        'description': 'Database solutions',
        'icon': '🗃️',
    },
    'AI + ML': {
        'products': [],
        'categories': ['ai-machine-learning'],
        'description': 'AI category',
        'icon': '🧠',
    },
    'Analytics': {
        'products': [],
        'categories': ['analytics'],
        'description': 'Analytics & BI',
        'icon': '📊',
    },
    'Migration': {
        'products': [],
        'categories': ['migration'],
        'description': 'Migration patterns',
        'icon': '🚚',
    },
    'Hybrid Cloud': {
        'products': [],
        'categories': ['hybrid'],
        'description': 'Hybrid scenarios',
        'icon': '🔀',
    },
    'IoT': {
        'products': [],
        'categories': ['iot'],
        'description': 'IoT solutions',
        'icon': '📡',
    },
}

QUALITY_PRESETS = {
    'Reference Only': {
        'require_yml': True,
        'topics': ['reference-architecture'],
        'description': 'Curated reference architectures only',
        'icon': '⭐',
    },
    'Examples Included': {
        'require_yml': False,
        'topics': ['reference-architecture', 'example-scenario', 'solution-idea'],
        'description': 'Include example scenarios',
        'icon': '📋',
    },
    'High Quality Only': {
        'require_yml': True,
        'topics': [],
        'description': 'YamlMime:Architecture files only',
        'icon': '✅',
    },
}


def render_filter_presets() -> None:
    """Render the filter presets tab."""
    st.header("Filter Presets")

    config = get_state('config')
    active_filters = get_state('active_filters')

    # Current filter status
    st.subheader("Current Filter Status")

    col1, col2, col3 = st.columns(3)

    with col1:
        if not active_filters['products'] and not active_filters['categories']:
            st.success("No filters active (showing all)")
        else:
            products_str = ', '.join(active_filters['products']) if active_filters['products'] else 'None'
            st.info(f"Products: {products_str}")

    with col2:
        categories_str = ', '.join(active_filters['categories']) if active_filters['categories'] else 'None'
        st.info(f"Categories: {categories_str}")

    with col3:
        topics = config.filters.allowed_topics
        topics_str = ', '.join(topics) if topics else 'All'
        st.info(f"Topics: {topics_str}")

    # Clear all filters button (prominent)
    if st.button("Clear All Filters (Show All)", type="primary", use_container_width=True):
        set_state('active_filters', {'products': [], 'categories': [], 'topics': []})
        config.filters.allowed_products = []
        config.filters.allowed_categories = []
        config.filters.require_architecture_yml = False
        set_state('config', config)
        st.success("All filters cleared!")
        st.rerun()

    st.markdown("---")

    # Product Presets
    st.subheader("Product Presets")
    st.markdown("Filter by Azure products and services")

    cols = st.columns(3)
    for i, (name, preset) in enumerate(PRODUCT_PRESETS.items()):
        col = cols[i % 3]
        with col:
            if st.button(
                f"{preset['icon']} {name}",
                key=f"product_{name}",
                help=preset['description'],
                use_container_width=True
            ):
                active_filters['products'] = preset['products']
                config.filters.allowed_products = preset['products']
                set_state('active_filters', active_filters)
                set_state('config', config)
                st.rerun()

    st.markdown("---")

    # Category Presets
    st.subheader("Category Presets")
    st.markdown("Filter by Azure categories")

    cols = st.columns(4)
    for i, (name, preset) in enumerate(CATEGORY_PRESETS.items()):
        col = cols[i % 4]
        with col:
            if st.button(
                f"{preset['icon']} {name}",
                key=f"category_{name}",
                help=preset['description'],
                use_container_width=True
            ):
                active_filters['categories'] = preset['categories']
                config.filters.allowed_categories = preset['categories']
                set_state('active_filters', active_filters)
                set_state('config', config)
                st.rerun()

    st.markdown("---")

    # Quality Presets
    st.subheader("Quality Presets")
    st.markdown("Filter by catalog quality level")

    cols = st.columns(3)
    for i, (name, preset) in enumerate(QUALITY_PRESETS.items()):
        col = cols[i % 3]
        with col:
            if st.button(
                f"{preset['icon']} {name}",
                key=f"quality_{name}",
                help=preset['description'],
                use_container_width=True
            ):
                config.filters.require_architecture_yml = preset.get('require_yml', False)
                if preset.get('topics'):
                    config.filters.allowed_topics = preset['topics']
                set_state('config', config)
                st.rerun()

    st.markdown("---")

    # Custom presets section
    st.subheader("Custom Presets")

    custom_presets = get_state('custom_presets', {})

    if custom_presets:
        st.markdown("Your saved presets:")
        for preset_name, preset_data in custom_presets.items():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{preset_name}**")
            with col2:
                if st.button("Load", key=f"load_{preset_name}"):
                    active_filters['products'] = preset_data.get('products', [])
                    active_filters['categories'] = preset_data.get('categories', [])
                    config.filters.allowed_products = preset_data.get('products', [])
                    config.filters.allowed_categories = preset_data.get('categories', [])
                    set_state('active_filters', active_filters)
                    set_state('config', config)
                    st.rerun()
            with col3:
                if st.button("Delete", key=f"delete_{preset_name}"):
                    del custom_presets[preset_name]
                    set_state('custom_presets', custom_presets)
                    st.rerun()
    else:
        st.info("No custom presets saved yet")

    # Save current as preset
    with st.expander("Save Current Filters as Preset"):
        preset_name = st.text_input("Preset Name", key="new_preset_name")
        if st.button("Save Preset", disabled=not preset_name):
            custom_presets[preset_name] = {
                'products': active_filters['products'],
                'categories': active_filters['categories'],
            }
            set_state('custom_presets', custom_presets)
            st.success(f"Saved preset: {preset_name}")
            st.rerun()
