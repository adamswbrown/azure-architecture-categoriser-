"""Preview panel component for catalog build preview."""

from pathlib import Path
from collections import Counter

import streamlit as st

from catalog_builder_gui.state import get_state


def render_preview_panel() -> None:
    """Render the preview build tab."""
    st.header("Build Catalog")

    repo_path = get_state('repo_path', '')

    # Quick generate section at top
    if repo_path and Path(repo_path).exists():
        st.subheader("Quick Generate")
        st.markdown("""
        Generate the catalog using current settings. With defaults, this produces ~170 architectures
        including reference architectures, example scenarios, and solution ideas.
        """)

        col1, col2 = st.columns([2, 1])
        with col1:
            quick_output = st.text_input(
                "Output File",
                value="architecture-catalog.json",
                key="quick_output",
                help="Path to save the catalog JSON"
            )
        with col2:
            st.write("")  # Spacer
            st.write("")
            if st.button("Generate Catalog", type="primary", use_container_width=True, key="quick_generate"):
                _generate_catalog(repo_path, quick_output)

        st.markdown("---")

    # Preview section
    st.subheader("Preview (Optional)")
    st.markdown("Preview what will be included before generating, or customize filters first.")

    # Explanation section
    with st.expander("ℹ️ How Preview Works", expanded=False):
        st.markdown("""
        ### What This Does
        The preview scans the Azure Architecture Center repository to find architecture documents
        and shows which ones would be included in the catalog based on your current settings.

        ### Detection Process
        1. **Folder Scanning**: Prioritizes architecture folders (example-scenario, reference-architectures, etc.)
        2. **Document Parsing**: Extracts frontmatter metadata (ms.topic, products, categories)
        3. **Architecture Detection**: Applies heuristics to identify architecture content
        4. **Filter Application**: Applies your topic/product/category filters

        ### Key Metadata Fields
        - **ms.topic**: Document type (reference-architecture, example-scenario, solution-idea)
        - **azureCategories**: Categories like web, containers, databases, ai-machine-learning
        - **products**: Azure products like azure-kubernetes-service, azure-app-service

        ### Default Behavior
        By default, the catalog includes documents with ms.topic values:
        - `reference-architecture` - Curated reference architectures
        - `example-scenario` - Real-world implementation examples
        - `solution-idea` - Conceptual solution designs

        Documents without these topic values (tutorials, guides, landing pages) are excluded.
        """)

    st.markdown("""
    Preview what architectures would be included in the catalog with current settings.
    The scan prioritizes architecture folders to show relevant results quickly.
    """)

    repo_path = get_state('repo_path', '')

    if not repo_path:
        st.warning("Please set the repository path in the sidebar first.")
        return

    repo = Path(repo_path)
    if not repo.exists() or not (repo / 'docs').exists():
        st.error("Invalid repository path. Please check the path in the sidebar.")
        return

    # Preview controls
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
        run_preview = st.button("Run Preview", type="primary", use_container_width=True)

    if run_preview:
        _run_preview_scan(repo, max_files)


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
            import traceback
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

    # Generate catalog section (only show if we have results)
    if len(included) > 0:
        st.markdown("---")
        _render_generate_section(len(included))


def _render_generate_section(preview_count: int) -> None:
    """Render the generate catalog section after preview."""
    st.subheader("Generate Full Catalog")
    st.markdown(f"""
    The preview found **{preview_count} architectures**. Generate the full catalog now.
    """)

    col1, col2 = st.columns([2, 1])

    with col1:
        output_path = st.text_input(
            "Output Path",
            value="architecture-catalog.json",
            key="preview_output",
            help="Path to save the generated catalog JSON file"
        )

    with col2:
        st.write("")  # Spacer
        st.write("")  # Align with input
        if st.button("Generate Catalog", type="primary", use_container_width=True, key="preview_generate"):
            repo_path = get_state('repo_path', '')
            _generate_catalog(repo_path, output_path)


def _generate_catalog(repo_path: str, output_path: str) -> None:
    """Generate the full catalog and display results."""
    import json
    from catalog_builder.catalog import CatalogBuilder

    config = get_state('config')

    if not repo_path:
        st.error("Repository path not set")
        return

    # Apply config to global state
    import catalog_builder.config as config_module
    config_module._config = config

    with st.spinner("Building full catalog (this may take a minute)..."):
        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            status_text.text("Initializing catalog builder...")
            progress_bar.progress(10)

            builder = CatalogBuilder(repo_path)

            status_text.text("Scanning repository...")
            progress_bar.progress(30)

            catalog = builder.build()

            status_text.text("Writing catalog file...")
            progress_bar.progress(80)

            # Write to file
            catalog_dict = catalog.model_dump(mode='json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(catalog_dict, f, indent=2, default=str)

            progress_bar.progress(100)
            status_text.empty()
            progress_bar.empty()

            # Success message with stats
            st.success(f"Catalog generated successfully!")

            col1, col2, col3 = st.columns(3)
            col1.metric("Architectures", len(catalog.architectures))
            col2.metric("Output File", output_path)
            col3.metric("File Size", f"{Path(output_path).stat().st_size / 1024:.1f} KB")

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
            import traceback
            with st.expander("Error Details"):
                st.code(traceback.format_exc())
