from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

PlannerAction = Literal["macro_and_microscopic", "macro", "microscopic", "verifier", "finalize"]
PendingAgent = Literal["macro", "microscopic", "verifier"]


class HypothesisEntry(BaseModel):
    name: str
    confidence: Optional[float] = None
    rationale: Optional[str] = None


class AgentReport(BaseModel):
    agent_name: Literal["microscopic", "macro", "verifier"]
    task_received: str
    tool_calls: list[str] = Field(default_factory=list)
    raw_results: dict[str, Any] = Field(default_factory=dict)
    structured_results: dict[str, Any] = Field(default_factory=dict)
    status: Literal["success", "partial", "failed"] = "success"
    planner_readable_report: str


class PlannerDecision(BaseModel):
    diagnosis: str
    action: PlannerAction
    current_hypothesis: str
    confidence: float
    needs_verifier: bool = False
    finalize: bool = False
    planned_agents: list[PendingAgent] = Field(default_factory=list)


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

    case_memory_hits: list[CaseMemoryEntry] = Field(default_factory=list)
    strategy_memory_hits: list[StrategyMemoryEntry] = Field(default_factory=list)
    reliability_memory_hits: list[ReliabilityMemoryEntry] = Field(default_factory=list)
    long_term_memory_path: Optional[str] = None

    last_planner_decision: Optional[PlannerDecision] = None
    final_answer: Optional[dict[str, Any]] = None
    state_snapshot: Optional[dict[str, Any]] = None
    finalize: bool = False
