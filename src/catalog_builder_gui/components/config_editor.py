"""Config editor component for visual YAML configuration editing."""

import yaml

import streamlit as st

from catalog_builder.config import CatalogConfig
from catalog_builder_gui.state import get_state, set_state
from architecture_recommendations_app.utils.sanitize import validate_output_path


def render_config_editor() -> None:
    """Render the config editor tab."""
    st.header("Configuration Editor")

    # Explanation section
    with st.expander("ℹ️ Configuration Reference", expanded=False):
        st.markdown("""
        ### Configuration Sections

        **1. Detection Settings**
        Controls how architectures are identified in documents:

        | Setting | Default | Purpose |
        |---------|---------|---------|
        | Folder Score | 0.3 | Weight when doc is in architecture folder |
        | Diagram Score | 0.2 | Weight when doc has architecture diagrams |
        | Section Score | 0.2 | Weight when doc has "Architecture" sections |
        | Keyword Score | 0.15 | Weight for architecture keywords |
        | Frontmatter Score | 0.15 | Weight for ms.topic metadata |
        | Min Confidence | 0.3 | Threshold to include (sum of weights) |

        A document needs total score ≥ min_confidence AND ≥2 signals to be included.

        **2. Filter Settings**
        Controls which documents make it into the catalog:

        | Setting | Default | Purpose |
        |---------|---------|---------|
        | Allowed Topics | reference-architecture, example-scenario, solution-idea | Only include these ms.topic values |
        | Allowed Categories | [] (all) | Restrict to specific azureCategories |
        | Require YML | False | Only include docs with YamlMime:Architecture |
        | Exclude Examples | False | Exclude learning/POC examples (for production-only catalogs) |

        **3. Classification Thresholds**
        Controls automatic classification assignment:

        | Setting | Default | Purpose |
        |---------|---------|---------|
        | Treatment Threshold | 2.0 | Min keyword score for treatment |
        | TIME Category Threshold | 2.0 | Min score for TIME category |
        | Security Score Threshold | 3.0 | Min for regulated security levels |
        | VM Rehost Boost | 3.0 | Boost rehost score when VMs present |
        | Container Refactor Boost | 2.0 | Boost refactor when containers present |
        | Managed Replatform Boost | 2.0 | Boost replatform for managed services |

        ### Using the Configuration

        Save the YAML and use with the CLI:
        ```bash
        catalog-builder build-catalog \\
            --repo-path ./architecture-center \\
            --config catalog-config.yaml \\
            --out catalog.json
        ```
        """)

    st.markdown("""
    Edit the complete configuration visually or directly in YAML format.
    Changes in either column will sync when applied.
    """)

    config = get_state('config')

    # Two column layout
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Form Editor")
        _render_form_editor(config)

    with col2:
        st.subheader("YAML Preview")
        _render_yaml_editor(config)


def _render_form_editor(config: CatalogConfig) -> None:
    """Render the form-based editor."""

    # Detection Settings
    with st.expander("Detection Settings", expanded=False):
        st.markdown("Score weights for architecture detection:")

        detection = config.detection

        col1, col2 = st.columns(2)
        with col1:
            detection.folder_score = st.slider(
                "Folder Score Weight",
                0.0, 1.0, detection.folder_score,
                step=0.1,
                help="Weight for folder location signals"
            )
            detection.diagram_score = st.slider(
                "Diagram Score Weight",
                0.0, 1.0, detection.diagram_score,
                step=0.1,
                help="Weight for diagram presence signals"
            )
            detection.section_score = st.slider(
                "Section Score Weight",
                0.0, 1.0, detection.section_score,
                step=0.1,
                help="Weight for architecture section signals"
            )
        with col2:
            detection.keyword_score = st.slider(
                "Keyword Score Weight",
                0.0, 1.0, detection.keyword_score,
                step=0.1,
                help="Weight for keyword signals"
            )
            detection.frontmatter_score = st.slider(
                "Frontmatter Score Weight",
                0.0, 1.0, detection.frontmatter_score,
                step=0.1,
                help="Weight for frontmatter signals"
            )
            detection.min_confidence = st.slider(
                "Min Confidence Threshold",
                0.0, 1.0, detection.min_confidence,
                step=0.1,
                help="Minimum confidence score to include"
            )

    # Filter Settings
    with st.expander("Filter Settings", expanded=True):
        filters = config.filters

        st.markdown("**Topic Filters:**")
        all_topics = [
            'reference-architecture', 'example-scenario', 'solution-idea',
            'concept-article', 'best-practice', 'include', 'hub-page'
        ]
        filters.allowed_topics = st.multiselect(
            "Allowed Topics",
            options=all_topics,
            default=filters.allowed_topics,
            help="Only include documents with these ms.topic values"
        )

        st.markdown("**Category Filters:**")
        all_categories = [
            'web', 'ai-machine-learning', 'analytics', 'compute', 'containers',
            'databases', 'devops', 'hybrid', 'identity', 'integration', 'iot',
            'management-and-governance', 'media', 'migration', 'networking',
            'security', 'storage', 'developer-tools'
        ]
        filters.allowed_categories = st.multiselect(
            "Allowed Categories",
            options=all_categories,
            default=filters.allowed_categories,
            help="Only include documents with these categories (empty = all)"
        )

        st.markdown("**Quality Filters:**")
        col1, col2 = st.columns(2)
        with col1:
            filters.require_architecture_yml = st.checkbox(
                "Require YamlMime:Architecture",
                value=filters.require_architecture_yml,
                help="Only include docs with paired .yml metadata files"
            )
        with col2:
            filters.exclude_examples = st.checkbox(
                "Exclude Examples",
                value=filters.exclude_examples,
                help="Exclude example scenarios and solution ideas"
            )

    # Classification Thresholds
    with st.expander("Classification Thresholds", expanded=False):
        classification = config.classification

        col1, col2 = st.columns(2)
        with col1:
            classification.treatment_threshold = st.number_input(
                "Treatment Threshold",
                min_value=0.0, max_value=10.0,
                value=classification.treatment_threshold,
                step=0.5,
                help="Min score for treatment selection"
            )
            classification.time_category_threshold = st.number_input(
                "TIME Category Threshold",
                min_value=0.0, max_value=10.0,
                value=classification.time_category_threshold,
                step=0.5,
                help="Min score for TIME category selection"
            )
            classification.security_score_threshold = st.number_input(
                "Security Score Threshold",
                min_value=0.0, max_value=10.0,
                value=classification.security_score_threshold,
                step=0.5,
                help="Min keywords for regulated security levels"
            )
        with col2:
            classification.vm_rehost_boost = st.number_input(
                "VM Rehost Boost",
                min_value=0.0, max_value=10.0,
                value=classification.vm_rehost_boost,
                step=0.5,
                help="Boost for rehost when VMs present"
            )
            classification.container_refactor_boost = st.number_input(
                "Container Refactor Boost",
                min_value=0.0, max_value=10.0,
                value=classification.container_refactor_boost,
                step=0.5,
                help="Boost for refactor when containers present"
            )
            classification.managed_replatform_boost = st.number_input(
                "Managed Service Replatform Boost",
                min_value=0.0, max_value=10.0,
                value=classification.managed_replatform_boost,
                step=0.5,
                help="Boost for replatform with managed services"
            )

    # URL Settings
    with st.expander("URL Settings", expanded=False):
        config.urls.learn_base_url = st.text_input(
            "Microsoft Learn Base URL",
            value=config.urls.learn_base_url,
            help="Base URL for generated Learn links"
        )

    # Apply button for form changes
    if st.button("Apply Form Changes", type="primary"):
        set_state('config', config)
        st.success("Configuration updated!")
        st.rerun()


def _render_yaml_editor(config: CatalogConfig) -> None:
    """Render the YAML editor panel."""

    # Show diff from defaults option
    show_diff = st.checkbox("Show Only Changes from Defaults", value=False)

    # Generate YAML
    if show_diff:
        yaml_content = _get_diff_yaml(config)
    else:
        yaml_content = yaml.dump(
            config.model_dump(),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True
        )

    # Editable YAML
    edited_yaml = st.text_area(
        "YAML Configuration",
        value=yaml_content,
        height=500,
        key="yaml_editor"
    )

    # Action buttons
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Validate YAML"):
            try:
                data = yaml.safe_load(edited_yaml)
                CatalogConfig.model_validate(data)
                st.success("YAML is valid!")
            except yaml.YAMLError as e:
                st.error(f"YAML syntax error: {e}")
            except Exception as e:
                st.error(f"Validation error: {e}")

    with col2:
        if st.button("Apply YAML Changes"):
            try:
                data = yaml.safe_load(edited_yaml)
                new_config = CatalogConfig.model_validate(data)
                set_state('config', new_config)
                st.success("Configuration applied!")
                st.rerun()
            except Exception as e:
                st.error(f"Error applying changes: {e}")

    with col3:
        st.download_button(
            "Download YAML",
            data=yaml_content,
            file_name="catalog-config.yaml",
            mime="application/x-yaml"
        )

    st.markdown("---")

    # Save to file
    st.subheader("Save Configuration")
    save_path = st.text_input(
        "Save Path",
        value="catalog-config.yaml",
        help="Path to save the configuration file"
    )

    if st.button("Save to File"):
        # Validate the save path before writing
        is_valid, message, validated_path = validate_output_path(save_path)
        if not is_valid:
            st.error(f"Invalid save path: {message}")
        else:
            try:
                with open(validated_path, 'w', encoding='utf-8') as f:
                    f.write(yaml_content)
                st.success(f"Saved to {validated_path}")
            except Exception as e:
                st.error(f"Error saving file: {e}")


def _get_diff_yaml(config: CatalogConfig) -> str:
    """Get YAML containing only values that differ from defaults."""
    default_config = CatalogConfig()
    current_dict = config.model_dump()
    default_dict = default_config.model_dump()

    diff_dict = _recursive_diff(current_dict, default_dict)

    if not diff_dict:
        return "# No changes from defaults"

    return yaml.dump(
        diff_dict,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True
    )


def _recursive_diff(current: dict, default: dict) -> dict:
    """Recursively find differences between current and default config."""
    diff = {}

    for key, value in current.items():
        default_value = default.get(key)

        if isinstance(value, dict) and isinstance(default_value, dict):
            nested_diff = _recursive_diff(value, default_value)
            if nested_diff:
                diff[key] = nested_diff
        elif value != default_value:
            diff[key] = value

    return diff
