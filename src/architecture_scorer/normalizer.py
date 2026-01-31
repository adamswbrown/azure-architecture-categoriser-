"""Context Normalizer - Phase 1 of the Scoring Engine.

Normalizes raw application context files into structured, typed objects.
Handles the messy reality of real-world data.
"""

import re
from typing import Optional

from .schema import (
    ApplicationContext,
    AppModResults,
    AppOverview,
    ApprovedServices,
    BusinessCriticality,
    CompatibilityStatus,
    DependencyComplexity,
    DetectedTechnology,
    PlatformCompatibility,
    RawAppModFinding,
    RawContextFile,
    RawServerDetail,
    ServerSummary,
    Treatment,
    UtilizationProfile,
    VMReadiness,
)


class ContextNormalizer:
    """Normalizes raw context files into structured ApplicationContext."""

    # Technology classification patterns
    RUNTIME_PATTERNS = {
        ".NET": [r"\.net", r"asp\.net", r"c#", r"dotnet"],
        "Java": [r"\bjava\b", r"spring", r"tomcat", r"jboss", r"wildfly"],
        "Node.js": [r"node\.?js", r"express", r"npm"],
        "Python": [r"\bpython\b", r"django", r"flask", r"fastapi"],
        "PHP": [r"\bphp\b", r"laravel", r"symfony"],
        "Ruby": [r"\bruby\b", r"rails"],
        "Go": [r"\bgo\b", r"golang"],
    }

    DATABASE_PATTERNS = {
        "SQL Server": [r"sql server", r"mssql", r"microsoft sql"],
        "PostgreSQL": [r"postgres", r"postgresql"],
        "MySQL": [r"mysql", r"mariadb"],
        "Oracle": [r"oracle"],
        "MongoDB": [r"mongo"],
        "Cosmos DB": [r"cosmos"],
        "Redis": [r"redis"],
        "Access": [r"microsoft access", r"access database"],
    }

    MIDDLEWARE_PATTERNS = {
        "IIS": [r"\biis\b", r"internet information"],
        "Apache": [r"apache http", r"httpd"],
        "nginx": [r"nginx"],
        "Tomcat": [r"tomcat"],
    }

    MESSAGING_PATTERNS = {
        "RabbitMQ": [r"rabbitmq"],
        "Kafka": [r"kafka"],
        "ActiveMQ": [r"activemq"],
        "MSMQ": [r"msmq"],
        "Service Bus": [r"service bus"],
    }

    # Treatment mapping from string values
    TREATMENT_MAP = {
        "retire": Treatment.RETIRE,
        "tolerate": Treatment.TOLERATE,
        "rehost": Treatment.REHOST,
        "replatform": Treatment.REPLATFORM,
        "refactor": Treatment.REFACTOR,
        "replace": Treatment.REPLACE,
        "rebuild": Treatment.REBUILD,
        "retain": Treatment.RETAIN,
    }

    # Platform name normalization
    PLATFORM_NORMALIZATIONS = {
        "azure_app_service": "Azure App Service",
        "azure_container_apps": "Azure Container Apps",
        "azure_kubernetes_service": "Azure Kubernetes Service",
        "aks": "Azure Kubernetes Service",
        "app_service": "Azure App Service",
        "container_apps": "Azure Container Apps",
    }

    def normalize(self, raw: RawContextFile) -> ApplicationContext:
        """Normalize a raw context file into an ApplicationContext."""
        return ApplicationContext(
            app_overview=self._normalize_app_overview(raw),
            server_summary=self._normalize_servers(raw.server_details),
            detected_technology=self._normalize_technology(raw),
            app_mod_results=self._normalize_app_mod(raw.app_mod_results),
            approved_services=self._normalize_approved_services(raw.app_approved_azure_services),
        )

    def _normalize_app_overview(self, raw: RawContextFile) -> AppOverview:
        """Normalize app overview from raw context."""
        if not raw.app_overview:
            raise ValueError("app_overview is required but empty")

        raw_overview = raw.app_overview[0]

        # Parse treatment from string
        declared_treatment = None
        if raw_overview.treatment:
            treatment_lower = raw_overview.treatment.lower().strip()
            declared_treatment = self.TREATMENT_MAP.get(treatment_lower)

        # Parse criticality (handles typo in original)
        criticality = BusinessCriticality.from_string(
            raw_overview.business_crtiticality or "Medium"
        )

        return AppOverview(
            application_name=raw_overview.application,
            app_type=raw_overview.app_type,
            business_criticality=criticality,
            declared_treatment=declared_treatment,
            description=raw_overview.description,
            owner=raw_overview.owner,
        )

    def _normalize_servers(self, servers: list[RawServerDetail]) -> ServerSummary:
        """Normalize server details into aggregated summary."""
        if not servers:
            return ServerSummary()

        # Collect environments
        environments = set()
        os_counts: dict[str, int] = {}
        readiness_counts: dict[str, int] = {}
        total_cpu = 0.0
        total_memory = 0.0
        cpu_count = 0
        memory_count = 0
        total_cores = 0
        total_memory_gb = 0.0

        for server in servers:
            # Environment
            if server.environment:
                environments.add(server.environment)

            # OS mix
            if server.OperatingSystem:
                os_type = self._classify_os(server.OperatingSystem)
                os_counts[os_type] = os_counts.get(os_type, 0) + 1

            # VM readiness
            if server.AzureVMReadiness:
                readiness = VMReadiness.from_string(server.AzureVMReadiness).value
                readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1

            # Utilization
            if server.CPUUsage is not None:
                total_cpu += server.CPUUsage
                cpu_count += 1
            if server.MemoryUsage is not None:
                total_memory += server.MemoryUsage
                memory_count += 1

            # Resources
            if server.Cores:
                total_cores += server.Cores
            if server.MemoryGB:
                total_memory_gb += server.MemoryGB

        # Calculate averages
        avg_cpu = total_cpu / cpu_count if cpu_count > 0 else None
        avg_memory = total_memory / memory_count if memory_count > 0 else None

        # Determine utilization profile
        utilization_profile = self._determine_utilization_profile(avg_cpu, avg_memory)

        # Determine dependency complexity from server count and tech diversity
        complexity = self._estimate_dependency_complexity(servers, os_counts)

        return ServerSummary(
            server_count=len(servers),
            servers=servers,
            environments_present=sorted(list(environments)),
            os_mix=os_counts,
            vm_readiness_distribution=readiness_counts,
            utilization_profile=utilization_profile,
            avg_cpu_usage=avg_cpu,
            avg_memory_usage=avg_memory,
            total_cores=total_cores,
            total_memory_gb=total_memory_gb,
            dependency_complexity=complexity,
        )

    def _classify_os(self, os_string: str) -> str:
        """Classify OS into Windows or Linux."""
        os_lower = os_string.lower()
        if "windows" in os_lower:
            return "Windows"
        elif any(linux in os_lower for linux in ["linux", "ubuntu", "centos", "rhel", "debian"]):
            return "Linux"
        else:
            return "Other"

    def _determine_utilization_profile(
        self, avg_cpu: Optional[float], avg_memory: Optional[float]
    ) -> UtilizationProfile:
        """Determine utilization profile from averages."""
        if avg_cpu is None and avg_memory is None:
            return UtilizationProfile.MEDIUM

        # Use the higher of the two
        max_util = max(avg_cpu or 0, avg_memory or 0)
        if max_util < 30:
            return UtilizationProfile.LOW
        elif max_util < 70:
            return UtilizationProfile.MEDIUM
        else:
            return UtilizationProfile.HIGH

    def _estimate_dependency_complexity(
        self, servers: list[RawServerDetail], os_counts: dict[str, int]
    ) -> DependencyComplexity:
        """Estimate dependency complexity from available signals."""
        # Simple heuristics based on server count and diversity
        server_count = len(servers)

        if server_count == 1:
            return DependencyComplexity.SIMPLE
        elif server_count <= 3 and len(os_counts) == 1:
            return DependencyComplexity.SIMPLE
        elif server_count <= 5:
            return DependencyComplexity.MODERATE
        else:
            return DependencyComplexity.COMPLEX

    def _normalize_technology(self, raw: RawContextFile) -> DetectedTechnology:
        """Normalize detected technology into structured format."""
        technologies = raw.detected_technology_running
        all_tech_text = " ".join(technologies).lower()

        # Detect primary runtime
        primary_runtime = None
        runtime_version = None
        frameworks = []

        for runtime, patterns in self.RUNTIME_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, all_tech_text, re.IGNORECASE):
                    primary_runtime = runtime
                    # Try to extract version
                    for tech in technologies:
                        if re.search(pattern, tech, re.IGNORECASE):
                            version_match = re.search(r'(\d+(?:\.\d+)*)', tech)
                            if version_match:
                                runtime_version = version_match.group(1)
                            # Tech items that aren't the runtime itself are frameworks
                            if not re.match(pattern + r'\s*\d*\.?\d*$', tech, re.IGNORECASE):
                                frameworks.append(tech)
                    break
            if primary_runtime:
                break

        # Detect databases
        database_types = []
        for db, patterns in self.DATABASE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, all_tech_text, re.IGNORECASE):
                    database_types.append(db)
                    break

        # Detect middleware
        middleware_types = []
        for mw, patterns in self.MIDDLEWARE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, all_tech_text, re.IGNORECASE):
                    middleware_types.append(mw)
                    break

        # Detect messaging
        messaging_types = []
        for msg, patterns in self.MESSAGING_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, all_tech_text, re.IGNORECASE):
                    messaging_types.append(msg)
                    break

        # Infer OS from technology
        # Note: CodeQL flags "asp.net" as incomplete URL sanitization, but this is
        # technology pattern matching, not URL handling (lgtm [py/incomplete-url-substring-sanitization])
        is_windows = any(
            tech.lower() in ["microsoft iis", "iis", "asp.net", ".net framework"]
            for tech in technologies
        ) or "asp.net" in all_tech_text or "iis" in all_tech_text  # codeql[py/incomplete-url-substring-sanitization]
        is_linux = "ubuntu" in all_tech_text or "centos" in all_tech_text or (
            primary_runtime in ["Java", "Node.js", "Python"] and not is_windows
        )

        return DetectedTechnology(
            technologies=technologies,
            primary_runtime=primary_runtime,
            runtime_version=runtime_version,
            frameworks=frameworks,
            database_present=len(database_types) > 0,
            database_types=database_types,
            middleware_present=len(middleware_types) > 0,
            middleware_types=middleware_types,
            messaging_present=len(messaging_types) > 0,
            messaging_types=messaging_types,
            is_windows=is_windows,
            is_linux=is_linux,
        )

    def _normalize_app_mod(
        self, app_mod_results: list
    ) -> Optional[AppModResults]:
        """Normalize App Mod results."""
        if not app_mod_results:
            return None

        raw_result = app_mod_results[0]

        # Normalize platform compatibility
        platform_compat = []
        for platform_key, status_str in raw_result.compatibility.items():
            normalized_platform = self._normalize_platform_name(platform_key)
            status = CompatibilityStatus.from_string(status_str)
            platform_compat.append(PlatformCompatibility(
                platform=normalized_platform,
                status=status,
            ))

        # Extract severity findings
        critical_findings = []
        high_findings = []
        for finding in raw_result.findings:
            if finding.severity.lower() == "critical":
                critical_findings.append(finding.description)
            elif finding.severity.lower() == "high":
                high_findings.append(finding.description)

        return AppModResults(
            technology=raw_result.technology,
            container_ready=raw_result.summary.container_ready,
            modernization_feasible=raw_result.summary.modernization_feasible,
            platform_compatibility=platform_compat,
            recommended_targets=raw_result.recommended_targets,
            findings=raw_result.findings,
            explicit_blockers=raw_result.blockers,
            critical_findings=critical_findings,
            high_severity_findings=high_findings,
        )

    def _normalize_platform_name(self, platform: str) -> str:
        """Normalize platform names to canonical form."""
        platform_lower = platform.lower().replace("-", "_").replace(" ", "_")
        return self.PLATFORM_NORMALIZATIONS.get(platform_lower, platform)

    def _normalize_approved_services(
        self, approved_services: list[dict[str, str]]
    ) -> ApprovedServices:
        """Normalize approved Azure service mappings."""
        if not approved_services:
            return ApprovedServices()

        # Merge all mapping dicts
        all_mappings: dict[str, str] = {}
        for mapping_dict in approved_services:
            all_mappings.update(mapping_dict)

        return ApprovedServices(mappings=all_mappings)


def load_context_file(file_path: str) -> ApplicationContext:
    """Load and normalize a context file from disk.

    Args:
        file_path: Path to the JSON context file.

    Returns:
        Normalized ApplicationContext ready for scoring.

    Raises:
        ValueError: If the file is invalid or cannot be parsed.
    """
    import json
    from pathlib import Path

    path = Path(file_path)
    if not path.exists():
        raise ValueError(f"Context file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Handle array wrapper (file is JSON array with one object)
    if isinstance(data, list):
        if len(data) != 1:
            raise ValueError(f"Expected exactly 1 context object, got {len(data)}")
        data = data[0]

    # Parse raw context
    raw = RawContextFile.model_validate(data)

    # Normalize and return
    normalizer = ContextNormalizer()
    return normalizer.normalize(raw)
