from __future__ import annotations

import uuid
from typing import Callable, Optional

from aie_mas.agents.planner import PlannerAgent
from aie_mas.agents.result_agents import MacroAgent, MicroscopicAgent, VerifierAgent
from aie_mas.compat.langgraph import END, StateGraph
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState
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
        self.planner = PlannerAgent(self.prompts, verifier_threshold=self.config.verifier_threshold)
        toolset = build_toolset(self.config)
        self.macro_agent = MacroAgent(tool=toolset.macro_tool)
        self.microscopic_agent = MicroscopicAgent(
            s0_tool=toolset.s0_tool,
            s1_tool=toolset.s1_tool,
        )
        self.verifier_agent = VerifierAgent(tool=toolset.verifier_tool)
        self.working_memory = WorkingMemoryManager()
        self.long_term_memory = LongTermMemoryStore(self.config.memory_dir)

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
        state.case_memory_hits = self.long_term_memory.load_case_hits(state.smiles)
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
        state.last_planner_decision = decision
        state.planner_diagnosis_history.append(decision.diagnosis)
        state.planner_action_history.append(decision.action)
        state.latest_evidence_summary = "Initial planning used only the user query and SMILES."
        state.latest_main_gap = "Internal macro and microscopic evidence are both missing."
        state.latest_conflict_status = "none"
        return state

    def run_macro(self, state: AieMasState) -> AieMasState:
        report = self.macro_agent.run(
            smiles=state.smiles,
            task_received="Run low-cost structural and empirical analysis for the current hypothesis.",
        )
        state.macro_reports.append(report)
        state.active_round_reports.append(report)
        state.pending_agents = [agent for agent in state.pending_agents if agent != "macro"]
        return state

    def run_microscopic(self, state: AieMasState) -> AieMasState:
        report = self.microscopic_agent.run(
            smiles=state.smiles,
            task_received="Run fixed first-stage S0/S1 optimization and return templated results.",
        )
        state.microscopic_reports.append(report)
        state.active_round_reports.append(report)
        state.pending_agents = [agent for agent in state.pending_agents if agent != "microscopic"]
        return state

    def planner_diagnosis(self, state: AieMasState) -> AieMasState:
        result = self.planner.plan_diagnosis(state)
        return self._apply_planner_result(state, result)

    def run_verifier(self, state: AieMasState) -> AieMasState:
        report = self.verifier_agent.run(
            smiles=state.smiles,
            current_hypothesis=state.current_hypothesis or "unknown",
            task_received="Retrieve external supervision evidence cards for the current hypothesis.",
        )
        state.verifier_reports.append(report)
        state.active_round_reports.append(report)
        state.pending_agents = [agent for agent in state.pending_agents if agent != "verifier"]
        return state

    def planner_reweight_or_finalize(self, state: AieMasState) -> AieMasState:
        result = self.planner.plan_reweight_or_finalize(state)
        return self._apply_planner_result(state, result)

    def update_working_memory(self, state: AieMasState) -> AieMasState:
        return self.working_memory.append_round_summary(state)

    def update_long_term_memory(self, state: AieMasState) -> AieMasState:
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
        state.finalize = decision.finalize  # type: ignore[union-attr]
        state.latest_evidence_summary = str(result["evidence_summary"])
        state.latest_main_gap = str(result["main_gap"])
        state.latest_conflict_status = str(result["conflict_status"])
        state.planner_diagnosis_history.append(decision.diagnosis)  # type: ignore[union-attr]
        state.planner_action_history.append(decision.action)  # type: ignore[union-attr]
        return state


def build_graph(config: Optional[AieMasConfig] = None):
    return AieMasWorkflow(config).build()


def get_runner(config: Optional[AieMasConfig] = None) -> Callable[[AieMasState], AieMasState]:
    graph = build_graph(config)
    return graph.invoke
