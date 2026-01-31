"""Preview panel component for catalog build preview."""

import os
from pathlib import Path
from collections import Counter

import streamlit as st

from catalog_builder_gui.state import get_state, set_state


def _get_default_output_path() -> str:
    """Get the default output path for the catalog (project root)."""
    # Try to find the project root (where architecture-catalog.json should live)
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / 'pyproject.toml').exists() or (parent / 'architecture-catalog.json').exists():
            return str(parent / 'architecture-catalog.json')
    # Fallback to current directory
    return 'architecture-catalog.json'


def _is_debug_mode() -> bool:
    """Check if debug mode is enabled via environment variable.

    Set CATALOG_BUILDER_DEBUG=1 to enable full stack traces.
    """
    return os.environ.get('CATALOG_BUILDER_DEBUG', '').lower() in ('1', 'true', 'yes')


def render_preview_panel() -> None:
    """Render the preview build tab."""
    repo_path = get_state('repo_path', '')

    # Check repo status first
    if not repo_path:
        st.warning("Please set the repository path in the sidebar first.")
        return

    repo = Path(repo_path)
    if not repo.exists() or not (repo / 'docs').exists():
        st.error("Invalid repository path. Please check the path in the sidebar.")
        return

    # =========================================================================
    # QUICK ACTION BUTTONS (Option 4)
    # =========================================================================
    st.header("Quick Build")

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.markdown("### Quick Build")
            st.markdown("**~51 Reference Architectures**")
            st.caption("Production-ready, curated patterns")
            if st.button("Build Quick Catalog", type="primary", use_container_width=True, key="quick_build"):
                # Set config for reference architectures only
                from catalog_builder.config import CatalogConfig
                config = CatalogConfig()  # Uses defaults (reference-architecture + exclude_examples=True)
                # Update session state so _generate_catalog uses the correct config
                set_state('config', config)
                _generate_catalog(repo_path, _get_default_output_path())

    with col2:
        with st.container(border=True):
            st.markdown("### Full Build")
            st.markdown("**~171 All Architectures**")
            st.caption("Includes examples & solution ideas")
            if st.button("Build Full Catalog", type="secondary", use_container_width=True, key="full_build"):
                # Set config for all content types
                from catalog_builder.config import CatalogConfig
                config = CatalogConfig()
                config.filters.allowed_topics = ['reference-architecture', 'example-scenario', 'solution-idea']
                config.filters.exclude_examples = False
                # Update session state so _generate_catalog uses the correct config
                set_state('config', config)
                _generate_catalog(repo_path, _get_default_output_path())

    st.markdown("---")

    # =========================================================================
    # CUSTOM BUILD (Option 1 + Option 3)
    # =========================================================================
    st.header("Custom Build")

    with st.container(border=True):
        st.markdown("Configure exactly what to include in your catalog.")

        # Content Type Selector (Option 1 - unified selector)
        st.subheader("Content Types")

        # Define content types with descriptions and approximate counts
        content_types = {
            "Reference Architectures (~51)": {
                "topic": "reference-architecture",
                "description": "Production-ready, curated architecture patterns",
                "is_example": False,
            },
            "Example Scenarios (~86)": {
                "topic": "example-scenario",
                "description": "Learning-focused implementations for POC/demos",
                "is_example": True,
            },
            "Solution Ideas (~34)": {
                "topic": "solution-idea",
                "description": "Conceptual solutions and starting points",
                "is_example": True,
            },
        }

        # Get current state
        config = get_state('config')
        active_filters = get_state('active_filters', {'products': [], 'categories': [], 'topics': []})
        current_topics = config.filters.allowed_topics or []

        # Build default selection based on current config
        default_selection = []
        for label, info in content_types.items():
            if info["topic"] in current_topics:
                # Check if examples are excluded - if so, don't show example types as selected
                if info["is_example"] and config.filters.exclude_examples:
                    continue
                default_selection.append(label)

        # If no selection and defaults, select reference architectures
        if not default_selection:
            default_selection = ["Reference Architectures (~51)"]

        # Multiselect for content types
        selected_types = st.multiselect(
            "Select content types to include:",
            options=list(content_types.keys()),
            default=default_selection,
            help="Choose which types of architecture documentation to include",
            key="content_type_selector"
        )

        # Show descriptions for selected types
        if selected_types:
            for label in selected_types:
                info = content_types[label]
                st.caption(f"  **{label.split('(')[0].strip()}**: {info['description']}")

        # Update config based on selection
        new_topics = [content_types[label]["topic"] for label in selected_types]
        has_examples = any(content_types[label]["is_example"] for label in selected_types)

        # Set exclude_examples based on whether any example types are selected
        config.filters.allowed_topics = new_topics
        config.filters.exclude_examples = not has_examples  # False if examples selected, True otherwise
        set_state('config', config)

        # =========================================================================
        # LIVE PREVIEW COUNT (Option 3)
        # =========================================================================
        st.markdown("---")

        # Calculate and show live preview
        if new_topics:
            estimated_count = 0
            breakdown = []
            for label in selected_types:
                info = content_types[label]
                # Extract count from label (e.g., "~51" from "Reference Architectures (~51)")
                import re
                match = re.search(r'\(~(\d+)\)', label)
                if match:
                    count = int(match.group(1))
                    estimated_count += count
                    breakdown.append(f"{info['topic'].replace('-', ' ').title()}: ~{count}")

            st.info(f"**Estimated catalog size: ~{estimated_count} architectures**")
            if len(breakdown) > 1:
                st.caption("Breakdown: " + " | ".join(breakdown))
        else:
            st.warning("Select at least one content type to build a catalog.")

        st.markdown("---")

        # Additional filters (optional)
        with st.expander("Additional Filters (optional)", expanded=False):
            # Product filter
            st.markdown("**Product Filter** (leave empty for all)")
            product_default = ", ".join(active_filters.get('products', []))

            product_input = st.text_input(
                "Products (comma-separated)",
                value=product_default,
                help="e.g., azure-kubernetes-service, azure-app-service",
                placeholder="azure-kubernetes-service, azure-sql-database"
            )

            # Parse and sync to config
            product_list = [p.strip() for p in product_input.split(",") if p.strip()]
            config.filters.allowed_products = product_list if product_list else None
            active_filters['products'] = product_list

            # Category filter
            st.markdown("**Category Filter** (leave empty for all)")
            category_default = ", ".join(active_filters.get('categories', []))

            category_input = st.text_input(
                "Categories (comma-separated)",
                value=category_default,
                help="e.g., web, containers, ai-machine-learning",
                placeholder="web, containers, databases"
            )

            # Parse and sync to config
            category_list = [c.strip() for c in category_input.split(",") if c.strip()]
            config.filters.allowed_categories = category_list if category_list else None
            active_filters['categories'] = category_list

            # Save state
            set_state('config', config)
            set_state('active_filters', active_filters)

            # Show filter summary if any filters are active
            if product_list or category_list:
                st.caption(
                    f"Active filters: "
                    f"{f'Products: {len(product_list)}' if product_list else ''}"
                    f"{' | ' if product_list and category_list else ''}"
                    f"{f'Categories: {len(category_list)}' if category_list else ''}"
                )

        # Preview scan (optional)
        with st.expander("Run Preview Scan (optional)", expanded=False):
            st.markdown("""
            Scan the repository to see exactly which architectures match your settings.
            This is optional - use it to verify your configuration before building.
            """)

            col1, col2 = st.columns([2, 1])
            with col1:
                max_files = st.slider(
                    "Max files to scan",
                    min_value=10,
                    max_value=500,
                    value=100,
                    step=10,
                    help="Limit the number of files to scan for faster preview"
                )
            with col2:
                st.write("")  # Spacer
                run_preview = st.button("Run Preview", type="secondary", use_container_width=True)

            if run_preview:
                _run_preview_scan(repo, max_files)

        st.markdown("---")

        # Generate button
        st.subheader("Generate Custom Catalog")

        col1, col2 = st.columns([2, 1])
        with col1:
            custom_output = st.text_input(
                "Output File",
                value=_get_default_output_path(),
                key="custom_output",
                help="Path to save the catalog JSON (defaults to project root)"
            )
        with col2:
            st.write("")  # Spacer
            st.write("")
            if st.button("Generate Catalog", type="primary", use_container_width=True, key="custom_generate",
                         disabled=not selected_types):
                _generate_catalog(repo_path, custom_output)


def _run_preview_scan(repo_path: Path, max_files: int) -> None:
    """Run the preview scan and display results."""
    from catalog_builder.parser import MarkdownParser
    from catalog_builder.detector import ArchitectureDetector

    # Resolve symlinks (e.g., /tmp -> /private/tmp on macOS)
    repo_path = repo_path.resolve()

    config = get_state('config')

    # Apply config to global state temporarily
    import catalog_builder.config as config_module
    config_module._config = config

    st.markdown("---")

    with st.spinner("Scanning repository..."):
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            parser = MarkdownParser()
            detector = ArchitectureDetector()

            # Find markdown files - prioritize architecture folders
            docs_path = repo_path / 'docs'

            # Architecture folders to scan first (where architectures are most likely)
            priority_folders = [
                'example-scenario',
                'reference-architectures',
                'solution-ideas',
                'ai-ml',
                'databases',
                'web-apps',
                'networking',
                'security',
                'hybrid',
                'microservices',
                'serverless',
                'iot',
                'data',
                'integration',
                'high-availability',
            ]

            md_files = []

            # Collect files from priority folders first
            for folder in priority_folders:
                folder_path = docs_path / folder
                if folder_path.exists():
                    folder_files = list(folder_path.rglob('*.md'))
                    md_files.extend(folder_files)
                    if len(md_files) >= max_files:
                        break

            # If we still need more files, add from other locations
            if len(md_files) < max_files:
                all_files = set(docs_path.rglob('*.md'))
                existing = set(md_files)
                remaining = list(all_files - existing)
                md_files.extend(remaining[:max_files - len(md_files)])

            # Limit to max_files
            md_files = md_files[:max_files]

            total = len(md_files)
            included = []
            excluded = []
            exclusion_reasons: Counter = Counter()
            categories: Counter = Counter()
            topics: Counter = Counter()

            # Track unique errors for debugging
            error_samples: dict[str, str] = {}

            for i, md_file in enumerate(md_files):
                progress_bar.progress((i + 1) / total)
                status_text.text(f"Scanning {md_file.name}...")

                # Resolve file path to match repo_path
                md_file = md_file.resolve()

                try:
                    # Get relative path first
                    try:
                        rel_path = md_file.relative_to(repo_path)
                    except ValueError as ve:
                        if 'relative_to' not in error_samples:
                            error_samples['relative_to'] = f"{md_file} not relative to {repo_path}"
                        raise ve

                    # Parse the document
                    try:
                        doc = parser.parse_file(md_file)
                        if doc is None:
                            raise ValueError("Parser returned None (encoding or IO error)")
                    except Exception as pe:
                        if 'parse' not in error_samples:
                            error_samples['parse'] = f"{md_file.name}: {str(pe)[:200]}"
                        raise pe

                    # Run detection - pass string path
                    try:
                        detection = detector.detect(doc, str(repo_path))
                    except Exception as de:
                        if 'detect' not in error_samples:
                            error_samples['detect'] = f"{md_file.name}: {str(de)[:200]}"
                        raise de

                    if detection.is_architecture:
                        included.append({
                            'path': str(rel_path),
                            'name': doc.title or md_file.stem.replace('-', ' ').title(),
                            'confidence': detection.confidence,
                            'reasons': detection.reasons,
                            'categories': doc.arch_metadata.azure_categories,
                            'products': doc.arch_metadata.products,
                            'topic': doc.arch_metadata.ms_topic,
                        })
                        # Track categories and topics
                        for cat in doc.arch_metadata.azure_categories:
                            categories[cat] += 1
                        if doc.arch_metadata.ms_topic:
                            topics[doc.arch_metadata.ms_topic] += 1
                    else:
                        reason = detection.exclusion_reasons[0] if detection.exclusion_reasons else 'Not architecture content'
                        excluded.append({
                            'path': str(rel_path),
                            'reason': reason,
                        })
                        exclusion_reasons[reason] += 1

                except Exception as e:
                    error_type = type(e).__name__
                    error_msg = str(e)[:100]
                    reason = f'{error_type}: {error_msg[:40]}'

                    # Track sample errors for debugging
                    if error_type not in error_samples:
                        error_samples[error_type] = f"{md_file.name}: {error_msg}"

                    # Use filename if relative_to fails
                    try:
                        path_str = str(md_file.relative_to(repo_path))
                    except ValueError:
                        path_str = md_file.name

                    excluded.append({
                        'path': path_str,
                        'reason': reason,
                    })
                    exclusion_reasons[f'Parse error'] += 1

            progress_bar.empty()
            status_text.empty()

            # Display results
            _display_results(
                total=total,
                included=included,
                excluded=excluded,
                exclusion_reasons=exclusion_reasons,
                categories=categories,
                topics=topics,
                error_samples=error_samples,
            )

        except Exception as e:
            st.error(f"Error during scan: {e}")
            # Only show full traceback in debug mode to prevent information disclosure
            if _is_debug_mode():
                import traceback
                with st.expander("Debug Details (CATALOG_BUILDER_DEBUG=1)"):
                    st.code(traceback.format_exc())


def _display_results(
    total: int,
    included: list,
    excluded: list,
    exclusion_reasons: Counter,
    categories: Counter,
    topics: Counter,
    error_samples: dict[str, str] | None = None,
) -> None:
    """Display the preview scan results."""
    # Metrics row
    st.subheader("Summary")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Scanned", total)
    col2.metric("Included", len(included))
    col3.metric("Excluded", len(excluded))
    inclusion_rate = (len(included) / total * 100) if total > 0 else 0
    col4.metric("Inclusion Rate", f"{inclusion_rate:.1f}%")

    st.markdown("---")

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("By Category")
        if categories:
            st.bar_chart(dict(categories.most_common(10)))
        else:
            st.info("No categories detected")

    with col2:
        st.subheader("By Topic Type")
        if topics:
            st.bar_chart(dict(topics.most_common(10)))
        else:
            st.info("No topics detected")

    st.markdown("---")

    # Included architectures
    st.subheader(f"Included Architectures ({len(included)})")
    if included:
        for arch in included[:20]:  # Limit display
            with st.expander(f"**{arch['name']}** (confidence: {arch['confidence']:.2f})"):
                st.write(f"**Path:** `{arch['path']}`")
                st.write(f"**Topic:** {arch.get('topic', 'N/A')}")
                if arch.get('categories'):
                    st.write(f"**Categories:** {', '.join(arch['categories'])}")
                if arch.get('products'):
                    st.write(f"**Products:** {', '.join(arch['products'][:5])}")
                st.write(f"**Detection Signals:** {', '.join(arch['reasons'][:5])}")
        if len(included) > 20:
            st.info(f"Showing 20 of {len(included)} included architectures")
    else:
        st.warning("No architectures included with current filters")

    st.markdown("---")

    # Exclusion reasons
    st.subheader("Exclusion Reasons")
    if exclusion_reasons:
        for reason, count in exclusion_reasons.most_common():
            st.write(f"- **{reason}**: {count}")
    else:
        st.info("No exclusions")

    # Show error samples for debugging
    if error_samples:
        with st.expander("🔍 Error Details (for debugging)", expanded=True):
            st.warning(f"Found {len(error_samples)} unique error types")
            for error_type, sample in error_samples.items():
                st.code(f"{error_type}: {sample}", language="text")

    # Show preview summary - user can proceed to Step 3 to generate
    if len(included) > 0:
        st.success(f"Preview complete. Found **{len(included)} architectures** matching your current settings. Proceed to **Step 3** below to generate the catalog.")


def _generate_catalog(repo_path: str, output_path: str) -> None:
    """Generate the full catalog and display results."""
    import json
    from catalog_builder.catalog import CatalogBuilder
    from catalog_builder.schema import GenerationSettings

    config = get_state('config')

    if not repo_path:
        st.error("Repository path not set")
        return

    # Apply config to global state
    import catalog_builder.config as config_module
    config_module._config = config

    # Create generation settings to document what was included
    generation_settings = GenerationSettings(
        allowed_topics=config.filters.allowed_topics or [],
        allowed_products=config.filters.allowed_products,
        allowed_categories=config.filters.allowed_categories,
        require_architecture_yml=config.filters.require_architecture_yml,
        exclude_examples=config.filters.exclude_examples,
    )

    with st.spinner("Building full catalog (this may take a minute)..."):
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("Initializing catalog builder...")
            progress_bar.progress(10)

            builder = CatalogBuilder(Path(repo_path))

            status_text.text("Scanning repository...")
            progress_bar.progress(30)

            catalog = builder.build(generation_settings=generation_settings)

            status_text.text("Writing catalog file...")
            progress_bar.progress(80)

            # Write to file
            catalog_dict = catalog.model_dump(mode='json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(catalog_dict, f, indent=2, default=str)

            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()

            # Update session state so other pages automatically pick up the new catalog
            resolved_path = str(Path(output_path).resolve())
            set_state('catalog_path', resolved_path)
            set_state('catalog_source', 'catalog_builder')

            # Log what was generated for debugging
            topics_used = config.filters.allowed_topics or ['reference-architecture']
            exclude_examples = config.filters.exclude_examples

            # Success message with stats
            st.success(f"Catalog generated successfully with **{len(catalog.architectures)}** architectures!")
            st.info(f"Topics: {', '.join(topics_used)} | Exclude Examples: {exclude_examples}")

            # Calculate useful stats from the catalog
            all_services = set()
            all_categories = set()
            for arch in catalog.architectures:
                if arch.core_services:
                    all_services.update(arch.core_services)
                if arch.supporting_services:
                    all_services.update(arch.supporting_services)
                if arch.browse_categories:
                    all_categories.update(arch.browse_categories)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Architectures", len(catalog.architectures))
            col2.metric("Services", len(all_services))
            col3.metric("Categories", len(all_categories))
            col4.metric("File Size", f"{Path(output_path).stat().st_size / 1024:.1f} KB")

            st.caption(f"📁 Saved to: `{output_path}`")

            # Download button
            st.download_button(
                "Download Catalog JSON",
                data=json.dumps(catalog_dict, indent=2, default=str),
                file_name="architecture-catalog.json",
                mime="application/json",
                use_container_width=True
            )

            # Show CLI command for reference
            with st.expander("CLI Command (for automation)"):
                st.code(f"""catalog-builder build-catalog \\
    --repo-path {repo_path} \\
    --out {output_path}""", language="bash")

        except Exception as e:
            progress_bar.empty()
            status_text.empty()
            st.error(f"Error generating catalog: {e}")
            # Only show full traceback in debug mode to prevent information disclosure
            if _is_debug_mode():
                import traceback
                with st.expander("Debug Details (CATALOG_BUILDER_DEBUG=1)"):
                    st.code(traceback.format_exc())
