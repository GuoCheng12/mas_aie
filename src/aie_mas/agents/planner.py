from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    AieMasState,
    CapabilityLessonEntry,
    HypothesisEntry,
    PlannerDecision,
)
from aie_mas.llm.openai_compatible import OpenAICompatiblePlannerClient
from aie_mas.memory.working import WorkingMemoryManager
from aie_mas.utils.prompts import PromptRepository


class PlannerInitialResponse(BaseModel):
    hypothesis_pool: list[HypothesisEntry]
    current_hypothesis: str
    confidence: float
    diagnosis: str
    action: str = "macro_and_microscopic"
    task_instruction: str = ""
    agent_task_instructions: dict[str, str] = Field(default_factory=dict)
    hypothesis_uncertainty_note: str = "Initial hypothesis uncertainty has not been assessed."
    capability_assessment: str = "Current specialized-agent capability has not been assessed."


class PlannerRoundResponse(BaseModel):
    diagnosis: str
    action: str
    current_hypothesis: str
    confidence: float
    needs_verifier: bool = False
    finalize: bool = False
    task_instruction: str = ""
    agent_task_instructions: dict[str, str] = Field(default_factory=dict)
    hypothesis_uncertainty_note: str = "Hypothesis uncertainty has not been assessed."
    final_hypothesis_rationale: str = ""
    capability_assessment: str = "Capability limits have not been assessed."
    stagnation_assessment: str = "Stagnation has not been assessed."
    contraction_reason: str = ""
    evidence_summary: str = "No additional evidence summary was provided."
    main_gap: str = "No main gap was provided."
    conflict_status: str = "none"
    information_gain_assessment: str = "Information gain has not been assessed."
    gap_trend: str = "Gap trend has not been assessed."
    stagnation_detected: bool = False
    capability_lesson_candidates: list[CapabilityLessonEntry] = Field(default_factory=list)


def _normalize_agent_task_instructions(raw_mapping: dict[str, str]) -> dict[str, str]:
    allowed_agents = {"macro", "microscopic", "verifier"}
    return {
        agent_name: instruction.strip()
        for agent_name, instruction in raw_mapping.items()
        if agent_name in allowed_agents and instruction.strip()
    }


def _serialize_hypothesis_pool(hypothesis_pool: list[HypothesisEntry]) -> list[dict[str, Any]]:
    return [entry.model_dump(mode="json") for entry in hypothesis_pool]


def _serialize_planner_decision(decision: PlannerDecision) -> dict[str, Any]:
    return decision.model_dump(mode="json")


def _planner_normalized_payload(
    *,
    decision: PlannerDecision,
    hypothesis_pool: list[HypothesisEntry] | None = None,
    evidence_summary: str | None = None,
    main_gap: str | None = None,
    conflict_status: str | None = None,
    hypothesis_uncertainty_note: str | None = None,
    final_hypothesis_rationale: str | None = None,
    capability_assessment: str | None = None,
    stagnation_assessment: str | None = None,
    contraction_reason: str | None = None,
    information_gain_assessment: str | None = None,
    gap_trend: str | None = None,
) -> dict[str, Any]:
    payload = {
        "decision": _serialize_planner_decision(decision),
    }
    if hypothesis_pool is not None:
        payload["hypothesis_pool"] = _serialize_hypothesis_pool(hypothesis_pool)
    if evidence_summary is not None:
        payload["evidence_summary"] = evidence_summary
    if main_gap is not None:
        payload["main_gap"] = main_gap
    if conflict_status is not None:
        payload["conflict_status"] = conflict_status
    if hypothesis_uncertainty_note is not None:
        payload["hypothesis_uncertainty_note"] = hypothesis_uncertainty_note
    if final_hypothesis_rationale is not None:
        payload["final_hypothesis_rationale"] = final_hypothesis_rationale
    if capability_assessment is not None:
        payload["capability_assessment"] = capability_assessment
    if stagnation_assessment is not None:
        payload["stagnation_assessment"] = stagnation_assessment
    if contraction_reason is not None:
        payload["contraction_reason"] = contraction_reason
    if information_gain_assessment is not None:
        payload["information_gain_assessment"] = information_gain_assessment
    if gap_trend is not None:
        payload["gap_trend"] = gap_trend
    return payload


def _normalize_final_hypothesis_rationale(
    *,
    raw_rationale: str | None,
    diagnosis: str,
    finalize: bool,
) -> str | None:
    if not finalize:
        return None
    rationale = (raw_rationale or "").strip()
    if rationale:
        return rationale
    return diagnosis.strip() or None


def _default_initial_agent_task_instructions(
    current_hypothesis: str,
    *,
    hypothesis_uncertainty_note: str,
    capability_assessment: str,
) -> dict[str, str]:
    return {
        "macro": (
            f"Assess macro-level structural evidence relevant to the current working hypothesis "
            f"'{current_hypothesis}'. Reuse the shared prepared structure context when available, summarize low-cost "
            f"structural indicators only, and stay within "
            f"current macro capability. Hypothesis uncertainty to keep in mind: {hypothesis_uncertainty_note}"
        ),
        "microscopic": (
            f"Run the first-round low-cost S0/S1 microscopic baseline task for the current working hypothesis "
            f"'{current_hypothesis}'. Reuse the shared prepared structure context when available. Prioritize semi-empirical or otherwise low-cost bounded evidence collection, "
            f"not heavy exhaustive geometry optimization. Report local microscopic results only, and do not attempt "
            f"mechanism discrimination beyond current microscopic capability. Capability note: {capability_assessment}"
        ),
    }


def _default_follow_up_task_instruction(
    action: str,
    current_hypothesis: str,
    payload: dict[str, Any],
) -> str | None:
    main_gap = payload.get("main_gap") or "clarify the unresolved signal."
    capability_assessment = payload.get("capability_assessment") or "Stay within current specialized-agent capability."
    contraction_reason = payload.get("contraction_reason") or ""
    shared_structure_note = payload.get("shared_structure_note") or ""
    if action == "macro":
        return (
            f"Collect additional macro-level structural evidence for the current working hypothesis "
            f"'{current_hypothesis}'. Focus on the current gap: {main_gap} "
            f"{shared_structure_note} "
            f"Only use low-cost structural proxies; do not attempt excited-state adjudication. "
            f"Capability note: {capability_assessment}"
        )
    if action == "microscopic":
        return (
            f"Collect additional microscopic evidence for the current working hypothesis "
            f"'{current_hypothesis}'. Focus on the current gap: {main_gap} "
            f"{shared_structure_note} "
            f"Keep the task low-cost and bounded to current microscopic capability. "
            f"{contraction_reason or capability_assessment}"
        )
    if action == "verifier":
        return (
            f"Retrieve external supervision evidence for the current working hypothesis "
            f"'{current_hypothesis}' and clarify the current gap: {main_gap} "
            f"Use verifier evidence because internal specialized-agent capability is currently insufficient "
            f"to close this gap safely."
        )
    return None


class PlannerBackend(Protocol):
    def plan_initial(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def plan_diagnosis(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def plan_reweight_or_finalize(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class OpenAIPlannerBackend:
    def __init__(
        self,
        config: AieMasConfig,
        verifier_threshold: float,
        client: OpenAICompatiblePlannerClient | None = None,
    ) -> None:
        self._config = config
        self._verifier_threshold = verifier_threshold
        self._client = client or OpenAICompatiblePlannerClient(config)

    def plan_initial(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.invoke_json_schema(
            messages=prompt_value_to_messages(rendered_prompt),
            response_model=PlannerInitialResponse,
            schema_name="planner_initial_response",
        )
        agent_task_instructions = _normalize_agent_task_instructions(response.agent_task_instructions)
        if not agent_task_instructions:
            agent_task_instructions = _normalize_agent_task_instructions(
                _default_initial_agent_task_instructions(
                    response.current_hypothesis,
                    hypothesis_uncertainty_note=response.hypothesis_uncertainty_note,
                    capability_assessment=response.capability_assessment,
                )
            )
        decision = PlannerDecision(
            diagnosis=response.diagnosis,
            action="macro_and_microscopic",
            current_hypothesis=response.current_hypothesis,
            confidence=self._clamp_confidence(response.confidence),
            needs_verifier=False,
            finalize=False,
            planned_agents=["macro", "microscopic"],
            task_instruction=response.task_instruction.strip()
            or "Dispatch first-round specialized macro and microscopic tasks for the current hypothesis.",
            agent_task_instructions=agent_task_instructions,  # type: ignore[arg-type]
            hypothesis_uncertainty_note=response.hypothesis_uncertainty_note,
            capability_assessment=response.capability_assessment,
            stagnation_assessment="No stagnation is present in the initial round.",
        )
        return {
            "hypothesis_pool": response.hypothesis_pool,
            "decision": decision,
            "raw_response": response.model_dump(mode="json"),
            "normalized_response": _planner_normalized_payload(
                decision=decision,
                hypothesis_pool=response.hypothesis_pool,
            ),
        }

    def plan_diagnosis(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.invoke_json_schema(
            messages=prompt_value_to_messages(rendered_prompt),
            response_model=PlannerRoundResponse,
            schema_name="planner_diagnosis_response",
        )
        return self._normalize_round_response(payload, response, post_verifier=False)

    def plan_reweight_or_finalize(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.invoke_json_schema(
            messages=prompt_value_to_messages(rendered_prompt),
            response_model=PlannerRoundResponse,
            schema_name="planner_reweight_response",
        )
        return self._normalize_round_response(payload, response, post_verifier=True)

    def _normalize_round_response(
        self,
        payload: dict[str, Any],
        response: PlannerRoundResponse,
        *,
        post_verifier: bool,
    ) -> dict[str, Any]:
        confidence = self._clamp_confidence(response.confidence)
        task_instruction = response.task_instruction.strip() or _default_follow_up_task_instruction(
            response.action,
            response.current_hypothesis,
            payload,
        )
        agent_task_instructions = _normalize_agent_task_instructions(response.agent_task_instructions)
        if not agent_task_instructions and task_instruction and response.action in {"macro", "microscopic", "verifier"}:
            agent_task_instructions = {response.action: task_instruction}
        final_hypothesis_rationale = _normalize_final_hypothesis_rationale(
            raw_rationale=response.final_hypothesis_rationale,
            diagnosis=response.diagnosis,
            finalize=response.finalize,
        )
        decision = PlannerDecision(
            diagnosis=response.diagnosis,
            action=self._normalize_action(response.action, post_verifier=post_verifier),
            current_hypothesis=response.current_hypothesis,
            confidence=confidence,
            needs_verifier=response.needs_verifier,
            finalize=response.finalize,
            planned_agents=[],
            task_instruction=task_instruction,
            agent_task_instructions=agent_task_instructions,  # type: ignore[arg-type]
            hypothesis_uncertainty_note=response.hypothesis_uncertainty_note,
            final_hypothesis_rationale=final_hypothesis_rationale,
            capability_assessment=response.capability_assessment,
            stagnation_assessment=response.stagnation_assessment,
            contraction_reason=response.contraction_reason,
            capability_lesson_candidates=list(response.capability_lesson_candidates),
            information_gain_assessment=response.information_gain_assessment,
            gap_trend=response.gap_trend,
            stagnation_detected=response.stagnation_detected,
        )

        evidence_summary = response.evidence_summary
        main_gap = response.main_gap
        conflict_status = response.conflict_status

        if not post_verifier:
            if confidence >= self._verifier_threshold:
                decision.action = "verifier"
                decision.needs_verifier = True
                decision.finalize = False
                # keep the Planner's global reasoning explicit when verifier is forced
                if not decision.contraction_reason:
                    decision.contraction_reason = (
                        "The Planner is conservatively contracting to verifier because internal confidence is already "
                        "high enough for an external check to be higher value than more internal expansion."
                    )
                decision.task_instruction = _default_follow_up_task_instruction(
                    "verifier",
                    decision.current_hypothesis,
                    {
                        "main_gap": main_gap,
                        "capability_assessment": decision.capability_assessment,
                        "contraction_reason": decision.contraction_reason,
                    },
                )
                decision.agent_task_instructions = _normalize_agent_task_instructions(
                    {"verifier": decision.task_instruction or ""}
                )  # type: ignore[assignment]
            elif decision.action == "finalize":
                decision.needs_verifier = False
                decision.finalize = True
                decision.task_instruction = None
                decision.agent_task_instructions = {}  # type: ignore[assignment]
                decision.final_hypothesis_rationale = _normalize_final_hypothesis_rationale(
                    raw_rationale=decision.final_hypothesis_rationale,
                    diagnosis=decision.diagnosis,
                    finalize=True,
                )
            decision.planned_agents = self._planned_agents_for_action(decision.action)
            if decision.action not in {"verifier", "finalize"}:
                decision.needs_verifier = False
                decision.finalize = False
                decision.final_hypothesis_rationale = None
                if decision.action in {"macro", "microscopic"} and not decision.agent_task_instructions:
                    decision.agent_task_instructions = _normalize_agent_task_instructions(
                        {decision.action: decision.task_instruction or ""}
                    )  # type: ignore[assignment]
        else:
            decision, conflict_status, main_gap = self._postprocess_reweight(decision, conflict_status, main_gap)

        return {
            "decision": decision,
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": conflict_status,
            "hypothesis_uncertainty_note": decision.hypothesis_uncertainty_note,
            "final_hypothesis_rationale": decision.final_hypothesis_rationale,
            "capability_assessment": decision.capability_assessment,
            "stagnation_assessment": decision.stagnation_assessment,
            "contraction_reason": decision.contraction_reason,
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
            "raw_response": response.model_dump(mode="json"),
            "normalized_response": _planner_normalized_payload(
                decision=decision,
                evidence_summary=evidence_summary,
                main_gap=main_gap,
                conflict_status=conflict_status,
                hypothesis_uncertainty_note=decision.hypothesis_uncertainty_note,
                final_hypothesis_rationale=decision.final_hypothesis_rationale,
                capability_assessment=decision.capability_assessment,
                stagnation_assessment=decision.stagnation_assessment,
                contraction_reason=decision.contraction_reason,
                information_gain_assessment=decision.information_gain_assessment,
                gap_trend=decision.gap_trend,
            ),
        }

    def _postprocess_reweight(
        self,
        decision: PlannerDecision,
        conflict_status: str,
        main_gap: str,
    ) -> tuple[PlannerDecision, str, str]:
        decision.needs_verifier = False
        decision.planned_agents = self._planned_agents_for_action(decision.action)
        if decision.action == "finalize":
            decision.finalize = True
            decision.task_instruction = None
            decision.agent_task_instructions = {}  # type: ignore[assignment]
            decision.final_hypothesis_rationale = _normalize_final_hypothesis_rationale(
                raw_rationale=decision.final_hypothesis_rationale,
                diagnosis=decision.diagnosis,
                finalize=True,
            )
        else:
            decision.finalize = False
            decision.final_hypothesis_rationale = None
            if not decision.task_instruction:
                decision.task_instruction = _default_follow_up_task_instruction(
                    decision.action,
                    decision.current_hypothesis,
                    {
                        "main_gap": main_gap,
                        "capability_assessment": decision.capability_assessment,
                        "contraction_reason": decision.contraction_reason,
                    },
                )
            if decision.action in {"macro", "microscopic"} and not decision.agent_task_instructions:
                decision.agent_task_instructions = _normalize_agent_task_instructions(
                    {decision.action: decision.task_instruction or ""}
                )  # type: ignore[assignment]
        return decision, conflict_status, main_gap

    def _normalize_action(self, action: str, *, post_verifier: bool) -> str:
        if post_verifier:
            return action if action in {"macro", "microscopic", "finalize"} else "microscopic"
        return action if action in {"macro", "microscopic", "verifier", "finalize"} else "microscopic"

    def _planned_agents_for_action(self, action: str) -> list[str]:
        if action == "macro":
            return ["macro"]
        if action == "microscopic":
            return ["microscopic"]
        if action == "verifier":
            return ["verifier"]
        return []

    def _clamp_confidence(self, confidence: float) -> float:
        return round(min(0.99, max(0.0, confidence)), 3)


class PlannerAgent:
    def __init__(
        self,
        prompts: PromptRepository,
        config: AieMasConfig,
        llm_client: OpenAICompatiblePlannerClient | None = None,
    ) -> None:
        self._prompts = prompts
        self._config = config
        self._working_memory = WorkingMemoryManager()
        self._backend = self._build_backend(config, llm_client)

    def plan_initial(self, state: AieMasState) -> dict[str, Any]:
        payload = {
            "user_query": state.user_query,
            "smiles": state.smiles,
            "shared_structure_status": state.shared_structure_status,
            "shared_structure_context": (
                state.shared_structure_context.model_dump(mode="json")
                if state.shared_structure_context is not None
                else None
            ),
            "runtime_context": {
                **self._config.runtime_context(),
                "microscopic_baseline_policy": (
                    "first-round microscopic work must stay low-cost and bounded; do not default to heavy exhaustive "
                    "DFT geometry optimization for large systems"
                ),
                "microscopic_supported_scope": (
                    "SMILES-to-3D preparation, low-cost Amesp aTB S0 optimization, bounded S1 vertical excitation"
                ),
            },
        }
        rendered_prompt = self._prompts.render("planner_initial", payload)
        return self._backend.plan_initial(rendered_prompt, payload)

    def plan_diagnosis(self, state: AieMasState) -> dict[str, Any]:
        latest_macro = state.macro_reports[-1].model_dump(mode="json") if state.macro_reports else None
        latest_microscopic = (
            state.microscopic_reports[-1].model_dump(mode="json") if state.microscopic_reports else None
        )
        latest_verifier = (
            state.verifier_reports[-1].model_dump(mode="json") if state.verifier_reports else None
        )
        payload = {
            "smiles": state.smiles,
            "current_hypothesis": state.current_hypothesis,
            "current_confidence": state.confidence,
            "working_memory_summary": [entry.model_dump(mode="json") for entry in state.working_memory],
            "recent_rounds_context": self._working_memory.build_recent_rounds_context(state),
            "recent_capability_context": self._working_memory.build_capability_context(state),
            "latest_macro_report": latest_macro,
            "latest_microscopic_report": latest_microscopic,
            "latest_verifier_report": latest_verifier,
            "hypothesis_pool": [entry.model_dump(mode="json") for entry in state.hypothesis_pool],
            "shared_structure_status": state.shared_structure_status,
            "shared_structure_context": (
                state.shared_structure_context.model_dump(mode="json")
                if state.shared_structure_context is not None
                else None
            ),
        }
        rendered_prompt = self._prompts.render("planner_diagnosis", payload)
        return self._backend.plan_diagnosis(rendered_prompt, payload)

    def plan_reweight_or_finalize(self, state: AieMasState) -> dict[str, Any]:
        payload = {
            "smiles": state.smiles,
            "current_hypothesis": state.current_hypothesis,
            "current_confidence": state.confidence,
            "working_memory_summary": [entry.model_dump(mode="json") for entry in state.working_memory],
            "recent_rounds_context": self._working_memory.build_recent_rounds_context(state),
            "recent_capability_context": self._working_memory.build_capability_context(state),
            "verifier_report": state.verifier_reports[-1].model_dump(mode="json")
            if state.verifier_reports
            else None,
            "recent_internal_evidence_summary": state.latest_evidence_summary,
            "hypothesis_pool": [entry.model_dump(mode="json") for entry in state.hypothesis_pool],
        }
        rendered_prompt = self._prompts.render("planner_reweight", payload)
        return self._backend.plan_reweight_or_finalize(rendered_prompt, payload)

    def _build_backend(
        self,
        config: AieMasConfig,
        llm_client: OpenAICompatiblePlannerClient | None,
    ) -> PlannerBackend:
        return OpenAIPlannerBackend(
            config=config,
            verifier_threshold=config.verifier_threshold,
            client=llm_client,
        )
