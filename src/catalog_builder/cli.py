"""CLI for the Azure Architecture Catalog Builder."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .catalog import build_catalog, CatalogBuilder, CatalogValidator
from .config import load_config, save_default_config, find_config_file, reset_config, get_config
from .schema import ArchitectureCatalog, ExtractionConfidence


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
    validate_only: bool
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
    console.print()

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
            catalog, issues = build_catalog(repo_path, out, progress_callback)
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


if __name__ == '__main__':
    main()
