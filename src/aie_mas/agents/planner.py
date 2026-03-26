from __future__ import annotations

from typing import Any, Protocol

import re

from pydantic import BaseModel, Field

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    AieMasState,
    CapabilityLessonEntry,
    DecisionGateStatus,
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
    hypothesis_reweight_explanation: dict[str, str] = Field(default_factory=dict)
    decision_gate_status: DecisionGateStatus = "not_ready"


class PlannerRoundResponse(BaseModel):
    hypothesis_pool: list[HypothesisEntry] = Field(default_factory=list)
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
    hypothesis_reweight_explanation: dict[str, str] = Field(default_factory=dict)
    decision_gate_status: DecisionGateStatus = "not_ready"


ALLOWED_HYPOTHESIS_LABELS = ("ICT", "TICT", "ESIPT", "neutral aromatic", "unknown")
_HYPOTHESIS_LABEL_MAP = {
    "ict": "ICT",
    "tict": "TICT",
    "esipt": "ESIPT",
    "neutral aromatic": "neutral aromatic",
    "neutral-aromatic": "neutral aromatic",
    "neutral_aromatic": "neutral aromatic",
    "unknown": "unknown",
    "uncertain": "unknown",
    "undetermined": "unknown",
}
_HYPOTHESIS_ORDER = {label: idx for idx, label in enumerate(ALLOWED_HYPOTHESIS_LABELS)}
_EVIDENCE_SPECIFICITY_RANK = {
    "no_direct_hit": 0,
    "generic_review": 1,
    "close_family": 2,
    "exact_compound": 3,
}


def _normalize_hypothesis_label(raw_label: str | None) -> str | None:
    if raw_label is None:
        return None
    collapsed = re.sub(r"[\s_-]+", " ", raw_label.strip().lower())
    return _HYPOTHESIS_LABEL_MAP.get(collapsed)


def _dedupe_hypothesis_entries(entries: list[HypothesisEntry]) -> list[HypothesisEntry]:
    deduped: dict[str, HypothesisEntry] = {}
    for entry in entries:
        existing = deduped.get(entry.name)
        if existing is None:
            deduped[entry.name] = entry
            continue
        existing_confidence = existing.confidence if existing.confidence is not None else -1.0
        candidate_confidence = entry.confidence if entry.confidence is not None else -1.0
        if candidate_confidence > existing_confidence:
            deduped[entry.name] = entry
    return list(deduped.values())


def _normalize_confidence(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, float(value))


def _sorted_hypothesis_pool(
    pool: list[HypothesisEntry],
    *,
    preferred_top_label: str | None = None,
) -> list[HypothesisEntry]:
    return sorted(
        pool,
        key=lambda entry: (
            -_normalize_confidence(entry.confidence),
            entry.name != preferred_top_label,
            _HYPOTHESIS_ORDER.get(entry.name, len(_HYPOTHESIS_ORDER)),
        ),
    )


def _normalize_hypothesis_pool(
    raw_pool: list[HypothesisEntry],
    raw_current_hypothesis: str,
    *,
    fallback_pool: list[HypothesisEntry] | None = None,
    fallback_confidence: float | None = None,
) -> tuple[list[HypothesisEntry], str]:
    source_pool = raw_pool or fallback_pool or []
    normalized_entries: list[HypothesisEntry] = []
    for entry in source_pool:
        label = _normalize_hypothesis_label(entry.name)
        if label is None:
            continue
        normalized_entries.append(
            HypothesisEntry(
                name=label,
                confidence=entry.confidence,
                rationale=entry.rationale,
                candidate_strength=entry.candidate_strength,
            )
        )

    normalized_entries = _dedupe_hypothesis_entries(normalized_entries)
    current_hypothesis = _normalize_hypothesis_label(raw_current_hypothesis) or "unknown"
    entry_map = {entry.name: entry for entry in normalized_entries}
    baseline_total = sum(_normalize_confidence(entry.confidence) for entry in normalized_entries)
    if not normalized_entries:
        entry_map = {}

    for label in ALLOWED_HYPOTHESIS_LABELS:
        if label not in entry_map:
            entry_map[label] = HypothesisEntry(
                name=label,
                confidence=0.0,
                rationale=None,
                candidate_strength="weak" if label == "unknown" else "medium",
            )

    if raw_pool == [] and fallback_pool:
        target_entry = entry_map[current_hypothesis]
        target_confidence = fallback_confidence if fallback_confidence is not None else target_entry.confidence
        target_confidence = min(1.0, max(0.0, _normalize_confidence(target_confidence)))
        remaining_total = sum(
            _normalize_confidence(entry_map[label].confidence)
            for label in ALLOWED_HYPOTHESIS_LABELS
            if label != current_hypothesis
        )
        for label in ALLOWED_HYPOTHESIS_LABELS:
            if label == current_hypothesis:
                entry_map[label].confidence = target_confidence
                continue
            if remaining_total > 0:
                entry_map[label].confidence = (
                    _normalize_confidence(entry_map[label].confidence) / remaining_total * max(0.0, 1.0 - target_confidence)
                )
            else:
                entry_map[label].confidence = 0.0
    elif not source_pool and fallback_confidence is not None:
        target_confidence = min(1.0, max(0.0, _normalize_confidence(fallback_confidence)))
        for label in ALLOWED_HYPOTHESIS_LABELS:
            if label == current_hypothesis:
                entry_map[label].confidence = target_confidence
            elif label == "unknown":
                entry_map[label].confidence = max(0.0, 1.0 - target_confidence)
            else:
                entry_map[label].confidence = 0.0

    total_confidence = sum(_normalize_confidence(entry.confidence) for entry in entry_map.values())
    if total_confidence <= 0.0:
        for label in ALLOWED_HYPOTHESIS_LABELS:
            entry_map[label].confidence = 1.0 if label == current_hypothesis else 0.0
    else:
        for entry in entry_map.values():
            entry.confidence = round(_normalize_confidence(entry.confidence) / total_confidence, 6)

    normalized_pool = _sorted_hypothesis_pool(
        list(entry_map.values()),
        preferred_top_label=current_hypothesis,
    )
    current_hypothesis = normalized_pool[0].name
    normalized_pool = _sorted_hypothesis_pool(
        normalized_pool,
        preferred_top_label=current_hypothesis,
    )
    return normalized_pool, current_hypothesis


def _runner_up_from_pool(hypothesis_pool: list[HypothesisEntry], current_hypothesis: str) -> tuple[str | None, float | None]:
    for entry in hypothesis_pool:
        if entry.name != current_hypothesis:
            return entry.name, _normalize_confidence(entry.confidence)
    return None, None


def _normalize_reweight_explanation(
    raw_explanation: dict[str, str],
    *,
    hypothesis_pool: list[HypothesisEntry],
) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for raw_label, explanation in raw_explanation.items():
        label = _normalize_hypothesis_label(raw_label)
        if label is None:
            continue
        text = explanation.strip()
        if text:
            normalized[label] = text
    for entry in hypothesis_pool:
        normalized.setdefault(
            entry.name,
            f"Reweighted to {(_normalize_confidence(entry.confidence)):.3f} from the current evidence chain.",
        )
    return normalized


def _decision_pair_from_pool(hypothesis_pool: list[HypothesisEntry]) -> list[str]:
    if len(hypothesis_pool) < 2:
        return [hypothesis_pool[0].name] if hypothesis_pool else []
    return [hypothesis_pool[0].name, hypothesis_pool[1].name]


def _decision_pair_key(decision_pair: list[str]) -> str | None:
    if len(decision_pair) < 2:
        return None
    return f"{decision_pair[0]}__vs__{decision_pair[1]}"


def _pairwise_decision_question(champion_hypothesis: str, challenger_hypothesis: str, main_gap: str) -> str:
    return (
        f"Distinguish '{champion_hypothesis}' versus '{challenger_hypothesis}' for the current molecule. "
        f"The unresolved discriminator is: {main_gap} "
        f"Retrieve the most decisive evidence that can separate these two mechanisms rather than generic background."
    )


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
    payload["runner_up_hypothesis"] = decision.runner_up_hypothesis
    payload["runner_up_confidence"] = decision.runner_up_confidence
    payload["hypothesis_reweight_explanation"] = dict(decision.hypothesis_reweight_explanation)
    payload["decision_pair"] = list(decision.decision_pair)
    payload["decision_gate_status"] = decision.decision_gate_status
    payload["pairwise_verifier_completed_for_pair"] = decision.pairwise_verifier_completed_for_pair
    payload["pairwise_verifier_evidence_specificity"] = decision.pairwise_verifier_evidence_specificity
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
        champion_hypothesis = str(payload.get("champion_hypothesis") or current_hypothesis)
        challenger_hypothesis = str(payload.get("challenger_hypothesis") or "unknown")
        pairwise_question = str(
            payload.get("pairwise_decision_question")
            or _pairwise_decision_question(champion_hypothesis, challenger_hypothesis, main_gap)
        )
        return (
            f"Run a pairwise external verification between champion hypothesis '{champion_hypothesis}' and "
            f"challenger hypothesis '{challenger_hypothesis}'. Current gap: {main_gap} "
            f"Decision question: {pairwise_question} "
            f"Focus on the strongest discriminator between these two mechanisms rather than generic background support."
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
        hypothesis_pool, current_hypothesis = _normalize_hypothesis_pool(
            response.hypothesis_pool,
            response.current_hypothesis,
            fallback_confidence=response.confidence,
        )
        runner_up_hypothesis, runner_up_confidence = _runner_up_from_pool(hypothesis_pool, current_hypothesis)
        agent_task_instructions = _normalize_agent_task_instructions(response.agent_task_instructions)
        if not agent_task_instructions:
            agent_task_instructions = _normalize_agent_task_instructions(
                _default_initial_agent_task_instructions(
                    current_hypothesis,
                    hypothesis_uncertainty_note=response.hypothesis_uncertainty_note,
                    capability_assessment=response.capability_assessment,
                )
            )
        decision = PlannerDecision(
            diagnosis=response.diagnosis,
            action="macro_and_microscopic",
            current_hypothesis=current_hypothesis,
            confidence=self._clamp_confidence(_normalize_confidence(hypothesis_pool[0].confidence)),
            needs_verifier=False,
            finalize=False,
            planned_agents=["macro", "microscopic"],
            task_instruction=response.task_instruction.strip()
            or "Dispatch first-round specialized macro and microscopic tasks for the current hypothesis.",
            agent_task_instructions=agent_task_instructions,  # type: ignore[arg-type]
            hypothesis_uncertainty_note=response.hypothesis_uncertainty_note,
            capability_assessment=response.capability_assessment,
            stagnation_assessment="No stagnation is present in the initial round.",
            runner_up_hypothesis=runner_up_hypothesis,
            runner_up_confidence=runner_up_confidence,
            hypothesis_reweight_explanation=_normalize_reweight_explanation(
                response.hypothesis_reweight_explanation,
                hypothesis_pool=hypothesis_pool,
            ),
            decision_pair=_decision_pair_from_pool(hypothesis_pool),
            decision_gate_status="not_ready",
        )
        return {
            "hypothesis_pool": hypothesis_pool,
            "decision": decision,
            "raw_response": {
                **response.model_dump(mode="json"),
                "hypothesis_pool": [entry.model_dump(mode="json") for entry in hypothesis_pool],
                "current_hypothesis": current_hypothesis,
            },
            "normalized_response": _planner_normalized_payload(
                decision=decision,
                hypothesis_pool=hypothesis_pool,
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
        existing_pool = [
            HypothesisEntry.model_validate(entry)
            for entry in list(payload.get("hypothesis_pool") or [])
            if isinstance(entry, dict)
        ]
        hypothesis_pool, current_hypothesis = _normalize_hypothesis_pool(
            response.hypothesis_pool,
            response.current_hypothesis,
            fallback_pool=existing_pool,
            fallback_confidence=response.confidence,
        )
        runner_up_hypothesis, runner_up_confidence = _runner_up_from_pool(hypothesis_pool, current_hypothesis)
        task_instruction = response.task_instruction.strip() or _default_follow_up_task_instruction(
            response.action,
            current_hypothesis,
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
            current_hypothesis=current_hypothesis,
            confidence=self._clamp_confidence(_normalize_confidence(hypothesis_pool[0].confidence)),
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
            runner_up_hypothesis=runner_up_hypothesis,
            runner_up_confidence=runner_up_confidence,
            hypothesis_reweight_explanation=_normalize_reweight_explanation(
                response.hypothesis_reweight_explanation,
                hypothesis_pool=hypothesis_pool,
            ),
            decision_pair=_decision_pair_from_pool(hypothesis_pool),
            decision_gate_status=response.decision_gate_status,
        )

        evidence_summary = response.evidence_summary
        main_gap = response.main_gap
        conflict_status = response.conflict_status

        if not post_verifier:
            decision = self._apply_pre_verifier_gate(
                decision=decision,
                main_gap=main_gap,
            )
            if decision.action == "verifier":
                decision.action = "verifier"
                decision.needs_verifier = True
                decision.finalize = False
                if not decision.contraction_reason:
                    decision.contraction_reason = (
                        "The Planner is entering pairwise verifier mode because the current top hypothesis needs a "
                        "top1-vs-top2 external discriminator before any final mechanism output."
                    )
                decision.task_instruction = _default_follow_up_task_instruction(
                    "verifier",
                    decision.current_hypothesis,
                    {
                        "main_gap": main_gap,
                        "champion_hypothesis": decision.current_hypothesis,
                        "challenger_hypothesis": decision.runner_up_hypothesis,
                        "pairwise_decision_question": _pairwise_decision_question(
                            decision.current_hypothesis,
                            decision.runner_up_hypothesis or "unknown",
                            main_gap,
                        ),
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
                decision.decision_gate_status = "not_ready"
                if decision.action in {"macro", "microscopic"} and not decision.agent_task_instructions:
                    decision.agent_task_instructions = _normalize_agent_task_instructions(
                        {decision.action: decision.task_instruction or ""}
                    )  # type: ignore[assignment]
        else:
            decision, conflict_status, main_gap = self._postprocess_reweight(
                decision,
                conflict_status,
                main_gap,
                payload,
            )

        return {
            "hypothesis_pool": hypothesis_pool,
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
            "raw_response": {
                **response.model_dump(mode="json"),
                "hypothesis_pool": [entry.model_dump(mode="json") for entry in hypothesis_pool],
                "current_hypothesis": current_hypothesis,
            },
            "normalized_response": _planner_normalized_payload(
                decision=decision,
                hypothesis_pool=hypothesis_pool,
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
        payload: dict[str, Any],
    ) -> tuple[PlannerDecision, str, str]:
        decision.needs_verifier = False
        decision.planned_agents = self._planned_agents_for_action(decision.action)
        current_pair_key = _decision_pair_key(decision.decision_pair)
        latest_verifier_report = payload.get("verifier_report")
        completed_pair_key, verifier_specificity = self._latest_pairwise_verifier_state(
            latest_verifier_report,
            decision.decision_pair,
        )
        decision.pairwise_verifier_completed_for_pair = completed_pair_key
        decision.pairwise_verifier_evidence_specificity = verifier_specificity
        gate_ready = self._can_finalize_after_pairwise(decision)
        if current_pair_key is not None and current_pair_key != completed_pair_key:
            decision.action = "verifier"
            decision.finalize = False
            decision.needs_verifier = True
            decision.planned_agents = ["verifier"]
            decision.decision_gate_status = "needs_pairwise_verifier"
            decision.final_hypothesis_rationale = None
            decision.task_instruction = _default_follow_up_task_instruction(
                "verifier",
                decision.current_hypothesis,
                {
                    "main_gap": main_gap,
                    "champion_hypothesis": decision.current_hypothesis,
                    "challenger_hypothesis": decision.runner_up_hypothesis,
                    "pairwise_decision_question": _pairwise_decision_question(
                        decision.current_hypothesis,
                        decision.runner_up_hypothesis or "unknown",
                        main_gap,
                    ),
                    "capability_assessment": decision.capability_assessment,
                    "contraction_reason": decision.contraction_reason,
                },
            )
            decision.agent_task_instructions = _normalize_agent_task_instructions(
                {"verifier": decision.task_instruction or ""}
            )  # type: ignore[assignment]
            return decision, conflict_status, main_gap
        if decision.action == "finalize":
            if gate_ready:
                decision.finalize = True
                decision.decision_gate_status = "ready_to_finalize"
                decision.task_instruction = None
                decision.agent_task_instructions = {}  # type: ignore[assignment]
                decision.final_hypothesis_rationale = _normalize_final_hypothesis_rationale(
                    raw_rationale=decision.final_hypothesis_rationale,
                    diagnosis=decision.diagnosis,
                    finalize=True,
                )
            else:
                decision.finalize = False
                decision.action = "microscopic"
                decision.planned_agents = ["microscopic"]
                decision.decision_gate_status = (
                    "blocked_by_missing_decisive_evidence"
                    if current_pair_key == completed_pair_key
                    else "needs_pairwise_verifier"
                )
                decision.final_hypothesis_rationale = None
                decision.task_instruction = _default_follow_up_task_instruction(
                    "microscopic",
                    decision.current_hypothesis,
                    {
                        "main_gap": (
                            f"Top1-vs-top2 remains unresolved between '{decision.current_hypothesis}' and "
                            f"'{decision.runner_up_hypothesis or 'unknown'}'. {main_gap}"
                        ),
                        "capability_assessment": decision.capability_assessment,
                        "contraction_reason": decision.contraction_reason,
                    },
                )
                decision.agent_task_instructions = _normalize_agent_task_instructions(
                    {"microscopic": decision.task_instruction or ""}
                )  # type: ignore[assignment]
        else:
            decision.finalize = False
            decision.final_hypothesis_rationale = None
            if current_pair_key != completed_pair_key:
                decision.decision_gate_status = "needs_pairwise_verifier"
            elif gate_ready:
                decision.decision_gate_status = "ready_to_finalize"
            else:
                decision.decision_gate_status = "blocked_by_missing_decisive_evidence"
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

    def _apply_pre_verifier_gate(
        self,
        *,
        decision: PlannerDecision,
        main_gap: str,
    ) -> PlannerDecision:
        needs_pairwise = (
            len(decision.decision_pair) == 2
            and (
                decision.confidence >= self._verifier_threshold
                or decision.action in {"verifier", "finalize"}
            )
        )
        if needs_pairwise:
            decision.action = "verifier"
            decision.decision_gate_status = "needs_pairwise_verifier"
            return decision
        decision.decision_gate_status = "not_ready"
        return decision

    def _decision_margin(self, decision: PlannerDecision) -> float:
        runner_up = decision.runner_up_confidence or 0.0
        return round((decision.confidence or 0.0) - runner_up, 6)

    def _latest_pairwise_verifier_state(
        self,
        latest_verifier_report: Any,
        decision_pair: list[str],
    ) -> tuple[str | None, str | None]:
        if not isinstance(latest_verifier_report, dict):
            return None, None
        structured = latest_verifier_report.get("structured_results")
        if not isinstance(structured, dict):
            return None, None
        pair_key = structured.get("pairwise_verifier_completed_for_pair")
        specificity = structured.get("pairwise_verifier_evidence_specificity")
        if isinstance(pair_key, str) and pair_key and pair_key == _decision_pair_key(decision_pair):
            return pair_key, str(specificity) if specificity else None
        return None, str(specificity) if specificity else None

    def _can_finalize_after_pairwise(self, decision: PlannerDecision) -> bool:
        current_pair_key = _decision_pair_key(decision.decision_pair)
        if current_pair_key is None:
            return False
        if decision.pairwise_verifier_completed_for_pair != current_pair_key:
            return False
        specificity = decision.pairwise_verifier_evidence_specificity or "no_direct_hit"
        if _EVIDENCE_SPECIFICITY_RANK.get(specificity, 0) < _EVIDENCE_SPECIFICITY_RANK["close_family"]:
            return False
        return self._decision_margin(decision) >= self._config.finalize_margin_threshold

    def _normalize_action(self, action: str, *, post_verifier: bool) -> str:
        if post_verifier:
            return action if action in {"macro", "microscopic", "verifier", "finalize"} else "microscopic"
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
            "molecule_identity_status": state.molecule_identity_status,
            "molecule_identity_context": (
                state.molecule_identity_context.model_dump(mode="json")
                if state.molecule_identity_context is not None
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
            "runner_up_hypothesis": state.runner_up_hypothesis,
            "runner_up_confidence": state.runner_up_confidence,
            "decision_pair": list(state.decision_pair),
            "decision_gate_status": state.decision_gate_status,
            "pairwise_verifier_completed_for_pair": state.pairwise_verifier_completed_for_pair,
            "pairwise_verifier_evidence_specificity": state.pairwise_verifier_evidence_specificity,
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
            "molecule_identity_status": state.molecule_identity_status,
            "molecule_identity_context": (
                state.molecule_identity_context.model_dump(mode="json")
                if state.molecule_identity_context is not None
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
            "runner_up_hypothesis": state.runner_up_hypothesis,
            "runner_up_confidence": state.runner_up_confidence,
            "decision_pair": list(state.decision_pair),
            "decision_gate_status": state.decision_gate_status,
            "pairwise_verifier_completed_for_pair": state.pairwise_verifier_completed_for_pair,
            "pairwise_verifier_evidence_specificity": state.pairwise_verifier_evidence_specificity,
            "working_memory_summary": [entry.model_dump(mode="json") for entry in state.working_memory],
            "recent_rounds_context": self._working_memory.build_recent_rounds_context(state),
            "recent_capability_context": self._working_memory.build_capability_context(state),
            "verifier_report": state.verifier_reports[-1].model_dump(mode="json")
            if state.verifier_reports
            else None,
            "recent_internal_evidence_summary": state.latest_evidence_summary,
            "hypothesis_pool": [entry.model_dump(mode="json") for entry in state.hypothesis_pool],
            "molecule_identity_status": state.molecule_identity_status,
            "molecule_identity_context": (
                state.molecule_identity_context.model_dump(mode="json")
                if state.molecule_identity_context is not None
                else None
            ),
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
