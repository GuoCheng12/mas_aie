from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

PlannerAction = Literal["macro_and_microscopic", "macro", "microscopic", "verifier", "finalize"]
PendingAgent = Literal["macro", "microscopic", "verifier"]
MicroscopicTaskMode = Literal["baseline_s0_s1", "targeted_follow_up"]
MicroscopicPlanStepType = Literal["structure_prep", "s0_optimization", "s1_vertical_excitation"]
MicroscopicStructureSource = Literal["prepared_from_smiles", "existing_prepared_structure"]


class HypothesisEntry(BaseModel):
    name: str
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    candidate_strength: Optional[Literal["strong", "medium", "weak"]] = None


class AgentReport(BaseModel):
    agent_name: Literal["microscopic", "macro", "verifier"]
    task_received: str
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


class WorkingMemoryAgentEntry(BaseModel):
    agent_name: Literal["microscopic", "macro", "verifier"]
    task_received: str
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
    needs_verifier: bool = False
    finalize: bool = False
    planned_agents: list[PendingAgent] = Field(default_factory=list)
    task_instruction: Optional[str] = None
    agent_task_instructions: dict[PendingAgent, str] = Field(default_factory=dict)
    hypothesis_uncertainty_note: Optional[str] = None
    capability_assessment: Optional[str] = None
    stagnation_assessment: Optional[str] = None
    contraction_reason: Optional[str] = None
    capability_lesson_candidates: list[CapabilityLessonEntry] = Field(default_factory=list)
    information_gain_assessment: Optional[str] = None
    gap_trend: Optional[str] = None
    stagnation_detected: bool = False


class WorkingMemoryEntry(BaseModel):
    round_id: int
    current_hypothesis: str
    confidence: float
    action_taken: str
    evidence_summary: str
    diagnosis_summary: str
    main_gap: str
    conflict_status: str
    next_action: str
    planner_task_instruction: Optional[str] = None
    planner_agent_task_instructions: dict[PendingAgent, str] = Field(default_factory=dict)
    hypothesis_uncertainty_note: Optional[str] = None
    capability_assessment: Optional[str] = None
    stagnation_assessment: Optional[str] = None
    contraction_reason: Optional[str] = None
    information_gain_assessment: Optional[str] = None
    gap_trend: Optional[str] = None
    stagnation_detected: bool = False
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


class MicroscopicExecutionPlan(BaseModel):
    plan_version: str = "amesp_baseline_v1"
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    structure_source: MicroscopicStructureSource
    supported_scope: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    steps: list[MicroscopicExecutionStep] = Field(default_factory=list)
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
    latest_capability_assessment: Optional[str] = None
    latest_stagnation_assessment: Optional[str] = None
    latest_contraction_reason: Optional[str] = None
    latest_information_gain_assessment: Optional[str] = None
    latest_gap_trend: Optional[str] = None
    stagnation_detected: bool = False
    capability_lesson_candidates: list[CapabilityLessonEntry] = Field(default_factory=list)
    next_microscopic_task: Optional[MicroscopicTaskSpec] = None
    last_microscopic_task: Optional[MicroscopicTaskSpec] = None

    case_memory_hits: list[CaseMemoryEntry] = Field(default_factory=list)
    strategy_memory_hits: list[StrategyMemoryEntry] = Field(default_factory=list)
    reliability_memory_hits: list[ReliabilityMemoryEntry] = Field(default_factory=list)
    long_term_memory_path: Optional[str] = None

    last_planner_decision: Optional[PlannerDecision] = None
    final_answer: Optional[dict[str, Any]] = None
    state_snapshot: Optional[dict[str, Any]] = None
    finalize: bool = False
