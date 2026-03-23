from __future__ import annotations

import uuid
from typing import Any, Callable, Literal, Optional, TypedDict

from aie_mas.agents.planner import PlannerAgent
from aie_mas.agents.result_agents import MacroAgent, MicroscopicAgent, VerifierAgent
from aie_mas.compat.langgraph import END, StateGraph
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState, MicroscopicTaskSpec, PlannerDecision
from aie_mas.memory.long_term import LongTermMemoryStore
from aie_mas.memory.working import WorkingMemoryManager
from aie_mas.tools.factory import build_toolset
from aie_mas.utils.prompts import PromptRepository


class GraphProgressEvent(TypedDict):
    phase: Literal["start", "end"]
    node: str
    round: int
    agent: str
    case_id: Optional[str]
    current_hypothesis: Optional[str]
    details: dict[str, Any]


class AieMasWorkflow:
    def __init__(
        self,
        config: Optional[AieMasConfig] = None,
        progress_callback: Optional[Callable[[GraphProgressEvent], None]] = None,
    ) -> None:
        self.config = config or AieMasConfig()
        self.progress_callback = progress_callback
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
            amesp_tool=toolset.amesp_micro_tool,
            prompts=self.prompts,
            tools_work_dir=self.config.tools_work_dir,
            config=self.config,
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
        graph.add_node("ingest_user_query", self._with_progress("ingest_user_query", self.ingest_user_query))
        graph.add_node("planner_initial", self._with_progress("planner_initial", self.planner_initial))
        graph.add_node("run_macro", self._with_progress("run_macro", self.run_macro))
        graph.add_node("run_microscopic", self._with_progress("run_microscopic", self.run_microscopic))
        graph.add_node("planner_diagnosis", self._with_progress("planner_diagnosis", self.planner_diagnosis))
        graph.add_node("run_verifier", self._with_progress("run_verifier", self.run_verifier))
        graph.add_node(
            "planner_reweight_or_finalize",
            self._with_progress("planner_reweight_or_finalize", self.planner_reweight_or_finalize),
        )
        graph.add_node(
            "update_working_memory",
            self._with_progress("update_working_memory", self.update_working_memory),
        )
        graph.add_node(
            "update_long_term_memory",
            self._with_progress("update_long_term_memory", self.update_long_term_memory),
        )
        graph.add_node("final_output", self._with_progress("final_output", self.final_output))

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
            recent_rounds_context=self.working_memory.build_recent_rounds_context(state),
            available_artifacts=(
                dict(state.microscopic_reports[-1].generated_artifacts)
                if state.microscopic_reports
                else {}
            ),
            case_id=state.case_id,
            round_index=state.round_idx + 1,
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

    def _with_progress(
        self,
        node_name: str,
        func: Callable[[AieMasState], AieMasState],
    ) -> Callable[[AieMasState], AieMasState]:
        def _wrapped(state: AieMasState) -> AieMasState:
            self._emit_progress("start", node_name, state)
            updated_state = func(state)
            self._emit_progress("end", node_name, updated_state)
            return updated_state

        return _wrapped

    def _emit_progress(
        self,
        phase: Literal["start", "end"],
        node_name: str,
        state: AieMasState,
    ) -> None:
        if self.progress_callback is None:
            return
        event: GraphProgressEvent = {
            "phase": phase,
            "node": node_name,
            "round": self._node_round(node_name, state, phase),
            "agent": self._node_agent(node_name),
            "case_id": state.case_id,
            "current_hypothesis": state.current_hypothesis,
            "details": self._progress_details(node_name, state, phase),
        }
        self.progress_callback(event)

    def _node_round(
        self,
        node_name: str,
        state: AieMasState,
        phase: Literal["start", "end"],
    ) -> int:
        if node_name == "ingest_user_query":
            return 0
        if phase == "end" and node_name in {"update_working_memory", "update_long_term_memory", "final_output"}:
            return state.round_idx
        return state.round_idx + 1

    def _node_agent(self, node_name: str) -> str:
        mapping = {
            "ingest_user_query": "system",
            "planner_initial": "planner",
            "planner_diagnosis": "planner",
            "planner_reweight_or_finalize": "planner",
            "run_macro": "macro",
            "run_microscopic": "microscopic",
            "run_verifier": "verifier",
            "update_working_memory": "memory",
            "update_long_term_memory": "memory",
            "final_output": "final",
        }
        return mapping.get(node_name, "system")

    def _progress_details(
        self,
        node_name: str,
        state: AieMasState,
        phase: Literal["start", "end"],
    ) -> dict[str, Any]:
        if phase == "start":
            details: dict[str, Any] = {}
            if node_name == "run_macro":
                details["task_instruction"] = state.pending_agent_instructions.get("macro")
            elif node_name == "run_microscopic":
                details["task_instruction"] = state.pending_agent_instructions.get("microscopic")
                details["task_spec"] = (
                    state.next_microscopic_task.model_dump(mode="json")
                    if state.next_microscopic_task
                    else None
                )
            elif node_name == "run_verifier":
                details["task_instruction"] = state.pending_agent_instructions.get("verifier")
            elif node_name.startswith("planner") and state.current_hypothesis:
                details["current_hypothesis"] = state.current_hypothesis
            return details

        if node_name in {"planner_initial", "planner_diagnosis", "planner_reweight_or_finalize"}:
            if state.last_planner_decision is None:
                return {}
            return {
                "diagnosis": state.last_planner_decision.diagnosis,
                "action": state.last_planner_decision.action,
                "confidence": state.last_planner_decision.confidence,
                "task_instruction": state.last_planner_decision.task_instruction,
                "agent_task_instructions": dict(state.last_planner_decision.agent_task_instructions),
                "hypothesis_uncertainty_note": state.last_planner_decision.hypothesis_uncertainty_note,
                "capability_assessment": state.last_planner_decision.capability_assessment,
            }
        if node_name == "run_macro" and state.macro_reports:
            report = state.macro_reports[-1]
            return self._report_details(report)
        if node_name == "run_microscopic" and state.microscopic_reports:
            report = state.microscopic_reports[-1]
            return self._report_details(report)
        if node_name == "run_verifier" and state.verifier_reports:
            report = state.verifier_reports[-1]
            return self._report_details(report)
        if node_name == "update_working_memory" and state.working_memory:
            entry = state.working_memory[-1]
            return {
                "round_id": entry.round_id,
                "action_taken": entry.action_taken,
                "main_gap": entry.main_gap,
                "next_action": entry.next_action,
                "evidence_summary": entry.evidence_summary,
                "diagnosis_summary": entry.diagnosis_summary,
                "local_uncertainty_summary": entry.local_uncertainty_summary,
                "agent_reports": [agent_entry.model_dump(mode="json") for agent_entry in entry.agent_reports],
            }
        if node_name == "final_output" and state.final_answer is not None:
            return dict(state.final_answer)
        return {}

    def _report_details(self, report: Any) -> dict[str, Any]:
        return {
            "agent_name": report.agent_name,
            "status": report.status,
            "task_received": report.task_received,
            "task_understanding": report.task_understanding,
            "reasoning_summary": report.reasoning_summary,
            "execution_plan": report.execution_plan,
            "result_summary": report.result_summary,
            "remaining_local_uncertainty": report.remaining_local_uncertainty,
            "generated_artifacts": dict(report.generated_artifacts),
        }


def build_graph(
    config: Optional[AieMasConfig] = None,
    progress_callback: Optional[Callable[[GraphProgressEvent], None]] = None,
):
    return AieMasWorkflow(config, progress_callback=progress_callback).build()


def normalize_graph_result(result: Any) -> AieMasState:
    if isinstance(result, AieMasState):
        return result
    if isinstance(result, dict):
        return AieMasState.model_validate(result)
    raise TypeError(f"Unsupported graph result type: {type(result)!r}")


def invoke_graph(graph: Any, initial_state: AieMasState) -> AieMasState:
    return normalize_graph_result(graph.invoke(initial_state))


def get_runner(
    config: Optional[AieMasConfig] = None,
    progress_callback: Optional[Callable[[GraphProgressEvent], None]] = None,
) -> Callable[[AieMasState], AieMasState]:
    graph = build_graph(config, progress_callback=progress_callback)

    def _runner(initial_state: AieMasState) -> AieMasState:
        return invoke_graph(graph, initial_state)

    return _runner
