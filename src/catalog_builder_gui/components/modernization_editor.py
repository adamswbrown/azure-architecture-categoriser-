"""Modernization Options Editor component for Catalog Builder GUI.

This module provides a Streamlit UI for viewing and editing technology-to-Azure
modernization mappings loaded from Modernisation_Options.csv.
"""

from pathlib import Path
from typing import Optional

import streamlit as st

from catalog_builder_gui.state import get_state, set_state

# Import modernization modules
from architecture_scorer.modernization_schema import (
    ModernizationConfig,
    ModernizationOption,
    TechnologyGroup,
)
from architecture_scorer.modernization_loader import (
    load_modernization_config,
    save_modernization_config,
    set_default_option,
    find_csv_path,
)

# Page size for pagination
ITEMS_PER_PAGE = 25


@st.cache_data(ttl=300)  # Cache for 5 minutes
def _cached_load_config() -> Optional[dict]:
    """Load modernization config with caching.

    Returns dict instead of Pydantic model for caching compatibility.
    """
    try:
        config = load_modernization_config()
        # Convert to dict for caching (Pydantic models can't be cached directly)
        return {"options": [opt.model_dump() for opt in config.options]}
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _load_config() -> Optional[ModernizationConfig]:
    """Load modernization config, using cached version if available."""
    # Check for in-memory config with changes
    config = get_state("modernization_config")
    if config is not None:
        return config

    # Load from cache
    cached_data = _cached_load_config()
    if cached_data is None:
        return None

    # Convert cached dict back to Pydantic model
    try:
        options = [ModernizationOption(**opt) for opt in cached_data["options"]]
        config = ModernizationConfig(options=options)
        set_state("modernization_config", config)
        set_state("modernization_changes", False)
        return config
    except Exception as e:
        st.error(f"Error loading modernization options: {e}")
        return None


def _render_filters(config: ModernizationConfig) -> ModernizationConfig:
    """Render filter controls and return filtered config."""
    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        search = st.text_input(
            "Search technologies",
            value=get_state("mod_search", ""),
            placeholder="Type to search...",
            key="mod_search_input",
        )
        set_state("mod_search", search)

    with col2:
        categories = ["All Categories"] + config.get_categories()
        selected_cat = st.selectbox(
            "Category",
            categories,
            index=0,
            key="mod_category_filter",
        )

    with col3:
        strategies = ["All Strategies"] + config.get_strategies()
        selected_strategy = st.selectbox(
            "Strategy",
            strategies,
            index=0,
            key="mod_strategy_filter",
        )

    # Apply filters
    filtered = config
    if search:
        filtered = filtered.search(search)
    if selected_cat != "All Categories":
        filtered = filtered.filter_by_category(selected_cat)
    if selected_strategy != "All Strategies":
        filtered = filtered.filter_by_strategy(selected_strategy)

    return filtered


def _render_option_card(
    option: ModernizationOption, is_default: bool, group_key: str, option_index: int, page_index: int
) -> tuple[bool, bool, dict]:
    """Render a single option card with edit controls.

    Returns:
        Tuple of (set_as_default, delete, updates_dict)
    """
    import hashlib

    set_default = False
    delete = False
    updates: dict = {}

    # Complexity color
    complexity_colors = {
        "Easy": "🟢",
        "Medium": "🟡",
        "Hard": "🔴",
    }
    complexity_icon = complexity_colors.get(option.modernisation_complexity, "⚪")

    # Strategy badge
    strategy_badges = {
        "PaaS": "🌐 PaaS",
        "IaaS": "🖥️ IaaS",
        "Eliminate": "❌ Eliminate",
        "SaaS": "☁️ SaaS",
    }
    strategy_badge = strategy_badges.get(
        option.modernisation_strategy, option.modernisation_strategy
    )

    # Build display - use hash for unique key including group, page, and option index
    default_marker = " ⭐ **Default**" if is_default else ""
    key_source = f"{group_key}_{option.modernisation_treatment}_{page_index}_{option_index}"
    card_key = hashlib.md5(key_source.encode()).hexdigest()[:16]

    with st.container(border=True):
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            st.markdown(
                f"**{option.modernisation_candidate}**{default_marker}"
            )
            if option.modernisation_candidate_description:
                st.caption(option.modernisation_candidate_description[:100] + "..."
                          if len(option.modernisation_candidate_description or "") > 100
                          else option.modernisation_candidate_description)

        with col2:
            st.markdown(
                f"{strategy_badge} | {complexity_icon} {option.modernisation_complexity} | {option.applicable_treatment}"
            )

        with col3:
            if not is_default:
                if st.button("Set Default", key=f"default_{card_key}", use_container_width=True):
                    set_default = True

        # Expandable edit section
        with st.expander("Edit Details", expanded=False):
            edit_col1, edit_col2 = st.columns(2)

            with edit_col1:
                new_complexity = st.selectbox(
                    "Complexity",
                    ["Easy", "Medium", "Hard"],
                    index=["Easy", "Medium", "Hard"].index(option.modernisation_complexity)
                    if option.modernisation_complexity in ["Easy", "Medium", "Hard"]
                    else 1,
                    key=f"complexity_{card_key}",
                )
                if new_complexity != option.modernisation_complexity:
                    updates["modernisation_complexity"] = new_complexity

                new_score = st.number_input(
                    "Complexity Score",
                    min_value=0,
                    max_value=4,
                    value=option.complexity_score,
                    key=f"score_{card_key}",
                )
                if new_score != option.complexity_score:
                    updates["complexity_score"] = new_score

            with edit_col2:
                new_strategy = st.selectbox(
                    "Strategy",
                    ["PaaS", "IaaS", "Eliminate", "SaaS"],
                    index=["PaaS", "IaaS", "Eliminate", "SaaS"].index(option.modernisation_strategy)
                    if option.modernisation_strategy in ["PaaS", "IaaS", "Eliminate", "SaaS"]
                    else 0,
                    key=f"strategy_{card_key}",
                )
                if new_strategy != option.modernisation_strategy:
                    updates["modernisation_strategy"] = new_strategy

                new_treatment = st.selectbox(
                    "Treatment",
                    ["Replatform/Refactor", "Replace", "Rehost", "Retire", "Retain"],
                    index=["Replatform/Refactor", "Replace", "Rehost", "Retire", "Retain"].index(
                        option.applicable_treatment
                    )
                    if option.applicable_treatment
                    in ["Replatform/Refactor", "Replace", "Rehost", "Retire", "Retain"]
                    else 0,
                    key=f"treatment_{card_key}",
                )
                if new_treatment != option.applicable_treatment:
                    updates["applicable_treatment"] = new_treatment

            new_benefits = st.text_area(
                "Key Benefits",
                value=option.key_benefits or "",
                height=80,
                key=f"benefits_{card_key}",
            )
            if new_benefits != (option.key_benefits or ""):
                updates["key_benefits"] = new_benefits if new_benefits else None

            new_description = st.text_area(
                "Description",
                value=option.modernisation_candidate_description or "",
                height=80,
                key=f"description_{card_key}",
            )
            if new_description != (option.modernisation_candidate_description or ""):
                updates["modernisation_candidate_description"] = (
                    new_description if new_description else None
                )

            # Delete button (in expander)
            if st.button(
                "🗑️ Delete Option",
                key=f"delete_{card_key}",
                type="secondary",
            ):
                delete = True

    return set_default, delete, updates


def _render_technology_group(group: TechnologyGroup, page_index: int) -> list[dict]:
    """Render a technology group with all its options.

    Args:
        group: The technology group to render.
        page_index: Index of this group on the current page (for unique keys).

    Returns:
        List of changes to apply.
    """
    changes = []
    group_key = group.friendly_name.replace(" ", "_").replace(".", "_")

    with st.expander(
        f"**{group.friendly_name}** ({group.server_sub_category}) - {len(group.options)} options",
        expanded=False,
    ):
        default_opt = group.default_option

        for idx, option in enumerate(group.options):
            is_default = default_opt and option.modernisation_candidate == default_opt.modernisation_candidate
            set_default, delete, updates = _render_option_card(
                option, is_default, group_key, idx, page_index
            )

            if set_default:
                changes.append({
                    "action": "set_default",
                    "friendly_name": group.friendly_name,
                    "modernisation_candidate": option.modernisation_candidate,
                })
            if delete:
                changes.append({
                    "action": "delete",
                    "friendly_name": group.friendly_name,
                    "modernisation_candidate": option.modernisation_candidate,
                })
            if updates:
                changes.append({
                    "action": "update",
                    "friendly_name": group.friendly_name,
                    "modernisation_candidate": option.modernisation_candidate,
                    "updates": updates,
                })

        # Add new option button
        st.markdown("---")
        if st.button(f"➕ Add Option for {group.friendly_name}", key=f"add_{group_key}"):
            set_state("adding_option_for", group.friendly_name)
            st.rerun()

    return changes


def _render_add_option_form(friendly_name: str) -> Optional[ModernizationOption]:
    """Render form for adding a new option."""
    st.subheader(f"Add New Option for {friendly_name}")

    with st.form(key="add_option_form"):
        col1, col2 = st.columns(2)

        with col1:
            candidate = st.text_input(
                "Azure Target Service *",
                placeholder="e.g., Azure App Service",
            )
            strategy = st.selectbox(
                "Strategy *",
                ["PaaS", "IaaS", "Eliminate", "SaaS"],
            )
            complexity = st.selectbox(
                "Complexity *",
                ["Easy", "Medium", "Hard"],
                index=1,
            )

        with col2:
            treatment = st.selectbox(
                "Treatment *",
                ["Replatform/Refactor", "Replace", "Rehost", "Retire", "Retain"],
            )
            score = st.number_input(
                "Complexity Score",
                min_value=0,
                max_value=4,
                value=1,
            )
            is_default = st.checkbox("Set as default option")

        benefits = st.text_area("Key Benefits", height=80)
        description = st.text_area("Description", height=80)

        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("Add Option", type="primary")
        with col_cancel:
            cancelled = st.form_submit_button("Cancel")

        if cancelled:
            set_state("adding_option_for", None)
            st.rerun()

        if submitted:
            if not candidate:
                st.error("Azure Target Service is required")
                return None

            # Get existing config for category info
            config = get_state("modernization_config")
            existing = config.get_options_for_technology(friendly_name)
            category = existing[0].server_sub_category if existing else "Other"

            option = ModernizationOption(
                server_sub_category=category,
                friendly_name=friendly_name,
                modernisation_candidate=candidate,
                modernisation_treatment=f"{friendly_name}-to-{candidate}",
                default_flag=is_default,
                modernisation_strategy=strategy,
                modernisation_complexity=complexity,
                applicable_treatment=treatment,
                complexity_score=score,
                key_benefits=benefits if benefits else None,
                modernisation_candidate_description=description if description else None,
            )

            set_state("adding_option_for", None)
            return option

    return None


def _render_add_technology_form() -> Optional[ModernizationOption]:
    """Render form for adding a completely new technology."""
    st.subheader("Add New Technology")

    with st.form(key="add_technology_form"):
        col1, col2 = st.columns(2)

        with col1:
            tech_name = st.text_input(
                "Technology Name *",
                placeholder="e.g., Ruby on Rails",
            )
            category = st.text_input(
                "Category *",
                placeholder="e.g., Ruby Framework",
            )
            candidate = st.text_input(
                "Azure Target Service *",
                placeholder="e.g., Azure App Service",
            )

        with col2:
            strategy = st.selectbox(
                "Strategy *",
                ["PaaS", "IaaS", "Eliminate", "SaaS"],
            )
            complexity = st.selectbox(
                "Complexity *",
                ["Easy", "Medium", "Hard"],
                index=1,
            )
            treatment = st.selectbox(
                "Treatment *",
                ["Replatform/Refactor", "Replace", "Rehost", "Retire", "Retain"],
            )

        benefits = st.text_area("Key Benefits", height=80)
        description = st.text_area("Description", height=80)

        col_submit, col_cancel = st.columns(2)
        with col_submit:
            submitted = st.form_submit_button("Add Technology", type="primary")
        with col_cancel:
            cancelled = st.form_submit_button("Cancel")

        if cancelled:
            set_state("adding_new_technology", False)
            st.rerun()

        if submitted:
            if not tech_name or not category or not candidate:
                st.error("Technology Name, Category, and Azure Target Service are required")
                return None

            option = ModernizationOption(
                server_sub_category=category,
                friendly_name=tech_name,
                modernisation_candidate=candidate,
                modernisation_treatment=f"{tech_name}-to-{candidate}",
                default_flag=True,  # First option is always default
                modernisation_strategy=strategy,
                modernisation_complexity=complexity,
                applicable_treatment=treatment,
                complexity_score=1,
                key_benefits=benefits if benefits else None,
                modernisation_candidate_description=description if description else None,
            )

            set_state("adding_new_technology", False)
            return option

    return None


def _apply_changes(config: ModernizationConfig, changes: list[dict]) -> ModernizationConfig:
    """Apply a list of changes to the configuration."""
    from architecture_scorer.modernization_loader import (
        remove_option,
        update_option,
        set_default_option,
    )

    for change in changes:
        action = change["action"]
        friendly_name = change["friendly_name"]
        candidate = change["modernisation_candidate"]

        if action == "set_default":
            config = set_default_option(config, friendly_name, candidate)
        elif action == "delete":
            config = remove_option(config, friendly_name, candidate)
        elif action == "update":
            config = update_option(config, friendly_name, candidate, change["updates"])

    return config


def render_modernization_editor() -> None:
    """Render the main modernization options editor."""
    st.header("Modernization Options Editor")
    st.markdown(
        "Configure technology-to-Azure-service mappings used when generating "
        "architecture recommendations from Dr. Migrate data."
    )

    # Load configuration
    config = _load_config()
    if config is None:
        st.warning(
            "Modernisation_Options.csv not found. Please ensure the file exists "
            "in the project root directory."
        )
        return

    # Check for add forms
    adding_option_for = get_state("adding_option_for")
    adding_new_tech = get_state("adding_new_technology", False)

    if adding_option_for:
        new_option = _render_add_option_form(adding_option_for)
        if new_option:
            from architecture_scorer.modernization_loader import add_option
            config = add_option(config, new_option)
            set_state("modernization_config", config)
            set_state("modernization_changes", True)
            st.success(f"Added {new_option.modernisation_candidate} for {adding_option_for}")
            st.rerun()
        return

    if adding_new_tech:
        new_option = _render_add_technology_form()
        if new_option:
            from architecture_scorer.modernization_loader import add_option
            config = add_option(config, new_option)
            set_state("modernization_config", config)
            set_state("modernization_changes", True)
            st.success(f"Added new technology: {new_option.friendly_name}")
            st.rerun()
        return

    # Stats bar
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Technologies", config.technology_count)
    with col2:
        st.metric("Total Options", config.option_count)
    with col3:
        st.metric("Categories", len(config.get_categories()))
    with col4:
        has_changes = get_state("modernization_changes", False)
        if has_changes:
            st.warning("Unsaved changes")
        else:
            st.success("No changes")

    st.markdown("---")

    # Action buttons
    btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

    with btn_col1:
        if st.button("➕ Add New Technology", type="primary", use_container_width=True):
            set_state("adding_new_technology", True)
            st.rerun()

    with btn_col2:
        has_changes = get_state("modernization_changes", False)
        if st.button(
            "💾 Save Changes",
            type="primary" if has_changes else "secondary",
            disabled=not has_changes,
            use_container_width=True,
        ):
            csv_path = find_csv_path()
            if csv_path:
                try:
                    save_modernization_config(config, csv_path, backup=True)
                    set_state("modernization_changes", False)
                    st.success(f"Saved to {csv_path}")
                except Exception as e:
                    st.error(f"Error saving: {e}")
            else:
                st.error("Could not find CSV path")

    with btn_col3:
        if st.button("🔄 Reload from CSV", use_container_width=True):
            set_state("modernization_config", None)
            set_state("modernization_changes", False)
            set_state("mod_current_page", 1)
            _cached_load_config.clear()  # Clear the cache
            st.rerun()

    with btn_col4:
        if st.button("📥 Export CSV", use_container_width=True):
            import io
            import csv as csv_module

            output = io.StringIO()
            fieldnames = [
                "ServerSubCategory", "FriendlyName", "modernisation_candidate",
                "modernisation_treatment", "default_flag", "modernisation_strategy",
                "modernisation_complexity", "applicable_treatment", "complexity_score",
                "migration_goal_category", "combo_flag", "light_modernisation_id",
                "modernisation_focused_id", "key_benefits",
                "modernisation_candidate_description", "modernisation_candidate_logo",
            ]
            writer = csv_module.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()

            for opt in config.options:
                writer.writerow({
                    "ServerSubCategory": opt.server_sub_category,
                    "FriendlyName": opt.friendly_name,
                    "modernisation_candidate": opt.modernisation_candidate,
                    "modernisation_treatment": opt.modernisation_treatment,
                    "default_flag": "1" if opt.default_flag else "0",
                    "modernisation_strategy": opt.modernisation_strategy,
                    "modernisation_complexity": opt.modernisation_complexity,
                    "applicable_treatment": opt.applicable_treatment,
                    "complexity_score": str(opt.complexity_score),
                    "migration_goal_category": opt.migration_goal_category or "",
                    "combo_flag": "1" if opt.combo_flag else "0",
                    "light_modernisation_id": str(opt.light_modernisation_id) if opt.light_modernisation_id else "",
                    "modernisation_focused_id": str(opt.modernisation_focused_id) if opt.modernisation_focused_id else "",
                    "key_benefits": opt.key_benefits or "",
                    "modernisation_candidate_description": opt.modernisation_candidate_description or "",
                    "modernisation_candidate_logo": opt.modernisation_candidate_logo or "",
                })

            st.download_button(
                "Download CSV",
                data=output.getvalue(),
                file_name="Modernisation_Options_export.csv",
                mime="text/csv",
            )

    st.markdown("---")

    # Filters
    filtered_config = _render_filters(config)

    st.markdown("---")

    # Show filtered count and pagination
    groups = filtered_config.get_technology_groups()
    total_groups = len(groups)
    total_pages = max(1, (total_groups + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)

    # Pagination controls
    page_col1, page_col2, page_col3 = st.columns([1, 2, 1])

    with page_col1:
        current_page = get_state("mod_current_page", 1)
        if current_page > total_pages:
            current_page = 1
            set_state("mod_current_page", 1)

    with page_col2:
        st.caption(
            f"Showing {total_groups} technologies ({filtered_config.option_count} options) "
            f"- Page {current_page} of {total_pages}"
        )

    with page_col3:
        new_page = st.number_input(
            "Page",
            min_value=1,
            max_value=total_pages,
            value=current_page,
            key="mod_page_input",
            label_visibility="collapsed",
        )
        if new_page != current_page:
            set_state("mod_current_page", new_page)
            st.rerun()

    # Pagination buttons
    nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)
    with nav_col1:
        if st.button("⏮️ First", disabled=current_page == 1, use_container_width=True):
            set_state("mod_current_page", 1)
            st.rerun()
    with nav_col2:
        if st.button("◀️ Previous", disabled=current_page == 1, use_container_width=True):
            set_state("mod_current_page", current_page - 1)
            st.rerun()
    with nav_col3:
        if st.button("Next ▶️", disabled=current_page == total_pages, use_container_width=True):
            set_state("mod_current_page", current_page + 1)
            st.rerun()
    with nav_col4:
        if st.button("Last ⏭️", disabled=current_page == total_pages, use_container_width=True):
            set_state("mod_current_page", total_pages)
            st.rerun()

    st.markdown("---")

    # Calculate page slice
    start_idx = (current_page - 1) * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, total_groups)
    page_groups = groups[start_idx:end_idx]

    # Render only current page of technology groups
    all_changes = []
    for page_idx, group in enumerate(page_groups):
        changes = _render_technology_group(group, page_idx)
        all_changes.extend(changes)

    # Apply any changes
    if all_changes:
        config = _apply_changes(config, all_changes)
        set_state("modernization_config", config)
        set_state("modernization_changes", True)
        st.rerun()
