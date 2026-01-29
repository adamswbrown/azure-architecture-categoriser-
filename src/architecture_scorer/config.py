"""Centralized configuration management for the architecture scorer."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field


class ScoringWeightsConfig(BaseModel):
    """Weights for different scoring dimensions.

    These weights control how much each factor contributes to the final
    match score. They should sum to approximately 1.0.
    """
    treatment_alignment: float = Field(
        0.20,
        description="Weight for migration treatment alignment (rehost, replatform, etc.)"
    )
    runtime_model_compatibility: float = Field(
        0.10,
        description="Weight for runtime model match (containers, VMs, serverless)"
    )
    platform_compatibility: float = Field(
        0.15,
        description="Weight for platform/technology compatibility"
    )
    app_mod_recommended: float = Field(
        0.10,
        description="Boost weight when App Mod recommends the target platform"
    )
    service_overlap: float = Field(
        0.10,
        description="Weight for overlap between required and architecture services"
    )
    browse_tag_overlap: float = Field(
        0.05,
        description="Weight for matching browse/topic tags"
    )
    availability_alignment: float = Field(
        0.10,
        description="Weight for availability/SLA requirements match"
    )
    operating_model_fit: float = Field(
        0.08,
        description="Weight for operational maturity alignment"
    )
    complexity_tolerance: float = Field(
        0.07,
        description="Weight for complexity vs. team capability match"
    )
    cost_posture_alignment: float = Field(
        0.05,
        description="Weight for cost optimization strategy alignment"
    )


class QualityWeightsConfig(BaseModel):
    """Weights for catalog quality levels.

    Higher quality entries get higher weights, boosting their scores.
    """
    curated: float = Field(1.0, description="Weight for curated (human-reviewed) architectures")
    ai_enriched: float = Field(0.95, description="Weight for AI-enriched architectures")
    ai_suggested: float = Field(0.90, description="Weight for AI-suggested architectures")
    example_only: float = Field(0.85, description="Weight for example-only architectures")


class ConfidenceThresholdsConfig(BaseModel):
    """Thresholds for confidence level determination.

    These thresholds determine when a recommendation is classified as
    High, Medium, or Low confidence.
    """
    high_score_threshold: float = Field(
        60.0,
        description="Minimum match score for High confidence (0-100)"
    )
    medium_score_threshold: float = Field(
        40.0,
        description="Minimum match score for Medium confidence (0-100)"
    )
    high_penalty_limit: float = Field(
        0.10,
        description="Maximum confidence penalty for High confidence"
    )
    medium_penalty_limit: float = Field(
        0.20,
        description="Maximum confidence penalty for Medium confidence"
    )
    high_max_low_signals: int = Field(
        1,
        description="Maximum low-confidence signals for High confidence"
    )
    medium_max_low_signals: int = Field(
        3,
        description="Maximum low-confidence signals for Medium confidence"
    )
    high_max_assumptions: int = Field(
        2,
        description="Maximum assumptions for High confidence"
    )


class QuestionGenerationConfig(BaseModel):
    """Configuration for clarification question generation."""
    question_threshold: str = Field(
        "low",
        description="Generate questions for signals at or below this confidence (low, medium, high)"
    )
    max_questions: int = Field(
        5,
        description="Maximum number of clarification questions to generate"
    )


class ScorerConfig(BaseModel):
    """Complete configuration for the architecture scorer."""
    scoring_weights: ScoringWeightsConfig = Field(default_factory=ScoringWeightsConfig)
    quality_weights: QualityWeightsConfig = Field(default_factory=QualityWeightsConfig)
    confidence_thresholds: ConfidenceThresholdsConfig = Field(default_factory=ConfidenceThresholdsConfig)
    question_generation: QuestionGenerationConfig = Field(default_factory=QuestionGenerationConfig)


# Global config instance
_config: Optional[ScorerConfig] = None


def get_config() -> ScorerConfig:
    """Get the current configuration.

    Returns the global config, initializing with defaults if not yet loaded.
    """
    global _config
    if _config is None:
        _config = ScorerConfig()
    return _config


def load_config(path: Path) -> ScorerConfig:
    """Load configuration from a YAML file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        The loaded ScorerConfig.
    """
    global _config

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    _config = ScorerConfig.model_validate(data or {})
    return _config


def reset_config() -> None:
    """Reset configuration to defaults."""
    global _config
    _config = ScorerConfig()


def find_config_file() -> Optional[Path]:
    """Find a scorer configuration file.

    Looks in (order of priority):
    1. ARCHITECTURE_SCORER_CONFIG environment variable
    2. ./scorer-config.yaml
    3. ./scorer-config.yml
    4. ~/.config/architecture-scorer/config.yaml
    """
    # Environment variable
    env_path = os.environ.get("ARCHITECTURE_SCORER_CONFIG")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path

    # Current directory
    for name in ["scorer-config.yaml", "scorer-config.yml"]:
        path = Path(name)
        if path.exists():
            return path

    # User config directory
    user_config = Path.home() / ".config" / "architecture-scorer" / "config.yaml"
    if user_config.exists():
        return user_config

    return None


def save_default_config(path: Path) -> None:
    """Save the default configuration to a YAML file.

    Args:
        path: Path where to save the configuration.
    """
    config = ScorerConfig()

    # Convert to dict and add comments
    data = config.model_dump()

    # Add header comment
    yaml_content = """# Architecture Scorer Configuration
# ================================
#
# This file configures the scoring algorithm, confidence thresholds,
# and question generation behavior.
#
# Copy this file to one of these locations:
#   - ./scorer-config.yaml (current directory)
#   - ~/.config/architecture-scorer/config.yaml (user config)
#
# Or set the ARCHITECTURE_SCORER_CONFIG environment variable.

"""
    yaml_content += yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(yaml_content)
