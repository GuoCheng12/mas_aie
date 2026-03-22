from __future__ import annotations

import uuid
from typing import Any, Callable, Optional

from aie_mas.agents.planner import PlannerAgent
from aie_mas.agents.result_agents import MacroAgent, MicroscopicAgent, VerifierAgent
from aie_mas.compat.langgraph import END, StateGraph
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState, MicroscopicTaskSpec, PlannerDecision
from aie_mas.memory.long_term import LongTermMemoryStore
from aie_mas.memory.working import WorkingMemoryManager
from aie_mas.tools.factory import build_toolset
from aie_mas.utils.prompts import PromptRepository


class AieMasWorkflow:
    def __init__(self, config: Optional[AieMasConfig] = None) -> None:
        self.config = config or AieMasConfig()
        self.config.ensure_runtime_dirs()
        self.config.assert_supported_runtime()
        self.prompts = PromptRepository(self.config.prompts_dir)
        self.planner = PlannerAgent(self.prompts, config=self.config)
        toolset = build_toolset(self.config)
        self.macro_agent = MacroAgent(tool=toolset.macro_tool, prompts=self.prompts)
        self.microscopic_agent = MicroscopicAgent(
            s0_tool=toolset.s0_tool,
            s1_tool=toolset.s1_tool,
            targeted_tool=toolset.targeted_micro_tool,
            prompts=self.prompts,
        )
        self.verifier_agent = VerifierAgent(tool=toolset.verifier_tool, prompts=self.prompts)
        self.working_memory = WorkingMemoryManager()
        self.long_term_memory = (
            LongTermMemoryStore(self.config.memory_dir)
            if self.config.enable_long_term_memory
            else None
        )

    def build(self):
        graph = StateGraph(AieMasState)
        graph.add_node("ingest_user_query", self.ingest_user_query)
        graph.add_node("planner_initial", self.planner_initial)
        graph.add_node("run_macro", self.run_macro)
        graph.add_node("run_microscopic", self.run_microscopic)
        graph.add_node("planner_diagnosis", self.planner_diagnosis)
        graph.add_node("run_verifier", self.run_verifier)
        graph.add_node("planner_reweight_or_finalize", self.planner_reweight_or_finalize)
        graph.add_node("update_working_memory", self.update_working_memory)
        graph.add_node("update_long_term_memory", self.update_long_term_memory)
        graph.add_node("final_output", self.final_output)

        graph.set_entry_point("ingest_user_query")
        graph.add_edge("ingest_user_query", "planner_initial")
        graph.add_edge("planner_initial", "run_macro")
        graph.add_edge("run_microscopic", "planner_diagnosis")
        graph.add_edge("planner_diagnosis", "update_working_memory")
        graph.add_edge("run_verifier", "planner_reweight_or_finalize")
        graph.add_edge("planner_reweight_or_finalize", "update_working_memory")
        graph.add_edge("update_long_term_memory", "final_output")
        graph.add_edge("final_output", END)
        graph.add_conditional_edges(
            "run_macro",
            self.route_after_macro,
            {
                "run_microscopic": "run_microscopic",
                "planner_diagnosis": "planner_diagnosis",
            },
        )
        graph.add_conditional_edges(
            "update_working_memory",
            self.route_after_working_memory,
            {
                "run_macro": "run_macro",
                "run_microscopic": "run_microscopic",
                "run_verifier": "run_verifier",
                "update_long_term_memory": "update_long_term_memory",
                "final_output": "final_output",
            },
        )
        return graph.compile()

    def ingest_user_query(self, state: AieMasState) -> AieMasState:
        if state.case_id is None:
            state.case_id = uuid.uuid4().hex[:12]
        if self.long_term_memory is None:
            state.case_memory_hits = []
            state.strategy_memory_hits = []
            state.reliability_memory_hits = []
            state.long_term_memory_path = None
            return state

        state.case_memory_hits = self.long_term_memory.load_case_hits(
            state.smiles,
            exclude_case_ids={state.case_id},
        )
        state.strategy_memory_hits = self.long_term_memory.load_strategy_hits(state.current_hypothesis)
        state.reliability_memory_hits = self.long_term_memory.load_reliability_hits()
        state.long_term_memory_path = str(self.long_term_memory.memory_dir)
        return state

    def planner_initial(self, state: AieMasState) -> AieMasState:
        result = self.planner.plan_initial(state)
        decision = result["decision"]
        state.hypothesis_pool = result["hypothesis_pool"]
        state.current_hypothesis = decision.current_hypothesis
        state.confidence = decision.confidence
        state.pending_agents = decision.planned_agents
        state.pending_agent_instructions = dict(decision.agent_task_instructions)
        state.last_planner_decision = decision
        state.planner_diagnosis_history.append(decision.diagnosis)
        state.planner_action_history.append(decision.action)
        state.latest_evidence_summary = "Initial planning used only the user query and SMILES."
        state.latest_main_gap = "Internal macro and microscopic evidence are both missing."
        state.latest_conflict_status = "none"
        state.latest_hypothesis_uncertainty_note = decision.hypothesis_uncertainty_note
        state.latest_capability_assessment = decision.capability_assessment
        state.latest_stagnation_assessment = decision.stagnation_assessment
        state.latest_contraction_reason = decision.contraction_reason
        state.capability_lesson_candidates = list(decision.capability_lesson_candidates)
        microscopic_instruction = (
            decision.agent_task_instructions.get("microscopic")
            or "Run fixed first-stage S0/S1 optimization."
        )
        state.next_microscopic_task = MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective=microscopic_instruction,
            target_property="baseline excited-state geometry",
        )
        return state

    def run_macro(self, state: AieMasState) -> AieMasState:
        task_instruction = state.pending_agent_instructions.get(
            "macro",
            "Run low-cost structural and empirical analysis for the current hypothesis.",
        )
        report = self.macro_agent.run(
            smiles=state.smiles,
            task_received=task_instruction,
            current_hypothesis=state.current_hypothesis or "unknown",
        )
        state.macro_reports.append(report)
        state.active_round_reports.append(report)
        state.pending_agents = [agent for agent in state.pending_agents if agent != "macro"]
        state.pending_agent_instructions.pop("macro", None)
        return state

    def run_microscopic(self, state: AieMasState) -> AieMasState:
        task_spec = state.next_microscopic_task or MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="fallback-baseline",
            objective="Run fixed S0/S1 optimization.",
            target_property="baseline excited-state geometry",
        )
        task_instruction = state.pending_agent_instructions.get("microscopic", task_spec.objective)
        report = self.microscopic_agent.run(
            smiles=state.smiles,
            task_received=task_instruction,
            task_spec=task_spec,
            current_hypothesis=state.current_hypothesis or "unknown",
        )
        state.microscopic_reports.append(report)
        state.active_round_reports.append(report)
        state.pending_agents = [agent for agent in state.pending_agents if agent != "microscopic"]
        state.pending_agent_instructions.pop("microscopic", None)
        state.last_microscopic_task = task_spec
        state.next_microscopic_task = None
        return state

    def planner_diagnosis(self, state: AieMasState) -> AieMasState:
        result = self.planner.plan_diagnosis(state)
        return self._apply_planner_result(state, result)

    def run_verifier(self, state: AieMasState) -> AieMasState:
        task_instruction = state.pending_agent_instructions.get(
            "verifier",
            "Retrieve external supervision evidence cards for the current hypothesis.",
        )
        report = self.verifier_agent.run(
            smiles=state.smiles,
            current_hypothesis=state.current_hypothesis or "unknown",
            task_received=task_instruction,
        )
        state.verifier_reports.append(report)
        state.active_round_reports.append(report)
        state.pending_agents = [agent for agent in state.pending_agents if agent != "verifier"]
        state.pending_agent_instructions.pop("verifier", None)
        return state

    def planner_reweight_or_finalize(self, state: AieMasState) -> AieMasState:
        result = self.planner.plan_reweight_or_finalize(state)
        return self._apply_planner_result(state, result)

    def update_working_memory(self, state: AieMasState) -> AieMasState:
        return self.working_memory.append_round_summary(state)

    def update_long_term_memory(self, state: AieMasState) -> AieMasState:
        if self.long_term_memory is not None and state.finalize:
            self.long_term_memory.write_case_entry(state)
        return state

    def final_output(self, state: AieMasState) -> AieMasState:
        decision = state.last_planner_decision
        state.final_answer = {
            "case_id": state.case_id,
            "smiles": state.smiles,
            "current_hypothesis": state.current_hypothesis,
            "confidence": state.confidence,
            "diagnosis": decision.diagnosis if decision else None,
            "action": decision.action if decision else None,
            "finalize": state.finalize,
            "hypothesis_uncertainty_note": state.latest_hypothesis_uncertainty_note,
            "capability_assessment": state.latest_capability_assessment,
            "stagnation_assessment": state.latest_stagnation_assessment,
            "contraction_reason": state.latest_contraction_reason,
            "working_memory_rounds": len(state.working_memory),
        }
        state.state_snapshot = state.model_dump(mode="json")
        return state

    def route_after_macro(self, state: AieMasState) -> str:
        if "microscopic" in state.pending_agents:
            return "run_microscopic"
        return "planner_diagnosis"

    def route_after_working_memory(self, state: AieMasState) -> str:
        if state.finalize or (state.last_planner_decision and state.last_planner_decision.finalize):
            return "update_long_term_memory"
        if state.round_idx >= self.config.max_rounds:
            return "final_output"
        if state.last_planner_decision is None:
            return "final_output"

        action = state.last_planner_decision.action
        if action == "verifier":
            return "run_verifier"
        if action == "macro":
            return "run_macro"
        if action == "microscopic":
            return "run_microscopic"
        if action == "finalize":
            return "update_long_term_memory"
        return "final_output"

    def _apply_planner_result(self, state: AieMasState, result: dict[str, object]) -> AieMasState:
        decision = result["decision"]
        state.last_planner_decision = decision  # type: ignore[assignment]
        state.current_hypothesis = decision.current_hypothesis  # type: ignore[union-attr]
        state.confidence = decision.confidence  # type: ignore[union-attr]
        state.pending_agents = decision.planned_agents  # type: ignore[union-attr]
        state.pending_agent_instructions = dict(decision.agent_task_instructions)  # type: ignore[union-attr]
        state.finalize = decision.finalize  # type: ignore[union-attr]
        state.latest_evidence_summary = str(result["evidence_summary"])
        state.latest_main_gap = str(result["main_gap"])
        state.latest_conflict_status = str(result["conflict_status"])
        state.latest_hypothesis_uncertainty_note = str(
            result.get("hypothesis_uncertainty_note") or decision.hypothesis_uncertainty_note or ""
        ) or None
        state.latest_capability_assessment = str(
            result.get("capability_assessment") or decision.capability_assessment or ""
        ) or None
        state.latest_stagnation_assessment = str(
            result.get("stagnation_assessment") or decision.stagnation_assessment or ""
        ) or None
        state.latest_contraction_reason = str(
            result.get("contraction_reason") or decision.contraction_reason or ""
        ) or None
        state.latest_information_gain_assessment = str(
            result.get("information_gain_assessment") or decision.information_gain_assessment or ""
        ) or None
        state.latest_gap_trend = str(result.get("gap_trend") or decision.gap_trend or "") or None
        state.stagnation_detected = bool(decision.stagnation_detected)
        state.capability_lesson_candidates = list(decision.capability_lesson_candidates)
        state.next_microscopic_task = self._build_next_microscopic_task(state, decision)
        state.planner_diagnosis_history.append(decision.diagnosis)  # type: ignore[union-attr]
        state.planner_action_history.append(decision.action)  # type: ignore[union-attr]
        return state

    def _build_next_microscopic_task(
        self,
        state: AieMasState,
        decision: PlannerDecision,
    ) -> MicroscopicTaskSpec | None:
        if decision.action != "microscopic":
            return None
        return MicroscopicTaskSpec(
            mode="targeted_follow_up",
            task_label=f"round-{state.round_idx + 1}-targeted-micro",
            objective=(
                decision.agent_task_instructions.get("microscopic")
                or decision.task_instruction
                or (
                    f"Investigate the current microscopic gap for hypothesis "
                    f"'{decision.current_hypothesis}': {state.latest_main_gap or 'refine the unresolved signal.'}"
                )
            ),
            target_property=state.latest_conflict_status or "micro_consistency",
        )


def build_graph(config: Optional[AieMasConfig] = None):
    return AieMasWorkflow(config).build()


def normalize_graph_result(result: Any) -> AieMasState:
    if isinstance(result, AieMasState):
        return result
    if isinstance(result, dict):
        return AieMasState.model_validate(result)
    raise TypeError(f"Unsupported graph result type: {type(result)!r}")


def invoke_graph(graph: Any, initial_state: AieMasState) -> AieMasState:
    return normalize_graph_result(graph.invoke(initial_state))


def get_runner(config: Optional[AieMasConfig] = None) -> Callable[[AieMasState], AieMasState]:
    graph = build_graph(config)

    def _runner(initial_state: AieMasState) -> AieMasState:
        return invoke_graph(graph, initial_state)

    return _runner
