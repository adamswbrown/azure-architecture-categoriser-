"""CLI for the Architecture Scoring Engine.

Provides command-line interface for scoring applications against
the architecture catalog.
"""

import json
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from .engine import ScoringEngine, validate_catalog, validate_context
from .schema import ScoringResult
from .drmigrate_generator import DrMigrateContextGenerator
from .drmigrate_schema import (
    DrMigrateApplicationData,
    DrMigrateApplicationOverview,
    DrMigrateServerOverview,
    DrMigrateInstalledApplication,
    DrMigrateKeySoftware,
    DrMigrateCloudServerCost,
    DrMigrateAppModCandidate,
    DrMigrateApplicationCostComparison,
)

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="architecture-scorer")
def main():
    """Architecture Scoring and Recommendation Engine.

    Evaluates application contexts against the Azure Architecture Catalog
    and returns ranked recommendations with clear reasoning.
    """
    pass


@main.command("score")
@click.option(
    "--catalog", "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to architecture-catalog.json"
)
@click.option(
    "--context", "-x",
    required=True,
    type=click.Path(exists=True),
    help="Path to application context JSON file"
)
@click.option(
    "--out", "-o",
    type=click.Path(),
    help="Output file for JSON results (default: stdout)"
)
@click.option(
    "--max-recommendations", "-n",
    default=5,
    type=int,
    help="Maximum number of recommendations to return"
)
@click.option(
    "--answer", "-a",
    multiple=True,
    help="Answer to clarification question (format: question_id=value)"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Show detailed output"
)
@click.option(
    "--json-output", "-j",
    is_flag=True,
    help="Output raw JSON instead of formatted text"
)
@click.option(
    "--interactive/--no-interactive", "-i/-I",
    default=True,
    help="Prompt for answers to clarification questions (default: interactive)"
)
def score_cmd(
    catalog: str,
    context: str,
    out: Optional[str],
    max_recommendations: int,
    answer: tuple,
    verbose: bool,
    json_output: bool,
    interactive: bool,
):
    """Score an application against the architecture catalog.

    Examples:
        architecture-scorer score -c catalog.json -x context.json
        architecture-scorer score -c catalog.json -x context.json -n 3 -v
        architecture-scorer score -c catalog.json -x context.json -a treatment=replatform
    """
    # Parse user answers
    user_answers = {}
    for ans in answer:
        if "=" in ans:
            key, value = ans.split("=", 1)
            user_answers[key.strip()] = value.strip()

    try:
        engine = ScoringEngine()
        engine.load_catalog(catalog)

        console.print(f"\n[bold blue]Architecture Scoring Engine[/bold blue]")
        console.print(f"Catalog: {catalog} ({engine.catalog.total_architectures} architectures)")
        console.print(f"Context: {context}")
        if user_answers:
            console.print(f"Answers provided: {len(user_answers)}")
        console.print()

        with console.status("Scoring application..."):
            result = engine.score(
                context,
                user_answers=user_answers if user_answers else None,
                max_recommendations=max_recommendations,
            )

        # Interactive mode: prompt for answers if questions pending
        if interactive and result.clarification_questions and not json_output:
            user_answers = prompt_for_answers(result.clarification_questions, user_answers)

            # Re-score with the new answers
            with console.status("Re-scoring with your answers..."):
                result = engine.score(
                    context,
                    user_answers=user_answers,
                    max_recommendations=max_recommendations,
                )

        if json_output:
            output_json(result, out)
        else:
            display_result(result, verbose, user_answers)
            if out:
                output_json(result, out)
                console.print(f"\n[green]Results saved to {out}[/green]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@main.command("questions")
@click.option(
    "--catalog", "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to architecture-catalog.json"
)
@click.option(
    "--context", "-x",
    required=True,
    type=click.Path(exists=True),
    help="Path to application context JSON file"
)
def questions_cmd(catalog: str, context: str):
    """Show clarification questions for an application context.

    Use this to see what questions the engine would ask before scoring.
    """
    try:
        engine = ScoringEngine()
        engine.load_catalog(catalog)
        questions = engine.get_questions(context)

        if not questions:
            console.print("[green]No clarification questions needed.[/green]")
            return

        console.print(f"\n[bold]Clarification Questions ({len(questions)}):[/bold]\n")

        for i, q in enumerate(questions, 1):
            console.print(f"[bold cyan]{i}. {q.question_text}[/bold cyan]")
            console.print(f"   ID: {q.question_id}")
            if q.current_inference:
                console.print(f"   Current inference: {q.current_inference} ({q.inference_confidence.value})")
            console.print(f"   Options:")
            for opt in q.options:
                console.print(f"     - {opt.value}: {opt.label}")
                if opt.description:
                    console.print(f"       {opt.description}")
            console.print()

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@main.command("validate")
@click.option(
    "--catalog", "-c",
    type=click.Path(),
    help="Path to architecture-catalog.json"
)
@click.option(
    "--context", "-x",
    type=click.Path(),
    help="Path to application context JSON file"
)
def validate_cmd(catalog: Optional[str], context: Optional[str]):
    """Validate catalog and/or context files.

    Examples:
        architecture-scorer validate -c catalog.json
        architecture-scorer validate -x context.json
        architecture-scorer validate -c catalog.json -x context.json
    """
    if not catalog and not context:
        console.print("[yellow]Please specify --catalog and/or --context to validate[/yellow]")
        return

    all_valid = True

    if catalog:
        is_valid, issues = validate_catalog(catalog)
        if is_valid:
            console.print(f"[green]✓ Catalog valid: {catalog}[/green]")
        else:
            console.print(f"[red]✗ Catalog invalid: {catalog}[/red]")
            for issue in issues:
                console.print(f"  - {issue}")
            all_valid = False

    if context:
        is_valid, issues = validate_context(context)
        if is_valid:
            console.print(f"[green]✓ Context valid: {context}[/green]")
        else:
            console.print(f"[red]✗ Context invalid: {context}[/red]")
            for issue in issues:
                console.print(f"  - {issue}")
            all_valid = False

    sys.exit(0 if all_valid else 1)


@main.command("inspect")
@click.option(
    "--catalog", "-c",
    required=True,
    type=click.Path(exists=True),
    help="Path to architecture-catalog.json"
)
@click.option(
    "--id", "arch_id",
    help="Show details for specific architecture ID"
)
@click.option(
    "--treatment", "-t",
    help="Filter by supported treatment"
)
@click.option(
    "--family", "-f",
    help="Filter by architecture family"
)
def inspect_cmd(catalog: str, arch_id: Optional[str], treatment: Optional[str], family: Optional[str]):
    """Inspect the architecture catalog.

    View catalog contents and filter by various criteria.
    """
    try:
        engine = ScoringEngine()
        engine.load_catalog(catalog)
        cat = engine.catalog

        console.print(f"\n[bold blue]Architecture Catalog[/bold blue]")
        console.print(f"Version: {cat.version}")
        console.print(f"Total Architectures: {cat.total_architectures}")
        console.print()

        if arch_id:
            # Show specific architecture
            arch = next((a for a in cat.architectures if a.architecture_id == arch_id), None)
            if not arch:
                console.print(f"[red]Architecture not found: {arch_id}[/red]")
                return
            display_architecture_detail(arch)
        else:
            # List architectures with filters
            filtered = cat.architectures

            if treatment:
                treatment_lower = treatment.lower()
                filtered = [a for a in filtered if any(
                    t.value.lower() == treatment_lower for t in a.supported_treatments
                )]

            if family:
                family_lower = family.lower()
                filtered = [a for a in filtered if a.family.value.lower() == family_lower]

            console.print(f"Showing {len(filtered)} architectures:\n")

            table = Table(show_header=True, header_style="bold")
            table.add_column("ID", style="cyan", no_wrap=True)
            table.add_column("Name")
            table.add_column("Family")
            table.add_column("Quality")
            table.add_column("Treatments")

            for arch in filtered[:20]:  # Limit display
                treatments = ", ".join(t.value for t in arch.supported_treatments[:3])
                if len(arch.supported_treatments) > 3:
                    treatments += "..."
                table.add_row(
                    arch.architecture_id[:30],
                    arch.name[:40],
                    arch.family.value,
                    arch.catalog_quality.value,
                    treatments,
                )

            console.print(table)

            if len(filtered) > 20:
                console.print(f"\n[dim]... and {len(filtered) - 20} more[/dim]")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def prompt_for_answers(
    questions: list,
    existing_answers: dict[str, str]
) -> dict[str, str]:
    """Interactively prompt user for answers to clarification questions."""
    answers = existing_answers.copy() if existing_answers else {}

    console.print("\n[bold yellow]━━━ Clarification Questions ━━━[/bold yellow]")
    console.print("[dim]Your answers will improve recommendation accuracy.[/dim]\n")

    for i, q in enumerate(questions, 1):
        # Build choices list with numbers
        choices = [opt.value for opt in q.options]
        choice_map = {str(idx): opt.value for idx, opt in enumerate(q.options, 1)}

        # Show question with current inference
        console.print(f"[bold cyan]{i}. {q.question_text}[/bold cyan]")
        if q.current_inference:
            console.print(f"   [dim]Current inference: {q.current_inference} (confidence: {q.inference_confidence.value})[/dim]")

        # Show numbered options
        console.print()
        for idx, opt in enumerate(q.options, 1):
            desc = f" - {opt.description}" if opt.description else ""
            marker = "→" if opt.value == q.current_inference else " "
            console.print(f"   {marker} [bold]{idx}[/bold]. {opt.label}{desc}")
        console.print()

        # Prompt for answer - accept number or value
        default = q.current_inference if q.current_inference in choices else choices[0]
        default_num = next((k for k, v in choice_map.items() if v == default), "1")

        try:
            raw_answer = click.prompt(
                f"   Select [1-{len(choices)}]",
                default=default_num,
            )
            # Accept either number or value
            if raw_answer in choice_map:
                answer = choice_map[raw_answer]
            elif raw_answer.lower() in [c.lower() for c in choices]:
                answer = next(c for c in choices if c.lower() == raw_answer.lower())
            else:
                console.print(f"   [yellow]Invalid choice, using default: {default}[/yellow]")
                answer = default

            answers[q.question_id] = answer
            console.print(f"   [green]✓ Selected: {answer}[/green]\n")
        except click.Abort:
            console.print("\n[yellow]Skipping remaining questions...[/yellow]")
            break

    console.print("[bold yellow]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold yellow]\n")
    return answers


def display_result(result: ScoringResult, verbose: bool, user_answers: Optional[dict[str, str]] = None):
    """Display scoring result in formatted text."""
    # Show user answers if provided
    if user_answers:
        console.print("[bold]Your Answers Applied:[/bold]")
        for qid, answer in user_answers.items():
            console.print(f"  • {qid}: [cyan]{answer}[/cyan]")
        console.print()

    # Summary
    summary = result.summary
    confidence_color = {
        "High": "green",
        "Medium": "yellow",
        "Low": "red",
    }.get(summary.confidence_level, "white")

    console.print(Panel(
        f"[bold]{result.application_name}[/bold]\n\n"
        f"Primary Recommendation: [bold cyan]{summary.primary_recommendation or 'None'}[/bold cyan]\n"
        f"Confidence: [{confidence_color}]{summary.confidence_level}[/{confidence_color}]\n"
        f"Eligible: {result.eligible_count} | Excluded: {result.excluded_count}",
        title="Scoring Summary",
    ))

    # Key drivers
    if summary.key_drivers:
        console.print("\n[bold]Key Drivers:[/bold]")
        for driver in summary.key_drivers:
            console.print(f"  [green]•[/green] {driver}")

    # Key risks
    if summary.key_risks:
        console.print("\n[bold]Key Risks:[/bold]")
        for risk in summary.key_risks:
            console.print(f"  [yellow]•[/yellow] {risk}")

    # Recommendations
    if result.recommendations:
        console.print("\n[bold]Top Recommendations:[/bold]\n")

        for i, rec in enumerate(result.recommendations[:5], 1):
            quality_badge = {
                "curated": "[green]curated[/green]",
                "ai_enriched": "[cyan]ai_enriched[/cyan]",
                "ai_suggested": "[yellow]ai_suggested[/yellow]",
                "example_only": "[dim]example_only[/dim]",
            }.get(rec.catalog_quality.value, rec.catalog_quality.value)

            console.print(
                f"  [bold cyan]{i}. {rec.name}[/bold cyan] "
                f"[bold]{rec.likelihood_score:.0f}%[/bold] {quality_badge}"
            )
            # Always show URL if available
            if rec.learn_url:
                console.print(f"     [blue]URL:[/blue] {rec.learn_url}")

            if verbose:
                console.print(f"     ID: {rec.architecture_id}")
                console.print(f"     Pattern: {rec.pattern_name}")

                if rec.fit_summary:
                    console.print(f"     [green]Fits:[/green] {'; '.join(rec.fit_summary[:2])}")
                if rec.struggle_summary:
                    console.print(f"     [yellow]Struggles:[/yellow] {'; '.join(rec.struggle_summary[:2])}")
                if rec.assumptions:
                    console.print(f"     [dim]Assumptions: {len(rec.assumptions)}[/dim]")

            console.print()

    # Clarification questions (only shown in non-interactive mode or if questions remain)
    if result.clarification_questions:
        console.print(f"\n[yellow]⚠ {len(result.clarification_questions)} clarification questions pending[/yellow]")
        console.print("[dim]Run interactively (default) to answer, or use -a question_id=value[/dim]")

    # Warnings
    if result.processing_warnings:
        console.print("\n[dim]Warnings:[/dim]")
        for warning in result.processing_warnings:
            console.print(f"  [dim]• {warning}[/dim]")


def display_architecture_detail(arch):
    """Display detailed architecture information."""
    tree = Tree(f"[bold cyan]{arch.name}[/bold cyan]")

    # Identity
    identity = tree.add("[bold]Identity[/bold]")
    identity.add(f"ID: {arch.architecture_id}")
    identity.add(f"Pattern: {arch.pattern_name}")
    identity.add(f"Quality: {arch.catalog_quality.value}")
    if arch.learn_url:
        identity.add(f"URL: {arch.learn_url}")

    # Classification
    classification = tree.add("[bold]Classification[/bold]")
    classification.add(f"Family: {arch.family.value}")
    classification.add(f"Domain: {arch.workload_domain.value}")
    classification.add(f"Runtime Models: {', '.join(r.value for r in arch.expected_runtime_models)}")

    # Treatments
    if arch.supported_treatments:
        treatments = tree.add("[bold]Supported Treatments[/bold]")
        for t in arch.supported_treatments:
            treatments.add(t.value)

    # Services
    if arch.core_services or arch.supporting_services:
        services = tree.add("[bold]Azure Services[/bold]")
        if arch.core_services:
            core = services.add("Core")
            for s in arch.core_services:
                core.add(s)
        if arch.supporting_services:
            supporting = services.add("Supporting")
            for s in arch.supporting_services:
                supporting.add(s)

    # Operational
    operational = tree.add("[bold]Operational[/bold]")
    operational.add(f"Operating Model: {arch.operating_model_required.value}")
    operational.add(f"Security Level: {arch.security_level.value}")
    operational.add(f"Cost Profile: {arch.cost_profile.value}")
    operational.add(f"Availability: {', '.join(a.value for a in arch.availability_models)}")

    # Complexity
    complexity = tree.add("[bold]Complexity[/bold]")
    complexity.add(f"Implementation: {arch.complexity.implementation.value}")
    complexity.add(f"Operations: {arch.complexity.operations.value}")

    # Exclusions
    if arch.not_suitable_for:
        exclusions = tree.add("[bold]Not Suitable For[/bold]")
        for ex in arch.not_suitable_for:
            exclusions.add(ex.value)

    console.print(tree)


def output_json(result: ScoringResult, out_path: Optional[str]):
    """Output result as JSON."""
    json_str = result.model_dump_json(indent=2)

    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(json_str)
    else:
        print(json_str)


@main.command("init-config")
@click.option(
    "--out", "-o",
    type=click.Path(),
    default="scorer-config.yaml",
    help="Output path for the configuration file"
)
@click.option(
    "--force", "-f",
    is_flag=True,
    help="Overwrite existing config file"
)
def init_config_cmd(out: str, force: bool):
    """Generate a default scorer configuration file.

    Creates a YAML configuration file with all available settings
    for customizing the scoring algorithm.

    Example:
        architecture-scorer init-config --out my-config.yaml
    """
    from .config import save_default_config

    out_path = Path(out)
    if out_path.exists() and not force:
        console.print(f"[red]Error:[/red] Config file already exists: {out}")
        console.print("Use --force to overwrite")
        sys.exit(1)

    try:
        save_default_config(out_path)
        console.print(f"[green]✓[/green] Config file created: {out}")
        console.print("\nThis file configures:")
        console.print("  • scoring_weights - How much each factor contributes to the match score")
        console.print("  • quality_weights - How catalog quality affects scores")
        console.print("  • confidence_thresholds - When to classify as High/Medium/Low confidence")
        console.print("  • question_generation - Which clarification questions to ask")
        console.print("\nThe scorer will look for config in this order:")
        console.print("  1. ARCHITECTURE_SCORER_CONFIG environment variable")
        console.print("  2. ./scorer-config.yaml (current directory)")
        console.print("  3. ~/.config/architecture-scorer/config.yaml")
    except Exception as e:
        console.print(f"[red]Error creating config:[/red] {e}")
        sys.exit(1)


@main.command("generate-context")
@click.option(
    "--input", "-i",
    "input_file",
    required=True,
    type=click.Path(exists=True),
    help="Path to Dr. Migrate data JSON file"
)
@click.option(
    "--out", "-o",
    type=click.Path(),
    help="Output file for generated context JSON (default: stdout)"
)
@click.option(
    "--include-costs/--no-include-costs",
    default=False,
    help="Include cost comparison data in output"
)
@click.option(
    "--include-network/--no-include-network",
    default=False,
    help="Include network dependency data in output"
)
@click.option(
    "--pretty/--compact",
    default=True,
    help="Pretty-print the JSON output"
)
def generate_context_cmd(
    input_file: str,
    out: Optional[str],
    include_costs: bool,
    include_network: bool,
    pretty: bool,
):
    """Generate context files from Dr. Migrate data.

    This command converts Dr. Migrate LLM-exposed data into the context file
    format expected by the Architecture Scoring Engine. This enables architecture
    recommendations for ALL applications, not just those with Java/.NET App Cat scans.

    The input JSON file should contain Dr. Migrate data in one of these formats:

    1. Single application (DrMigrateApplicationData):
       {
         "application_overview": {...},
         "server_overviews": [...],
         "installed_applications": [...],
         ...
       }

    2. Multiple applications (list of DrMigrateApplicationData):
       [
         {"application_overview": {...}, ...},
         {"application_overview": {...}, ...}
       ]

    Examples:
        architecture-scorer generate-context -i drmigrate.json -o context.json
        architecture-scorer generate-context -i drmigrate.json --include-costs
    """
    try:
        # Load input data
        with open(input_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)

        # Initialize generator
        generator = DrMigrateContextGenerator(
            include_cost_data=include_costs,
            include_network_data=include_network,
        )

        # Determine if single app or multiple apps
        if isinstance(raw_data, list):
            # Multiple applications
            results = {}
            for item in raw_data:
                app_data = DrMigrateApplicationData.model_validate(item)
                app_name = app_data.application_overview.application
                context = generator.generate_context(app_data)
                results[app_name] = context

            console.print(f"[green]Generated context files for {len(results)} applications[/green]")

            # Output
            output_data = results
        else:
            # Single application
            app_data = DrMigrateApplicationData.model_validate(raw_data)
            context = generator.generate_context(app_data)
            app_name = app_data.application_overview.application

            console.print(f"[green]Generated context file for: {app_name}[/green]")

            output_data = context

        # Write output
        indent = 2 if pretty else None
        json_output = json.dumps(output_data, indent=indent, default=str)

        if out:
            with open(out, "w", encoding="utf-8") as f:
                f.write(json_output)
            console.print(f"[green]✓[/green] Context file saved to: {out}")
        else:
            print(json_output)

    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing input JSON:[/red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


@main.command("generate-sample-drmigrate")
@click.option(
    "--out", "-o",
    type=click.Path(),
    default="sample-drmigrate-input.json",
    help="Output file for sample Dr. Migrate data"
)
@click.option(
    "--app-name", "-n",
    default="SampleApplication",
    help="Application name for the sample"
)
def generate_sample_drmigrate_cmd(out: str, app_name: str):
    """Generate a sample Dr. Migrate input file.

    Creates a sample JSON file showing the expected format for Dr. Migrate data
    that can be used with the generate-context command.

    Example:
        architecture-scorer generate-sample-drmigrate -o my-app.json -n MyApp
    """
    sample_data = {
        "application_overview": {
            "application": app_name,
            "number_of_machines": 3,
            "number_of_environments": 2,
            "environment_names": "Production, Development",
            "complexity_rating": "Medium",
            "migration_scope": "Yes",
            "app_function": "Business Application",
            "app_type": "In-house",
            "app_owner": "IT Department",
            "business_critical": "Yes",
            "inherent_risk": "Medium",
            "high_availability": "Yes",
            "disaster_recovery": "No",
            "pii_data": "No",
            "unique_operating_systems": "Windows Server 2019, Ubuntu 20.04",
            "sql_server_count": "1",
            "other_tech_stack_components": "Java 11, Spring Boot, PostgreSQL",
            "assigned_migration_strategy": "Replatform",
            "suitable_migration_strategy_options": "Replatform, Refactor, Rehost",
            "detected_app_components": "Web Application, API, Database",
            "app_component_modernization_options": "Containerize, Migrate to PaaS",
        },
        "server_overviews": [
            {
                "machine": "APP-WEB-01",
                "application": app_name,
                "environment": "Production",
                "OperatingSystem": "Ubuntu 20.04",
                "os_support_status": "Supported",
                "PowerStatus": "On",
                "CloudVMReadiness": "Ready",
                "AllocatedMemoryInGB": 8.0,
                "Cores": 4,
                "CPUUsageInPct": 45.5,
                "MemoryUsageInPct": 62.0,
                "StorageGB": 100.0,
                "DiskReadOpsPerSec": 150.0,
                "DiskWriteOpsPerSec": 75.0,
                "NetworkInMBPS": "50",
                "NetworkOutMBPS": "30",
            },
            {
                "machine": "APP-DB-01",
                "application": app_name,
                "environment": "Production",
                "OperatingSystem": "Windows Server 2019",
                "os_support_status": "Supported",
                "PowerStatus": "On",
                "CloudVMReadiness": "Ready",
                "AllocatedMemoryInGB": 16.0,
                "Cores": 8,
                "CPUUsageInPct": 30.0,
                "MemoryUsageInPct": 55.0,
                "StorageGB": 500.0,
                "DiskReadOpsPerSec": 500.0,
                "DiskWriteOpsPerSec": 200.0,
                "NetworkInMBPS": "100",
                "NetworkOutMBPS": "80",
            },
        ],
        "installed_applications": [
            {
                "machine": "APP-WEB-01",
                "key_software": "Java 11",
                "key_software_category": "Runtime",
                "key_software_type": "Server",
            },
            {
                "machine": "APP-WEB-01",
                "key_software": "Apache Tomcat",
                "key_software_category": "Web Server",
                "key_software_type": "Server",
            },
            {
                "machine": "APP-DB-01",
                "key_software": "PostgreSQL",
                "key_software_category": "Database",
                "key_software_type": "Server",
            },
        ],
        "key_software": [
            {
                "application": app_name,
                "key_software": "Spring Boot",
                "key_software_category": "Framework",
            },
        ],
        "cloud_server_costs": [
            {
                "machine": "APP-WEB-01",
                "application": app_name,
                "assigned_treatment": "Replatform",
                "assigned_target": "Azure App Service",
                "cloud_compute_cost_annual": 2400.0,
                "cloud_storage_cost_annual": 120.0,
                "cloud_total_cost_annual": 2520.0,
            },
            {
                "machine": "APP-DB-01",
                "application": app_name,
                "assigned_treatment": "Replatform",
                "assigned_target": "Azure Database for PostgreSQL",
                "cloud_compute_cost_annual": 3600.0,
                "cloud_storage_cost_annual": 600.0,
                "cloud_total_cost_annual": 4200.0,
            },
        ],
        "app_mod_candidates": [
            {
                "application": app_name,
                "app_mod_candidate_technology": "Java",
                "number_of_machines_with_tech": 1,
            },
        ],
        "cost_comparison": {
            "application": app_name,
            "current_total_cost_annual": 12000.0,
            "cloud_compute_cost_annual": 6000.0,
            "cloud_storage_cost_annual": 720.0,
            "cloud_total_cost_annual": 6720.0,
            "Currency": "USD",
            "Symbol": "$",
        },
    }

    try:
        with open(out, "w", encoding="utf-8") as f:
            json.dump(sample_data, f, indent=2)

        console.print(f"[green]✓[/green] Sample Dr. Migrate data saved to: {out}")
        console.print("\nThis file demonstrates the expected input format for the generate-context command.")
        console.print("\nTo generate a context file from this sample:")
        console.print(f"  [cyan]architecture-scorer generate-context -i {out} -o context.json[/cyan]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
