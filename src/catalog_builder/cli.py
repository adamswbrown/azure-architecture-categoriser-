"""CLI for the Azure Architecture Catalog Builder."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .catalog import build_catalog, CatalogBuilder, CatalogValidator
from .config import load_config, save_default_config, find_config_file, reset_config, get_config
from .schema import ArchitectureCatalog, ExtractionConfidence, GenerationSettings
from .blob_upload import upload_catalog_to_blob


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="catalog-builder")
def main():
    """Azure Architecture Catalog Builder.

    Build-time CLI for compiling Azure Architecture Center documentation
    into a structured architecture catalog.
    """
    pass


@main.command(name='build-catalog')
@click.option(
    '--repo-path',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help='Path to the architecture-center repository clone'
)
@click.option(
    '--out',
    type=click.Path(path_type=Path),
    default='architecture-catalog.json',
    help='Output path for the catalog JSON file'
)
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    help='Path to configuration YAML file'
)
@click.option(
    '--category',
    multiple=True,
    help='Filter by Azure category (can specify multiple). E.g., --category web --category ai-machine-learning'
)
@click.option(
    '--product',
    multiple=True,
    help='Filter by Azure product (can specify multiple). E.g., --product azure-app-service'
)
@click.option(
    '--topic',
    multiple=True,
    help='Filter by ms.topic (can specify multiple). E.g., --topic reference-architecture'
)
@click.option(
    '--require-yml',
    is_flag=True,
    help='Only include documents with YamlMime:Architecture metadata files'
)
@click.option(
    '--exclude-examples',
    is_flag=True,
    help='Exclude example scenarios (keep only validated reference architectures)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Show detailed progress information'
)
@click.option(
    '--validate-only',
    is_flag=True,
    help='Only validate an existing catalog, do not build'
)
@click.option(
    '--extract-insights',
    is_flag=True,
    help='Extract content-derived insights from full document text (hybrid extraction)'
)
@click.option(
    '--use-llm/--no-llm',
    default=True,
    help='Use LLM for semantic extraction (default: enabled if API key available)'
)
@click.option(
    '--llm-provider',
    type=click.Choice(['auto', 'openai', 'anthropic', 'mock']),
    default='auto',
    help='LLM provider for semantic extraction (auto-detects from env vars)'
)
@click.option(
    '--api-key',
    type=str,
    envvar=['ANTHROPIC_API_KEY', 'OPENAI_API_KEY'],
    help='API key for LLM provider (or set ANTHROPIC_API_KEY/OPENAI_API_KEY env var)'
)
@click.option(
    '--upload-url',
    type=str,
    envvar='CATALOG_BLOB_URL',
    default=None,
    help='Azure Blob Storage SAS URL to upload the catalog after building (or set CATALOG_BLOB_URL env var)'
)
def build_catalog_cmd(
    repo_path: Path,
    out: Path,
    config: Path,
    category: tuple,
    product: tuple,
    topic: tuple,
    require_yml: bool,
    exclude_examples: bool,
    verbose: bool,
    validate_only: bool,
    extract_insights: bool,
    use_llm: bool,
    llm_provider: str,
    api_key: str,
    upload_url: str
):
    """Build the architecture catalog from source documentation.

    This command scans the Azure Architecture Center repository and
    generates a structured JSON catalog of architecture patterns.

    Example:
        catalog-builder build-catalog --repo-path ./architecture-center --out catalog.json
    """
    if validate_only:
        _validate_existing(out)
        return

    # Load config if specified, otherwise try to find one
    config_path = config or find_config_file()
    if config_path:
        try:
            load_config(config_path)
            if verbose:
                console.print(f"Loaded config from: {config_path}")
        except Exception as e:
            console.print(f"[yellow]Warning:[/yellow] Could not load config: {e}")
            reset_config()
    else:
        reset_config()

    # Apply CLI filter overrides
    cfg = get_config()
    if category:
        cfg.filters.allowed_categories = list(category)
    if product:
        cfg.filters.allowed_products = list(product)
    if topic:
        cfg.filters.allowed_topics = list(topic)
    if require_yml:
        cfg.filters.require_architecture_yml = True
    if exclude_examples:
        cfg.filters.exclude_examples = True

    console.print(f"\n[bold blue]Azure Architecture Catalog Builder[/bold blue]")
    console.print(f"Repository: {repo_path}")
    console.print(f"Output: {out}")
    if config_path:
        console.print(f"Config: {config_path}")

    # Show active filters
    active_filters = []
    if cfg.filters.allowed_categories:
        active_filters.append(f"categories: {', '.join(cfg.filters.allowed_categories)}")
    if cfg.filters.allowed_products:
        active_filters.append(f"products: {', '.join(cfg.filters.allowed_products)}")
    if cfg.filters.allowed_topics:
        active_filters.append(f"topics: {', '.join(cfg.filters.allowed_topics)}")
    if cfg.filters.require_architecture_yml:
        active_filters.append("require YamlMime:Architecture")
    if cfg.filters.exclude_examples:
        active_filters.append("excluding examples (reference architectures only)")

    if active_filters:
        console.print(f"Filters: {'; '.join(active_filters)}")

    if extract_insights:
        console.print(f"Content Insights: enabled (LLM: {llm_provider if use_llm else 'disabled'})")
    console.print()

    # Set API key in environment if provided via CLI
    if api_key and use_llm:
        import os
        if llm_provider == 'anthropic':
            os.environ['ANTHROPIC_API_KEY'] = api_key
        elif llm_provider == 'openai':
            os.environ['OPENAI_API_KEY'] = api_key
        elif llm_provider == 'auto':
            # Set both for auto-detection
            os.environ['ANTHROPIC_API_KEY'] = api_key
            os.environ['OPENAI_API_KEY'] = api_key

    # Create generation settings to document what was included
    generation_settings = GenerationSettings(
        allowed_topics=cfg.filters.allowed_topics or [],
        allowed_products=cfg.filters.allowed_products,
        allowed_categories=cfg.filters.allowed_categories,
        require_architecture_yml=cfg.filters.require_architecture_yml,
        exclude_examples=cfg.filters.exclude_examples,
    )

    def progress_callback(message: str):
        if verbose:
            console.print(f"  {message}")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=not verbose
    ) as progress:
        task = progress.add_task("Building catalog...", total=None)

        try:
            catalog, issues = build_catalog(
                repo_path,
                out,
                progress_callback,
                generation_settings=generation_settings,
                extract_content_insights=extract_insights,
                use_llm=use_llm,
                llm_provider=llm_provider
            )
        except Exception as e:
            console.print(f"\n[red]Error building catalog:[/red] {e}")
            if verbose:
                import traceback
                console.print(traceback.format_exc())
            sys.exit(1)

        progress.update(task, description="Complete!")

    # Print summary
    _print_summary(catalog)

    # Print issues if any
    if issues:
        console.print(f"\n[yellow]Validation Issues ({len(issues)}):[/yellow]")
        for issue in issues[:20]:  # Show first 20
            console.print(f"  • {issue}")
        if len(issues) > 20:
            console.print(f"  ... and {len(issues) - 20} more")

    console.print(f"\n[green]✓[/green] Catalog saved to: {out}")

    # Upload to Azure Blob Storage if requested
    if upload_url:
        try:
            console.print(f"\n[bold blue]Uploading to Azure Blob Storage...[/bold blue]")
            blob_url = upload_catalog_to_blob(out, blob_url=upload_url)
            console.print(f"[green]✓[/green] Uploaded to: {blob_url}")
        except ImportError as e:
            console.print(f"\n[red]Error:[/red] {e}")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]Upload failed:[/red] {e}")
            if verbose:
                import traceback
                console.print(traceback.format_exc())
            sys.exit(1)


@main.command(name='init-config')
@click.option(
    '--out', '-o',
    type=click.Path(path_type=Path),
    default='catalog-config.yaml',
    help='Output path for the configuration file'
)
@click.option(
    '--force', '-f',
    is_flag=True,
    help='Overwrite existing config file'
)
def init_config(out: Path, force: bool):
    """Generate a default configuration file.

    Creates a YAML configuration file with all available settings.
    Edit this file to customize detection, classification, and service normalization.

    Example:
        catalog-builder init-config --out my-config.yaml
    """
    if out.exists() and not force:
        console.print(f"[red]Error:[/red] Config file already exists: {out}")
        console.print("Use --force to overwrite")
        sys.exit(1)

    try:
        save_default_config(out)
        console.print(f"[green]✓[/green] Config file created: {out}")
        console.print("\nEdit this file to customize:")
        console.print("  • detection.include_folders - Folders to scan")
        console.print("  • detection.exclude_folders - Folders to skip")
        console.print("  • detection.architecture_keywords - Keywords for detection")
        console.print("  • classification.domain_keywords - Workload domain keywords")
        console.print("  • classification.family_keywords - Architecture family keywords")
        console.print("  • services.normalizations - Service name mappings")
        console.print("\nThen use with: catalog-builder build-catalog --config", str(out))
    except Exception as e:
        console.print(f"[red]Error creating config:[/red] {e}")
        sys.exit(1)


def _print_summary(catalog: ArchitectureCatalog):
    """Print a summary of the built catalog."""
    console.print(f"\n[bold]Catalog Summary[/bold]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")

    table.add_row("Total Architectures", str(catalog.total_architectures))

    # Count by family
    families = {}
    for arch in catalog.architectures:
        families[arch.family.value] = families.get(arch.family.value, 0) + 1

    for family, count in sorted(families.items(), key=lambda x: -x[1]):
        table.add_row(f"  Family: {family}", str(count))

    # Count by domain
    domains = {}
    for arch in catalog.architectures:
        domains[arch.workload_domain.value] = domains.get(arch.workload_domain.value, 0) + 1

    table.add_row("", "")
    for domain, count in sorted(domains.items(), key=lambda x: -x[1]):
        table.add_row(f"  Domain: {domain}", str(count))

    # Count AI suggestions
    ai_suggested = sum(
        1 for arch in catalog.architectures
        if arch.family_confidence.confidence == ExtractionConfidence.AI_SUGGESTED
    )
    table.add_row("", "")
    table.add_row("AI-Suggested Classifications", str(ai_suggested))
    table.add_row("Require Human Review", str(ai_suggested))

    # Content insights statistics
    with_insights = [a for a in catalog.architectures if a.content_insights]
    if with_insights:
        table.add_row("", "")
        table.add_row("[bold]Content Insights[/bold]", "")

        # Extraction source breakdown
        hybrid_count = sum(1 for a in with_insights if a.content_insights.extraction_source == "hybrid")
        rule_only = len(with_insights) - hybrid_count
        table.add_row("  LLM-enhanced (hybrid)", str(hybrid_count))
        table.add_row("  Rule-based only", str(rule_only))

        # Intended audience distribution
        audiences = {}
        for arch in with_insights:
            if arch.content_insights.intended_audience:
                aud = arch.content_insights.intended_audience.value
                audiences[aud] = audiences.get(aud, 0) + 1

        if audiences:
            table.add_row("", "")
            table.add_row("[bold]Intended Audience[/bold]", "")
            for aud, count in sorted(audiences.items(), key=lambda x: -x[1]):
                table.add_row(f"  {aud}", str(count))

        # Maturity tier distribution
        tiers = {}
        for arch in with_insights:
            if arch.content_insights.maturity_tier:
                tier = arch.content_insights.maturity_tier.value
                tiers[tier] = tiers.get(tier, 0) + 1

        if tiers:
            table.add_row("", "")
            table.add_row("[bold]Maturity Tier[/bold]", "")
            for tier, count in sorted(tiers.items(), key=lambda x: -x[1]):
                table.add_row(f"  {tier}", str(count))

        # Design patterns found
        all_patterns = set()
        for arch in with_insights:
            all_patterns.update(p.value for p in arch.content_insights.design_patterns)
        if all_patterns:
            table.add_row("", "")
            table.add_row("Design Patterns Found", str(len(all_patterns)))

        # WAF pillars coverage
        all_pillars = set()
        for arch in with_insights:
            all_pillars.update(p.value for p in arch.content_insights.waf_pillars_covered)
        if all_pillars:
            table.add_row("WAF Pillars Covered", str(len(all_pillars)))

    console.print(table)


def _validate_existing(catalog_path: Path):
    """Validate an existing catalog file."""
    import json

    if not catalog_path.exists():
        console.print(f"[red]Error:[/red] Catalog file not found: {catalog_path}")
        sys.exit(1)

    try:
        with open(catalog_path, 'r') as f:
            data = json.load(f)
        catalog = ArchitectureCatalog.model_validate(data)
    except Exception as e:
        console.print(f"[red]Error loading catalog:[/red] {e}")
        sys.exit(1)

    validator = CatalogValidator()
    issues = validator.validate(catalog)

    console.print(f"\n[bold]Catalog Validation[/bold]")
    console.print(f"Total architectures: {catalog.total_architectures}")

    if issues:
        console.print(f"\n[yellow]Issues ({len(issues)}):[/yellow]")
        for issue in issues:
            console.print(f"  • {issue}")
        sys.exit(1)
    else:
        console.print(f"\n[green]✓[/green] Catalog is valid")


@main.command()
@click.option(
    '--catalog',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to the catalog JSON file'
)
@click.option(
    '--id',
    'arch_id',
    type=str,
    help='Show details for a specific architecture ID'
)
@click.option(
    '--family',
    type=str,
    help='Filter by architecture family'
)
@click.option(
    '--domain',
    type=str,
    help='Filter by workload domain'
)
def inspect(catalog: Path, arch_id: str, family: str, domain: str):
    """Inspect the contents of a catalog file.

    Example:
        catalog-builder inspect --catalog architecture-catalog.json --family cloud_native
    """
    import json

    with open(catalog, 'r') as f:
        data = json.load(f)
    cat = ArchitectureCatalog.model_validate(data)

    if arch_id:
        # Show single architecture
        for arch in cat.architectures:
            if arch.architecture_id == arch_id:
                _print_architecture_detail(arch)
                return
        console.print(f"[red]Architecture not found:[/red] {arch_id}")
        return

    # Filter and list
    architectures = cat.architectures
    if family:
        architectures = [a for a in architectures if a.family.value == family]
    if domain:
        architectures = [a for a in architectures if a.workload_domain.value == domain]

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="cyan", max_width=40)
    table.add_column("Name", max_width=50)
    table.add_column("Family")
    table.add_column("Domain")
    table.add_column("Services", justify="right")

    for arch in architectures[:50]:
        table.add_row(
            arch.architecture_id,
            arch.name[:50] if arch.name else "-",
            arch.family.value,
            arch.workload_domain.value,
            str(len(arch.azure_services_used))
        )

    console.print(table)

    if len(architectures) > 50:
        console.print(f"\n... showing 50 of {len(architectures)} architectures")


def _print_architecture_detail(arch):
    """Print detailed information about an architecture."""
    console.print(f"\n[bold blue]{arch.name}[/bold blue]")
    console.print(f"ID: {arch.architecture_id}")
    console.print(f"Path: {arch.source_repo_path}")
    if arch.learn_url:
        console.print(f"URL: {arch.learn_url}")

    console.print(f"\n[bold]Description[/bold]")
    console.print(arch.description or "(none)")

    console.print(f"\n[bold]Classification[/bold]")
    console.print(f"  Family: {arch.family.value} ({arch.family_confidence.confidence.value})")
    console.print(f"  Domain: {arch.workload_domain.value} ({arch.workload_domain_confidence.confidence.value})")

    console.print(f"\n[bold]Runtime Models[/bold]")
    for model in arch.expected_runtime_models:
        console.print(f"  • {model.value}")

    console.print(f"\n[bold]Azure Services ({len(arch.azure_services_used)})[/bold]")
    for service in arch.azure_services_used:
        console.print(f"  • {service}")

    console.print(f"\n[bold]Complexity[/bold]")
    console.print(f"  Implementation: {arch.complexity.implementation.value}")
    console.print(f"  Operations: {arch.complexity.operations.value}")

    if arch.diagram_assets:
        console.print(f"\n[bold]Diagrams ({len(arch.diagram_assets)})[/bold]")
        for diagram in arch.diagram_assets:
            console.print(f"  • {diagram}")

    if arch.extraction_warnings:
        console.print(f"\n[yellow]Warnings[/yellow]")
        for warning in arch.extraction_warnings:
            console.print(f"  • {warning}")

    # Content insights
    if arch.content_insights:
        ci = arch.content_insights
        console.print(f"\n[bold]Content Insights[/bold] (source: {ci.extraction_source})")

        if ci.intended_audience:
            console.print(f"  Intended Audience: {ci.intended_audience.value}")
        if ci.maturity_tier:
            console.print(f"  Maturity Tier: {ci.maturity_tier.value}")
        if ci.target_slo:
            console.print(f"  Target SLO: {ci.target_slo}%")

        if ci.waf_pillars_covered:
            console.print(f"\n  [bold]WAF Pillars:[/bold]")
            for pillar in ci.waf_pillars_covered:
                console.print(f"    • {pillar.value}")

        if ci.design_patterns:
            console.print(f"\n  [bold]Design Patterns:[/bold]")
            for pattern in ci.design_patterns:
                console.print(f"    • {pattern.value}")

        if ci.team_prerequisites:
            console.print(f"\n  [bold]Team Prerequisites:[/bold]")
            for prereq in ci.team_prerequisites:
                console.print(f"    • {prereq}")

        if ci.key_tradeoffs:
            console.print(f"\n  [bold]Key Tradeoffs:[/bold]")
            for tradeoff in ci.key_tradeoffs:
                console.print(f"    • {tradeoff}")

        if ci.explicit_limitations:
            console.print(f"\n  [bold]Limitations:[/bold]")
            for limitation in ci.explicit_limitations:
                console.print(f"    • {limitation}")


@main.command()
@click.option(
    '--catalog',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to the catalog JSON file'
)
def stats(catalog: Path):
    """Show statistics about a catalog.

    Example:
        catalog-builder stats --catalog architecture-catalog.json
    """
    import json

    with open(catalog, 'r') as f:
        data = json.load(f)
    cat = ArchitectureCatalog.model_validate(data)

    console.print(f"\n[bold blue]Catalog Statistics[/bold blue]")
    console.print(f"Generated: {cat.generated_at}")
    console.print(f"Source: {cat.source_repo}")
    if cat.source_commit:
        console.print(f"Commit: {cat.source_commit[:12]}")

    # Show generation settings if present
    if cat.generation_settings:
        console.print(f"\n[bold]Generation Settings[/bold]")
        gs = cat.generation_settings
        if gs.allowed_topics:
            console.print(f"  Topics: {', '.join(gs.allowed_topics)}")
        else:
            console.print(f"  Topics: all (no filter)")
        if gs.allowed_products:
            console.print(f"  Products: {', '.join(gs.allowed_products)}")
        if gs.allowed_categories:
            console.print(f"  Categories: {', '.join(gs.allowed_categories)}")
        if gs.require_architecture_yml:
            console.print(f"  YamlMime:Architecture: required")
        if gs.exclude_examples:
            console.print(f"  Examples: excluded")

    # Aggregate stats
    total_services = sum(len(a.azure_services_used) for a in cat.architectures)
    total_diagrams = sum(len(a.diagram_assets) for a in cat.architectures)

    # Unique services
    all_services = set()
    for a in cat.architectures:
        all_services.update(a.azure_services_used)

    console.print(f"\n[bold]Overview[/bold]")
    console.print(f"  Total architectures: {cat.total_architectures}")
    console.print(f"  Total service references: {total_services}")
    console.print(f"  Unique services: {len(all_services)}")
    console.print(f"  Total diagrams: {total_diagrams}")

    # Confidence breakdown
    auto = sum(1 for a in cat.architectures
               if a.family_confidence.confidence == ExtractionConfidence.AUTOMATIC)
    ai = sum(1 for a in cat.architectures
             if a.family_confidence.confidence == ExtractionConfidence.AI_SUGGESTED)
    manual = sum(1 for a in cat.architectures
                 if a.family_confidence.confidence == ExtractionConfidence.MANUAL_REQUIRED)

    console.print(f"\n[bold]Classification Confidence[/bold]")
    console.print(f"  Automatic: {auto}")
    console.print(f"  AI-Suggested: {ai}")
    console.print(f"  Manual Required: {manual}")

    # Top services
    service_counts = {}
    for a in cat.architectures:
        for s in a.azure_services_used:
            service_counts[s] = service_counts.get(s, 0) + 1

    console.print(f"\n[bold]Top 10 Azure Services[/bold]")
    for service, count in sorted(service_counts.items(), key=lambda x: -x[1])[:10]:
        console.print(f"  {count:3d} × {service}")

    # Content insights statistics
    with_insights = [a for a in cat.architectures if a.content_insights]
    if with_insights:
        console.print(f"\n[bold]Content Insights[/bold]")
        hybrid_count = sum(1 for a in with_insights if a.content_insights.extraction_source == "hybrid")
        rule_only = len(with_insights) - hybrid_count
        console.print(f"  With insights: {len(with_insights)}/{cat.total_architectures}")
        console.print(f"  LLM-enhanced (hybrid): {hybrid_count}")
        console.print(f"  Rule-based only: {rule_only}")

        # Intended audience distribution
        audiences = {}
        for arch in with_insights:
            if arch.content_insights.intended_audience:
                aud = arch.content_insights.intended_audience.value
                audiences[aud] = audiences.get(aud, 0) + 1

        if audiences:
            console.print(f"\n[bold]Intended Audience Distribution[/bold]")
            for aud, count in sorted(audiences.items(), key=lambda x: -x[1]):
                console.print(f"  {count:3d} × {aud}")

        # Maturity tier distribution
        tiers = {}
        for arch in with_insights:
            if arch.content_insights.maturity_tier:
                tier = arch.content_insights.maturity_tier.value
                tiers[tier] = tiers.get(tier, 0) + 1

        if tiers:
            console.print(f"\n[bold]Maturity Tier Distribution[/bold]")
            for tier, count in sorted(tiers.items(), key=lambda x: -x[1]):
                console.print(f"  {count:3d} × {tier}")

        # Top design patterns
        pattern_counts = {}
        for arch in with_insights:
            for p in arch.content_insights.design_patterns:
                pattern_counts[p.value] = pattern_counts.get(p.value, 0) + 1

        if pattern_counts:
            console.print(f"\n[bold]Top Design Patterns[/bold]")
            for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1])[:8]:
                console.print(f"  {count:3d} × {pattern}")

        # WAF pillars coverage
        pillar_counts = {}
        for arch in with_insights:
            for p in arch.content_insights.waf_pillars_covered:
                pillar_counts[p.value] = pillar_counts.get(p.value, 0) + 1

        if pillar_counts:
            console.print(f"\n[bold]WAF Pillar Coverage[/bold]")
            for pillar, count in sorted(pillar_counts.items(), key=lambda x: -x[1]):
                console.print(f"  {count:3d} × {pillar}")


@main.command(name='list-filters')
@click.option(
    '--repo-path',
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help='Path to the architecture-center repository clone'
)
@click.option(
    '--type', 'filter_type',
    type=click.Choice(['all', 'categories', 'products', 'topics']),
    default='all',
    help='Type of filters to list'
)
@click.option(
    '--min-count',
    type=int,
    default=1,
    help='Minimum document count to show a filter value'
)
def list_filters(repo_path: Path, filter_type: str, min_count: int):
    """List available filter values from the repository.

    Scans YML files to show available categories, products, and topics
    with document counts. Use this to discover valid filter values.

    Products support prefix matching: --product azure matches all azure-* products.

    Example:
        catalog-builder list-filters --repo-path ./architecture-center
        catalog-builder list-filters --repo-path ./repo --type products --min-count 5
    """
    from collections import Counter
    import yaml

    console.print(f"\n[bold blue]Scanning Filter Values[/bold blue]")
    console.print(f"Repository: {repo_path}\n")

    categories: Counter = Counter()
    products: Counter = Counter()
    topics: Counter = Counter()

    # Scan all YML files
    docs_path = repo_path / "docs"
    if not docs_path.exists():
        console.print("[red]Error:[/red] docs/ directory not found")
        sys.exit(1)

    yml_files = list(docs_path.rglob("*.yml"))
    console.print(f"Scanning {len(yml_files)} YML files...")

    for yml_file in yml_files:
        try:
            with open(yml_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # Skip non-architecture YML files
            if not content.startswith('### YamlMime:Architecture'):
                continue

            # Parse YAML (skip the first line)
            lines = content.split('\n', 1)
            if len(lines) > 1:
                data = yaml.safe_load(lines[1])
                if data:
                    # Extract categories
                    if 'azureCategories' in data:
                        for cat in data['azureCategories']:
                            if isinstance(cat, str):
                                categories[cat] += 1

                    # Extract products
                    if 'products' in data:
                        for prod in data['products']:
                            if isinstance(prod, str):
                                products[prod] += 1

                    # Extract topic from metadata
                    if 'metadata' in data and isinstance(data['metadata'], dict):
                        topic = data['metadata'].get('ms.topic')
                        if topic:
                            topics[topic] += 1

        except Exception:
            continue

    # Display results
    if filter_type in ('all', 'categories'):
        _print_filter_table(
            "Azure Categories",
            categories,
            min_count,
            "Use with: --category <value>"
        )

    if filter_type in ('all', 'products'):
        # Group products by prefix for hierarchical view
        _print_filter_table(
            "Azure Products",
            products,
            min_count,
            "Use with: --product <value> (prefix matching: 'azure' matches all 'azure-*')"
        )

        # Show product prefixes summary
        if filter_type == 'products':
            _print_product_prefixes(products)

    if filter_type in ('all', 'topics'):
        _print_filter_table(
            "Topics (ms.topic)",
            topics,
            min_count,
            "Use with: --topic <value>"
        )

    # Print summary
    console.print(f"\n[bold]Summary[/bold]")
    console.print(f"  Unique categories: {len(categories)}")
    console.print(f"  Unique products: {len(products)}")
    console.print(f"  Unique topics: {len(topics)}")


def _print_filter_table(title: str, counter, min_count: int, hint: str):
    """Print a table of filter values with counts."""
    from collections import Counter
    filtered = [(k, v) for k, v in counter.items() if v >= min_count]
    if not filtered:
        console.print(f"\n[bold]{title}[/bold]: (none with count >= {min_count})")
        return

    console.print(f"\n[bold]{title}[/bold] ({len(filtered)} values)")
    console.print(f"[dim]{hint}[/dim]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Value", style="cyan")
    table.add_column("Count", justify="right")

    for value, count in sorted(filtered, key=lambda x: (-x[1], x[0])):
        table.add_row(value, str(count))

    console.print(table)


def _print_product_prefixes(products):
    """Show product prefix groupings for hierarchical filtering."""
    from collections import Counter

    prefixes: Counter = Counter()
    for product in products:
        # Extract prefix (first part before hyphen)
        if '-' in product:
            prefix = product.split('-')[0]
            prefixes[prefix] += products[product]
        else:
            prefixes[product] += products[product]

    console.print(f"\n[bold]Product Prefixes (for hierarchical filtering)[/bold]")
    console.print("[dim]Use --product <prefix> to match all products starting with that prefix[/dim]")

    table = Table(show_header=True, header_style="bold")
    table.add_column("Prefix", style="cyan")
    table.add_column("Matches", justify="right")
    table.add_column("Example Products")

    for prefix, count in sorted(prefixes.items(), key=lambda x: (-x[1], x[0]))[:15]:
        # Find example products
        examples = [p for p in products if p.startswith(prefix)][:3]
        table.add_row(prefix, str(count), ", ".join(examples))

    console.print(table)


@main.command()
@click.option(
    '--catalog',
    type=click.Path(exists=True, path_type=Path),
    required=True,
    help='Path to the catalog JSON file to upload'
)
@click.option(
    '--blob-url',
    type=str,
    envvar='CATALOG_BLOB_URL',
    default=None,
    help='Full Azure Blob SAS URL (blob-level or container-level). Env: CATALOG_BLOB_URL'
)
@click.option(
    '--connection-string',
    type=str,
    envvar='AZURE_STORAGE_CONNECTION_STRING',
    default=None,
    help='Azure Storage connection string. Env: AZURE_STORAGE_CONNECTION_STRING'
)
@click.option(
    '--account-url',
    type=str,
    envvar='AZURE_STORAGE_ACCOUNT_URL',
    default=None,
    help='Storage account URL (uses DefaultAzureCredential). Env: AZURE_STORAGE_ACCOUNT_URL'
)
@click.option(
    '--container-name',
    type=str,
    envvar='CATALOG_CONTAINER_NAME',
    default='catalogs',
    help='Blob container name (default: catalogs). Env: CATALOG_CONTAINER_NAME'
)
@click.option(
    '--blob-name',
    type=str,
    default=None,
    help='Blob name in the container (defaults to the catalog filename)'
)
@click.option(
    '--overwrite/--no-overwrite',
    default=True,
    help='Whether to overwrite an existing blob (default: overwrite)'
)
@click.option(
    '--verbose', '-v',
    is_flag=True,
    help='Show detailed output'
)
def upload(
    catalog: Path,
    blob_url: str,
    connection_string: str,
    account_url: str,
    container_name: str,
    blob_name: str,
    overwrite: bool,
    verbose: bool,
):
    """Upload a catalog JSON file to Azure Blob Storage.

    Supports three authentication methods (in priority order):

    \b
    1. SAS URL (--blob-url): Full blob or container URL with SAS token.
       Simplest option for CI/CD pipelines.
    2. Connection string (--connection-string): Standard Azure Storage
       connection string with --container-name.
    3. DefaultAzureCredential (--account-url): Uses managed identity,
       Azure CLI, or OIDC. Best for production with RBAC.

    Examples:

    \b
        # Upload with a blob-level SAS URL
        catalog-builder upload --catalog catalog.json \\
          --blob-url "https://acct.blob.core.windows.net/catalogs/catalog.json?sv=..."

    \b
        # Upload with a connection string
        catalog-builder upload --catalog catalog.json \\
          --connection-string "DefaultEndpointsProtocol=https;..."

    \b
        # Upload with DefaultAzureCredential (managed identity / az login)
        catalog-builder upload --catalog catalog.json \\
          --account-url "https://acct.blob.core.windows.net"
    """
    if not blob_url and not connection_string and not account_url:
        console.print(
            "[red]Error:[/red] Provide one of --blob-url, --connection-string, or --account-url"
        )
        sys.exit(1)

    # Determine auth method for display
    if blob_url:
        auth_method = "SAS URL"
    elif connection_string:
        auth_method = "Connection String"
    else:
        auth_method = "DefaultAzureCredential"

    console.print(f"\n[bold blue]Azure Blob Storage Upload[/bold blue]")
    console.print(f"Catalog: {catalog}")
    console.print(f"Auth: {auth_method}")
    console.print(f"Container: {container_name}")
    console.print(f"Blob name: {blob_name or catalog.name}")
    console.print(f"Overwrite: {overwrite}")
    console.print()

    try:
        result_url = upload_catalog_to_blob(
            catalog,
            blob_url=blob_url,
            connection_string=connection_string,
            account_url=account_url,
            container_name=container_name,
            blob_name=blob_name,
            overwrite=overwrite,
        )
        console.print(f"[green]✓[/green] Uploaded successfully to: {result_url}")
    except ImportError as e:
        console.print(f"\n[red]Error:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[red]Upload failed:[/red] {e}")
        if verbose:
            import traceback
            console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
