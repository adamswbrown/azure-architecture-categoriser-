"""Pydantic models for the Architecture Scoring Engine.

Input schemas for application context and output schemas for recommendations.
These schemas match the actual format from AppCatContextFileCreator.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

# Re-export catalog enums for convenience
from catalog_builder.schema import (
    ArchitectureFamily,
    AvailabilityModel,
    CatalogQuality,
    ComplexityLevel,
    CostProfile,
    ExclusionReason,
    OperatingModel,
    RuntimeModel,
    SecurityLevel,
    TimeCategory,
    Treatment,
)


# =============================================================================
# Confidence and Signal Enums
# =============================================================================


class SignalConfidence(str, Enum):
    """Confidence level for derived signals."""
    HIGH = "high"  # Explicit from App Mod or user input
    MEDIUM = "medium"  # Inferred with strong evidence
    LOW = "low"  # Inferred with weak evidence
    UNKNOWN = "unknown"  # Cannot be determined


class CompatibilityStatus(str, Enum):
    """App Mod compatibility status for a target platform."""
    FULLY_SUPPORTED = "FullySupported"
    SUPPORTED = "Supported"
    SUPPORTED_WITH_CHANGES = "SupportedWithChanges"
    SUPPORTED_WITH_REFACTOR = "SupportedWithRefactor"
    NOT_SUPPORTED = "NotSupported"
    UNKNOWN = "Unknown"

    @classmethod
    def from_string(cls, value: str) -> "CompatibilityStatus":
        """Parse compatibility status from string."""
        mapping = {
            "fullysupported": cls.FULLY_SUPPORTED,
            "supported": cls.SUPPORTED,
            "supportedwithchanges": cls.SUPPORTED_WITH_CHANGES,
            "supportedwithrefactor": cls.SUPPORTED_WITH_REFACTOR,
            "notsupported": cls.NOT_SUPPORTED,
        }
        return mapping.get(value.lower().replace("_", ""), cls.UNKNOWN)

    def is_supported(self) -> bool:
        """Check if this status indicates the platform is supported."""
        return self in (
            self.FULLY_SUPPORTED,
            self.SUPPORTED,
            self.SUPPORTED_WITH_CHANGES,
            self.SUPPORTED_WITH_REFACTOR,
        )


class ModernizationDepth(str, Enum):
    """Maximum feasible modernization depth."""
    TOLERATE = "tolerate"
    REHOST = "rehost"
    REPLATFORM = "replatform"
    REFACTOR = "refactor"
    REBUILD = "rebuild"


class CloudNativeFeasibility(str, Enum):
    """Cloud-native transformation feasibility."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class BusinessCriticality(str, Enum):
    """Business criticality level."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    MISSION_CRITICAL = "MissionCritical"

    @classmethod
    def from_string(cls, value: str) -> "BusinessCriticality":
        """Parse criticality from string (handles typos)."""
        if not value:
            return cls.MEDIUM
        mapping = {
            "low": cls.LOW,
            "medium": cls.MEDIUM,
            "high": cls.HIGH,
            "missioncritical": cls.MISSION_CRITICAL,
            "mission-critical": cls.MISSION_CRITICAL,
            "critical": cls.MISSION_CRITICAL,
        }
        return mapping.get(value.lower().replace("_", "").replace(" ", ""), cls.MEDIUM)


class VMReadiness(str, Enum):
    """Azure VM readiness status."""
    READY = "Ready"
    READY_WITH_CONDITIONS = "ReadyWithConditions"
    NOT_READY = "NotReady"
    UNKNOWN = "Unknown"

    @classmethod
    def from_string(cls, value: str) -> "VMReadiness":
        """Parse readiness from string."""
        if not value:
            return cls.UNKNOWN
        mapping = {
            "ready": cls.READY,
            "readywithconditions": cls.READY_WITH_CONDITIONS,
            "notready": cls.NOT_READY,
        }
        return mapping.get(value.lower().replace("_", "").replace(" ", ""), cls.UNKNOWN)


class UtilizationProfile(str, Enum):
    """Server utilization profile."""
    LOW = "low"  # < 30% average
    MEDIUM = "medium"  # 30-70% average
    HIGH = "high"  # > 70% average


class DependencyComplexity(str, Enum):
    """Dependency complexity level."""
    SIMPLE = "simple"  # Few, well-defined dependencies
    MODERATE = "moderate"  # Multiple dependencies, manageable
    COMPLEX = "complex"  # Many interdependencies
    UNKNOWN = "unknown"


class NetworkExposure(str, Enum):
    """Application network exposure type."""
    EXTERNAL = "external"  # Internet-facing, public access
    INTERNAL = "internal"  # Internal only, corporate network
    MIXED = "mixed"  # Both internal and external components


# =============================================================================
# Raw Input Models (matching AppCatContextFileCreator format)
# =============================================================================


class RawAppOverview(BaseModel):
    """Raw app overview from context file."""
    application: str
    app_type: Optional[str] = None
    business_crtiticality: Optional[str] = None  # Note: typo in original
    treatment: Optional[str] = None
    description: Optional[str] = None
    owner: Optional[str] = None

    class Config:
        extra = "allow"


class RawServerDetail(BaseModel):
    """Raw server detail from context file."""
    machine: str
    environment: Optional[str] = None
    OperatingSystem: Optional[str] = None
    ip_address: list[str] = Field(default_factory=list)
    StorageGB: Optional[int] = None
    MemoryGB: Optional[float] = None
    Cores: Optional[int] = None
    CPUUsage: Optional[float] = None
    MemoryUsage: Optional[float] = None
    DiskReadOpsPersec: Optional[float] = None
    DiskWriteOpsPerSec: Optional[float] = None
    NetworkInMBPS: Optional[float] = None
    NetworkOutMBPS: Optional[float] = None
    StandardSSDDisks: Optional[int] = None
    StandardHDDDisks: Optional[int] = None
    PremiumDisks: Optional[int] = None
    AzureVMReadiness: Optional[str] = None
    AzureReadinessIssues: Optional[str] = None
    migration_strategy: Optional[str] = None
    detected_COTS: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class RawAppModFinding(BaseModel):
    """Raw App Mod finding."""
    type: str
    severity: str
    description: str

    class Config:
        extra = "allow"


class RawAppModSummary(BaseModel):
    """Raw App Mod summary - flexible to handle different formats."""
    projects: Optional[int] = None
    services_scanned: Optional[int] = None
    spring_boot_apps: Optional[int] = None
    container_ready: Optional[bool] = None
    modernization_feasible: Optional[bool] = None

    class Config:
        extra = "allow"


class RawAppModResult(BaseModel):
    """Raw App Mod result from context file."""
    technology: str
    summary: RawAppModSummary = Field(default_factory=RawAppModSummary)
    findings: list[RawAppModFinding] = Field(default_factory=list)
    compatibility: dict[str, str] = Field(default_factory=dict)
    recommended_targets: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)

    class Config:
        extra = "allow"


class RawContextFile(BaseModel):
    """Raw context file as produced by AppCatContextFileCreator.

    Note: The actual file is a JSON array with one object.
    """
    app_overview: list[RawAppOverview]
    detected_technology_running: list[str] = Field(default_factory=list)
    app_approved_azure_services: list[dict[str, str]] = Field(default_factory=list)
    server_details: list[RawServerDetail] = Field(default_factory=list)
    # Note: key has a space in the original
    app_mod_results: list[RawAppModResult] = Field(
        default_factory=list,
        alias="App Mod results"
    )

    class Config:
        populate_by_name = True
        extra = "allow"


# =============================================================================
# Normalized Application Context Models
# =============================================================================


class AppOverview(BaseModel):
    """Normalized application overview."""
    application_name: str
    application_id: Optional[str] = None
    app_type: Optional[str] = None
    business_criticality: BusinessCriticality = BusinessCriticality.MEDIUM
    declared_treatment: Optional[Treatment] = None
    declared_time_category: Optional[TimeCategory] = None
    description: Optional[str] = None
    owner: Optional[str] = None

    # Optional explicit requirements (from user answers)
    availability_requirement: Optional[AvailabilityModel] = None
    compliance_requirements: list[str] = Field(default_factory=list)


class ServerSummary(BaseModel):
    """Aggregated server details."""
    server_count: int = 0
    servers: list[RawServerDetail] = Field(default_factory=list)

    # Derived aggregates
    environments_present: list[str] = Field(default_factory=list)
    os_mix: dict[str, int] = Field(default_factory=dict)
    vm_readiness_distribution: dict[str, int] = Field(default_factory=dict)
    utilization_profile: UtilizationProfile = UtilizationProfile.MEDIUM
    avg_cpu_usage: Optional[float] = None
    avg_memory_usage: Optional[float] = None
    total_cores: int = 0
    total_memory_gb: float = 0.0

    # Dependency info
    dependency_complexity: DependencyComplexity = DependencyComplexity.UNKNOWN


class DetectedTechnology(BaseModel):
    """Normalized detected technology stack."""
    technologies: list[str] = Field(default_factory=list)
    primary_runtime: Optional[str] = None
    runtime_version: Optional[str] = None
    frameworks: list[str] = Field(default_factory=list)

    # Derived flags
    database_present: bool = False
    database_types: list[str] = Field(default_factory=list)
    middleware_present: bool = False
    middleware_types: list[str] = Field(default_factory=list)
    messaging_present: bool = False
    messaging_types: list[str] = Field(default_factory=list)

    # Capability flags
    containerized: bool = False
    uses_modern_auth: bool = False
    has_ci_cd: bool = False

    # OS inference
    is_windows: bool = False
    is_linux: bool = False


class PlatformCompatibility(BaseModel):
    """Normalized platform compatibility from App Mod."""
    platform: str
    status: CompatibilityStatus
    blockers: list[str] = Field(default_factory=list)
    required_changes: list[str] = Field(default_factory=list)


class AppModResults(BaseModel):
    """Normalized App Modernization results.

    This is the AUTHORITATIVE source for platform compatibility.
    When App Mod conflicts with VM or tech inference, App Mod WINS.
    """
    technology: str = "Unknown"
    container_ready: Optional[bool] = None
    modernization_feasible: Optional[bool] = None

    # Platform compatibility (normalized)
    platform_compatibility: list[PlatformCompatibility] = Field(default_factory=list)

    # Recommended targets (authoritative)
    recommended_targets: list[str] = Field(default_factory=list)

    # Findings and blockers
    findings: list[RawAppModFinding] = Field(default_factory=list)
    explicit_blockers: list[str] = Field(default_factory=list)

    # High severity issues
    critical_findings: list[str] = Field(default_factory=list)
    high_severity_findings: list[str] = Field(default_factory=list)

    def is_platform_supported(self, platform: str) -> tuple[bool, CompatibilityStatus]:
        """Check if a platform is supported by App Mod results."""
        platform_lower = platform.lower().replace(" ", "_").replace("-", "_")
        for pc in self.platform_compatibility:
            pc_normalized = pc.platform.lower().replace(" ", "_").replace("-", "_")
            if pc_normalized == platform_lower:
                return pc.status.is_supported(), pc.status
        return True, CompatibilityStatus.UNKNOWN  # Unknown means we don't block


class ApprovedServices(BaseModel):
    """Approved Azure service mappings."""
    mappings: dict[str, str] = Field(default_factory=dict)

    def get_approved_service(self, source_tech: str) -> Optional[str]:
        """Get the approved Azure service for a source technology."""
        return self.mappings.get(source_tech)

    def get_all_approved_services(self) -> list[str]:
        """Get all approved Azure services."""
        return list(set(self.mappings.values()))


class ApplicationContext(BaseModel):
    """Normalized application context for scoring.

    This is the primary input to the scoring engine after normalization.
    """
    app_overview: AppOverview
    server_summary: ServerSummary = Field(default_factory=ServerSummary)
    detected_technology: DetectedTechnology = Field(default_factory=DetectedTechnology)
    app_mod_results: Optional[AppModResults] = None
    approved_services: ApprovedServices = Field(default_factory=ApprovedServices)

    # User-provided clarifications
    user_answers: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw: RawContextFile) -> "ApplicationContext":
        """Create normalized context from raw context file."""
        from .normalizer import ContextNormalizer
        normalizer = ContextNormalizer()
        return normalizer.normalize(raw)


# =============================================================================
# Derived Intent Models
# =============================================================================


class DerivedSignal(BaseModel):
    """A signal derived from application context."""
    value: Any
    confidence: SignalConfidence
    source: str  # Where this was derived from
    reasoning: Optional[str] = None


class DerivedIntent(BaseModel):
    """Architectural intent derived from application context."""
    likely_runtime_model: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=RuntimeModel.UNKNOWN,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    modernization_depth_feasible: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=ModernizationDepth.REHOST,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    cloud_native_feasibility: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=CloudNativeFeasibility.LOW,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    operational_maturity_estimate: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=OperatingModel.TRADITIONAL_IT,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    availability_requirement: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=AvailabilityModel.SINGLE_REGION,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    security_requirement: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=SecurityLevel.BASIC,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    cost_posture: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=CostProfile.BALANCED,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    treatment: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=Treatment.REHOST,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    time_category: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=TimeCategory.MIGRATE,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )
    network_exposure: DerivedSignal = Field(
        default_factory=lambda: DerivedSignal(
            value=NetworkExposure.INTERNAL,
            confidence=SignalConfidence.UNKNOWN,
            source="default"
        )
    )


# =============================================================================
# Clarification Question Models
# =============================================================================


class ClarificationOption(BaseModel):
    """An option for a clarification question."""
    value: str
    label: str
    description: Optional[str] = None


class ClarificationQuestion(BaseModel):
    """A question to clarify missing intent."""
    question_id: str
    dimension: str  # Which intent dimension this clarifies
    question_text: str
    options: list[ClarificationOption]
    required: bool = False
    affects_eligibility: bool = True  # If true, answer materially affects results
    current_inference: Optional[str] = None
    inference_confidence: Optional[SignalConfidence] = None


# =============================================================================
# Scoring and Output Models
# =============================================================================


class ScoringDimension(BaseModel):
    """A single scoring dimension."""
    dimension: str
    weight: float
    raw_score: float  # 0-100 before weighting
    weighted_score: float
    reasoning: str
    is_hard_gate: bool = False
    passed_gate: bool = True


class MatchedDimension(BaseModel):
    """A dimension where the architecture matched."""
    dimension: str
    value: str
    reasoning: str


class MismatchedDimension(BaseModel):
    """A dimension where the architecture didn't match well."""
    dimension: str
    expected: str
    actual: str
    impact: str  # How this affects the recommendation


class AssumptionMade(BaseModel):
    """An assumption made during scoring."""
    dimension: str
    assumption: str
    confidence: SignalConfidence
    impact: str  # How this affects confidence


class ArchitectureRecommendation(BaseModel):
    """A recommended architecture with full explanation."""
    architecture_id: str
    name: str
    pattern_name: str
    description: str
    likelihood_score: float = Field(..., ge=0, le=100)
    catalog_quality: CatalogQuality

    # Detailed scoring breakdown
    scoring_dimensions: list[ScoringDimension] = Field(default_factory=list)

    # Explanation
    matched_dimensions: list[MatchedDimension] = Field(default_factory=list)
    mismatched_dimensions: list[MismatchedDimension] = Field(default_factory=list)
    assumptions: list[AssumptionMade] = Field(default_factory=list)

    # Why this fits
    fit_summary: list[str] = Field(default_factory=list)
    # Where it struggles
    struggle_summary: list[str] = Field(default_factory=list)

    # Additional metadata
    core_services: list[str] = Field(default_factory=list)
    supporting_services: list[str] = Field(default_factory=list)
    learn_url: Optional[str] = None
    browse_tags: list[str] = Field(default_factory=list)

    # Confidence adjustment
    confidence_penalty: float = Field(
        default=0.0,
        description="Penalty applied for assumptions/low confidence"
    )


class ExclusionReasonDetail(BaseModel):
    """Detailed reason for excluding an architecture."""
    reason_type: str  # e.g., "treatment_mismatch", "app_mod_blocker"
    description: str
    blocking_value: Optional[str] = None
    required_value: Optional[str] = None


class ExcludedArchitecture(BaseModel):
    """An architecture that was excluded from recommendations."""
    architecture_id: str
    name: str
    reasons: list[ExclusionReasonDetail]


class RecommendationSummary(BaseModel):
    """Summary of the recommendation results."""
    primary_recommendation: Optional[str] = None
    primary_recommendation_id: Optional[str] = None
    confidence_level: str = "Low"  # High, Medium, Low
    key_drivers: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    assumptions_count: int = 0
    clarifications_needed: int = 0


class ScoringResult(BaseModel):
    """Complete output from the scoring engine."""
    # Metadata
    scoring_version: str = Field(default="1.0.0")
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    application_name: str
    catalog_version: str
    catalog_architecture_count: int

    # Derived intent (for transparency)
    derived_intent: DerivedIntent

    # Clarification questions (if any)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list)
    questions_pending: bool = False

    # Results
    recommendations: list[ArchitectureRecommendation] = Field(default_factory=list)
    excluded: list[ExcludedArchitecture] = Field(default_factory=list)

    # Summary
    summary: RecommendationSummary = Field(default_factory=RecommendationSummary)

    # Debug/audit info
    eligible_count: int = 0
    excluded_count: int = 0
    processing_warnings: list[str] = Field(default_factory=list)
