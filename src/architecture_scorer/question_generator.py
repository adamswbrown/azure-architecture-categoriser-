"""Question Generator - Phase 3 of the Scoring Engine.

Identifies missing intent dimensions and generates clarification questions.
Only asks questions when the answer materially affects eligibility or scoring.
"""

from typing import Optional

from catalog_builder.schema import (
    AvailabilityModel,
    CostProfile,
    OperatingModel,
    SecurityLevel,
    TimeCategory,
    Treatment,
)

from .schema import (
    ApplicationContext,
    ClarificationOption,
    ClarificationQuestion,
    DerivedIntent,
    NetworkExposure,
    SignalConfidence,
)


class QuestionGenerator:
    """Generates clarification questions for missing/low-confidence signals.

    Principles:
    - Only ask when the answer materially affects results
    - Questions must be business-readable
    - Constrained answer sets only
    - User answers override inferred values
    """

    # Confidence threshold below which we consider asking questions
    QUESTION_THRESHOLD = SignalConfidence.LOW

    def generate_questions(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Generate clarification questions for low-confidence signals.

        Args:
            context: Normalized application context
            intent: Derived intent with confidence levels

        Returns:
            List of clarification questions, ordered by importance
        """
        questions = []

        # Network exposure is ALWAYS asked (critical for architecture selection)
        questions.extend(self._check_network_exposure(context, intent))

        # Check each intent dimension
        questions.extend(self._check_treatment(context, intent))
        questions.extend(self._check_time_category(context, intent))
        questions.extend(self._check_availability(context, intent))
        questions.extend(self._check_security(context, intent))
        questions.extend(self._check_operating_model(context, intent))
        questions.extend(self._check_cost_posture(context, intent))

        # Sort by importance (required first, then by eligibility impact)
        questions.sort(
            key=lambda q: (not q.required, not q.affects_eligibility, q.question_id)
        )

        return questions

    def _should_ask(self, confidence: SignalConfidence) -> bool:
        """Determine if a signal's confidence warrants asking a question."""
        confidence_order = {
            SignalConfidence.HIGH: 3,
            SignalConfidence.MEDIUM: 2,
            SignalConfidence.LOW: 1,
            SignalConfidence.UNKNOWN: 0,
        }
        threshold_order = confidence_order.get(self.QUESTION_THRESHOLD, 1)
        signal_order = confidence_order.get(confidence, 0)
        return signal_order <= threshold_order

    def _check_network_exposure(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Check network exposure - ALWAYS ASKED.

        This is a critical question that affects architecture selection:
        - External: Needs WAF, DDoS protection, public endpoints
        - Internal: Can use private endpoints, simpler security
        - Mixed: Most complex, needs both patterns
        """
        questions = []
        exposure_signal = intent.network_exposure

        # Check if already answered in user_answers
        if context.user_answers.get("network_exposure"):
            return questions

        # ALWAYS ask this question - it's critical for architecture selection
        questions.append(ClarificationQuestion(
            question_id="network_exposure",
            dimension="network_exposure",
            question_text="Is this application external-facing, internal-only, or mixed?",
            options=[
                ClarificationOption(
                    value=NetworkExposure.EXTERNAL.value,
                    label="External (Internet-facing)",
                    description="Publicly accessible from the internet (customers, partners, public APIs)"
                ),
                ClarificationOption(
                    value=NetworkExposure.INTERNAL.value,
                    label="Internal Only",
                    description="Only accessible within corporate network (employees, internal systems)"
                ),
                ClarificationOption(
                    value=NetworkExposure.MIXED.value,
                    label="Mixed (Both)",
                    description="Has both public-facing and internal-only components"
                ),
            ],
            required=True,  # Always required
            affects_eligibility=True,  # Affects architecture selection significantly
            current_inference=exposure_signal.value.value if exposure_signal.value else None,
            inference_confidence=exposure_signal.confidence,
        ))

        return questions

    def _check_treatment(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Check if treatment needs clarification."""
        questions = []
        treatment_signal = intent.treatment

        # If declared treatment exists, don't ask
        if context.app_overview.declared_treatment:
            return questions

        # If low confidence and no App Mod, ask
        if self._should_ask(treatment_signal.confidence):
            questions.append(ClarificationQuestion(
                question_id="treatment",
                dimension="treatment",
                question_text="What is the target migration strategy for this application?",
                options=[
                    ClarificationOption(
                        value=Treatment.TOLERATE.value,
                        label="Tolerate (Keep as-is)",
                        description="Maintain current state, minimal cloud involvement"
                    ),
                    ClarificationOption(
                        value=Treatment.REHOST.value,
                        label="Rehost (Lift & Shift)",
                        description="Move to cloud VMs with minimal changes"
                    ),
                    ClarificationOption(
                        value=Treatment.REPLATFORM.value,
                        label="Replatform (Lift & Optimize)",
                        description="Move to PaaS services with minimal code changes"
                    ),
                    ClarificationOption(
                        value=Treatment.REFACTOR.value,
                        label="Refactor (Modernize)",
                        description="Significant changes to leverage cloud-native capabilities"
                    ),
                ],
                required=False,  # We can proceed with inference
                affects_eligibility=True,  # Treatment is a hard gate
                current_inference=treatment_signal.value.value,
                inference_confidence=treatment_signal.confidence,
            ))

        return questions

    def _check_time_category(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Check if TIME category needs clarification."""
        questions = []
        time_signal = intent.time_category

        # If declared, don't ask
        if context.app_overview.declared_time_category:
            return questions

        # TIME category is usually derived from treatment, so only ask if very uncertain
        if time_signal.confidence == SignalConfidence.UNKNOWN:
            questions.append(ClarificationQuestion(
                question_id="time_category",
                dimension="time_category",
                question_text="What is the strategic investment posture for this application?",
                options=[
                    ClarificationOption(
                        value=TimeCategory.TOLERATE.value,
                        label="Tolerate",
                        description="Maintain but don't invest - eventual phase out"
                    ),
                    ClarificationOption(
                        value=TimeCategory.MIGRATE.value,
                        label="Migrate",
                        description="Move to cloud with measured investment"
                    ),
                    ClarificationOption(
                        value=TimeCategory.INVEST.value,
                        label="Invest",
                        description="Strategic asset - significant modernization investment"
                    ),
                    ClarificationOption(
                        value=TimeCategory.ELIMINATE.value,
                        label="Eliminate",
                        description="Phase out and replace with alternative"
                    ),
                ],
                required=False,
                affects_eligibility=True,
                current_inference=time_signal.value.value if time_signal.value else None,
                inference_confidence=time_signal.confidence,
            ))

        return questions

    def _check_availability(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Check if availability requirement needs clarification."""
        questions = []
        avail_signal = intent.availability_requirement

        # If explicitly specified, don't ask
        if context.app_overview.availability_requirement:
            return questions

        # Availability affects architecture selection significantly
        if self._should_ask(avail_signal.confidence):
            questions.append(ClarificationQuestion(
                question_id="availability",
                dimension="availability_requirement",
                question_text="What are the availability requirements for this application?",
                options=[
                    ClarificationOption(
                        value=AvailabilityModel.SINGLE_REGION.value,
                        label="Single Region",
                        description="Standard availability within one Azure region"
                    ),
                    ClarificationOption(
                        value=AvailabilityModel.ZONE_REDUNDANT.value,
                        label="Zone Redundant",
                        description="High availability across availability zones"
                    ),
                    ClarificationOption(
                        value=AvailabilityModel.MULTI_REGION_ACTIVE_PASSIVE.value,
                        label="Multi-Region (Active/Passive)",
                        description="Disaster recovery with failover to secondary region"
                    ),
                    ClarificationOption(
                        value=AvailabilityModel.MULTI_REGION_ACTIVE_ACTIVE.value,
                        label="Multi-Region (Active/Active)",
                        description="Always-on global availability across regions"
                    ),
                ],
                required=False,
                affects_eligibility=True,
                current_inference=avail_signal.value.value if avail_signal.value else None,
                inference_confidence=avail_signal.confidence,
            ))

        return questions

    def _check_security(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Check if security requirements need clarification."""
        questions = []
        security_signal = intent.security_requirement

        # If compliance requirements are specified, we have clear signal
        if context.app_overview.compliance_requirements:
            return questions

        # Security level affects architecture selection
        if self._should_ask(security_signal.confidence):
            questions.append(ClarificationQuestion(
                question_id="security_level",
                dimension="security_requirement",
                question_text="What security/compliance level is required for this application?",
                options=[
                    ClarificationOption(
                        value=SecurityLevel.BASIC.value,
                        label="Basic",
                        description="Standard security practices, no specific compliance"
                    ),
                    ClarificationOption(
                        value=SecurityLevel.ENTERPRISE.value,
                        label="Enterprise",
                        description="Enterprise security (Zero Trust, private endpoints)"
                    ),
                    ClarificationOption(
                        value=SecurityLevel.REGULATED.value,
                        label="Regulated",
                        description="Industry compliance (SOC 2, ISO 27001, GDPR)"
                    ),
                    ClarificationOption(
                        value=SecurityLevel.HIGHLY_REGULATED.value,
                        label="Highly Regulated",
                        description="Strict compliance (HIPAA, PCI-DSS, FedRAMP)"
                    ),
                ],
                required=False,
                affects_eligibility=True,
                current_inference=security_signal.value.value if security_signal.value else None,
                inference_confidence=security_signal.confidence,
            ))

        return questions

    def _check_operating_model(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Check if operating model needs clarification."""
        questions = []
        ops_signal = intent.operational_maturity_estimate

        # Ask if confidence is low - operating model affects many architectures
        if self._should_ask(ops_signal.confidence):
            questions.append(ClarificationQuestion(
                question_id="operating_model",
                dimension="operational_maturity_estimate",
                question_text="What is your team's operational maturity level?",
                options=[
                    ClarificationOption(
                        value=OperatingModel.TRADITIONAL_IT.value,
                        label="Traditional IT",
                        description="Manual deployments, ITIL processes, separate ops team"
                    ),
                    ClarificationOption(
                        value=OperatingModel.TRANSITIONAL.value,
                        label="Transitional",
                        description="Some automation, moving toward DevOps practices"
                    ),
                    ClarificationOption(
                        value=OperatingModel.DEVOPS.value,
                        label="DevOps",
                        description="CI/CD, infrastructure as code, team owns deployment"
                    ),
                    ClarificationOption(
                        value=OperatingModel.SRE.value,
                        label="SRE",
                        description="SLO-driven, comprehensive observability, error budgets"
                    ),
                ],
                required=False,
                affects_eligibility=True,  # Some architectures require DevOps maturity
                current_inference=ops_signal.value.value if ops_signal.value else None,
                inference_confidence=ops_signal.confidence,
            ))

        return questions

    def _check_cost_posture(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
    ) -> list[ClarificationQuestion]:
        """Check if cost posture needs clarification."""
        questions = []
        cost_signal = intent.cost_posture

        # Ask if confidence is low - cost affects architecture matching
        if self._should_ask(cost_signal.confidence):
            questions.append(ClarificationQuestion(
                question_id="cost_posture",
                dimension="cost_posture",
                question_text="What is your cost optimization priority for this application?",
                options=[
                    ClarificationOption(
                        value=CostProfile.COST_MINIMIZED.value,
                        label="Cost Minimized",
                        description="Minimize spend, use consumption/spot pricing where possible"
                    ),
                    ClarificationOption(
                        value=CostProfile.BALANCED.value,
                        label="Balanced",
                        description="Balance cost and performance for production workloads"
                    ),
                    ClarificationOption(
                        value=CostProfile.SCALE_OPTIMIZED.value,
                        label="Scale Optimized",
                        description="Prioritize scalability and performance over cost"
                    ),
                    ClarificationOption(
                        value=CostProfile.INNOVATION_FIRST.value,
                        label="Innovation First",
                        description="Use latest services (AI, preview features) regardless of cost"
                    ),
                ],
                required=False,
                affects_eligibility=False,  # Cost doesn't block eligibility
                current_inference=cost_signal.value.value if cost_signal.value else None,
                inference_confidence=cost_signal.confidence,
            ))

        return questions

    def apply_answers(
        self,
        context: ApplicationContext,
        intent: DerivedIntent,
        answers: dict[str, str],
    ) -> DerivedIntent:
        """Apply user answers to override derived intent signals.

        Args:
            context: Application context
            intent: Current derived intent
            answers: User answers keyed by question_id

        Returns:
            Updated DerivedIntent with user overrides applied
        """
        # Create a copy of the intent to modify
        updated_intent = intent.model_copy(deep=True)

        # Apply treatment answer
        if "treatment" in answers:
            updated_intent.treatment.value = Treatment(answers["treatment"])
            updated_intent.treatment.confidence = SignalConfidence.HIGH
            updated_intent.treatment.source = "user_answer"
            updated_intent.treatment.reasoning = "User specified treatment"

        # Apply TIME category answer
        if "time_category" in answers:
            updated_intent.time_category.value = TimeCategory(answers["time_category"])
            updated_intent.time_category.confidence = SignalConfidence.HIGH
            updated_intent.time_category.source = "user_answer"
            updated_intent.time_category.reasoning = "User specified TIME category"

        # Apply availability answer
        if "availability" in answers:
            updated_intent.availability_requirement.value = AvailabilityModel(answers["availability"])
            updated_intent.availability_requirement.confidence = SignalConfidence.HIGH
            updated_intent.availability_requirement.source = "user_answer"
            updated_intent.availability_requirement.reasoning = "User specified availability"

        # Apply security answer
        if "security_level" in answers:
            updated_intent.security_requirement.value = SecurityLevel(answers["security_level"])
            updated_intent.security_requirement.confidence = SignalConfidence.HIGH
            updated_intent.security_requirement.source = "user_answer"
            updated_intent.security_requirement.reasoning = "User specified security level"

        # Apply operating model answer
        if "operating_model" in answers:
            updated_intent.operational_maturity_estimate.value = OperatingModel(answers["operating_model"])
            updated_intent.operational_maturity_estimate.confidence = SignalConfidence.HIGH
            updated_intent.operational_maturity_estimate.source = "user_answer"
            updated_intent.operational_maturity_estimate.reasoning = "User specified operating model"

        # Apply cost posture answer
        if "cost_posture" in answers:
            updated_intent.cost_posture.value = CostProfile(answers["cost_posture"])
            updated_intent.cost_posture.confidence = SignalConfidence.HIGH
            updated_intent.cost_posture.source = "user_answer"
            updated_intent.cost_posture.reasoning = "User specified cost posture"

        # Apply network exposure answer
        if "network_exposure" in answers:
            updated_intent.network_exposure.value = NetworkExposure(answers["network_exposure"])
            updated_intent.network_exposure.confidence = SignalConfidence.HIGH
            updated_intent.network_exposure.source = "user_answer"
            updated_intent.network_exposure.reasoning = "User specified network exposure"

        return updated_intent
