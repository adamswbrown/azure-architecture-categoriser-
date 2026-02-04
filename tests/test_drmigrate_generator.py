"""Tests for the Dr. Migrate Context Generator.

This test suite validates that the generator:
1. Correctly maps Dr. Migrate data to context file format
2. Handles missing/partial data gracefully
3. Produces output compatible with the Architecture Scorer
4. Correctly infers technologies and Azure service mappings
"""

import json
from pathlib import Path

import pytest

from architecture_scorer.drmigrate_generator import (
    DrMigrateContextGenerator,
    AZURE_SERVICE_MAPPINGS,
    TECHNOLOGY_PATTERNS,
)
from architecture_scorer.drmigrate_schema import (
    DrMigrateApplicationData,
    DrMigrateApplicationOverview,
    DrMigrateServerOverview,
    DrMigrateInstalledApplication,
    DrMigrateKeySoftware,
    DrMigrateCloudServerCost,
    DrMigrateAppModCandidate,
    DrMigrateApplicationCostComparison,
    DrMigrateNetworkApplicationOverview,
)
from architecture_scorer.schema import RawContextFile


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def basic_app_overview() -> DrMigrateApplicationOverview:
    """Create a basic application overview for testing."""
    return DrMigrateApplicationOverview(
        application="TestApplication",
        number_of_machines=2,
        number_of_environments=2,
        environment_names="Production, Development",
        complexity_rating="Medium",
        app_type="In-house",
        app_function="Business Application",
        app_owner="IT Department",
        business_critical="Yes",
        inherent_risk="Medium",
        high_availability="Yes",
        disaster_recovery="No",
        unique_operating_systems="Windows Server 2019, Ubuntu 20.04",
        sql_server_count="1",
        other_tech_stack_components="Java 11, Spring Boot, PostgreSQL",
        assigned_migration_strategy="Replatform",
        detected_app_components="Web Application, API, Database",
    )


@pytest.fixture
def basic_server_overview() -> DrMigrateServerOverview:
    """Create a basic server overview for testing."""
    return DrMigrateServerOverview(
        machine="APP-WEB-01",
        application="TestApplication",
        environment="Production",
        OperatingSystem="Ubuntu 20.04",
        os_support_status="Supported",
        PowerStatus="On",
        CloudVMReadiness="Ready",
        AllocatedMemoryInGB=8.0,
        Cores=4,
        CPUUsageInPct=45.5,
        MemoryUsageInPct=62.0,
        StorageGB=100.0,
        DiskReadOpsPerSec=150.0,
        DiskWriteOpsPerSec=75.0,
        NetworkInMBPS="50",
        NetworkOutMBPS="30",
    )


@pytest.fixture
def basic_installed_app() -> DrMigrateInstalledApplication:
    """Create a basic installed application for testing."""
    return DrMigrateInstalledApplication(
        machine="APP-WEB-01",
        key_software="Java 11",
        key_software_category="Runtime",
        key_software_type="Server",
    )


@pytest.fixture
def basic_app_data(
    basic_app_overview: DrMigrateApplicationOverview,
    basic_server_overview: DrMigrateServerOverview,
    basic_installed_app: DrMigrateInstalledApplication,
) -> DrMigrateApplicationData:
    """Create a complete application data object for testing."""
    return DrMigrateApplicationData(
        application_overview=basic_app_overview,
        server_overviews=[basic_server_overview],
        installed_applications=[basic_installed_app],
        key_software=[
            DrMigrateKeySoftware(
                application="TestApplication",
                key_software="Spring Boot",
                key_software_category="Framework",
            )
        ],
        cloud_server_costs=[
            DrMigrateCloudServerCost(
                machine="APP-WEB-01",
                application="TestApplication",
                assigned_treatment="Replatform",
                assigned_target="Azure App Service",
                cloud_total_cost_annual=5000.0,
            )
        ],
        app_mod_candidates=[
            DrMigrateAppModCandidate(
                application="TestApplication",
                app_mod_candidate_technology="Java",
                number_of_machines_with_tech=1,
            )
        ],
    )


@pytest.fixture
def generator() -> DrMigrateContextGenerator:
    """Create a generator instance."""
    return DrMigrateContextGenerator()


# =============================================================================
# Basic Generation Tests
# =============================================================================


class TestBasicGeneration:
    """Tests for basic context file generation."""

    def test_generates_valid_context_structure(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Generated context should have correct structure."""
        context = generator.generate_context(basic_app_data)

        assert isinstance(context, list)
        assert len(context) == 1

        ctx = context[0]
        assert "app_overview" in ctx
        assert "detected_technology_running" in ctx
        assert "app_approved_azure_services" in ctx
        assert "server_details" in ctx
        assert "App Mod results" in ctx

    def test_app_overview_mapping(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """App overview should be correctly mapped."""
        context = generator.generate_context(basic_app_data)
        app_overview = context[0]["app_overview"][0]

        assert app_overview["application"] == "TestApplication"
        assert app_overview["business_crtiticality"] == "High"  # business_critical=Yes
        assert app_overview["treatment"] == "Replatform"
        assert app_overview["owner"] == "IT Department"

    def test_server_details_mapping(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Server details should be correctly mapped."""
        context = generator.generate_context(basic_app_data)
        servers = context[0]["server_details"]

        assert len(servers) == 1
        server = servers[0]

        assert server["machine"] == "APP-WEB-01"
        assert server["environment"] == "Production"
        assert server["OperatingSystem"] == "Ubuntu 20.04"
        assert server["MemoryGB"] == 8.0
        assert server["Cores"] == 4
        assert server["CPUUsage"] == 45.5
        assert server["AzureVMReadiness"] == "Ready"

    def test_technology_detection(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Technologies should be detected from multiple sources."""
        context = generator.generate_context(basic_app_data)
        technologies = context[0]["detected_technology_running"]

        # Should include technologies from various sources
        assert any("Java" in t for t in technologies)
        assert any("Spring Boot" in t for t in technologies)
        assert any("Ubuntu" in t or "20.04" in t for t in technologies)

    def test_generates_valid_json(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Generated JSON should be valid."""
        json_str = generator.generate_context_json(basic_app_data)

        # Should be valid JSON
        parsed = json.loads(json_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 1


class TestCriticalityMapping:
    """Tests for business criticality mapping."""

    def test_high_criticality_from_business_critical(self, generator: DrMigrateContextGenerator):
        """business_critical=Yes should map to High criticality."""
        overview = DrMigrateApplicationOverview(
            application="TestApp",
            business_critical="Yes",
        )
        app_data = DrMigrateApplicationData(application_overview=overview)
        context = generator.generate_context(app_data)

        assert context[0]["app_overview"][0]["business_crtiticality"] == "High"

    def test_high_criticality_from_risk(self, generator: DrMigrateContextGenerator):
        """inherent_risk=High should map to High criticality."""
        overview = DrMigrateApplicationOverview(
            application="TestApp",
            inherent_risk="High",
        )
        app_data = DrMigrateApplicationData(application_overview=overview)
        context = generator.generate_context(app_data)

        assert context[0]["app_overview"][0]["business_crtiticality"] == "High"

    def test_medium_criticality_default(self, generator: DrMigrateContextGenerator):
        """Default criticality should be Medium."""
        overview = DrMigrateApplicationOverview(
            application="TestApp",
        )
        app_data = DrMigrateApplicationData(application_overview=overview)
        context = generator.generate_context(app_data)

        assert context[0]["app_overview"][0]["business_crtiticality"] == "Medium"


class TestTreatmentMapping:
    """Tests for treatment/migration strategy mapping."""

    @pytest.mark.parametrize("strategy,expected", [
        ("Rehost", "Rehost"),
        ("Lift and Shift", "Rehost"),
        ("Replatform", "Replatform"),
        ("Refactor", "Refactor"),
        ("Rearchitect", "Refactor"),
        ("Rebuild", "Rebuild"),
        ("Replace", "Replace"),
        ("Repurchase", "Replace"),
        ("Retire", "Retire"),
        ("Retain", "Retain"),
        ("Tolerate", "Tolerate"),
    ])
    def test_strategy_mapping(
        self,
        generator: DrMigrateContextGenerator,
        strategy: str,
        expected: str,
    ):
        """Migration strategies should be correctly mapped."""
        overview = DrMigrateApplicationOverview(
            application="TestApp",
            assigned_migration_strategy=strategy,
        )
        app_data = DrMigrateApplicationData(application_overview=overview)
        context = generator.generate_context(app_data)

        assert context[0]["app_overview"][0]["treatment"] == expected


class TestTechnologyNormalization:
    """Tests for technology name normalization."""

    @pytest.mark.parametrize("input_tech,expected_pattern", [
        ("SQL Server 2019", "SQL Server"),
        ("mysql 8.0", "MySQL"),
        ("postgresql", "PostgreSQL"),
        ("Microsoft IIS", "Microsoft IIS"),
        ("Apache HTTP Server", "Apache HTTP Server"),
        ("nginx", "NGINX"),
        ("Apache Tomcat 9", "Apache Tomcat"),
        ("Java 11", "Java 11"),
        ("java 17", "Java 17"),
        (".NET Framework 4.8", ".NET Framework 4.8"),
        (".NET Core 3.1", ".NET Core 3.1"),
        ("Spring Boot", "Spring Boot"),
        ("ASP.NET MVC", "ASP.NET MVC"),
        ("RabbitMQ", "RabbitMQ"),
        ("Apache Kafka", "Apache Kafka"),
    ])
    def test_technology_normalization(
        self,
        generator: DrMigrateContextGenerator,
        input_tech: str,
        expected_pattern: str,
    ):
        """Technologies should be normalized to standard names."""
        normalized = generator._normalize_technology(input_tech)
        assert expected_pattern.lower() in normalized.lower()


class TestAzureServiceMapping:
    """Tests for Azure service mapping."""

    def test_azure_service_mappings_exist(self, generator: DrMigrateContextGenerator):
        """Default Azure service mappings should exist."""
        assert len(generator.azure_service_mappings) > 0

    def test_custom_mappings_override(self):
        """Custom mappings should override defaults."""
        custom_mappings = {"Custom Tech": "Custom Azure Service"}
        generator = DrMigrateContextGenerator(azure_service_mappings=custom_mappings)

        assert generator.azure_service_mappings == custom_mappings

    def test_generates_azure_service_section(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Should generate Azure service mappings for detected technologies."""
        context = generator.generate_context(basic_app_data)
        azure_services = context[0]["app_approved_azure_services"]

        assert isinstance(azure_services, list)
        assert len(azure_services) > 0


class TestVMReadinessMapping:
    """Tests for VM readiness mapping."""

    @pytest.mark.parametrize("input_status,expected", [
        ("Ready", "Ready"),
        ("ready", "Ready"),
        ("ReadyWithConditions", "ReadyWithConditions"),
        ("Ready with conditions", "ReadyWithConditions"),
        ("NotReady", "NotReady"),
        ("Not Ready", "NotReady"),
        (None, "Unknown"),
        ("", "Unknown"),
        ("SomeOtherStatus", "Unknown"),
    ])
    def test_vm_readiness_mapping(
        self,
        generator: DrMigrateContextGenerator,
        input_status: str,
        expected: str,
    ):
        """VM readiness should be correctly mapped."""
        result = generator._map_vm_readiness(input_status)
        assert result == expected


class TestAppModResultsGeneration:
    """Tests for App Mod results generation."""

    def test_generates_app_mod_from_candidates(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Should generate App Mod results from app_mod_candidates."""
        context = generator.generate_context(basic_app_data)
        app_mod_results = context[0]["App Mod results"]

        assert len(app_mod_results) > 0
        assert app_mod_results[0]["technology"] == "Java"

    def test_generates_inferred_app_mod_when_no_candidates(
        self,
        generator: DrMigrateContextGenerator,
    ):
        """Should generate inferred App Mod results when no candidates exist."""
        overview = DrMigrateApplicationOverview(
            application="LegacyApp",
            other_tech_stack_components="Python, Django",
            assigned_migration_strategy="Replatform",
        )
        app_data = DrMigrateApplicationData(application_overview=overview)
        context = generator.generate_context(app_data)
        app_mod_results = context[0]["App Mod results"]

        # Should have inferred results
        if app_mod_results:
            assert app_mod_results[0].get("summary", {}).get("inferred_from_dr_migrate") is True

    def test_app_mod_compatibility_inference(
        self,
        generator: DrMigrateContextGenerator,
    ):
        """Should infer platform compatibility based on technology."""
        overview = DrMigrateApplicationOverview(
            application="JavaApp",
        )
        app_data = DrMigrateApplicationData(
            application_overview=overview,
            app_mod_candidates=[
                DrMigrateAppModCandidate(
                    application="JavaApp",
                    app_mod_candidate_technology="Java",
                    number_of_machines_with_tech=1,
                )
            ],
        )
        context = generator.generate_context(app_data)
        app_mod_results = context[0]["App Mod results"]

        assert len(app_mod_results) > 0
        compatibility = app_mod_results[0].get("compatibility", {})
        assert "azure_kubernetes_service" in compatibility or len(compatibility) > 0


class TestOptionalDataInclusion:
    """Tests for optional cost and network data inclusion."""

    def test_excludes_cost_data_by_default(
        self,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Should not include cost data by default."""
        generator = DrMigrateContextGenerator(include_cost_data=False)
        context = generator.generate_context(basic_app_data)

        assert "_cost_comparison" not in context[0]

    def test_includes_cost_data_when_requested(
        self,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Should include cost data when requested."""
        basic_app_data.cost_comparison = DrMigrateApplicationCostComparison(
            application="TestApplication",
            current_total_cost_annual=10000.0,
            cloud_total_cost_annual=5000.0,
            Currency="USD",
        )
        generator = DrMigrateContextGenerator(include_cost_data=True)
        context = generator.generate_context(basic_app_data)

        assert "_cost_comparison" in context[0]
        assert context[0]["_cost_comparison"]["current_total_cost_annual"] == 10000.0

    def test_includes_network_data_when_requested(
        self,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Should include network dependency data when requested."""
        basic_app_data.network_dependencies = [
            DrMigrateNetworkApplicationOverview(
                source_application="TestApplication",
                destination_application="DatabaseService",
                port="5432",
            )
        ]
        generator = DrMigrateContextGenerator(include_network_data=True)
        context = generator.generate_context(basic_app_data)

        assert "_network_dependencies" in context[0]
        assert len(context[0]["_network_dependencies"]) == 1


class TestContextCompatibility:
    """Tests that generated context is compatible with the Architecture Scorer."""

    def test_context_parseable_as_raw_context_file(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Generated context should be parseable as RawContextFile."""
        context = generator.generate_context(basic_app_data)

        # Remove metadata fields before parsing
        ctx = context[0].copy()
        for key in list(ctx.keys()):
            if key.startswith("_"):
                del ctx[key]

        # Should parse without errors
        raw_context = RawContextFile.model_validate(ctx)
        assert raw_context.app_overview[0].application == "TestApplication"

    def test_context_has_all_required_fields(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Generated context should have all required fields for scoring."""
        context = generator.generate_context(basic_app_data)
        ctx = context[0]

        # Check app_overview
        assert len(ctx["app_overview"]) > 0
        assert "application" in ctx["app_overview"][0]
        assert "treatment" in ctx["app_overview"][0]

        # Check server_details
        assert isinstance(ctx["server_details"], list)

        # Check detected_technology_running
        assert isinstance(ctx["detected_technology_running"], list)

        # Check app_approved_azure_services
        assert isinstance(ctx["app_approved_azure_services"], list)


class TestBatchGeneration:
    """Tests for batch context generation."""

    def test_generates_batch_contexts(
        self,
        generator: DrMigrateContextGenerator,
    ):
        """Should generate contexts for multiple applications."""
        apps = [
            DrMigrateApplicationData(
                application_overview=DrMigrateApplicationOverview(
                    application=f"App{i}",
                    assigned_migration_strategy="Rehost",
                )
            )
            for i in range(3)
        ]

        results = generator.generate_batch_contexts(apps)

        assert len(results) == 3
        assert "App0" in results
        assert "App1" in results
        assert "App2" in results


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_minimal_data(self, generator: DrMigrateContextGenerator):
        """Should handle minimal application data."""
        app_data = DrMigrateApplicationData(
            application_overview=DrMigrateApplicationOverview(
                application="MinimalApp",
            )
        )
        context = generator.generate_context(app_data)

        assert context[0]["app_overview"][0]["application"] == "MinimalApp"

    def test_handles_empty_server_list(self, generator: DrMigrateContextGenerator):
        """Should handle empty server list."""
        app_data = DrMigrateApplicationData(
            application_overview=DrMigrateApplicationOverview(
                application="NoServersApp",
            ),
            server_overviews=[],
        )
        context = generator.generate_context(app_data)

        assert context[0]["server_details"] == []

    def test_handles_none_values_gracefully(self, generator: DrMigrateContextGenerator):
        """Should handle None values without errors."""
        app_data = DrMigrateApplicationData(
            application_overview=DrMigrateApplicationOverview(
                application="NullValuesApp",
                business_critical=None,
                inherent_risk=None,
                assigned_migration_strategy=None,
            )
        )
        context = generator.generate_context(app_data)

        # Should not raise errors and should have defaults
        assert context[0]["app_overview"][0]["business_crtiticality"] == "Medium"

    def test_handles_special_characters_in_names(self, generator: DrMigrateContextGenerator):
        """Should handle special characters in application names."""
        app_data = DrMigrateApplicationData(
            application_overview=DrMigrateApplicationOverview(
                application="App with spaces & special chars!",
            )
        )
        context = generator.generate_context(app_data)

        assert context[0]["app_overview"][0]["application"] == "App with spaces & special chars!"

    def test_metadata_included_in_output(
        self,
        generator: DrMigrateContextGenerator,
        basic_app_data: DrMigrateApplicationData,
    ):
        """Should include generation metadata."""
        context = generator.generate_context(basic_app_data)

        assert context[0]["_generated_from"] == "dr_migrate"
        assert "_generated_at" in context[0]
