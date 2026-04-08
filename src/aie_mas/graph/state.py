from __future__ import annotations

from typing import Any, Literal, Optional, TypedDict

from pydantic import BaseModel, Field

PlannerAction = Literal["macro_and_microscopic", "macro", "microscopic", "verifier", "finalize"]
PendingAgent = Literal["macro", "microscopic", "verifier"]
DecisionGateStatus = Literal[
    "not_ready",
    "needs_portfolio_screening",
    "needs_pairwise_discriminative_task",
    "needs_high_confidence_verifier",
    "ready_to_finalize_decisive",
    "ready_to_finalize_best_available",
    "blocked_by_missing_decisive_evidence",
]
PairwiseTaskAgent = Literal["macro", "microscopic"]
PairwiseTaskOutcome = Literal[
    "not_run",
    "dedicated_pairwise_task_completed",
    "resolved_by_accumulated_internal_evidence",
    "resolved_with_verifier_support",
    "best_available_tool_blocked",
]
FinalizationMode = Literal["none", "decisive", "best_available"]
ReasoningPhase = Literal["portfolio_screening", "pairwise_contraction"]
AgentFramingMode = Literal["portfolio_neutral", "hypothesis_anchored"]
HypothesisScreeningStatus = Literal[
    "untested",
    "indirectly_weakened",
    "directly_screened",
    "blocked_by_capability",
    "dropped_with_reason",
]
HypothesisScreeningPriority = Literal["none", "low", "normal", "high"]
EvidenceFamily = Literal[
    "geometry_precondition",
    "state_ordering_brightness",
    "torsion_sensitivity",
    "charge_localization",
    "external_precedent",
    "raw_artifact_inspection",
]
MicroscopicTaskMode = Literal["baseline_s0_s1", "targeted_follow_up"]
MicroscopicPlanStepType = Literal[
    "structure_prep",
    "conformer_bundle_generation",
    "torsion_snapshot_generation",
    "artifact_parse",
    "s0_optimization",
    "s0_singlepoint",
    "s1_vertical_excitation",
]
MicroscopicStructureSource = Literal["prepared_from_smiles", "existing_prepared_structure"]
MicroscopicCapabilityRoute = Literal[
    "baseline_bundle",
    "conformer_bundle_follow_up",
    "torsion_snapshot_follow_up",
    "artifact_parse_only",
    "targeted_property_follow_up",
    "targeted_state_characterization_follow_up",
    "excited_state_relaxation_follow_up",
]
MicroscopicCapabilityName = Literal[
    "list_rotatable_dihedrals",
    "list_available_conformers",
    "list_artifact_bundles",
    "list_artifact_bundle_members",
    "run_baseline_bundle",
    "run_conformer_bundle",
    "run_torsion_snapshots",
    "run_targeted_charge_analysis",
    "run_targeted_localized_orbital_analysis",
    "run_targeted_natural_orbital_analysis",
    "run_targeted_density_population_analysis",
    "run_targeted_transition_dipole_analysis",
    "run_ris_state_characterization",
    "parse_snapshot_outputs",
    "extract_ct_descriptors_from_bundle",
    "extract_geometry_descriptors_from_bundle",
    "inspect_raw_artifact_bundle",
    "run_targeted_state_characterization",
    "unsupported_excited_state_relaxation",
]
AmespCapabilityName = MicroscopicCapabilityName
TEMPORARILY_DISABLED_MICROSCOPIC_CAPABILITIES: tuple[str, ...] = ()
MicroscopicBudgetProfile = Literal["conservative", "balanced", "aggressive"]
MicroscopicToolCallKind = Literal["discovery", "execution"]
DihedralBondType = Literal["aryl-aryl", "aryl-vinyl", "heteroaryl-linkage", "other"]
DihedralRelevance = Literal["high", "medium", "low"]
ArtifactBundleKind = Literal[
    "baseline_bundle",
    "torsion_snapshots",
    "conformer_bundle",
    "targeted_property_follow_up",
]
ArtifactBundleCompletionStatus = Literal["complete", "partial"]
MicroscopicTargetSelectionMode = Literal["bundle_wide", "representative_subset", "exact_members"]
ConformerSource = Literal["shared_structure", "microscopic_follow_up"]
DiscoveryStructureSource = Literal["shared_prepared_structure", "round_s0_optimized_geometry", "latest_available"]
MicroscopicCompletionReasonCode = Literal[
    "capability_unsupported",
    "runtime_failed",
    "precondition_missing",
    "resource_budget_exceeded",
    "parse_failed",
    "protocol_parse_failed",
    "action_not_supported_by_registry",
    "partial_observable_only",
]
MacroPlanStepType = Literal["shared_context_load", "topology_analysis", "geometry_proxy_analysis", "focus_selection"]
MacroStructureSource = Literal["shared_prepared_structure", "smiles_only_fallback"]
VerifierEvidenceKind = Literal["case_memory", "external_summary", "mechanistic_note"]
SharedStructureStatus = Literal["missing", "ready", "failed"]
MoleculeIdentityStatus = Literal["missing", "ready", "partial", "failed"]
WorkflowProgressPhase = Literal["start", "probe", "end"]
VerifierComparisonBucket = Literal[
    "exact_identity",
    "champion_family",
    "challenger_family",
    "pairwise_discriminator",
    "limitation",
]
VerifierEvidenceSpecificity = Literal[
    "exact_compound",
    "close_family",
    "generic_review",
    "no_direct_hit",
]
VerifierSupplementStatus = Literal["missing", "partial", "sufficient"]
VerifierInformationGain = Literal["none", "low", "medium", "high"]
VerifierEvidenceRelation = Literal["supports_top1", "challenges_top1", "mixed", "no_new_info"]
ClosureJustificationStatus = Literal["missing", "collecting", "sufficient", "blocked"]
ClosureJustificationEvidenceSource = Literal["internal", "external", "mixed"]
ClosureJustificationBasis = Literal["existing_evidence", "new_targeted_task"]


class WorkflowProgressEvent(TypedDict):
    phase: WorkflowProgressPhase
    node: str
    round: int
    agent: str
    case_id: Optional[str]
    current_hypothesis: Optional[str]
    details: dict[str, Any]


class HypothesisEntry(BaseModel):
    name: str
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    candidate_strength: Optional[Literal["strong", "medium", "weak"]] = None


class HypothesisScreeningRecord(BaseModel):
    hypothesis: str
    screening_status: HypothesisScreeningStatus = "untested"
    screening_priority: HypothesisScreeningPriority = "normal"
    evidence_families_covered: list[EvidenceFamily] = Field(default_factory=list)
    screening_note: Optional[str] = None


class AgentReport(BaseModel):
    agent_name: Literal["microscopic", "macro", "verifier"]
    task_received: str
    task_completion_status: Literal["completed", "contracted", "partial", "failed"] = "completed"
    completion_reason_code: Optional[MicroscopicCompletionReasonCode] = None
    task_completion: str = "Task completion was not provided."
    task_understanding: str = "Task understanding was not provided."
    reasoning_summary: str = "Reasoning summary was not provided."
    execution_plan: str = "Execution plan was not provided."
    result_summary: str = "Result summary was not provided."
    remaining_local_uncertainty: str = "Remaining local uncertainty was not provided."
    tool_calls: list[str] = Field(default_factory=list)
    raw_results: dict[str, Any] = Field(default_factory=dict)
    structured_results: dict[str, Any] = Field(default_factory=dict)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    status: Literal["success", "partial", "failed"] = "success"
    planner_readable_report: str


class VerifierEvidenceCard(BaseModel):
    card_id: str
    source: str
    title: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    observation: str
    topic_tags: list[str] = Field(default_factory=list)
    evidence_kind: VerifierEvidenceKind
    why_relevant: Optional[str] = None
    query_group: Literal[
        "exact_identity",
        "similar_family",
        "mechanistic_discriminator",
        "champion_family",
        "challenger_family",
        "pairwise_discriminator",
        "limitation",
    ] = "similar_family"
    match_level: Literal[
        "exact_molecule",
        "same_family",
        "specific_test_criterion",
        "similar_structural_class",
        "generic_mechanistic_context",
        "retrieval_limitation",
    ] = "generic_mechanistic_context"
    mechanism_claim: Optional[str] = None
    experimental_context: Optional[str] = None
    comparison_bucket: VerifierComparisonBucket = "pairwise_discriminator"
    relevant_hypotheses: list[str] = Field(default_factory=list)
    criterion_type: Optional[str] = None
    evidence_specificity: VerifierEvidenceSpecificity = "generic_review"


class WorkingMemoryAgentEntry(BaseModel):
    agent_name: Literal["microscopic", "macro", "verifier"]
    task_received: str
    task_completion_status: Literal["completed", "contracted", "partial", "failed"] = "completed"
    completion_reason_code: Optional[MicroscopicCompletionReasonCode] = None
    task_completion: str = "Task completion was not provided."
    task_understanding: str
    reasoning_summary: str = "Reasoning summary was not provided."
    execution_plan: str
    result_summary: str
    remaining_local_uncertainty: str
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)
    status: Literal["success", "partial", "failed"] = "success"


class CapabilityLessonEntry(BaseModel):
    agent_name: Literal["microscopic", "macro", "verifier"]
    blocked_task_pattern: str
    observed_limitation: str
    recommended_contraction: str


class PlannerDecision(BaseModel):
    diagnosis: str
    action: PlannerAction
    current_hypothesis: str
    confidence: float
    reasoning_phase: ReasoningPhase = "portfolio_screening"
    agent_framing_mode: AgentFramingMode = "portfolio_neutral"
    portfolio_screening_complete: bool = False
    coverage_debt_hypotheses: list[str] = Field(default_factory=list)
    credible_alternative_hypotheses: list[str] = Field(default_factory=list)
    hypothesis_screening_ledger: list[HypothesisScreeningRecord] = Field(default_factory=list)
    portfolio_screening_summary: Optional[str] = None
    screening_focus_hypotheses: list[str] = Field(default_factory=list)
    screening_focus_summary: Optional[str] = None
    needs_verifier: bool = False
    finalize: bool = False
    planned_agents: list[PendingAgent] = Field(default_factory=list)
    task_instruction: Optional[str] = None
    agent_task_instructions: dict[PendingAgent, str] = Field(default_factory=dict)
    hypothesis_uncertainty_note: Optional[str] = None
    final_hypothesis_rationale: Optional[str] = None
    capability_assessment: Optional[str] = None
    stagnation_assessment: Optional[str] = None
    contraction_reason: Optional[str] = None
    capability_lesson_candidates: list[CapabilityLessonEntry] = Field(default_factory=list)
    information_gain_assessment: Optional[str] = None
    gap_trend: Optional[str] = None
    stagnation_detected: bool = False
    runner_up_hypothesis: Optional[str] = None
    runner_up_confidence: Optional[float] = None
    hypothesis_reweight_explanation: dict[str, str] = Field(default_factory=dict)
    decision_pair: list[str] = Field(default_factory=list)
    decision_gate_status: DecisionGateStatus = "not_ready"
    verifier_supplement_target_pair: Optional[str] = None
    verifier_supplement_status: VerifierSupplementStatus = "missing"
    verifier_information_gain: VerifierInformationGain = "none"
    verifier_evidence_relation: VerifierEvidenceRelation = "no_new_info"
    verifier_supplement_summary: Optional[str] = None
    closure_justification_target_pair: Optional[str] = None
    closure_justification_status: ClosureJustificationStatus = "missing"
    closure_justification_evidence_source: Optional[ClosureJustificationEvidenceSource] = None
    closure_justification_basis: Optional[ClosureJustificationBasis] = None
    closure_justification_summary: Optional[str] = None
    pairwise_task_agent: Optional[PairwiseTaskAgent] = None
    pairwise_task_completed_for_pair: Optional[str] = None
    pairwise_task_outcome: PairwiseTaskOutcome = "not_run"
    pairwise_task_rationale: Optional[str] = None
    pairwise_resolution_mode: Optional[PairwiseTaskOutcome] = None
    pairwise_resolution_evidence_sources: list[str] = Field(default_factory=list)
    pairwise_resolution_summary: Optional[str] = None
    finalization_mode: FinalizationMode = "none"
    pairwise_verifier_completed_for_pair: Optional[str] = None
    pairwise_verifier_evidence_specificity: Optional[VerifierEvidenceSpecificity] = None
    planned_action_label: Optional[str] = None
    executed_action_labels: list[str] = Field(default_factory=list)


class WorkingMemoryEntry(BaseModel):
    round_id: int
    current_hypothesis: str
    confidence: float
    hypothesis_pool: list[HypothesisEntry] = Field(default_factory=list)
    reasoning_phase: ReasoningPhase = "portfolio_screening"
    agent_framing_mode: AgentFramingMode = "portfolio_neutral"
    portfolio_screening_complete: bool = False
    coverage_debt_hypotheses: list[str] = Field(default_factory=list)
    credible_alternative_hypotheses: list[str] = Field(default_factory=list)
    hypothesis_screening_ledger: list[HypothesisScreeningRecord] = Field(default_factory=list)
    portfolio_screening_summary: Optional[str] = None
    screening_focus_hypotheses: list[str] = Field(default_factory=list)
    screening_focus_summary: Optional[str] = None
    runner_up_hypothesis: Optional[str] = None
    runner_up_confidence: Optional[float] = None
    action_taken: str
    evidence_summary: str
    diagnosis_summary: str
    main_gap: str
    conflict_status: str
    next_action: str
    planner_task_instruction: Optional[str] = None
    planner_agent_task_instructions: dict[PendingAgent, str] = Field(default_factory=dict)
    hypothesis_uncertainty_note: Optional[str] = None
    final_hypothesis_rationale: Optional[str] = None
    capability_assessment: Optional[str] = None
    stagnation_assessment: Optional[str] = None
    contraction_reason: Optional[str] = None
    information_gain_assessment: Optional[str] = None
    gap_trend: Optional[str] = None
    stagnation_detected: bool = False
    hypothesis_reweight_explanation: dict[str, str] = Field(default_factory=dict)
    decision_pair: list[str] = Field(default_factory=list)
    decision_gate_status: DecisionGateStatus = "not_ready"
    verifier_supplement_target_pair: Optional[str] = None
    verifier_supplement_status: VerifierSupplementStatus = "missing"
    verifier_information_gain: VerifierInformationGain = "none"
    verifier_evidence_relation: VerifierEvidenceRelation = "no_new_info"
    verifier_supplement_summary: Optional[str] = None
    closure_justification_target_pair: Optional[str] = None
    closure_justification_status: ClosureJustificationStatus = "missing"
    closure_justification_evidence_source: Optional[ClosureJustificationEvidenceSource] = None
    closure_justification_basis: Optional[ClosureJustificationBasis] = None
    closure_justification_summary: Optional[str] = None
    pairwise_task_agent: Optional[PairwiseTaskAgent] = None
    pairwise_task_completed_for_pair: Optional[str] = None
    pairwise_task_outcome: PairwiseTaskOutcome = "not_run"
    pairwise_task_rationale: Optional[str] = None
    pairwise_resolution_mode: Optional[PairwiseTaskOutcome] = None
    pairwise_resolution_evidence_sources: list[str] = Field(default_factory=list)
    pairwise_resolution_summary: Optional[str] = None
    finalization_mode: FinalizationMode = "none"
    pairwise_verifier_completed_for_pair: Optional[str] = None
    pairwise_verifier_evidence_specificity: Optional[VerifierEvidenceSpecificity] = None
    planned_action_label: Optional[str] = None
    executed_action_labels: list[str] = Field(default_factory=list)
    executed_evidence_families: list[EvidenceFamily] = Field(default_factory=list)
    local_uncertainty_summary: Optional[str] = None
    repeated_local_uncertainty_signals: list[str] = Field(default_factory=list)
    capability_lesson_candidates: list[CapabilityLessonEntry] = Field(default_factory=list)
    agent_reports: list[WorkingMemoryAgentEntry] = Field(default_factory=list)


class MicroscopicTaskSpec(BaseModel):
    mode: MicroscopicTaskMode
    task_label: str
    objective: str
    target_property: Optional[str] = None


class MicroscopicExecutionStep(BaseModel):
    step_id: str
    step_type: MicroscopicPlanStepType
    description: str
    input_source: str
    keywords: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)


class DihedralDescriptor(BaseModel):
    dihedral_id: str
    atom_indices: list[int] = Field(default_factory=list)
    central_bond_indices: list[int] = Field(default_factory=list)
    label: str
    bond_type: DihedralBondType = "other"
    adjacent_to_nsnc_core: bool = False
    central_conjugation_relevance: DihedralRelevance = "low"
    peripheral: bool = False
    rotatable: bool = True


class ConformerDescriptor(BaseModel):
    conformer_id: str
    source: ConformerSource = "shared_structure"
    rank: int
    prepared_xyz_path: str
    summary_label: str


class ArtifactBundleDescriptor(BaseModel):
    artifact_bundle_id: str
    source_round: int
    source_capability: str
    artifact_kind: ArtifactBundleKind
    bundle_completion_status: ArtifactBundleCompletionStatus = "complete"
    snapshot_count: int = 0
    available_files: list[str] = Field(default_factory=list)
    available_deliverables: list[str] = Field(default_factory=list)


class ArtifactBundleMemberMetadata(BaseModel):
    member_id: str
    member_label: str
    source_bundle_id: Optional[str] = None
    source_member_id: Optional[str] = None
    generated_files: list[str] = Field(default_factory=list)
    parse_capabilities_supported: list[MicroscopicCapabilityName] = Field(default_factory=list)


class ArtifactBundle(BaseModel):
    bundle_id: str
    bundle_kind: ArtifactBundleKind
    source_round: int
    source_capability: str
    bundle_completion_status: ArtifactBundleCompletionStatus = "complete"
    available_files: list[str] = Field(default_factory=list)
    available_deliverables: list[str] = Field(default_factory=list)
    parse_capabilities_supported: list[MicroscopicCapabilityName] = Field(default_factory=list)
    source_bundle_id: Optional[str] = None
    source_member_ids: list[str] = Field(default_factory=list)


class ArtifactBundleRegistryEntry(BaseModel):
    artifact_bundle: ArtifactBundle
    bundle_members: list[ArtifactBundleMemberMetadata] = Field(default_factory=list)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)


class SelectionPolicy(BaseModel):
    exclude_dihedral_ids: list[str] = Field(default_factory=list)
    hard_exclude_dihedral_ids: list[str] = Field(default_factory=list)
    prefer_adjacent_to_nsnc_core: bool = False
    min_relevance: DihedralRelevance = "medium"
    include_peripheral: bool = True
    preferred_bond_types: list[DihedralBondType] = Field(default_factory=list)
    selection_relaxation_allowed: bool = True
    artifact_kind: Optional[ArtifactBundleKind] = None
    source_round_preference: Optional[int] = None


class MicroscopicToolRequest(BaseModel):
    capability_name: MicroscopicCapabilityName
    structure_source: Optional[DiscoveryStructureSource] = None
    perform_new_calculation: bool = True
    optimize_ground_state: bool = True
    reuse_existing_artifacts_only: bool = False
    artifact_source_round: Optional[int] = None
    artifact_scope: Optional[str] = None
    artifact_bundle_id: Optional[str] = None
    artifact_kind: Optional[ArtifactBundleKind] = None
    artifact_member_id: Optional[str] = None
    artifact_member_ids: list[str] = Field(default_factory=list)
    target_selection_mode: MicroscopicTargetSelectionMode = "bundle_wide"
    descriptor_scope: list[str] = Field(default_factory=list)
    requested_observable_scope: list[str] = Field(default_factory=list)
    source_round_preference: Optional[int] = None
    min_relevance: Optional[DihedralRelevance] = None
    include_peripheral: Optional[bool] = None
    preferred_bond_types: list[DihedralBondType] = Field(default_factory=list)
    hard_exclude_dihedral_ids: list[str] = Field(default_factory=list)
    selection_relaxation_allowed: bool = True
    dihedral_id: Optional[str] = None
    dihedral_atom_indices: list[int] = Field(default_factory=list)
    conformer_id: Optional[str] = None
    conformer_ids: list[str] = Field(default_factory=list)
    max_conformers: Optional[int] = None
    snapshot_count: Optional[int] = None
    target_count: Optional[int] = None
    angle_offsets_deg: list[float] = Field(default_factory=list)
    state_window: list[int] = Field(default_factory=list)
    honor_exact_target: bool = True
    allow_fallback: bool = False
    deliverables: list[str] = Field(default_factory=list)
    budget_profile: MicroscopicBudgetProfile = "balanced"
    requested_route_summary: str = "No microscopic tool-request summary was provided."


class MicroscopicToolCall(BaseModel):
    call_id: str
    call_kind: MicroscopicToolCallKind
    request: MicroscopicToolRequest


class MicroscopicToolPlan(BaseModel):
    calls: list[MicroscopicToolCall] = Field(default_factory=list)
    requested_route_summary: str = "No microscopic tool-plan summary was provided."
    requested_deliverables: list[str] = Field(default_factory=list)
    selection_policy: SelectionPolicy = Field(default_factory=SelectionPolicy)
    normalization_notes: list[str] = Field(default_factory=list)
    failure_reporting: str = "Return a local failed or partial report if the selected microscopic capability cannot be completed."


class MicroscopicExecutionPlan(BaseModel):
    plan_version: str = "amesp_baseline_v1"
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    capability_route: MicroscopicCapabilityRoute = "baseline_bundle"
    microscopic_tool_plan: MicroscopicToolPlan = Field(default_factory=MicroscopicToolPlan)
    microscopic_tool_request: Optional[MicroscopicToolRequest] = None
    budget_profile: MicroscopicBudgetProfile = "balanced"
    requested_route_summary: str = "No microscopic route summary was provided."
    structure_source: MicroscopicStructureSource
    supported_scope: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    planning_unmet_constraints: list[str] = Field(default_factory=list)
    steps: list[MicroscopicExecutionStep] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    failure_reporting: str


class SharedStructureContext(BaseModel):
    input_smiles: str
    canonical_smiles: str
    charge: int
    multiplicity: int
    atom_count: int
    conformer_count: int
    selected_conformer_id: int
    prepared_xyz_path: str
    prepared_sdf_path: str
    summary_path: str
    rotatable_bond_count: int
    aromatic_ring_count: int
    ring_system_count: int
    hetero_atom_count: int
    branch_point_count: int
    donor_acceptor_partition_proxy: float
    planarity_proxy: float
    compactness_proxy: float
    torsion_candidate_count: int
    principal_span_proxy: float
    conformer_dispersion_proxy: float


class MoleculeIdentityContext(BaseModel):
    input_smiles: str
    canonical_smiles: Optional[str] = None
    molecular_formula: Optional[str] = None
    inchi: Optional[str] = None
    inchikey: Optional[str] = None


class MacroExecutionStep(BaseModel):
    step_id: str
    step_type: MacroPlanStepType
    description: str
    input_source: str
    expected_outputs: list[str] = Field(default_factory=list)


class MacroExecutionPlan(BaseModel):
    plan_version: str = "macro_context_v1"
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    structure_source: MacroStructureSource
    focus_areas: list[str] = Field(default_factory=list)
    supported_scope: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    steps: list[MacroExecutionStep] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    failure_reporting: str


class CaseMemoryEntry(BaseModel):
    case_id: Optional[str] = None
    smiles: str
    scaffold: Optional[str] = None
    initial_hypothesis: Optional[str] = None
    final_mechanism: Optional[str] = None
    final_confidence: Optional[float] = None
    key_supporting_evidence: list[str] = Field(default_factory=list)
    key_conflicts: list[str] = Field(default_factory=list)
    critical_turning_points: list[str] = Field(default_factory=list)
    useful_actions: list[str] = Field(default_factory=list)
    failed_actions: list[str] = Field(default_factory=list)
    capability_lessons: list[str] = Field(default_factory=list)
    final_gt_source: Optional[str] = None


class StrategyMemoryEntry(BaseModel):
    context_pattern: str
    recommended_action: str
    reason: str
    applicability_scope: Optional[str] = None


class ReliabilityMemoryEntry(BaseModel):
    signal_type: str
    source_type: str
    reliability_judgment: Literal["high", "medium", "low"]
    note: str


class AieMasState(BaseModel):
    case_id: Optional[str] = None
    user_query: str
    smiles: str
    round_idx: int = 0
    pending_agents: list[PendingAgent] = Field(default_factory=list)
    pending_agent_instructions: dict[PendingAgent, str] = Field(default_factory=dict)

    hypothesis_pool: list[HypothesisEntry] = Field(default_factory=list)
    current_hypothesis: Optional[str] = None
    confidence: Optional[float] = None
    runner_up_hypothesis: Optional[str] = None
    runner_up_confidence: Optional[float] = None
    reasoning_phase: ReasoningPhase = "portfolio_screening"
    agent_framing_mode: AgentFramingMode = "portfolio_neutral"
    portfolio_screening_complete: bool = False
    coverage_debt_hypotheses: list[str] = Field(default_factory=list)
    credible_alternative_hypotheses: list[str] = Field(default_factory=list)
    hypothesis_screening_ledger: list[HypothesisScreeningRecord] = Field(default_factory=list)
    portfolio_screening_summary: Optional[str] = None
    screening_focus_hypotheses: list[str] = Field(default_factory=list)
    screening_focus_summary: Optional[str] = None
    decision_pair: list[str] = Field(default_factory=list)
    decision_gate_status: DecisionGateStatus = "not_ready"
    verifier_supplement_target_pair: Optional[str] = None
    verifier_supplement_status: VerifierSupplementStatus = "missing"
    verifier_information_gain: VerifierInformationGain = "none"
    verifier_evidence_relation: VerifierEvidenceRelation = "no_new_info"
    verifier_supplement_summary: Optional[str] = None
    closure_justification_target_pair: Optional[str] = None
    closure_justification_status: ClosureJustificationStatus = "missing"
    closure_justification_evidence_source: Optional[ClosureJustificationEvidenceSource] = None
    closure_justification_basis: Optional[ClosureJustificationBasis] = None
    closure_justification_summary: Optional[str] = None
    pairwise_task_agent: Optional[PairwiseTaskAgent] = None
    pairwise_task_completed_for_pair: Optional[str] = None
    pairwise_task_outcome: PairwiseTaskOutcome = "not_run"
    pairwise_task_rationale: Optional[str] = None
    pairwise_resolution_mode: Optional[PairwiseTaskOutcome] = None
    pairwise_resolution_evidence_sources: list[str] = Field(default_factory=list)
    pairwise_resolution_summary: Optional[str] = None
    finalization_mode: FinalizationMode = "none"
    pairwise_verifier_completed_for_pair: Optional[str] = None
    pairwise_verifier_evidence_specificity: Optional[VerifierEvidenceSpecificity] = None
    planned_action_label: Optional[str] = None
    executed_action_labels: list[str] = Field(default_factory=list)
    executed_evidence_families: list[EvidenceFamily] = Field(default_factory=list)
    hypothesis_reweight_history: list[dict[str, str]] = Field(default_factory=list)

    planner_diagnosis_history: list[str] = Field(default_factory=list)
    planner_action_history: list[str] = Field(default_factory=list)

    macro_reports: list[AgentReport] = Field(default_factory=list)
    microscopic_reports: list[AgentReport] = Field(default_factory=list)
    verifier_reports: list[AgentReport] = Field(default_factory=list)
    active_round_reports: list[AgentReport] = Field(default_factory=list)

    working_memory: list[WorkingMemoryEntry] = Field(default_factory=list)
    latest_evidence_summary: Optional[str] = None
    latest_main_gap: Optional[str] = None
    latest_conflict_status: Optional[str] = None
    latest_hypothesis_uncertainty_note: Optional[str] = None
    latest_final_hypothesis_rationale: Optional[str] = None
    latest_capability_assessment: Optional[str] = None
    latest_stagnation_assessment: Optional[str] = None
    latest_contraction_reason: Optional[str] = None
    latest_information_gain_assessment: Optional[str] = None
    latest_gap_trend: Optional[str] = None
    stagnation_detected: bool = False
    capability_lesson_candidates: list[CapabilityLessonEntry] = Field(default_factory=list)
    next_microscopic_task: Optional[MicroscopicTaskSpec] = None
    last_microscopic_task: Optional[MicroscopicTaskSpec] = None
    shared_structure_status: SharedStructureStatus = "missing"
    shared_structure_context: Optional[SharedStructureContext] = None
    shared_structure_error: Optional[dict[str, Any]] = None
    molecule_identity_status: MoleculeIdentityStatus = "missing"
    molecule_identity_context: Optional[MoleculeIdentityContext] = None
    molecule_identity_error: Optional[dict[str, Any]] = None

    case_memory_hits: list[CaseMemoryEntry] = Field(default_factory=list)
    strategy_memory_hits: list[StrategyMemoryEntry] = Field(default_factory=list)
    reliability_memory_hits: list[ReliabilityMemoryEntry] = Field(default_factory=list)
    long_term_memory_path: Optional[str] = None

    last_planner_decision: Optional[PlannerDecision] = None
    last_planner_raw_response: Optional[dict[str, Any]] = None
    last_planner_normalized_response: Optional[dict[str, Any]] = None
    planner_response_history: list[dict[str, Any]] = Field(default_factory=list)
    final_answer: Optional[dict[str, Any]] = None
    state_snapshot: Optional[dict[str, Any]] = None
    finalize: bool = False
