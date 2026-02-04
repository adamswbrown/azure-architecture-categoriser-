"""Pydantic models for Dr. Migrate LLM-exposed data sources.

These models define the input format from Dr. Migrate's SQL/PostgreSQL views
that can be used to generate context files for the Architecture Scoring Engine.
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# =============================================================================
# Enums for Dr. Migrate data
# =============================================================================


class ComplexityRating(str, Enum):
    """Complexity rating from Dr. Migrate."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    EXTRA_HIGH = "Extra High"


class MigrationStrategy(str, Enum):
    """Migration strategy options."""
    REHOST = "Rehost"
    REPLATFORM = "Replatform"
    REFACTOR = "Refactor"
    REBUILD = "Rebuild"
    REPLACE = "Replace"
    RETIRE = "Retire"
    RETAIN = "Retain"
    TOLERATE = "Tolerate"


# =============================================================================
# Application Overview (from Application_Overview.sql)
# =============================================================================


class DrMigrateApplicationOverview(BaseModel):
    """Application overview from Dr. Migrate Application_Overview view.

    Provides overview information for each application, including:
    - Machine counts
    - Environments
    - Migration planning
    - Risk, materiality, and compliance indicators
    - Technology stack and modernization options
    """
    application: str = Field(..., description="Application name")
    number_of_machines: Optional[int] = Field(None, description="Number of machines")
    number_of_environments: Optional[int] = Field(None, description="Number of environments")
    environment_names: Optional[str] = Field(None, description="List of environments")
    planned_migration_wave: Optional[str] = Field(None, description="Migration wave")
    migration_squad: Optional[str] = Field(None, description="Migration squad")
    migration_start_date: Optional[str] = Field(None, description="Planned start date")
    migration_end_date: Optional[str] = Field(None, description="Planned end date")
    complexity_rating: Optional[str] = Field(None, description="Low → Extra High")
    migration_scope: Optional[str] = Field(None, description="In migration scope flag")
    app_function: Optional[str] = Field(None, description="IT Tool / Business Application")
    app_type: Optional[str] = Field(None, description="COTS/ISV or In-house")
    app_owner: Optional[str] = Field(None, description="Application owner")
    app_sme: Optional[str] = Field(None, description="Subject matter expert")
    high_availability: Optional[str] = Field(None, description="HA enabled")
    business_critical: Optional[str] = Field(None, description="Business critical")
    inherent_risk: Optional[str] = Field(None, description="Risk level")
    materiality: Optional[str] = Field(None, description="Material flag")
    pii_data: Optional[str] = Field(None, description="Contains PII")
    disaster_recovery: Optional[str] = Field(None, description="DR enabled")
    number_of_unique_operating_systems: Optional[str] = Field(None, description="Count")
    unique_operating_systems: Optional[str] = Field(None, description="OS list")
    number_of_machines_with_out_of_support_OS: Optional[str] = Field(None, description="Unsupported OS count")
    sql_server_count: Optional[str] = Field(None, description="SQL Server count")
    non_sql_databases: Optional[str] = Field(None, description="Non-SQL DBs")
    other_tech_stack_components: Optional[str] = Field(None, description="Tech stack")
    assigned_migration_strategy: Optional[str] = Field(None, description="Assigned strategy")
    suitable_migration_strategy_options: Optional[str] = Field(None, description="Options")
    detected_app_components: Optional[str] = Field(None, description="Detected components")
    app_component_modernization_options: Optional[str] = Field(None, description="Modernization options")

    class Config:
        extra = "allow"


# =============================================================================
# Server Overview (from Server_Overview_Current.sql)
# =============================================================================


class DrMigrateServerOverview(BaseModel):
    """Server overview from Dr. Migrate Server_Overview_Current view.

    Current server configuration, performance, and readiness information.
    """
    machine: str = Field(..., description="VM name")
    application: Optional[str] = Field(None, description="Application")
    environment: Optional[str] = Field(None, description="Prod / Dev / Test")
    OperatingSystem: Optional[str] = Field(None, description="OS")
    os_support_status: Optional[str] = Field(None, description="Support status")
    PowerStatus: Optional[str] = Field(None, description="Power state")
    CloudVMReadiness: Optional[str] = Field(None, description="Cloud readiness")
    AllocatedMemoryInGB: Optional[float] = Field(None, description="Memory in GB")
    Cores: Optional[int] = Field(None, description="CPU cores")
    CPUUsageInPct: Optional[float] = Field(None, description="CPU usage percentage")
    MemoryUsageInPct: Optional[float] = Field(None, description="Memory usage percentage")
    StorageGB: Optional[float] = Field(None, description="Storage in GB")
    DiskReadOpsPerSec: Optional[float] = Field(None, description="Disk read IOPS")
    DiskWriteOpsPerSec: Optional[float] = Field(None, description="Disk write IOPS")
    NetworkInMBPS: Optional[str] = Field(None, description="Network in MBPS")
    NetworkOutMBPS: Optional[str] = Field(None, description="Network out MBPS")

    # Additional fields that may be present
    ip_address: Optional[str] = Field(None, description="IP address(es)")

    class Config:
        extra = "allow"


# =============================================================================
# Installed Applications (from InstalledApplications.sql)
# =============================================================================


class DrMigrateInstalledApplication(BaseModel):
    """Installed application from Dr. Migrate InstalledApplications view.

    Installed software details per server.
    """
    machine: str = Field(..., description="VM name")
    key_software: Optional[str] = Field(None, description="Detected COTS software")
    key_software_category: Optional[str] = Field(None, description="Software category")
    key_software_type: Optional[str] = Field(None, description="Client / Server")
    specific_software_detected: Optional[str] = Field(None, description="Installed software")

    class Config:
        extra = "allow"


# =============================================================================
# Key Software (from Key_Software.sql)
# =============================================================================


class DrMigrateKeySoftware(BaseModel):
    """Key software from Dr. Migrate Key_Software view.

    Detected COTS key software and categories.
    """
    application: Optional[str] = Field(None, description="Application name")
    key_software: Optional[str] = Field(None, description="Software name")
    key_software_category: Optional[str] = Field(None, description="Software category")

    class Config:
        extra = "allow"


# =============================================================================
# Cloud Server Cost (from Cloud_Server_Cost.sql)
# =============================================================================


class DrMigrateCloudServerCost(BaseModel):
    """Cloud server cost from Dr. Migrate Cloud_Server_Cost view.

    Annualized future cloud cost per server.
    """
    machine: str = Field(..., description="VM name")
    application: Optional[str] = Field(None, description="Application")
    assigned_treatment: Optional[str] = Field(None, description="6R treatment")
    assigned_target: Optional[str] = Field(None, description="Cloud target")
    cloud_compute_cost_annual: Optional[float] = Field(None, description="Compute cost")
    cloud_storage_cost_annual: Optional[float] = Field(None, description="Storage cost")
    cloud_total_cost_annual: Optional[float] = Field(None, description="Total cloud cost")

    class Config:
        extra = "allow"


# =============================================================================
# Current Server Cost (from Current_Server_Cost.sql)
# =============================================================================


class DrMigrateCurrentServerCost(BaseModel):
    """Current server cost from Dr. Migrate Current_Server_Cost view.

    Annualized current on-prem cost per server.
    """
    machine: str = Field(..., description="VM name")
    hardware_cost_annual: Optional[float] = Field(None, description="Hardware")
    software_cost_annual: Optional[float] = Field(None, description="Software")
    electricity_cost_annual: Optional[float] = Field(None, description="Electricity")
    data_center_cost_annual: Optional[float] = Field(None, description="Data center")
    virtualisation_cost_annual: Optional[float] = Field(None, description="Virtualization")
    networking_cost_annual: Optional[float] = Field(None, description="Networking")
    storage_cost_annual: Optional[float] = Field(None, description="Storage")
    backup_cost_annual: Optional[float] = Field(None, description="Backup")
    disaster_recovery_cost_annual: Optional[float] = Field(None, description="DR")
    total_cost_annual: Optional[float] = Field(None, description="Total cost")

    class Config:
        extra = "allow"


# =============================================================================
# App Modernization Candidates (from App_Modernization_Candidates.sql)
# =============================================================================


class DrMigrateAppModCandidate(BaseModel):
    """App modernization candidate from Dr. Migrate App_Modernization_Candidates view.

    Applications suitable for modernization.
    """
    application: str = Field(..., description="Application")
    app_mod_candidate_technology: Optional[str] = Field(None, description="Technology")
    number_of_machines_with_tech: Optional[int] = Field(None, description="Machine count")

    class Config:
        extra = "allow"


# =============================================================================
# Application Cost Comparison (from Application_Cost_Comparison.sql)
# =============================================================================


class DrMigrateApplicationCostComparison(BaseModel):
    """Application cost comparison from Dr. Migrate Application_Cost_Comparison view.

    Aggregated current vs cloud cost per application.
    """
    application: str = Field(..., description="Application")
    current_total_cost_annual: Optional[float] = Field(None, description="On-prem total")
    cloud_compute_cost_annual: Optional[float] = Field(None, description="Cloud compute")
    cloud_storage_cost_annual: Optional[float] = Field(None, description="Cloud storage")
    cloud_total_cost_annual: Optional[float] = Field(None, description="Cloud total")
    Currency: Optional[str] = Field(None, description="Currency code")
    Symbol: Optional[str] = Field(None, description="Currency symbol")

    class Config:
        extra = "allow"


# =============================================================================
# Network Data (from PostgreSQL views/functions)
# =============================================================================


class DrMigrateNetworkServerOverview(BaseModel):
    """Network server overview from Dr. Migrate network_server_overview view.

    VM-to-VM network communications.
    """
    source_machine: Optional[str] = Field(None, description="Source VM")
    destination_machine: Optional[str] = Field(None, description="Destination VM")
    port: Optional[str] = Field(None, description="Port")
    protocol: Optional[str] = Field(None, description="Protocol")

    class Config:
        extra = "allow"


class DrMigrateNetworkApplicationOverview(BaseModel):
    """Network application overview from Dr. Migrate network_application_overview view.

    Application-to-application communications.
    """
    source_application: Optional[str] = Field(None, description="Source application")
    destination_application: Optional[str] = Field(None, description="Destination application")
    port: Optional[str] = Field(None, description="Port")

    class Config:
        extra = "allow"


class DrMigrateFirewallRule(BaseModel):
    """Firewall rule from Dr. Migrate get_network_data_suggested_firewall_rules function.

    Suggested firewall rules per application.
    """
    firewall_rule_id: Optional[int] = Field(None, description="Rule ID")
    direction: Optional[str] = Field(None, description="In / Out")
    source_application: Optional[str] = Field(None, description="Source app")
    destination_application: Optional[str] = Field(None, description="Destination app")
    destination_port: Optional[str] = Field(None, description="Port")
    source_subnet: Optional[str] = Field(None, description="Source subnet")
    destination_subnet: Optional[str] = Field(None, description="Destination subnet")

    class Config:
        extra = "allow"


# =============================================================================
# Composite Input Model for Context Generation
# =============================================================================


class DrMigrateApplicationData(BaseModel):
    """Complete Dr. Migrate data for a single application.

    This model aggregates all Dr. Migrate data sources for one application,
    which can then be converted to a context file for the Architecture Scorer.
    """
    # Required: Application overview
    application_overview: DrMigrateApplicationOverview

    # Server details for this application
    server_overviews: list[DrMigrateServerOverview] = Field(default_factory=list)

    # Installed applications/software on servers
    installed_applications: list[DrMigrateInstalledApplication] = Field(default_factory=list)

    # Key software detected
    key_software: list[DrMigrateKeySoftware] = Field(default_factory=list)

    # Cloud cost projections
    cloud_server_costs: list[DrMigrateCloudServerCost] = Field(default_factory=list)

    # Current on-prem costs
    current_server_costs: list[DrMigrateCurrentServerCost] = Field(default_factory=list)

    # App modernization candidates (if any)
    app_mod_candidates: list[DrMigrateAppModCandidate] = Field(default_factory=list)

    # Cost comparison summary
    cost_comparison: Optional[DrMigrateApplicationCostComparison] = None

    # Network dependencies
    network_dependencies: list[DrMigrateNetworkApplicationOverview] = Field(default_factory=list)

    # Firewall rules
    firewall_rules: list[DrMigrateFirewallRule] = Field(default_factory=list)

    class Config:
        extra = "allow"
