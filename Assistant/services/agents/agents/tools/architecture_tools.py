"""
Architecture Recommendation Tools

Provides tools for the System Architect persona to score applications
against the Azure Architecture Catalog and return ranked recommendations.

Tools:
- get_architecture_recommendation: Score an application and return recommendations
- list_scorable_applications: List applications available for scoring
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from pydantic_ai import ModelRetry, RunContext
from pydantic_ai.toolsets import FunctionToolset

from ..deps import AgentDeps
from .architecture_mapper import build_context_from_db

try:
    from architecture_scorer.engine import ScoringEngine
    from architecture_scorer.schema import RawContextFile, ScoringResult
    _SCORER_AVAILABLE = True
except ImportError:
    _SCORER_AVAILABLE = False

import logging

logger = logging.getLogger(__name__)

# --- Lazy singleton for the scoring engine ---
_engine: Optional["ScoringEngine"] = None


def _download_catalog(url: str) -> Path:
    """Download catalog from Azure Blob Storage using the agent's ConfigLoader.

    Uses the same identity-based authentication as the rest of the agent
    infrastructure (Managed Identity in prod, az login in dev).

    Args:
        url: Azure Blob Storage HTTPS URL to the catalog JSON.

    Returns:
        Path to the locally cached catalog file.

    Raises:
        FileNotFoundError: If download or validation fails.
    """
    from ..config import agents as agents_config
    from ..config.llm_router.core.loader import ConfigLoader, LoaderError

    environment = "local" if agents_config.MODE == "dev" else "azure_vm"
    loader = ConfigLoader(environment=environment)

    try:
        logger.info("Downloading architecture catalog from %s (env=%s)...", url, environment)
        data = loader.load(url)
    except LoaderError as e:
        raise FileNotFoundError(f"Failed to download catalog: {e}")

    # Persist to local cache so ScoringEngine.load_catalog() can read it
    cache_dir = Path(__file__).resolve().parents[2] / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "architecture-catalog.json"
    cache_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    logger.info("Catalog downloaded and cached at: %s", cache_file)
    return cache_file


def _get_engine() -> "ScoringEngine":
    """Get or create the cached ScoringEngine with catalog loaded.

    Catalog resolution order:
    1. ARCHITECTURE_CATALOG_PATH env var (local file path)
    2. CATALOG_URL from config.toml (standard production config)
    3. CATALOG_URL env var (override)
    4. Local file search (project root, cwd)

    Remote URLs are fetched via ConfigLoader using the agent's identity-based
    authentication (Managed Identity in prod, az login in dev).
    """
    global _engine
    if _engine is not None:
        return _engine

    if not _SCORER_AVAILABLE:
        raise RuntimeError(
            "architecture_scorer package is not installed. "
            "Add azure-architecture-catalog-builder to dependencies."
        )

    catalog_path: Optional[str] = None

    # 1. Check for a local file path override
    local_path = os.environ.get("ARCHITECTURE_CATALOG_PATH")
    if local_path and Path(local_path).exists():
        catalog_path = local_path

    # 2. Check for a remote URL (config.toml first, env var as override)
    if not catalog_path:
        catalog_url: Optional[str] = None
        try:
            from ..config import agents as agents_config
            catalog_url = agents_config.CATALOG_URL
        except Exception:
            pass
        # Env var overrides config.toml
        catalog_url = os.environ.get("CATALOG_URL", catalog_url)
        if catalog_url:
            cached = _download_catalog(catalog_url)
            catalog_path = str(cached)

    # 3. Fall back to local file search (development)
    if not catalog_path:
        candidates = [
            Path(__file__).resolve().parents[4] / "architecture-catalog.json",
            Path.cwd() / "architecture-catalog.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                catalog_path = str(candidate)
                break

    if not catalog_path:
        raise FileNotFoundError(
            "Architecture catalog not found. Set CATALOG_URL in config.toml, "
            "or use ARCHITECTURE_CATALOG_PATH env var (local file path)."
        )

    engine = ScoringEngine()
    engine.load_catalog(catalog_path)
    _engine = engine
    logger.info("Architecture scoring engine initialized with catalog: %s", catalog_path)
    return _engine


def _signal_value(signal) -> str:
    """Extract the display string from a DerivedSignal's value (which may be an enum)."""
    val = signal.value
    # If it's an enum, get its .value string; otherwise str()
    return val.value if hasattr(val, "value") else str(val)


def _format_result(result: ScoringResult, ref: str) -> str:
    """Format a ScoringResult into a structured text summary for the agent."""
    lines = []

    # Header
    lines.append(f"## Architecture Recommendation: {result.application_name}")
    lines.append("")

    # Derived intent summary
    intent = result.derived_intent
    lines.append("### Derived Intent")
    lines.append(f"- **Treatment**: {_signal_value(intent.treatment)} (confidence: {intent.treatment.confidence.value})")
    lines.append(f"- **Runtime Model**: {_signal_value(intent.likely_runtime_model)} ({intent.likely_runtime_model.confidence.value})")
    lines.append(f"- **Modernization Depth**: {_signal_value(intent.modernization_depth_feasible)} ({intent.modernization_depth_feasible.confidence.value})")
    lines.append(f"- **Cloud Native Feasibility**: {_signal_value(intent.cloud_native_feasibility)}")
    lines.append(f"- **Cost Posture**: {_signal_value(intent.cost_posture)}")
    lines.append("")

    # Top recommendation
    if result.recommendations:
        top = result.recommendations[0]
        lines.append(f"### Top Recommendation: {top.name} ({top.likelihood_score:.0f}%)")
        lines.append(f"{top.description}")
        lines.append("")

        if top.fit_summary:
            lines.append("**Strengths:**")
            for item in top.fit_summary:
                lines.append(f"- {item}")
            lines.append("")

        if top.struggle_summary:
            lines.append("**Considerations:**")
            for item in top.struggle_summary:
                lines.append(f"- {item}")
            lines.append("")

        services = ", ".join(top.core_services[:6])
        lines.append(f"**Core Azure Services:** {services}")

        if top.learn_url:
            lines.append(f"**Learn more:** [{top.name}]({top.learn_url})")
        lines.append("")

    # All recommendations summary
    if len(result.recommendations) > 1:
        lines.append(f"### All Recommendations (stored as `{ref}`)")
        lines.append("")
        for i, rec in enumerate(result.recommendations, 1):
            services_short = ", ".join(rec.core_services[:3])
            url_part = f" | [Docs]({rec.learn_url})" if rec.learn_url else ""
            lines.append(f"{i}. **{rec.name}** — {rec.likelihood_score:.0f}% | {services_short}{url_part}")
        lines.append("")

    # Stats
    lines.append(f"*{result.eligible_count} architectures evaluated, {result.excluded_count} excluded.*")

    return "\n".join(lines)


# --- Toolset ---
architecture_toolset = FunctionToolset[AgentDeps](sequential=False)


@architecture_toolset.tool(retries=3)
async def get_architecture_recommendation(
    ctx: RunContext[AgentDeps],
    application_name: str,
    max_recommendations: int = 5,
) -> str:
    """
    Score an application against the Azure Architecture Catalog and return
    ranked architecture recommendations with explanations.

    Queries the database for the application's tech stack, servers, and
    modernization data, then runs the scoring engine to find the best-fit
    Azure architectures.

    After calling this tool, use the returned data reference with
    generate_chart (bar chart of scores) and display_kpi_tiles to present
    the results visually.

    Args:
        application_name: The name of the application to score (must match an application in the database)
        max_recommendations: Maximum number of recommendations to return (default: 5)

    Returns:
        Structured text with recommendations and a DuckDB reference for charting
    """
    thread_id = ctx.deps.thread_id
    db = ctx.deps.database

    # Step 1: Query application_overview
    try:
        app_sql = f"SELECT * FROM application_overview WHERE application = '{application_name}'"
        app_df = db.execute_view_query("application_overview", app_sql)
    except Exception as e:
        logger.error("Failed to query application_overview: %s", e)
        raise ModelRetry(
            f"Error querying application data: {e}. "
            "Please verify the application name is correct."
        )

    if app_df.empty:
        raise ModelRetry(
            f"No application found with name '{application_name}'. "
            "Use list_scorable_applications to see available applications."
        )

    # Step 2: Query server_overview_current
    try:
        server_sql = f"SELECT * FROM server_overview_current WHERE application = '{application_name}'"
        server_df = db.execute_view_query("server_overview_current", server_sql)
    except Exception as e:
        logger.warning("Failed to query server data: %s", e)
        server_df = pd.DataFrame()

    # Step 3: Query key_software_overview for machines belonging to this app
    software_df = pd.DataFrame()
    if not server_df.empty and "machine" in server_df.columns:
        machines = server_df["machine"].dropna().unique().tolist()
        if machines:
            machine_list = ", ".join(f"'{m}'" for m in machines)
            try:
                sw_sql = f"SELECT * FROM key_software_overview WHERE machine IN ({machine_list})"
                software_df = db.execute_view_query("key_software_overview", sw_sql)
            except Exception as e:
                logger.warning("Failed to query software data: %s", e)

    # Step 4: Query app_modernization_candidates
    try:
        mod_sql = f"SELECT * FROM app_modernization_candidates WHERE application = '{application_name}'"
        mod_df = db.execute_view_query("app_modernization_candidates", mod_sql)
    except Exception as e:
        logger.warning("Failed to query modernization data: %s", e)
        mod_df = pd.DataFrame()

    # Step 5: Build context from DB results
    try:
        context_dict = build_context_from_db(app_df, server_df, software_df, mod_df)
    except ValueError as e:
        raise ModelRetry(f"Error building context: {e}")

    # Step 6: Run scoring engine
    try:
        engine = _get_engine()
        raw_context = RawContextFile.model_validate(context_dict)
        from architecture_scorer.normalizer import ContextNormalizer
        normalizer = ContextNormalizer()
        app_context = normalizer.normalize(raw_context)
        result = engine.score_context(app_context, max_recommendations=max_recommendations)
    except FileNotFoundError as e:
        return f"Error: Architecture catalog not found. {e}"
    except Exception as e:
        logger.error("Scoring engine error: %s", e)
        raise ModelRetry(f"Error running scoring engine: {e}")

    # Step 7: Store recommendations as DataFrame for charting
    if result.recommendations:
        rec_data = []
        for i, rec in enumerate(result.recommendations, 1):
            rec_data.append({
                "rank": i,
                "name": rec.name,
                "score": round(rec.likelihood_score, 1),
                "description": rec.description[:100] if rec.description else "",
                "core_services": ", ".join(rec.core_services[:4]),
            })
        rec_df = pd.DataFrame(rec_data)
        ref = db.store(rec_df, thread_id=thread_id)
    else:
        ref = "no_results"

    # Step 8: Format and return
    return _format_result(result, ref)


@architecture_toolset.tool
async def list_scorable_applications(ctx: RunContext[AgentDeps]) -> str:
    """
    List all applications available for architecture scoring.

    Returns the distinct application names from the database that can be
    passed to get_architecture_recommendation.

    Returns:
        Formatted list of application names
    """
    db = ctx.deps.database

    try:
        sql = "SELECT DISTINCT application FROM application_overview ORDER BY application"
        df = db.execute_view_query("application_overview", sql)
    except Exception as e:
        logger.error("Failed to list applications: %s", e)
        raise ModelRetry(f"Error querying applications: {e}")

    if df.empty:
        return "No applications found in the database."

    app_names = df["application"].dropna().tolist()
    result_lines = [f"**{len(app_names)} applications available for architecture scoring:**"]
    for name in app_names:
        result_lines.append(f"- {name}")

    return "\n".join(result_lines)
