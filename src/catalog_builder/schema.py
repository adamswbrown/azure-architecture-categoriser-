"""Pydantic models for the architecture catalog schema."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ArchitectureFamily(str, Enum):
    """Architecture family classification."""
    FOUNDATION = "foundation"
    IAAS = "iaas"
    PAAS = "paas"
    CLOUD_NATIVE = "cloud_native"
    DATA = "data"
    INTEGRATION = "integration"
    SPECIALIZED = "specialized"


class WorkloadDomain(str, Enum):
    """Workload domain classification."""
    WEB = "web"
    DATA = "data"
    INTEGRATION = "integration"
    SECURITY = "security"
    AI = "ai"
    INFRASTRUCTURE = "infrastructure"
    GENERAL = "general"


class RuntimeModel(str, Enum):
    """Expected runtime model for the architecture."""
    MONOLITH = "monolith"
    N_TIER = "n_tier"
    API = "api"
    MICROSERVICES = "microservices"
    EVENT_DRIVEN = "event_driven"
    BATCH = "batch"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class TrinaryOption(str, Enum):
    """Three-state option for characteristics."""
    TRUE = "true"
    FALSE = "false"
    OPTIONAL = "optional"


class Treatment(str, Enum):
    """Supported migration/modernization treatments (Gartner 8R)."""
    RETIRE = "retire"
    TOLERATE = "tolerate"
    REHOST = "rehost"
    REPLATFORM = "replatform"
    REFACTOR = "refactor"
    REPLACE = "replace"
    REBUILD = "rebuild"  # Complete re-architecture from scratch
    RETAIN = "retain"  # Keep on-premises with hybrid/extension to cloud


class TimeCategory(str, Enum):
    """Time investment categories."""
    TOLERATE = "tolerate"
    MIGRATE = "migrate"
    INVEST = "invest"
    ELIMINATE = "eliminate"


class AvailabilityModel(str, Enum):
    """Availability deployment models."""
    SINGLE_REGION = "single_region"
    ZONE_REDUNDANT = "zone_redundant"
    MULTI_REGION_ACTIVE_PASSIVE = "multi_region_active_passive"
    MULTI_REGION_ACTIVE_ACTIVE = "multi_region_active_active"


class SecurityLevel(str, Enum):
    """Security level classifications."""
    BASIC = "basic"
    ENTERPRISE = "enterprise"
    REGULATED = "regulated"
    HIGHLY_REGULATED = "highly_regulated"


class OperatingModel(str, Enum):
    """Required operating model."""
    TRADITIONAL_IT = "traditional_it"
    TRANSITIONAL = "transitional"
    DEVOPS = "devops"
    SRE = "sre"


class CostProfile(str, Enum):
    """Cost optimization profile."""
    COST_MINIMIZED = "cost_minimized"
    BALANCED = "balanced"
    SCALE_OPTIMIZED = "scale_optimized"
    INNOVATION_FIRST = "innovation_first"


class ComplexityLevel(str, Enum):
    """Complexity level rating."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ExclusionReason(str, Enum):
    """Reasons an architecture is not suitable."""
    REHOST_ONLY = "rehost_only"
    TOLERATE_ONLY = "tolerate_only"
    LOW_MATURITY_TEAMS = "low_maturity_teams"
    LOW_DEVOPS_MATURITY = "low_devops_maturity"  # Team lacks DevOps skills
    VM_ONLY_APPS = "vm_only_apps"
    SINGLE_VM_WORKLOADS = "single_vm_workloads"  # Over-engineered for single VM
    REGULATED_WORKLOADS = "regulated_workloads"
    LOW_BUDGET = "low_budget"
    SKILL_CONSTRAINED = "skill_constrained"
    GREENFIELD_ONLY = "greenfield_only"  # Only suitable for new projects
    SIMPLE_WORKLOADS = "simple_workloads"  # Over-engineered for simple needs
    WINDOWS_ONLY = "windows_only"  # Linux incompatibility
    LINUX_ONLY = "linux_only"  # Windows incompatibility
    HIGH_LATENCY_TOLERANCE = "high_latency_tolerance"  # Requires low latency
    LEGACY_SYSTEMS = "legacy_systems"  # Not suitable for legacy modernization
    NO_CONTAINER_EXPERIENCE = "no_container_experience"  # Requires container skills
    STATEFUL_APPS = "stateful_apps"  # Not suitable for stateful workloads


class ExtractionConfidence(str, Enum):
    """Confidence level for extracted/suggested values."""
    CURATED = "curated"  # From authoritative source (browse metadata, YML)
    HIGH = "high"  # High confidence from content analysis
    AUTOMATIC = "automatic"  # Extracted automatically with high confidence
    MEDIUM = "medium"  # Medium confidence, reasonable inference
    AI_SUGGESTED = "ai_suggested"  # AI-assisted suggestion, needs human review
    LOW = "low"  # Low confidence, heuristic fallback
    MANUAL_REQUIRED = "manual_required"  # Cannot be determined automatically


class CatalogQuality(str, Enum):
    """Quality level of the catalog entry.

    Levels from highest to lowest quality:
    - curated: From authoritative browse metadata (YamlMime:Architecture)
    - ai_enriched: AI-enhanced with high confidence
    - ai_suggested: Primarily AI-generated, needs human review
    - example_only: Example scenarios (not reference architectures) - use with caution
    """
    CURATED = "curated"  # From authoritative browse metadata
    AI_ENRICHED = "ai_enriched"  # AI-enhanced with confidence
    AI_SUGGESTED = "ai_suggested"  # Primarily AI-generated, needs review
    EXAMPLE_ONLY = "example_only"  # Example scenarios, not reference architectures


class ExpectedCharacteristics(BaseModel):
    """Expected architectural characteristics."""
    containers: TrinaryOption = TrinaryOption.OPTIONAL
    stateless: TrinaryOption = TrinaryOption.OPTIONAL
    devops_required: bool = False
    ci_cd_required: bool = False
    private_networking_required: bool = False


class Complexity(BaseModel):
    """Complexity ratings for implementation and operations."""
    implementation: ComplexityLevel = ComplexityLevel.MEDIUM
    operations: ComplexityLevel = ComplexityLevel.MEDIUM


class ClassificationMeta(BaseModel):
    """Metadata about how a value was determined."""
    confidence: ExtractionConfidence
    source: Optional[str] = None  # e.g., "filename", "frontmatter", "content_analysis"


class ArchitectureEntry(BaseModel):
    """Complete architecture catalog entry."""

    # Identity
    architecture_id: str = Field(..., description="Unique identifier derived from path")
    name: str = Field(..., description="Human-readable architecture name (use pattern_name)")
    pattern_name: str = Field(
        default="",
        description="Normalized pattern name representing architectural intent"
    )
    pattern_name_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.MANUAL_REQUIRED)
    )
    description: str = Field(..., description="Brief description of the architecture")
    source_repo_path: str = Field(..., description="Path in source repository")
    learn_url: Optional[str] = Field(None, description="Microsoft Learn URL")

    # Browse Metadata (from YamlMime:Architecture)
    browse_tags: list[str] = Field(
        default_factory=list,
        description="Browse tags from YML (e.g., 'Azure', 'Containers')"
    )
    browse_categories: list[str] = Field(
        default_factory=list,
        description="Browse categories from YML (e.g., 'Architecture', 'Baseline')"
    )

    # Classification
    family: ArchitectureFamily = Field(
        default=ArchitectureFamily.GENERAL if hasattr(ArchitectureFamily, 'GENERAL') else ArchitectureFamily.FOUNDATION,
        description="Architecture family"
    )
    family_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.MANUAL_REQUIRED)
    )
    workload_domain: WorkloadDomain = Field(
        default=WorkloadDomain.GENERAL,
        description="Workload domain"
    )
    workload_domain_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.MANUAL_REQUIRED)
    )

    # Architectural Expectations
    expected_runtime_models: list[RuntimeModel] = Field(
        default_factory=lambda: [RuntimeModel.UNKNOWN],
        description="Expected runtime models"
    )
    runtime_models_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.MANUAL_REQUIRED)
    )
    expected_characteristics: ExpectedCharacteristics = Field(
        default_factory=ExpectedCharacteristics,
        description="Expected architectural characteristics"
    )

    # Supported Change Models
    supported_treatments: list[Treatment] = Field(
        default_factory=list,
        description="Supported migration/modernization treatments"
    )
    treatments_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.AI_SUGGESTED)
    )
    supported_time_categories: list[TimeCategory] = Field(
        default_factory=list,
        description="Supported time investment categories"
    )
    time_categories_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.AI_SUGGESTED)
    )

    # Operational Expectations
    availability_models: list[AvailabilityModel] = Field(
        default_factory=lambda: [AvailabilityModel.SINGLE_REGION],
        description="Supported availability models"
    )
    availability_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.AI_SUGGESTED)
    )
    security_level: SecurityLevel = Field(
        default=SecurityLevel.BASIC,
        description="Security level classification"
    )
    security_level_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.AI_SUGGESTED)
    )
    operating_model_required: OperatingModel = Field(
        default=OperatingModel.TRADITIONAL_IT,
        description="Required operating model"
    )
    operating_model_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.AI_SUGGESTED)
    )

    # Cost & Complexity
    cost_profile: CostProfile = Field(
        default=CostProfile.BALANCED,
        description="Cost optimization profile"
    )
    cost_profile_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.AI_SUGGESTED)
    )
    complexity: Complexity = Field(
        default_factory=Complexity,
        description="Complexity ratings"
    )
    complexity_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.MANUAL_REQUIRED)
    )

    # Exclusion Rules (manual only)
    not_suitable_for: list[ExclusionReason] = Field(
        default_factory=list,
        description="Scenarios where this architecture is not suitable"
    )

    # Azure Services (split by role)
    core_services: list[str] = Field(
        default_factory=list,
        description="Azure services required to realize the pattern (compute, data, networking)"
    )
    supporting_services: list[str] = Field(
        default_factory=list,
        description="Supporting services for observability, security, and operations"
    )
    services_confidence: ClassificationMeta = Field(
        default_factory=lambda: ClassificationMeta(confidence=ExtractionConfidence.AI_SUGGESTED)
    )

    # Metadata
    diagram_assets: list[str] = Field(
        default_factory=list,
        description="Paths to diagram assets"
    )
    last_repo_update: Optional[datetime] = Field(
        None,
        description="Last update time from repository"
    )

    # Catalog quality
    catalog_quality: CatalogQuality = Field(
        default=CatalogQuality.AI_SUGGESTED,
        description="Quality level of this catalog entry"
    )

    # Extraction metadata
    extraction_warnings: list[str] = Field(
        default_factory=list,
        description="Warnings generated during extraction"
    )

    @property
    def azure_services_used(self) -> list[str]:
        """Backward-compatible property combining core and supporting services."""
        return self.core_services + self.supporting_services


class ArchitectureCatalog(BaseModel):
    """Complete architecture catalog."""
    version: str = Field(default="1.0.0", description="Catalog schema version")
    generated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Generation timestamp"
    )
    source_repo: str = Field(..., description="Source repository URL or path")
    source_commit: Optional[str] = Field(None, description="Source repository commit hash")
    total_architectures: int = Field(default=0, description="Total number of architectures")
    architectures: list[ArchitectureEntry] = Field(
        default_factory=list,
        description="Architecture entries"
    )

    def model_post_init(self, __context) -> None:
        """Update total count after initialization."""
        self.total_architectures = len(self.architectures)
