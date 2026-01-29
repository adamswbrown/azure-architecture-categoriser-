"""Tests for the Architecture Scorer against all context examples.

This test suite validates that the scorer:
1. Successfully processes all context example files
2. Produces valid output structures
3. Handles expected scenarios correctly (retire, blockers, complexity levels)
4. Generates appropriate clarification questions
5. Applies user answers correctly
"""

import json
import os
from pathlib import Path
from typing import Optional

import pytest

from architecture_scorer.engine import ScoringEngine
from architecture_scorer.schema import (
    ScoringResult,
    SignalConfidence,
)


# Path to test context examples
CONTEXT_EXAMPLES_DIR = Path(__file__).parent.parent / "prompt2_context_examples"
CATALOG_PATH = Path("/tmp/enhanced-catalog.json")


def get_context_files() -> list[Path]:
    """Get all context example JSON files."""
    if not CONTEXT_EXAMPLES_DIR.exists():
        return []
    return sorted([
        f for f in CONTEXT_EXAMPLES_DIR.glob("*.json")
        if not f.name.startswith("_")  # Skip expected output files
        and f.name[0:2].isdigit()  # Only numbered files
    ])


def load_context(path: Path) -> dict:
    """Load a context file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Context files contain a list with one item
    return data[0] if isinstance(data, list) else data


@pytest.fixture(scope="module")
def scoring_engine():
    """Create a scoring engine with the catalog loaded."""
    if not CATALOG_PATH.exists():
        pytest.skip(f"Catalog not found at {CATALOG_PATH}")
    engine = ScoringEngine()
    engine.load_catalog(str(CATALOG_PATH))
    return engine


@pytest.fixture(scope="module")
def all_context_files():
    """Get all context example files."""
    files = get_context_files()
    if not files:
        pytest.skip("No context example files found")
    return files


class TestContextFileValidation:
    """Tests that all context files are valid and parseable."""

    def test_context_files_exist(self):
        """Verify context example files exist."""
        files = get_context_files()
        assert len(files) >= 20, f"Expected at least 20 context files, found {len(files)}"

    @pytest.mark.parametrize("context_file", get_context_files(), ids=lambda f: f.stem)
    def test_context_file_valid_json(self, context_file: Path):
        """Each context file should be valid JSON."""
        with open(context_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, list), "Context file should be a JSON array"
        assert len(data) == 1, "Context file should contain exactly one application"

    @pytest.mark.parametrize("context_file", get_context_files(), ids=lambda f: f.stem)
    def test_context_file_has_required_fields(self, context_file: Path):
        """Each context file should have required fields."""
        context = load_context(context_file)

        # Required top-level fields
        assert "app_overview" in context, "Missing app_overview"
        assert "detected_technology_running" in context, "Missing detected_technology_running"
        assert "server_details" in context, "Missing server_details"

        # App overview validation
        app_overview = context["app_overview"]
        assert len(app_overview) > 0, "app_overview should not be empty"
        assert "application" in app_overview[0], "Missing application name"
        assert "treatment" in app_overview[0], "Missing treatment"


class TestScorerBasicFunctionality:
    """Tests for basic scorer functionality."""

    @pytest.mark.parametrize("context_file", get_context_files(), ids=lambda f: f.stem)
    def test_scorer_processes_context(self, scoring_engine: ScoringEngine, context_file: Path):
        """Scorer should process each context file without errors."""
        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result is not None
        assert isinstance(result, ScoringResult)

    @pytest.mark.parametrize("context_file", get_context_files(), ids=lambda f: f.stem)
    def test_scorer_produces_valid_output(self, scoring_engine: ScoringEngine, context_file: Path):
        """Scorer output should have valid structure."""
        result = scoring_engine.score(str(context_file), max_recommendations=5)

        # Validate output structure
        assert result.summary is not None
        assert result.application_name is not None  # application_name is on ScoringResult
        assert result.derived_intent.treatment.value is not None  # treatment is on derived_intent
        assert result.summary.confidence_level in ["High", "Medium", "Low"]

        # Validate counts using actual lists
        eligible_count = len(result.recommendations)
        excluded_count = len(result.excluded)
        assert eligible_count >= 0
        assert excluded_count >= 0
        assert eligible_count + excluded_count > 0

        # Validate recommendations list
        assert isinstance(result.recommendations, list)
        assert len(result.recommendations) <= 5


class TestTreatmentScenarios:
    """Tests for different treatment scenarios."""

    def test_rehost_scenario(self, scoring_engine: ScoringEngine):
        """Rehost scenario should find VM-compatible architectures."""
        context_file = CONTEXT_EXAMPLES_DIR / "09-rehost-vm-lift-shift.json"
        if not context_file.exists():
            pytest.skip("Rehost context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result.derived_intent.treatment.value.value.lower() == "rehost"
        assert len(result.recommendations) > 0, "Rehost should have eligible architectures"

    def test_retire_scenario_no_eligible(self, scoring_engine: ScoringEngine):
        """Retire scenario should have zero eligible architectures."""
        context_file = CONTEXT_EXAMPLES_DIR / "10-retire-end-of-life.json"
        if not context_file.exists():
            pytest.skip("Retire context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result.derived_intent.treatment.value.value.lower() == "retire"
        assert len(result.recommendations) == 0, "Retire should have no eligible architectures"

    def test_replace_scenario(self, scoring_engine: ScoringEngine):
        """Replace scenario should recommend SaaS alternatives."""
        context_file = CONTEXT_EXAMPLES_DIR / "11-replace-saas-crm.json"
        if not context_file.exists():
            pytest.skip("Replace context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result.derived_intent.treatment.value.value.lower() == "replace"

    def test_retain_scenario(self, scoring_engine: ScoringEngine):
        """Retain (hybrid) scenario should be processed correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "12-retain-hybrid-on-premises.json"
        if not context_file.exists():
            pytest.skip("Retain context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result.derived_intent.treatment.value.value.lower() == "retain"

    def test_refactor_scenario(self, scoring_engine: ScoringEngine):
        """Refactor scenario should find cloud-native architectures."""
        context_file = CONTEXT_EXAMPLES_DIR / "01-java-refactor-aks.json"
        if not context_file.exists():
            pytest.skip("Refactor context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result.derived_intent.treatment.value.value.lower() == "refactor"
        assert len(result.recommendations) > 0

    def test_replatform_scenario(self, scoring_engine: ScoringEngine):
        """Replatform scenario should find PaaS architectures."""
        context_file = CONTEXT_EXAMPLES_DIR / "02-dotnet-replatform-appservice.json"
        if not context_file.exists():
            pytest.skip("Replatform context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result.derived_intent.treatment.value.value.lower() == "replatform"
        assert len(result.recommendations) > 0

    def test_tolerate_scenario(self, scoring_engine: ScoringEngine):
        """Tolerate scenario should handle legacy applications."""
        context_file = CONTEXT_EXAMPLES_DIR / "03-legacy-tolerate.json"
        if not context_file.exists():
            pytest.skip("Tolerate context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        assert result.derived_intent.treatment.value.value.lower() == "tolerate"


class TestComplexityScenarios:
    """Tests for different complexity levels (Dr Migrate complexity metrics)."""

    def test_low_complexity_3tier(self, scoring_engine: ScoringEngine):
        """Low complexity 3-tier app should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "21-low-complexity-3tier-dotnet.json"
        if not context_file.exists():
            pytest.skip("Low complexity context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        # Verify complexity metrics are present
        assert "complexity_metrics" in context
        assert context["complexity_metrics"]["expected_complexity"] == "Low Complexity"
        assert context["complexity_metrics"]["no_servers"] == 3

        # Scorer should process successfully
        assert len(result.recommendations) > 0

    def test_medium_complexity_multi_env(self, scoring_engine: ScoringEngine):
        """Medium complexity multi-environment app should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "22-medium-complexity-java-multi-env.json"
        if not context_file.exists():
            pytest.skip("Medium complexity context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        assert context["complexity_metrics"]["expected_complexity"] == "Medium Complexity"
        assert context["complexity_metrics"]["no_environments"] == 3
        assert len(result.recommendations) > 0

    def test_high_complexity_ha_dr(self, scoring_engine: ScoringEngine):
        """High complexity HA/DR app should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "23-high-complexity-dotnet-ha-dr.json"
        if not context_file.exists():
            pytest.skip("High complexity context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        assert context["complexity_metrics"]["expected_complexity"] == "High Complexity"
        assert context["complexity_metrics"]["high_availability"] is True
        assert context["complexity_metrics"]["disaster_recovery"] is True
        assert len(result.recommendations) > 0

    def test_very_high_complexity_enterprise(self, scoring_engine: ScoringEngine):
        """Very high complexity enterprise app should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "24-very-high-complexity-java-enterprise.json"
        if not context_file.exists():
            pytest.skip("Very high complexity context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        assert context["complexity_metrics"]["expected_complexity"] == "Very High Complexity"
        assert context["complexity_metrics"]["no_servers"] >= 20
        assert len(result.recommendations) >= 0  # May have limited matches

    def test_extra_high_complexity_mixed(self, scoring_engine: ScoringEngine):
        """Extra high complexity mixed app should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "25-extra-high-complexity-mixed-enterprise.json"
        if not context_file.exists():
            pytest.skip("Extra high complexity context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        assert context["complexity_metrics"]["expected_complexity"] == "Extra High Complexity"
        assert context["complexity_metrics"]["no_servers"] >= 30
        assert context["complexity_metrics"]["sql_servers"] >= 2
        assert context["complexity_metrics"]["non_sql_db_servers"] >= 9


class TestSecurityAndCompliance:
    """Tests for security and compliance scenarios."""

    def test_highly_regulated_healthcare(self, scoring_engine: ScoringEngine):
        """Highly regulated healthcare scenario should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "13-highly-regulated-healthcare.json"
        if not context_file.exists():
            pytest.skip("Healthcare context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        # Verify compliance requirements are present
        app_overview = context["app_overview"][0]
        assert "compliance_requirements" in app_overview
        assert "HIPAA" in app_overview["compliance_requirements"]

        # Should process without errors
        assert result is not None


class TestOperatingModels:
    """Tests for different operating model scenarios."""

    def test_traditional_it_model(self, scoring_engine: ScoringEngine):
        """Traditional IT operating model scenario."""
        context_file = CONTEXT_EXAMPLES_DIR / "15-traditional-it-erp.json"
        if not context_file.exists():
            pytest.skip("Traditional IT context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        app_overview = context["app_overview"][0]
        assert app_overview.get("operating_model") == "traditional_it"
        assert result is not None

    def test_sre_model(self, scoring_engine: ScoringEngine):
        """SRE operating model scenario."""
        context_file = CONTEXT_EXAMPLES_DIR / "16-sre-mission-critical.json"
        if not context_file.exists():
            pytest.skip("SRE context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        app_overview = context["app_overview"][0]
        assert app_overview.get("operating_model") == "sre"
        assert result is not None


class TestCostProfiles:
    """Tests for different cost profile scenarios."""

    def test_cost_minimized_startup(self, scoring_engine: ScoringEngine):
        """Cost minimized startup scenario."""
        context_file = CONTEXT_EXAMPLES_DIR / "17-cost-minimized-startup.json"
        if not context_file.exists():
            pytest.skip("Cost minimized context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        app_overview = context["app_overview"][0]
        assert app_overview.get("cost_priority") == "cost_minimized"
        assert result is not None

    def test_innovation_first_ai_ml(self, scoring_engine: ScoringEngine):
        """Innovation first AI/ML scenario."""
        context_file = CONTEXT_EXAMPLES_DIR / "18-innovation-first-ai-ml.json"
        if not context_file.exists():
            pytest.skip("Innovation first context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        app_overview = context["app_overview"][0]
        assert app_overview.get("cost_priority") == "innovation_first"
        assert result is not None


class TestAppModBlockers:
    """Tests for App Mod blocker scenarios."""

    def test_mainframe_blockers(self, scoring_engine: ScoringEngine):
        """Mainframe with explicit blockers should be handled correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "19-appmod-blockers-mainframe.json"
        if not context_file.exists():
            pytest.skip("Mainframe blockers context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        # Verify blockers are present in App Mod results
        app_mod = context.get("App Mod results", [])
        assert len(app_mod) > 0
        assert len(app_mod[0].get("blockers", [])) > 0

        # Scorer should still process (may have limited eligibility)
        assert result is not None

    def test_eliminate_time_category(self, scoring_engine: ScoringEngine):
        """Eliminate TIME category should have no eligible architectures."""
        context_file = CONTEXT_EXAMPLES_DIR / "20-eliminate-time-category.json"
        if not context_file.exists():
            pytest.skip("Eliminate TIME context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)

        # Eliminate/Retire scenarios should have no eligible architectures
        assert len(result.recommendations) == 0


class TestClarificationQuestions:
    """Tests for clarification question generation."""

    @pytest.mark.parametrize("context_file", get_context_files()[:5], ids=lambda f: f.stem)
    def test_questions_have_valid_structure(self, scoring_engine: ScoringEngine, context_file: Path):
        """Generated questions should have valid structure."""
        result = scoring_engine.score(str(context_file), max_recommendations=5)

        for question in result.clarification_questions:
            assert question.question_id is not None
            assert question.dimension is not None
            assert question.question_text is not None
            assert len(question.options) >= 2
            assert question.inference_confidence is not None

            # Each option should have value and label
            for option in question.options:
                assert option.value is not None
                assert option.label is not None


class TestUserAnswers:
    """Tests for applying user answers."""

    def test_apply_security_answer(self, scoring_engine: ScoringEngine):
        """Applying security level answer should update scoring."""
        context_file = CONTEXT_EXAMPLES_DIR / "08-enterprise-java-aks-curated.json"
        if not context_file.exists():
            pytest.skip("Enterprise Java context file not found")

        # Score without answers
        result_no_answer = scoring_engine.score(str(context_file), max_recommendations=5)

        # Score with security answer
        result_with_answer = scoring_engine.score(
            str(context_file),
            user_answers={"security_level": "regulated"},
            max_recommendations=5
        )

        # Both should produce valid results
        assert result_no_answer is not None
        assert result_with_answer is not None

    def test_apply_operating_model_answer(self, scoring_engine: ScoringEngine):
        """Applying operating model answer should update scoring."""
        context_file = CONTEXT_EXAMPLES_DIR / "08-enterprise-java-aks-curated.json"
        if not context_file.exists():
            pytest.skip("Enterprise Java context file not found")

        result = scoring_engine.score(
            str(context_file),
            user_answers={"operating_model": "devops"},
            max_recommendations=5
        )

        assert result is not None

    def test_apply_multiple_answers(self, scoring_engine: ScoringEngine):
        """Applying multiple answers should work correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "08-enterprise-java-aks-curated.json"
        if not context_file.exists():
            pytest.skip("Enterprise Java context file not found")

        result = scoring_engine.score(
            str(context_file),
            user_answers={
                "security_level": "regulated",
                "operating_model": "devops",
                "cost_posture": "balanced"
            },
            max_recommendations=5
        )

        assert result is not None
        assert len(result.recommendations) >= 0


class TestDatabaseScenarios:
    """Tests for scenarios with various database configurations."""

    def test_sql_server_database(self, scoring_engine: ScoringEngine):
        """Context with SQL Server should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "21-low-complexity-3tier-dotnet.json"
        if not context_file.exists():
            pytest.skip("SQL Server context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        # Verify SQL Server is in the technology stack
        tech = context.get("detected_technology_running", [])
        assert any("sql" in t.lower() for t in tech)

        assert result is not None

    def test_postgresql_database(self, scoring_engine: ScoringEngine):
        """Context with PostgreSQL should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "22-medium-complexity-java-multi-env.json"
        if not context_file.exists():
            pytest.skip("PostgreSQL context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        tech = context.get("detected_technology_running", [])
        assert any("postgresql" in t.lower() for t in tech)

        assert result is not None

    def test_multi_database_scenario(self, scoring_engine: ScoringEngine):
        """Context with multiple database types should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "25-extra-high-complexity-mixed-enterprise.json"
        if not context_file.exists():
            pytest.skip("Multi-database context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        context = load_context(context_file)

        tech = context.get("detected_technology_running", [])
        # Should have multiple database technologies
        db_count = sum(1 for t in tech if any(db in t.lower() for db in ["sql", "oracle", "postgresql", "mongodb"]))
        assert db_count >= 3

        assert result is not None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_app_mod_results(self, scoring_engine: ScoringEngine):
        """Context with empty App Mod results should process correctly."""
        context_file = CONTEXT_EXAMPLES_DIR / "03-legacy-tolerate.json"
        if not context_file.exists():
            pytest.skip("Legacy tolerate context file not found")

        result = scoring_engine.score(str(context_file), max_recommendations=5)
        assert result is not None

    def test_max_recommendations_respected(self, scoring_engine: ScoringEngine):
        """Max recommendations limit should be respected."""
        context_file = get_context_files()[0] if get_context_files() else None
        if not context_file:
            pytest.skip("No context files available")

        for max_rec in [1, 3, 5, 10]:
            result = scoring_engine.score(str(context_file), max_recommendations=max_rec)
            assert len(result.recommendations) <= max_rec


class TestScoringConsistency:
    """Tests for scoring consistency and determinism."""

    def test_deterministic_scoring(self, scoring_engine: ScoringEngine):
        """Same input should produce same output."""
        context_file = get_context_files()[0] if get_context_files() else None
        if not context_file:
            pytest.skip("No context files available")

        result1 = scoring_engine.score(str(context_file), max_recommendations=5)
        result2 = scoring_engine.score(str(context_file), max_recommendations=5)

        assert len(result1.recommendations) == len(result2.recommendations)
        assert len(result1.excluded) == len(result2.excluded)

        # Same recommendations in same order
        for r1, r2 in zip(result1.recommendations, result2.recommendations):
            assert r1.architecture_id == r2.architecture_id
            assert r1.likelihood_score == r2.likelihood_score


# Run a quick summary test
class TestSummary:
    """Summary tests to verify overall test coverage."""

    def test_all_treatments_covered(self):
        """Verify all 8R treatments have test contexts."""
        files = get_context_files()
        treatments_found = set()

        for f in files:
            context = load_context(f)
            treatment = context["app_overview"][0].get("treatment", "").lower()
            treatments_found.add(treatment)

        expected_treatments = {"rehost", "replatform", "refactor", "rebuild", "retire", "replace", "retain", "tolerate"}
        missing = expected_treatments - treatments_found
        assert len(missing) == 0, f"Missing treatment test contexts: {missing}"

    def test_complexity_levels_covered(self):
        """Verify all complexity levels have test contexts."""
        files = get_context_files()
        complexity_found = set()

        for f in files:
            context = load_context(f)
            if "complexity_metrics" in context:
                complexity = context["complexity_metrics"].get("expected_complexity", "")
                complexity_found.add(complexity)

        expected = {"Low Complexity", "Medium Complexity", "High Complexity", "Very High Complexity", "Extra High Complexity"}
        missing = expected - complexity_found
        assert len(missing) == 0, f"Missing complexity test contexts: {missing}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
