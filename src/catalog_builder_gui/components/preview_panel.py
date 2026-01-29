"""Preview panel component for catalog build preview."""

from pathlib import Path
from collections import Counter

import streamlit as st

from catalog_builder_gui.state import get_state


def render_preview_panel() -> None:
    """Render the preview build tab."""
    st.header("Preview Catalog Build")
    st.markdown("""
    Preview what architectures would be included in the catalog with current settings.
    This scans the repository without building the full catalog.
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

            # Find markdown files
            docs_path = repo_path / 'docs'
            md_files = list(docs_path.rglob('*.md'))[:max_files]

            total = len(md_files)
            included = []
            excluded = []
            exclusion_reasons: Counter = Counter()
            categories: Counter = Counter()
            topics: Counter = Counter()

            for i, md_file in enumerate(md_files):
                progress_bar.progress((i + 1) / total)
                status_text.text(f"Scanning {md_file.name}...")

                try:
                    # Parse the document
                    doc = parser.parse(md_file)

                    # Run detection
                    detection = detector.detect(doc, repo_path)
                    rel_path = md_file.relative_to(repo_path)

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
                    excluded.append({
                        'path': str(md_file.relative_to(repo_path)),
                        'reason': f'Error: {str(e)[:50]}',
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
