"""
Mapper: Dr. Migrate DB query results -> RawContextFile dict.

Converts DataFrames from the application_overview, server_overview_current,
key_software_overview, and app_modernization_candidates views into the
dict structure expected by architecture_scorer.schema.RawContextFile.
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _safe_str(value) -> Optional[str]:
    """Convert a value to string, returning None for NaN/None."""
    if pd.isna(value):
        return None
    return str(value).strip() if value else None


def _safe_float(value) -> Optional[float]:
    """Convert a value to float, returning None for NaN/None."""
    if pd.isna(value):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value) -> Optional[int]:
    """Convert a value to int, returning None for NaN/None."""
    if pd.isna(value):
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _split_csv_field(value) -> list[str]:
    """Split a comma-separated DB field into a cleaned list."""
    if pd.isna(value) or not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _map_business_criticality(business_critical: str, inherent_risk: str = None) -> str:
    """Map DB boolean flag + risk to RawContextFile criticality string.

    DB has business_critical as 'Yes'/'No' boolean flag.
    RawContextFile expects: 'Low', 'Medium', 'High', 'MissionCritical'.
    """
    # Check inherent_risk first for more granular mapping
    if inherent_risk and not pd.isna(inherent_risk):
        risk_lower = str(inherent_risk).strip().lower()
        if risk_lower == "extreme":
            return "MissionCritical"
        if risk_lower == "heightened":
            return "High"

    # Fall back to boolean business_critical flag
    if business_critical and not pd.isna(business_critical):
        if str(business_critical).strip().lower() in ("yes", "true", "1"):
            return "High"

    return "Medium"


def build_context_from_db(
    app_df: pd.DataFrame,
    server_df: pd.DataFrame,
    software_df: pd.DataFrame,
    mod_df: pd.DataFrame,
) -> dict:
    """Build a RawContextFile-compatible dict from DB query DataFrames.

    Args:
        app_df: Result from application_overview (expected: 1 row)
        server_df: Result from server_overview_current (0+ rows)
        software_df: Result from key_software_overview (0+ rows)
        mod_df: Result from app_modernization_candidates (0+ rows)

    Returns:
        Dict matching the RawContextFile JSON structure.
        Pass to RawContextFile.model_validate() or RawContextFile(**result).
    """
    if app_df.empty:
        raise ValueError("application_overview returned no rows")

    app_row = app_df.iloc[0]

    # --- app_overview ---
    app_overview = {
        "application": str(app_row.get("application", "Unknown")),
        "app_type": _safe_str(app_row.get("app_type")),
        "business_crtiticality": _map_business_criticality(
            app_row.get("business_critical"),
            app_row.get("inherent_risk"),
        ),
        "treatment": _safe_str(app_row.get("assigned_migration_strategy")),
        "description": _safe_str(app_row.get("app_function")),
        "owner": _safe_str(app_row.get("app_owner")),
    }

    # --- detected_technology_running ---
    technologies: set[str] = set()

    # From key_software_overview
    if not software_df.empty and "key_software" in software_df.columns:
        for val in software_df["key_software"].dropna().unique():
            technologies.add(str(val).strip())

    # From application_overview comma-separated fields
    technologies.update(_split_csv_field(app_row.get("other_tech_stack_components")))
    technologies.update(_split_csv_field(app_row.get("detected_app_components")))
    technologies.update(_split_csv_field(app_row.get("non_sql_databases")))

    # Add SQL Server if detected
    sql_count = _safe_int(app_row.get("sql_server_count"))
    if sql_count and sql_count > 0:
        technologies.add("SQL Server")

    # --- server_details ---
    # Build per-machine software lookup from key_software_overview
    machine_software: dict[str, list[str]] = {}
    if not software_df.empty:
        for _, sw_row in software_df.iterrows():
            machine = _safe_str(sw_row.get("machine"))
            software = _safe_str(sw_row.get("key_software"))
            if machine and software:
                machine_software.setdefault(machine, []).append(software)

    server_details = []
    for _, srv_row in server_df.iterrows():
        machine_name = _safe_str(srv_row.get("machine"))
        ip_addr = _safe_str(srv_row.get("IPAddress"))

        detail = {
            "machine": machine_name or "Unknown",
            "environment": _safe_str(srv_row.get("environment")),
            "OperatingSystem": _safe_str(srv_row.get("OperatingSystem")),
            "Cores": _safe_int(srv_row.get("Cores")),
            "MemoryGB": _safe_float(srv_row.get("AllocatedMemoryInGB")),
            "CPUUsage": _safe_float(srv_row.get("CPUUsageInPct")),
            "MemoryUsage": _safe_float(srv_row.get("MemoryUsageInPct")),
            "StorageGB": _safe_int(srv_row.get("StorageGB")),
            "AzureVMReadiness": _safe_str(srv_row.get("CloudVMReadiness")),
            "AzureReadinessIssues": _safe_str(srv_row.get("CloudReadinessIssues")),
            "migration_strategy": _safe_str(srv_row.get("assigned_treatment")),
            "ip_address": [ip_addr] if ip_addr else [],
            "detected_COTS": machine_software.get(machine_name, []),
            "DiskReadOpsPersec": _safe_float(srv_row.get("DiskReadOpsPersec")),
            "DiskWriteOpsPerSec": _safe_float(srv_row.get("DiskWriteOpsPerSec")),
            "NetworkInMBPS": _safe_float(srv_row.get("NetworkInMBPS")),
            "NetworkOutMBPS": _safe_float(srv_row.get("NetworkOutMBPS")),
        }
        server_details.append(detail)

    # --- app_mod_results ---
    app_mod_results = []
    mod_options = _split_csv_field(app_row.get("app_component_modernization_options"))

    if not mod_df.empty:
        for _, mod_row in mod_df.iterrows():
            tech = _safe_str(mod_row.get("app_mod_candidate_technology")) or "Unknown"
            machines_count = _safe_int(mod_row.get("number_of_machines_with_tech"))
            app_mod_results.append({
                "technology": tech,
                "summary": {
                    "services_scanned": machines_count or 0,
                },
                "findings": [],
                "compatibility": {},
                "recommended_targets": mod_options,
                "blockers": [],
            })

    # --- app_approved_azure_services ---
    # Parse modernization options as technology -> Azure service mappings
    approved_services: list[dict[str, str]] = []
    if mod_options:
        # Each option may be in "Technology -> Azure Service" or similar format
        # If not parseable, store as-is with a generic key
        service_map: dict[str, str] = {}
        for option in mod_options:
            if "->" in option:
                parts = option.split("->", 1)
                service_map[parts[0].strip()] = parts[1].strip()
            elif ":" in option:
                parts = option.split(":", 1)
                service_map[parts[0].strip()] = parts[1].strip()
            else:
                # Store the Azure service with itself as key
                service_map[option] = option
        if service_map:
            approved_services.append(service_map)

    context = {
        "app_overview": [app_overview],
        "detected_technology_running": sorted(technologies),
        "server_details": server_details,
        "App Mod results": app_mod_results,
        "app_approved_azure_services": approved_services,
    }

    logger.info(
        "Built context for '%s': %d technologies, %d servers, %d app mod results",
        app_overview["application"],
        len(technologies),
        len(server_details),
        len(app_mod_results),
    )

    return context
