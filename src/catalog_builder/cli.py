"""CLI for the Azure Architecture Catalog Builder."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from .catalog import build_catalog, CatalogBuilder, CatalogValidator
from .config import load_config, save_default_config, find_config_file, reset_config
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
    '--verbose', '-v',
    is_flag=True,
    help='Show detailed progress information'
)
@click.option(
    '--validate-only',
    is_flag=True,
    help='Only validate an existing catalog, do not build'
)
def build_catalog_cmd(repo_path: Path, out: Path, config: Path, verbose: bool, validate_only: bool):
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

    console.print(f"\n[bold blue]Azure Architecture Catalog Builder[/bold blue]")
    console.print(f"Repository: {repo_path}")
    console.print(f"Output: {out}")
    if config_path:
        console.print(f"Config: {config_path}")
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


if __name__ == '__main__':
    main()
