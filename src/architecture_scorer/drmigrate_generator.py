"""Generator for creating context files from Dr. Migrate data.

This module converts Dr. Migrate LLM-exposed data (from SQL Server and PostgreSQL views)
into the context file format expected by the Architecture Scoring Engine.

This enables architecture recommendations for ALL applications in Dr. Migrate,
not just those with Java/.NET components that have been scanned by App Cat/App Mod.
"""

import json
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from .drmigrate_schema import (
    DrMigrateApplicationData,
    DrMigrateApplicationOverview,
    DrMigrateCloudServerCost,
    DrMigrateInstalledApplication,
    DrMigrateServerOverview,
)


# =============================================================================
# Technology Detection Patterns
# =============================================================================

# Patterns for detecting technology categories from software names
TECHNOLOGY_PATTERNS = {
    # Databases
    "databases": [
        (r"sql\s*server", "SQL Server"),
        (r"mysql", "MySQL"),
        (r"postgresql|postgres", "PostgreSQL"),
        (r"oracle\s*database|oracle\s*db", "Oracle Database"),
        (r"mongodb", "MongoDB"),
        (r"redis", "Redis"),
        (r"mariadb", "MariaDB"),
        (r"db2", "IBM DB2"),
        (r"sqlite", "SQLite"),
        (r"microsoft\s*access", "Microsoft Access"),
    ],
    # Web servers
    "web_servers": [
        (r"iis|internet\s*information\s*services", "Microsoft IIS"),
        (r"apache\s*http|apache2|httpd", "Apache HTTP Server"),
        (r"nginx", "NGINX"),
        (r"tomcat", "Apache Tomcat"),
    ],
    # Runtimes
    "runtimes": [
        (r"\.net\s*framework\s*(\d+\.?\d*)", ".NET Framework {0}"),
        (r"\.net\s*core\s*(\d+\.?\d*)", ".NET Core {0}"),
        (r"\.net\s*(\d+)", ".NET {0}"),
        (r"java\s*(\d+)", "Java {0}"),
        (r"jdk\s*(\d+)", "Java {0}"),
        (r"jre\s*(\d+)", "Java {0}"),
        (r"python\s*(\d+\.?\d*)", "Python {0}"),
        (r"node\.?js\s*(\d+\.?\d*)", "Node.js {0}"),
        (r"php\s*(\d+\.?\d*)", "PHP {0}"),
    ],
    # Frameworks
    "frameworks": [
        (r"spring\s*boot", "Spring Boot"),
        (r"spring\s*framework", "Spring Framework"),
        (r"asp\.?net\s*mvc", "ASP.NET MVC"),
        (r"asp\.?net\s*core", "ASP.NET Core"),
        (r"asp\.?net", "ASP.NET"),
        (r"django", "Django"),
        (r"flask", "Flask"),
        (r"express", "Express.js"),
        (r"react", "React"),
        (r"angular", "Angular"),
        (r"vue\.?js|vuejs", "Vue.js"),
    ],
    # Messaging
    "messaging": [
        (r"rabbitmq", "RabbitMQ"),
        (r"kafka", "Apache Kafka"),
        (r"activemq", "Apache ActiveMQ"),
        (r"msmq", "Microsoft MSMQ"),
        (r"ibm\s*mq|websphere\s*mq", "IBM MQ"),
    ],
    # Middleware
    "middleware": [
        (r"websphere", "IBM WebSphere"),
        (r"weblogic", "Oracle WebLogic"),
        (r"jboss|wildfly", "JBoss/WildFly"),
        (r"biztalk", "Microsoft BizTalk"),
    ],
}

# Azure service mapping for common on-prem technologies
AZURE_SERVICE_MAPPINGS = {
    # Databases
    "SQL Server": "Azure SQL Database",
    "MySQL": "Azure Database for MySQL",
    "PostgreSQL": "Azure Database for PostgreSQL",
    "Oracle Database": "Oracle Database@Azure",
    "MongoDB": "Azure Cosmos DB",
    "Redis": "Azure Cache for Redis",
    "MariaDB": "Azure Database for MariaDB",
    # Web servers
    "Microsoft IIS": "Azure App Service",
    "Apache HTTP Server": "Azure App Service",
    "NGINX": "Azure App Service",
    "Apache Tomcat": "Azure App Service",
    # Runtimes
    ".NET Framework": "Azure Virtual Machines",
    ".NET Core": "Azure App Service",
    ".NET": "Azure App Service",
    "Java": "Azure App Service",
    "Python": "Azure App Service",
    "Node.js": "Azure App Service",
    "PHP": "Azure App Service",
    # Messaging
    "RabbitMQ": "Azure Service Bus",
    "Apache Kafka": "Azure Event Hubs",
    "Apache ActiveMQ": "Azure Service Bus",
    "Microsoft MSMQ": "Azure Service Bus",
    "IBM MQ": "Azure Service Bus",
    # Middleware
    "IBM WebSphere": "Azure Kubernetes Service",
    "Oracle WebLogic": "Azure Kubernetes Service",
    "JBoss/WildFly": "Azure App Service",
}


# =============================================================================
# Generator Class
# =============================================================================


class DrMigrateContextGenerator:
    """Generates context files from Dr. Migrate data sources.

    This class transforms Dr. Migrate data into the format expected by the
    Architecture Scoring Engine, enabling architecture recommendations for
    applications that don't have App Cat/App Mod scan results.
    """

    def __init__(
        self,
        include_cost_data: bool = False,
        include_network_data: bool = False,
        azure_service_mappings: Optional[dict[str, str]] = None,
    ):
        """Initialize the generator.

        Args:
            include_cost_data: Include cost information in extended fields
            include_network_data: Include network dependency information
            azure_service_mappings: Custom Azure service mappings (overrides defaults)
        """
        self.include_cost_data = include_cost_data
        self.include_network_data = include_network_data
        self.azure_service_mappings = azure_service_mappings or AZURE_SERVICE_MAPPINGS

    def generate_context(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate a context file from Dr. Migrate application data.

        Args:
            app_data: Complete Dr. Migrate data for an application

        Returns:
            Context file structure as a list with one dictionary (matching expected format)
        """
        context = {
            "app_overview": self._generate_app_overview(app_data),
            "detected_technology_running": self._detect_technologies(app_data),
            "app_approved_azure_services": self._generate_azure_services(app_data),
            "server_details": self._generate_server_details(app_data),
            "App Mod results": self._generate_app_mod_results(app_data),
        }

        # Add extended data if requested
        if self.include_cost_data and app_data.cost_comparison:
            context["_cost_comparison"] = {
                "current_total_cost_annual": app_data.cost_comparison.current_total_cost_annual,
                "cloud_total_cost_annual": app_data.cost_comparison.cloud_total_cost_annual,
                "currency": app_data.cost_comparison.Currency,
            }

        if self.include_network_data and app_data.network_dependencies:
            context["_network_dependencies"] = [
                {
                    "source": dep.source_application,
                    "destination": dep.destination_application,
                    "port": dep.port,
                }
                for dep in app_data.network_dependencies
            ]

        # Add metadata about generation
        context["_generated_from"] = "dr_migrate"
        context["_generated_at"] = datetime.utcnow().isoformat()

        return [context]

    def _generate_app_overview(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate app_overview section from Application_Overview data."""
        overview = app_data.application_overview

        return [{
            "application": overview.application,
            "app_type": self._determine_app_type(overview),
            "business_crtiticality": self._determine_criticality(overview),
            "treatment": self._map_migration_strategy(overview.assigned_migration_strategy),
            "description": self._generate_description(overview),
            "owner": overview.app_owner,
        }]

    def _determine_app_type(self, overview: DrMigrateApplicationOverview) -> str:
        """Determine application type from Dr. Migrate data."""
        if overview.app_type:
            return overview.app_type

        if overview.app_function:
            if "tool" in overview.app_function.lower():
                return "IT Tool"
            elif "business" in overview.app_function.lower():
                return "Business Application"

        return "Application"

    def _determine_criticality(self, overview: DrMigrateApplicationOverview) -> str:
        """Determine business criticality from available indicators."""
        # Check explicit business_critical field first
        if overview.business_critical:
            bc_lower = overview.business_critical.lower()
            if bc_lower in ("yes", "true", "high", "critical"):
                return "High"
            elif bc_lower in ("no", "false", "low"):
                return "Low"

        # Check inherent_risk as secondary indicator
        if overview.inherent_risk:
            risk_lower = overview.inherent_risk.lower()
            if "high" in risk_lower or "critical" in risk_lower:
                return "High"
            elif "medium" in risk_lower:
                return "Medium"
            elif "low" in risk_lower:
                return "Low"

        # Check materiality
        if overview.materiality:
            mat_lower = overview.materiality.lower()
            if mat_lower in ("yes", "true", "material"):
                return "High"

        # Check high_availability and disaster_recovery as indicators
        if overview.high_availability and overview.high_availability.lower() in ("yes", "true"):
            return "High"
        if overview.disaster_recovery and overview.disaster_recovery.lower() in ("yes", "true"):
            return "High"

        return "Medium"  # Default

    def _map_migration_strategy(self, strategy: Optional[str]) -> Optional[str]:
        """Map Dr. Migrate strategy to context file treatment."""
        if not strategy:
            return None

        strategy_lower = strategy.lower()
        mapping = {
            "rehost": "Rehost",
            "lift and shift": "Rehost",
            "replatform": "Replatform",
            "refactor": "Refactor",
            "rearchitect": "Refactor",
            "rebuild": "Rebuild",
            "replace": "Replace",
            "repurchase": "Replace",
            "retire": "Retire",
            "retain": "Retain",
            "tolerate": "Tolerate",
        }

        for key, value in mapping.items():
            if key in strategy_lower:
                return value

        return strategy  # Return original if no mapping found

    def _generate_description(self, overview: DrMigrateApplicationOverview) -> str:
        """Generate a description from available metadata."""
        parts = []

        if overview.app_function:
            parts.append(overview.app_function)

        if overview.complexity_rating:
            parts.append(f"Complexity: {overview.complexity_rating}")

        if overview.number_of_machines:
            parts.append(f"{overview.number_of_machines} servers")

        if overview.number_of_environments:
            parts.append(f"{overview.number_of_environments} environments")

        return ". ".join(parts) if parts else ""

    def _detect_technologies(self, app_data: DrMigrateApplicationData) -> list[str]:
        """Detect and normalize technologies from all available sources."""
        technologies = set()

        # From Application_Overview tech stack
        if app_data.application_overview.other_tech_stack_components:
            techs = app_data.application_overview.other_tech_stack_components.split(",")
            for tech in techs:
                normalized = self._normalize_technology(tech.strip())
                if normalized:
                    technologies.add(normalized)

        # From Application_Overview detected components
        if app_data.application_overview.detected_app_components:
            components = app_data.application_overview.detected_app_components.split(",")
            for comp in components:
                normalized = self._normalize_technology(comp.strip())
                if normalized:
                    technologies.add(normalized)

        # From unique operating systems
        if app_data.application_overview.unique_operating_systems:
            oses = app_data.application_overview.unique_operating_systems.split(",")
            for os in oses:
                technologies.add(os.strip())

        # From installed applications
        for app in app_data.installed_applications:
            if app.key_software:
                normalized = self._normalize_technology(app.key_software)
                if normalized:
                    technologies.add(normalized)
            if app.specific_software_detected:
                normalized = self._normalize_technology(app.specific_software_detected)
                if normalized:
                    technologies.add(normalized)

        # From key software
        for sw in app_data.key_software:
            if sw.key_software:
                normalized = self._normalize_technology(sw.key_software)
                if normalized:
                    technologies.add(normalized)

        # From app mod candidates (modernization technologies)
        for candidate in app_data.app_mod_candidates:
            if candidate.app_mod_candidate_technology:
                technologies.add(candidate.app_mod_candidate_technology)

        # From server details (OS)
        for server in app_data.server_overviews:
            if server.OperatingSystem:
                technologies.add(server.OperatingSystem)

        return sorted(list(technologies))

    def _normalize_technology(self, tech: str) -> Optional[str]:
        """Normalize a technology name using pattern matching."""
        if not tech:
            return None

        tech_lower = tech.lower()

        # Check all pattern categories
        for category, patterns in TECHNOLOGY_PATTERNS.items():
            for pattern, name_template in patterns:
                match = re.search(pattern, tech_lower, re.IGNORECASE)
                if match:
                    if "{0}" in name_template and match.groups():
                        return name_template.format(match.group(1))
                    return name_template

        # Return original if no pattern matched (might be a valid tech name)
        return tech if len(tech) > 1 else None

    def _generate_azure_services(self, app_data: DrMigrateApplicationData) -> list[dict[str, str]]:
        """Generate Azure service mappings for detected technologies."""
        mappings = {}

        # Get all detected technologies
        technologies = self._detect_technologies(app_data)

        for tech in technologies:
            # Check direct mapping
            if tech in self.azure_service_mappings:
                mappings[tech] = self.azure_service_mappings[tech]
                continue

            # Check pattern-based mapping
            tech_lower = tech.lower()
            for source, target in self.azure_service_mappings.items():
                if source.lower() in tech_lower:
                    mappings[tech] = target
                    break

        # Also check cloud server costs for assigned targets
        for cost in app_data.cloud_server_costs:
            if cost.assigned_target:
                # Try to map the treatment to a technology
                if cost.assigned_treatment:
                    mappings[cost.assigned_treatment] = cost.assigned_target

        return [mappings] if mappings else [{}]

    def _generate_server_details(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate server_details section from Server_Overview_Current data."""
        servers = []

        # Create lookup maps for additional data
        cloud_costs_by_machine = {
            cost.machine: cost for cost in app_data.cloud_server_costs
        }
        installed_apps_by_machine: dict[str, list[str]] = {}
        for app in app_data.installed_applications:
            if app.machine not in installed_apps_by_machine:
                installed_apps_by_machine[app.machine] = []
            if app.key_software:
                installed_apps_by_machine[app.machine].append(app.key_software)

        for server in app_data.server_overviews:
            server_detail = {
                "machine": server.machine,
                "environment": server.environment or "Production",
                "OperatingSystem": server.OperatingSystem,
                "ip_address": self._parse_ip_addresses(server.ip_address),
                "StorageGB": server.StorageGB,
                "MemoryGB": server.AllocatedMemoryInGB,
                "Cores": server.Cores,
                "CPUUsage": server.CPUUsageInPct,
                "MemoryUsage": server.MemoryUsageInPct,
                "DiskReadOpsPersec": server.DiskReadOpsPerSec,
                "DiskWriteOpsPerSec": server.DiskWriteOpsPerSec,
                "NetworkInMBPS": self._parse_network_value(server.NetworkInMBPS),
                "NetworkOutMBPS": self._parse_network_value(server.NetworkOutMBPS),
                "StandardSSDDisks": 0,  # Not available in Dr. Migrate
                "StandardHDDDisks": 0,
                "PremiumDisks": 0,
                "AzureVMReadiness": self._map_vm_readiness(server.CloudVMReadiness),
                "AzureReadinessIssues": self._get_readiness_issues(server),
                "migration_strategy": self._map_migration_strategy(
                    app_data.application_overview.assigned_migration_strategy
                ),
                "detected_COTS": installed_apps_by_machine.get(server.machine, []),
            }

            # Add treatment option from cloud costs if available
            cloud_cost = cloud_costs_by_machine.get(server.machine)
            if cloud_cost:
                server_detail["treatment_option"] = cloud_cost.assigned_target
                server_detail["assigned_treatment"] = cloud_cost.assigned_treatment

            servers.append(server_detail)

        return servers

    def _parse_ip_addresses(self, ip_string: Optional[str]) -> list[str]:
        """Parse IP addresses from a string."""
        if not ip_string:
            return []

        # Handle comma-separated or space-separated IPs
        ips = re.split(r"[,;\s]+", ip_string)
        return [ip.strip() for ip in ips if ip.strip()]

    def _parse_network_value(self, value: Optional[str]) -> Optional[float]:
        """Parse network value to float."""
        if value is None:
            return None

        try:
            return float(value)
        except (ValueError, TypeError):
            # Try to extract numeric part
            match = re.search(r"[\d.]+", str(value))
            if match:
                return float(match.group())
            return None

    def _map_vm_readiness(self, readiness: Optional[str]) -> str:
        """Map Dr. Migrate CloudVMReadiness to context file format."""
        if not readiness:
            return "Unknown"

        readiness_lower = readiness.lower()
        if "ready" in readiness_lower and "not" not in readiness_lower:
            if "condition" in readiness_lower:
                return "ReadyWithConditions"
            return "Ready"
        elif "not" in readiness_lower or "no" in readiness_lower:
            return "NotReady"

        return "Unknown"

    def _get_readiness_issues(self, server: DrMigrateServerOverview) -> Optional[str]:
        """Determine readiness issues from server data."""
        issues = []

        # Check OS support status
        if server.os_support_status:
            if "unsupported" in server.os_support_status.lower():
                issues.append("Unsupported OS")
            elif "end" in server.os_support_status.lower():
                issues.append("End of support OS")

        # Check power status
        if server.PowerStatus and server.PowerStatus.lower() == "off":
            issues.append("Server powered off")

        return "; ".join(issues) if issues else None

    def _generate_app_mod_results(self, app_data: DrMigrateApplicationData) -> list[dict[str, Any]]:
        """Generate App Mod results section.

        For applications without Java/.NET App Cat scans, this generates
        a minimal/inferred result based on available data.
        """
        # Check if we have app mod candidates
        app_mod_techs = set()
        for candidate in app_data.app_mod_candidates:
            if candidate.app_mod_candidate_technology:
                app_mod_techs.add(candidate.app_mod_candidate_technology)

        # Check for modernization options in application overview
        mod_options = app_data.application_overview.app_component_modernization_options

        # If no modernization data available, return minimal structure
        if not app_mod_techs and not mod_options:
            return self._generate_inferred_app_mod_results(app_data)

        results = []
        for tech in app_mod_techs:
            result = {
                "technology": tech,
                "summary": {
                    "modernization_feasible": True,
                    "inferred_from_dr_migrate": True,
                },
                "findings": [],
                "compatibility": self._infer_compatibility(tech),
                "recommended_targets": self._get_recommended_targets(tech),
                "blockers": [],
            }
            results.append(result)

        return results if results else self._generate_inferred_app_mod_results(app_data)

    def _generate_inferred_app_mod_results(
        self, app_data: DrMigrateApplicationData
    ) -> list[dict[str, Any]]:
        """Generate inferred App Mod results when no explicit data available."""
        # Detect primary technology from available data
        technologies = self._detect_technologies(app_data)
        primary_tech = self._detect_primary_technology(technologies)

        if not primary_tech:
            # Return empty if we can't determine technology
            return []

        # Determine if modernization is feasible based on treatment
        strategy = app_data.application_overview.assigned_migration_strategy
        mod_feasible = strategy and strategy.lower() in (
            "refactor", "rearchitect", "replatform", "rebuild"
        )

        return [{
            "technology": primary_tech,
            "summary": {
                "modernization_feasible": mod_feasible,
                "inferred_from_dr_migrate": True,
                "no_appcat_scan": True,
            },
            "findings": [{
                "type": "InferredFromDrMigrate",
                "severity": "Info",
                "description": "App Mod results inferred from Dr. Migrate data. "
                              "No App Cat scan available for this application."
            }],
            "compatibility": self._infer_compatibility(primary_tech),
            "recommended_targets": self._get_recommended_targets(primary_tech),
            "blockers": [],
        }]

    def _detect_primary_technology(self, technologies: list[str]) -> str:
        """Detect the primary technology from a list of technologies."""
        # Priority order for primary technology detection
        priority_patterns = [
            (r"java", "Java"),
            (r"\.net|dotnet", ".NET"),
            (r"python", "Python"),
            (r"node\.?js", "Node.js"),
            (r"php", "PHP"),
            (r"ruby", "Ruby"),
            (r"go|golang", "Go"),
        ]

        for tech in technologies:
            tech_lower = tech.lower()
            for pattern, name in priority_patterns:
                if re.search(pattern, tech_lower):
                    return name

        # Default based on OS
        for tech in technologies:
            if "windows" in tech.lower():
                return "Windows Application"
            elif "linux" in tech.lower() or "ubuntu" in tech.lower() or "centos" in tech.lower():
                return "Linux Application"

        return "Unknown"

    def _infer_compatibility(self, technology: str) -> dict[str, str]:
        """Infer platform compatibility based on technology."""
        tech_lower = technology.lower()

        # Default compatibility based on technology
        if "java" in tech_lower:
            return {
                "azure_app_service": "SupportedWithChanges",
                "azure_kubernetes_service": "Supported",
                "azure_container_apps": "Supported",
                "azure_virtual_machines": "FullySupported",
            }
        elif ".net core" in tech_lower or "dotnet core" in tech_lower:
            return {
                "azure_app_service": "FullySupported",
                "azure_kubernetes_service": "Supported",
                "azure_container_apps": "Supported",
                "azure_virtual_machines": "FullySupported",
            }
        elif ".net framework" in tech_lower or "dotnet framework" in tech_lower:
            return {
                "azure_app_service": "SupportedWithChanges",
                "azure_kubernetes_service": "NotSupported",
                "azure_container_apps": "NotSupported",
                "azure_virtual_machines": "FullySupported",
            }
        elif ".net" in tech_lower or "dotnet" in tech_lower:
            return {
                "azure_app_service": "Supported",
                "azure_virtual_machines": "FullySupported",
            }
        elif "python" in tech_lower or "node" in tech_lower or "php" in tech_lower:
            return {
                "azure_app_service": "Supported",
                "azure_kubernetes_service": "Supported",
                "azure_container_apps": "Supported",
                "azure_virtual_machines": "FullySupported",
            }
        else:
            # Conservative default for unknown technologies
            return {
                "azure_virtual_machines": "Supported",
            }

    def _get_recommended_targets(self, technology: str) -> list[str]:
        """Get recommended Azure targets based on technology."""
        tech_lower = technology.lower()

        if "java" in tech_lower:
            return ["Azure App Service", "Azure Kubernetes Service", "Azure Container Apps"]
        elif ".net core" in tech_lower or "dotnet core" in tech_lower:
            return ["Azure App Service", "Azure Container Apps", "Azure Kubernetes Service"]
        elif ".net framework" in tech_lower or "dotnet framework" in tech_lower:
            return ["Azure Virtual Machines", "Azure App Service"]
        elif ".net" in tech_lower or "dotnet" in tech_lower:
            return ["Azure App Service", "Azure Virtual Machines"]
        elif "python" in tech_lower or "node" in tech_lower:
            return ["Azure App Service", "Azure Container Apps", "Azure Functions"]
        else:
            return ["Azure Virtual Machines"]

    def generate_context_json(self, app_data: DrMigrateApplicationData, indent: int = 2) -> str:
        """Generate context file as JSON string.

        Args:
            app_data: Complete Dr. Migrate data for an application
            indent: JSON indentation level

        Returns:
            JSON string of the context file
        """
        context = self.generate_context(app_data)
        return json.dumps(context, indent=indent, default=str)

    def generate_batch_contexts(
        self,
        applications: list[DrMigrateApplicationData],
    ) -> dict[str, list[dict[str, Any]]]:
        """Generate context files for multiple applications.

        Args:
            applications: List of Dr. Migrate application data

        Returns:
            Dictionary mapping application names to their context files
        """
        return {
            app.application_overview.application: self.generate_context(app)
            for app in applications
        }
