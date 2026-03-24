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


def _strength_from_confidence(confidence: float) -> str:
    if confidence >= 0.5:
        return "strong"
    if confidence >= 0.3:
        return "medium"
    return "weak"


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


def _mock_initial_hypothesis_setup() -> tuple[list[HypothesisEntry], str, float, str, str]:
    hypothesis_pool = [
        HypothesisEntry(
            name="restriction of intramolecular motion (RIM)-dominated AIE",
            confidence=0.38,
            rationale="Generic fallback candidate under the mock Planner backend.",
            candidate_strength=_strength_from_confidence(0.38),  # type: ignore[arg-type]
        ),
        HypothesisEntry(
            name="ICT-assisted emission with aggregation-enabled rigidification",
            confidence=0.31,
            rationale="Generic fallback alternative under the mock Planner backend.",
            candidate_strength=_strength_from_confidence(0.31),  # type: ignore[arg-type]
        ),
        HypothesisEntry(
            name="packing-assisted excimer or aggregate-state emission",
            confidence=0.22,
            rationale="Generic fallback aggregate-state alternative under the mock Planner backend.",
            candidate_strength=_strength_from_confidence(0.22),  # type: ignore[arg-type]
        ),
    ]
    current_hypothesis = hypothesis_pool[0].name
    confidence = hypothesis_pool[0].confidence or 0.38
    hypothesis_uncertainty_note = (
        "This is a generic mock fallback hypothesis pool rather than chemistry-specific reasoning. "
        "Use planner_backend='openai_sdk' when you want the Planner to form the hypothesis pool through LLM reasoning."
    )
    capability_assessment = (
        "Current specialized agents can only collect low-cost structural signals, low-cost bounded S0/S1 microscopic "
        "evidence, and mock verifier evidence. The first-round microscopic baseline should prioritize computational "
        "efficiency plus usable local evidence rather than heavy exhaustive geometry optimization. They cannot directly "
        "prove a final photophysical mechanism, so the Planner must keep the early hypothesis conservative."
    )
    return hypothesis_pool, current_hypothesis, confidence, hypothesis_uncertainty_note, capability_assessment


def _collect_local_uncertainties(*reports: dict[str, Any]) -> list[str]:
    uncertainties: list[str] = []
    for report in reports:
        if not report:
            continue
        uncertainty = str(report.get("remaining_local_uncertainty") or "").strip()
        if uncertainty and uncertainty != "Remaining local uncertainty was not provided.":
            uncertainties.append(uncertainty)
    return uncertainties


def _verifier_topic_summary(cards: list[dict[str, Any]]) -> str:
    topics: list[str] = []
    for card in cards:
        for tag in card.get("topic_tags", []):
            tag_text = str(tag).strip().lower()
            if tag_text and tag_text not in topics:
                topics.append(tag_text)
    return ", ".join(topics) if topics else "no specific external topics"


def _mock_verifier_tag_profile(current_hypothesis: str) -> tuple[set[str], set[str]]:
    hypothesis = current_hypothesis.lower()
    if any(token in hypothesis for token in ("restriction", "rotation", "motion", "rim", "rir")):
        return {"restriction"}, {"ict"}
    if "ict" in hypothesis or "charge transfer" in hypothesis:
        return {"ict"}, {"restriction"}
    if any(token in hypothesis for token in ("aggregate", "packing", "excimer")):
        return {"aggregation", "packing"}, {"ict"}
    return set(), {"ict"}


def _interpret_mock_verifier_cards(
    current_hypothesis: str,
    cards: list[dict[str, Any]],
) -> dict[str, Any]:
    support_tags, conflict_tags = _mock_verifier_tag_profile(current_hypothesis)
    support_cards: list[dict[str, Any]] = []
    conflict_cards: list[dict[str, Any]] = []
    neutral_cards: list[dict[str, Any]] = []

    for card in cards:
        tags = {str(tag).strip().lower() for tag in card.get("topic_tags", []) if str(tag).strip()}
        if support_tags and tags & support_tags:
            support_cards.append(card)
        elif conflict_tags and tags & conflict_tags:
            conflict_cards.append(card)
        else:
            neutral_cards.append(card)

    conflict_topics = sorted(
        {
            str(tag).strip().lower()
            for card in conflict_cards
            for tag in card.get("topic_tags", [])
            if str(tag).strip()
        }
    )
    support_topics = sorted(
        {
            str(tag).strip().lower()
            for card in support_cards
            for tag in card.get("topic_tags", [])
            if str(tag).strip()
        }
    )
    return {
        "support_cards": support_cards,
        "conflict_cards": conflict_cards,
        "neutral_cards": neutral_cards,
        "support_count": len(support_cards),
        "conflict_count": len(conflict_cards),
        "neutral_count": len(neutral_cards),
        "support_topics": support_topics,
        "conflict_topics": conflict_topics,
        "topic_summary": _verifier_topic_summary(cards),
    }


def _has_meaningful_uncertainty(report: dict[str, Any]) -> bool:
    uncertainty = str(report.get("remaining_local_uncertainty") or "").strip()
    return bool(
        uncertainty
        and uncertainty != "Remaining local uncertainty was not provided."
    )


def _best_alternative_hypothesis(
    current_hypothesis: str,
    hypothesis_pool: list[dict[str, Any]],
) -> str:
    ranked_entries = sorted(
        (
            HypothesisEntry.model_validate(entry)
            for entry in hypothesis_pool
            if entry.get("name") and entry.get("name") != current_hypothesis
        ),
        key=lambda entry: entry.confidence or 0.0,
        reverse=True,
    )
    if ranked_entries:
        return ranked_entries[0].name
    return current_hypothesis


def _derive_capability_lesson_candidates(
    *,
    blocking_agents: list[str],
    main_gap: str,
    capability_assessment: str,
    contraction_reason: str | None,
) -> list[CapabilityLessonEntry]:
    if not contraction_reason:
        return []
    return [
        CapabilityLessonEntry(
            agent_name=agent_name,  # type: ignore[arg-type]
            blocked_task_pattern=main_gap,
            observed_limitation=capability_assessment,
            recommended_contraction=contraction_reason,
        )
        for agent_name in blocking_agents
    ]


class PlannerBackend(Protocol):
    def plan_initial(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def plan_diagnosis(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def plan_reweight_or_finalize(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        ...


class MockPlannerBackend:
    def __init__(self, verifier_threshold: float) -> None:
        self._verifier_threshold = verifier_threshold

    def plan_initial(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _ = rendered_prompt
        (
            hypothesis_pool,
            current_hypothesis,
            confidence,
            hypothesis_uncertainty_note,
            capability_assessment,
        ) = _mock_initial_hypothesis_setup()
        agent_task_instructions = _default_initial_agent_task_instructions(
            current_hypothesis,
            hypothesis_uncertainty_note=hypothesis_uncertainty_note,
            capability_assessment=capability_assessment,
        )
        shared_structure_status = payload.get("shared_structure_status", "missing")
        shared_structure_note = {
            "ready": "A shared prepared 3D structure context is already available for the first round.",
            "failed": "Shared 3D structure preparation failed, so specialized agents may need to degrade to fallback behavior.",
        }.get(shared_structure_status, "Shared 3D structure context is not yet available.")
        diagnosis = (
            f"Current task: assess the likely emission mechanism for SMILES {payload['smiles']}. "
            f"The leading working hypothesis is {current_hypothesis}. "
            f"Hypothesis uncertainty: {hypothesis_uncertainty_note} "
            f"{shared_structure_note} "
            "This remains preliminary because only the initial task context and bounded structural inputs are available so far. "
            "The first round should therefore collect both macro structural evidence and low-cost microscopic S0/S1 "
            f"baseline evidence before any external verification or finalization. Capability note: "
            f"{capability_assessment}"
        )
        return {
            "hypothesis_pool": hypothesis_pool,
            "decision": PlannerDecision(
                diagnosis=diagnosis,
                action="macro_and_microscopic",
                current_hypothesis=current_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["macro", "microscopic"],
                task_instruction=(
                    "Dispatch first-round specialized macro and microscopic tasks for the current hypothesis."
                ),
                agent_task_instructions=_normalize_agent_task_instructions(agent_task_instructions),
                hypothesis_uncertainty_note=hypothesis_uncertainty_note,
                capability_assessment=capability_assessment,
                stagnation_assessment="No stagnation is present in the initial round.",
            ),
        }

    def plan_diagnosis(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _ = rendered_prompt
        macro_report = payload["latest_macro_report"] or {}
        microscopic_report = payload["latest_microscopic_report"] or {}
        macro_results = macro_report.get("structured_results", {})
        micro_results = microscopic_report.get("structured_results", {})
        macro_task_understanding = str(macro_report.get("task_understanding") or "").strip()
        macro_reasoning_summary = str(macro_report.get("reasoning_summary") or "").strip()
        macro_execution_plan = str(macro_report.get("execution_plan") or "").strip()
        macro_result_summary = str(macro_report.get("result_summary") or "").strip()
        micro_task_understanding = str(microscopic_report.get("task_understanding") or "").strip()
        micro_reasoning_summary = str(microscopic_report.get("reasoning_summary") or "").strip()
        micro_execution_plan = str(microscopic_report.get("execution_plan") or "").strip()
        micro_result_summary = str(microscopic_report.get("result_summary") or "").strip()
        local_uncertainty_bits = _collect_local_uncertainties(macro_report, microscopic_report)
        recent_rounds_context = payload.get("recent_rounds_context", [])
        recent_capability_context = payload.get("recent_capability_context", {})
        repeated_main_gaps = recent_capability_context.get("repeated_main_gaps", [])
        repeated_actions = recent_capability_context.get("repeated_actions", [])
        repeated_local_uncertainties = recent_capability_context.get("repeated_local_uncertainties", [])
        low_information_round_ids = recent_capability_context.get("low_information_round_ids", [])
        recent_gap_values = [
            str(entry.get("main_gap") or "").strip()
            for entry in recent_rounds_context
            if str(entry.get("main_gap") or "").strip()
        ]
        recent_action_values = [
            str(entry.get("action_taken") or "").strip()
            for entry in recent_rounds_context
            if str(entry.get("action_taken") or "").strip()
        ]
        shared_structure_note = {
            "ready": "Reuse the shared prepared structure context that is already available for this case.",
            "failed": "Shared 3D structure preparation previously failed, so any follow-up must stay compatible with fallback behavior.",
        }.get(payload.get("shared_structure_status"), "")
        recent_gap_repetition_detected = (
            len(recent_gap_values) >= 2 and len(set(recent_gap_values[-2:])) == 1
        )
        recent_action_repetition_detected = (
            len(recent_action_values) >= 2 and len(set(recent_action_values[-2:])) == 1
        )

        confidence = float(payload["current_confidence"] or 0.4)
        evidence_bits: list[str] = []
        support_score = 0.0

        if macro_results:
            evidence_bits.append(
                "macro evidence added aromatic count "
                f"{macro_results.get('aromatic_atom_count', 0)} and flexibility proxy "
                f"{macro_results.get('flexibility_proxy', 0)}"
            )
            if macro_results.get("aromatic_atom_count", 0) >= 6:
                support_score += 0.11
            if macro_results.get("branch_point_count", 0) >= 1:
                support_score += 0.11
            if macro_results.get("flexibility_proxy", 0.0) >= 2.0:
                support_score += 0.08
            if macro_task_understanding:
                evidence_bits.append(f"macro task understanding: {macro_task_understanding}")
            if macro_reasoning_summary and macro_reasoning_summary != "Reasoning summary was not provided.":
                evidence_bits.append(f"macro reasoning summary: {macro_reasoning_summary}")
            if macro_execution_plan:
                evidence_bits.append(f"macro execution plan: {macro_execution_plan}")
            if macro_result_summary:
                evidence_bits.append(f"macro agent summary: {macro_result_summary}")

        if micro_results:
            evidence_bits.append(
                "microscopic evidence added geometry-change proxy "
                f"{micro_results.get('geometry_change_proxy', 0)} and oscillator proxy "
                f"{micro_results.get('oscillator_strength_proxy', 0)}"
            )
            if micro_results.get("relaxation_gap", 0.0) >= 0.4:
                support_score += 0.12
            if micro_results.get("geometry_change_proxy", 1.0) <= 0.45:
                support_score += 0.06
            if micro_results.get("oscillator_strength_proxy", 0.0) >= 0.55:
                support_score += 0.07
            if micro_task_understanding:
                evidence_bits.append(f"microscopic task understanding: {micro_task_understanding}")
            if micro_reasoning_summary and micro_reasoning_summary != "Reasoning summary was not provided.":
                evidence_bits.append(f"microscopic reasoning summary: {micro_reasoning_summary}")
            if micro_execution_plan:
                evidence_bits.append(f"microscopic execution plan: {micro_execution_plan}")
            if micro_result_summary:
                evidence_bits.append(f"microscopic agent summary: {micro_result_summary}")
        if local_uncertainty_bits:
            evidence_bits.append(
                "remaining local uncertainty: " + " ".join(local_uncertainty_bits)
            )

        confidence = round(min(0.89, confidence + support_score), 3)
        evidence_impact = "strengthens" if support_score >= 0.22 else "is still insufficient for"
        evidence_summary = "; ".join(evidence_bits) if evidence_bits else "no new internal evidence was added"
        if recent_rounds_context:
            evidence_summary = (
                f"Recent-round window reviewed: {len(recent_rounds_context)} round(s). {evidence_summary}"
            )
        unresolved = (
            " ".join(local_uncertainty_bits)
            if local_uncertainty_bits
            else "External supervision has not checked whether the current internal signal is consistent."
        )
        main_gap = "Verifier evidence is required before a temporary conclusion can be trusted."
        low_signal_micro = (
            micro_results
            and float(micro_results.get("relaxation_gap", 0.0)) < 0.2
            and float(micro_results.get("oscillator_strength_proxy", 0.0)) < 0.4
        )
        capability_limit_triggered = bool(repeated_local_uncertainties) or bool(low_signal_micro)
        if repeated_main_gaps and repeated_actions:
            capability_limit_triggered = True
        if recent_gap_repetition_detected and recent_action_repetition_detected:
            capability_limit_triggered = True

        if str(payload["current_hypothesis"]).startswith("ICT-assisted"):
            hypothesis_uncertainty_note = (
                "The ICT-like hypothesis remains plausible, but the current evidence still does not separate pure "
                "charge-transfer behavior from aggregation-enabled rigidification or mixed pathways."
            )
        elif capability_limit_triggered:
            hypothesis_uncertainty_note = (
                "The current hypothesis remains uncertain because the internal evidence is not yet discriminative enough "
                "to separate it clearly from nearby alternatives under the present mock setup."
            )
        else:
            hypothesis_uncertainty_note = (
                "The current hypothesis still has meaningful uncertainty because the internal evidence has not yet "
                "isolated the dominant mechanism from nearby alternatives."
            )

        if capability_limit_triggered:
            capability_assessment = (
                "Recent evidence suggests the current specialized agents are close to their practical current capability "
                "limit for this gap. They can summarize structural and S0/S1 proxy trends, but they are not adding "
                "enough discriminative information to resolve the present uncertainty safely."
            )
        else:
            capability_assessment = (
                "The current specialized agents still appear capable of adding bounded internal evidence within their "
                "mock scope, although they still cannot make a final mechanism judgment."
            )

        if capability_limit_triggered and (repeated_main_gaps or repeated_local_uncertainties or low_information_round_ids):
            information_gain_assessment = (
                "Compared with the recent rounds, the current loop is adding limited new information and is mostly "
                "repeating the same unresolved local uncertainty."
            )
            gap_trend = "The main gap is not shrinking."
            stagnation_detected = True
            stagnation_assessment = (
                "Stagnation is emerging primarily because repeated rounds keep surfacing the same gap and the same "
                "local uncertainty, which points more to current agent capability limits than to a clear hypothesis reversal."
            )
        elif capability_limit_triggered:
            information_gain_assessment = (
                "The current round adds some information, but the signal is already close to the limit of what the "
                "current specialized agents can clarify."
            )
            gap_trend = "The main gap is shrinking only slowly."
            stagnation_detected = False
            stagnation_assessment = (
                "Full stagnation is not yet established, but capability-limited slowdown is already visible."
            )
        elif support_score >= 0.22:
            information_gain_assessment = "The current round adds substantive new information."
            gap_trend = "The main gap is shrinking."
            stagnation_detected = False
            stagnation_assessment = "No stagnation is currently visible."
        else:
            information_gain_assessment = (
                "The current round adds only modest information and still leaves a substantial unresolved gap."
            )
            gap_trend = "The main gap is shrinking only slowly."
            stagnation_detected = False
            stagnation_assessment = "No clear stagnation is visible yet, but the gap is not shrinking quickly."

        contraction_reason: str | None = None
        if confidence >= self._verifier_threshold:
            action = "verifier"
            needs_verifier = True
            planned_agents = ["verifier"]
            contraction_reason = (
                "Confidence is already high enough that the Planner should stop internal expansion and force an "
                "external verifier check before any temporary conclusion."
            )
        elif capability_limit_triggered:
            action = "verifier"
            needs_verifier = True
            planned_agents = ["verifier"]
            main_gap = (
                "Capability-limited stagnation: internal evidence is no longer shrinking the gap effectively under "
                "current specialized-agent capability."
            )
            contraction_reason = (
                "Further repetition of the same internal action is unlikely to close the gap under current mock agent "
                "capability, so the Planner is conservatively contracting to verifier."
            )
        elif not macro_results:
            action = "macro"
            needs_verifier = False
            planned_agents = ["macro"]
            main_gap = "Macro structural evidence is missing."
        else:
            action = "microscopic"
            needs_verifier = False
            planned_agents = ["microscopic"]
            main_gap = "Microscopic evidence is still too thin."
        task_instruction = _default_follow_up_task_instruction(
            action,
            str(payload["current_hypothesis"]),
            {
                "main_gap": main_gap,
                "capability_assessment": capability_assessment,
                "contraction_reason": contraction_reason,
                "shared_structure_note": shared_structure_note,
            },
        )
        agent_task_instructions = (
            {action: task_instruction}
            if action in {"macro", "microscopic", "verifier"} and task_instruction
            else {}
        )
        blocking_agents = [
            agent_name
            for agent_name, report in (("macro", macro_report), ("microscopic", microscopic_report))
            if report and _has_meaningful_uncertainty(report)
        ]
        capability_lesson_candidates = _derive_capability_lesson_candidates(
            blocking_agents=blocking_agents,
            main_gap=main_gap,
            capability_assessment=capability_assessment,
            contraction_reason=contraction_reason,
        )

        diagnosis = (
            f"Current leading hypothesis: {payload['current_hypothesis']}. "
            f"Hypothesis uncertainty: {hypothesis_uncertainty_note} "
            f"New evidence added: {evidence_summary}. "
            f"This new evidence {evidence_impact} the current hypothesis at confidence {confidence:.2f}. "
            f"What remains unresolved: {unresolved} "
            f"Capability assessment: {capability_assessment} "
            f"Relative to the recent rounds, {information_gain_assessment} "
            f"Recent-round review count: {len(recent_rounds_context)}. "
            f"The current gap trend is: {gap_trend} "
            f"Stagnation assessment: {stagnation_assessment} "
            f"The main gap is {main_gap} "
            f"Contraction reason: {contraction_reason or 'No conservative contraction is required yet.'} "
            f"The chosen next action is {action} because it addresses the highest-value missing evidence now."
        )
        return {
            "decision": PlannerDecision(
                diagnosis=diagnosis,
                action=action,
                current_hypothesis=payload["current_hypothesis"],
                confidence=confidence,
                needs_verifier=needs_verifier,
                finalize=False,
                planned_agents=planned_agents,
                task_instruction=task_instruction,
                agent_task_instructions=_normalize_agent_task_instructions(agent_task_instructions),
                hypothesis_uncertainty_note=hypothesis_uncertainty_note,
                capability_assessment=capability_assessment,
                stagnation_assessment=stagnation_assessment,
                contraction_reason=contraction_reason,
                capability_lesson_candidates=capability_lesson_candidates,
                information_gain_assessment=information_gain_assessment,
                gap_trend=gap_trend,
                stagnation_detected=stagnation_detected,
            ),
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": "none",
            "hypothesis_uncertainty_note": hypothesis_uncertainty_note,
            "capability_assessment": capability_assessment,
            "stagnation_assessment": stagnation_assessment,
            "contraction_reason": contraction_reason,
            "information_gain_assessment": information_gain_assessment,
            "gap_trend": gap_trend,
        }

    def plan_reweight_or_finalize(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _ = rendered_prompt
        verifier_report = payload["verifier_report"] or {}
        verifier_cards = verifier_report.get("structured_results", {}).get("evidence_cards", [])
        verifier_result_summary = str(verifier_report.get("result_summary") or "").strip()
        interpreted = _interpret_mock_verifier_cards(payload["current_hypothesis"], verifier_cards)
        support_count = interpreted["support_count"]
        conflict_count = interpreted["conflict_count"]
        neutral_count = interpreted["neutral_count"]
        support_topics = interpreted["support_topics"]
        conflict_topics = interpreted["conflict_topics"]
        topic_summary = interpreted["topic_summary"]
        current_confidence = float(payload["current_confidence"] or 0.5)
        current_hypothesis = payload["current_hypothesis"]
        next_hypothesis = _best_alternative_hypothesis(
            current_hypothesis,
            payload["hypothesis_pool"],
        )
        recent_capability_context = payload.get("recent_capability_context", {})
        repeated_local_uncertainties = recent_capability_context.get("repeated_local_uncertainties", [])
        repeated_main_gaps = recent_capability_context.get("repeated_main_gaps", [])
        stagnation_round_ids = recent_capability_context.get("stagnation_round_ids", [])
        evidence_summary = (
            verifier_result_summary
            or (
                f"Verifier returned {len(verifier_cards)} raw evidence card(s) covering these topics: {topic_summary}. "
                f"The mock Planner interprets them as {support_count} supportive, {conflict_count} competing, "
                f"and {neutral_count} neutral cards for the current hypothesis."
            )
        )
        strong_conflict = conflict_count >= 2 or (support_count == 0 and len(conflict_topics) >= 2)
        weak_conflict = conflict_count > 0 and not strong_conflict

        if strong_conflict:
            confidence = round(max(0.34, current_confidence - 0.18), 3)
            conflict_status = "strong"
            hypothesis_uncertainty_note = (
                "The current hypothesis is materially weakened because the Planner reads multiple verifier cards as "
                "pointing toward competing explanations."
            )
            capability_assessment = (
                "Current specialized agents can still gather bounded evidence for a switched hypothesis, but they should "
                "not be asked to rescue a verifier-weakened mechanism through repeated broad refinement."
            )
            stagnation_assessment = (
                "This is not mere stagnation: verifier evidence materially changed the global picture and justifies reweighting."
            )
            contraction_reason = (
                "Conservatively contract by switching to the strongest remaining alternative hypothesis and restart with "
                "fresh bounded internal evidence."
            )
            main_gap = "The switched hypothesis needs fresh internal evidence."
            task_instruction = _default_follow_up_task_instruction(
                "macro",
                next_hypothesis,
                {
                    "main_gap": main_gap,
                    "capability_assessment": capability_assessment,
                    "contraction_reason": contraction_reason,
                },
            )
            capability_lesson_candidates = _derive_capability_lesson_candidates(
                blocking_agents=["macro"],
                main_gap=main_gap,
                capability_assessment=capability_assessment,
                contraction_reason=contraction_reason,
            )
            diagnosis = (
                f"Planner interpretation of verifier evidence now materially conflicts with the current hypothesis {current_hypothesis}. "
                f"The verifier returned {len(verifier_cards)} raw evidence card(s) covering {topic_summary}. "
                f"The Planner reads {conflict_count} card(s) as competing and {support_count} card(s) as supportive, "
                f"with conflict topics such as {', '.join(conflict_topics) if conflict_topics else 'none identified'}. "
                "This is treated as strong conflict. "
                f"Hypothesis uncertainty: {hypothesis_uncertainty_note} "
                f"Capability assessment: {capability_assessment} "
                f"Stagnation assessment: {stagnation_assessment} "
                f"Contraction reason: {contraction_reason} "
                f"The Planner therefore switches the leading hypothesis to {next_hypothesis} and requests fresh macro evidence."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="macro",
                current_hypothesis=next_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["macro"],
                task_instruction=task_instruction,
                agent_task_instructions=_normalize_agent_task_instructions(
                    {"macro": task_instruction or ""}
                ),
                hypothesis_uncertainty_note=hypothesis_uncertainty_note,
                capability_assessment=capability_assessment,
                stagnation_assessment=stagnation_assessment,
                contraction_reason=contraction_reason,
                capability_lesson_candidates=capability_lesson_candidates,
                information_gain_assessment="Verifier evidence materially changes the hypothesis ranking.",
                gap_trend="The previous gap is replaced by a new switched-hypothesis validation gap.",
                stagnation_detected=False,
            )
        elif weak_conflict:
            confidence = round(max(0.46, current_confidence - 0.03), 3)
            conflict_status = "weak"
            hypothesis_uncertainty_note = (
                "The current hypothesis remains viable, but the Planner reads part of the verifier evidence as pointing "
                "toward a competing explanation, so the story is not yet clean enough for closure."
            )
            capability_assessment = (
                "Current specialized agents can still perform one bounded microscopic follow-up on the verifier-exposed "
                "local inconsistency, but they should not be asked for broad mechanism discrimination."
            )
            stagnation_detected = bool(repeated_local_uncertainties or stagnation_round_ids)
            stagnation_assessment = (
                "A mild capability-limited stagnation risk remains because verifier conflict is weak and local "
                "uncertainties may repeat, but one targeted follow-up is still justified."
            )
            contraction_reason = (
                "Do not switch hypotheses on weak conflict. Instead, contract to one bounded microscopic follow-up that "
                "targets the verifier-exposed inconsistency."
            )
            main_gap = "Weak verifier conflict remains, so one bounded internal refinement step is needed."
            task_instruction = _default_follow_up_task_instruction(
                "microscopic",
                current_hypothesis,
                {
                    "main_gap": main_gap,
                    "capability_assessment": capability_assessment,
                    "contraction_reason": contraction_reason,
                },
            )
            capability_lesson_candidates = _derive_capability_lesson_candidates(
                blocking_agents=["microscopic"],
                main_gap=main_gap,
                capability_assessment=capability_assessment,
                contraction_reason=contraction_reason,
            )
            diagnosis = (
                f"Planner interpretation of verifier evidence introduces a weak conflict with the current hypothesis {current_hypothesis}. "
                f"The verifier returned {len(verifier_cards)} raw evidence card(s) covering {topic_summary}. "
                f"The Planner reads {support_count} card(s) as supportive, {conflict_count} as competing, and {neutral_count} as neutral. "
                f"Support topics include {', '.join(support_topics) if support_topics else 'none identified'}, while competing topics include {', '.join(conflict_topics) if conflict_topics else 'none identified'}. "
                "The conflict is therefore weak rather than decisive. "
                f"Hypothesis uncertainty: {hypothesis_uncertainty_note} "
                f"Capability assessment: {capability_assessment} "
                f"Stagnation assessment: {stagnation_assessment} "
                f"Contraction reason: {contraction_reason} "
                "The Planner keeps the current hypothesis, avoids premature switching, and requests one targeted "
                "microscopic follow-up."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="microscopic",
                current_hypothesis=current_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["microscopic"],
                task_instruction=task_instruction,
                agent_task_instructions=_normalize_agent_task_instructions(
                    {"microscopic": task_instruction or ""}
                ),
                hypothesis_uncertainty_note=hypothesis_uncertainty_note,
                capability_assessment=capability_assessment,
                stagnation_assessment=stagnation_assessment,
                contraction_reason=contraction_reason,
                capability_lesson_candidates=capability_lesson_candidates,
                information_gain_assessment="Verifier evidence adds a meaningful but still mixed signal.",
                gap_trend="The main gap narrows, but a verifier-exposed inconsistency remains.",
                stagnation_detected=stagnation_detected,
            )
        elif support_count == 0 and conflict_count == 0:
            confidence = round(max(0.36, current_confidence - 0.05), 3)
            conflict_status = "uncertain"
            hypothesis_uncertainty_note = (
                "The current hypothesis remains provisional because the raw verifier evidence does not yet separate it "
                "from nearby alternatives."
            )
            capability_assessment = (
                "The combination of neutral verifier evidence and recent repeated local uncertainty indicates that the "
                "current specialized agents are close to their practical limit for this case."
                if repeated_local_uncertainties or repeated_main_gaps
                else "Verifier evidence is neutral, but one bounded internal follow-up is still available within current microscopic capability."
            )
            stagnation_detected = bool(
                repeated_local_uncertainties or repeated_main_gaps or stagnation_round_ids
            )
            stagnation_assessment = (
                "The case is near capability-limited stagnation: verifier evidence is neutral, the main gap remains, and "
                "continued repetition should be tightly bounded."
            )
            contraction_reason = (
                "Do not keep expanding the same search space. Allow at most one bounded microscopic follow-up; if it still "
                "fails to shrink the gap, leave the case unresolved under current capability."
            )
            main_gap = "Verifier evidence is neutral, so only a bounded follow-up is justified before unresolved exit."
            task_instruction = _default_follow_up_task_instruction(
                "microscopic",
                current_hypothesis,
                {
                    "main_gap": main_gap,
                    "capability_assessment": capability_assessment,
                    "contraction_reason": contraction_reason,
                },
            )
            capability_lesson_candidates = _derive_capability_lesson_candidates(
                blocking_agents=["microscopic"],
                main_gap=main_gap,
                capability_assessment=capability_assessment,
                contraction_reason=contraction_reason,
            )
            diagnosis = (
                f"Planner interpretation of verifier evidence remains uncertain for the current hypothesis {current_hypothesis}. "
                f"The verifier returned {len(verifier_cards)} raw evidence card(s) covering {topic_summary}, "
                f"but the Planner reads them as {neutral_count} neutral cards with no clear supportive or competing signal. "
                f"Hypothesis uncertainty: {hypothesis_uncertainty_note} "
                f"Capability assessment: {capability_assessment} "
                f"Stagnation assessment: {stagnation_assessment} "
                f"Contraction reason: {contraction_reason} "
                "The Planner therefore avoids hypothesis switching, does not finalize, and requests only one bounded "
                "microscopic follow-up."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="microscopic",
                current_hypothesis=current_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["microscopic"],
                task_instruction=task_instruction,
                agent_task_instructions=_normalize_agent_task_instructions(
                    {"microscopic": task_instruction or ""}
                ),
                hypothesis_uncertainty_note=hypothesis_uncertainty_note,
                capability_assessment=capability_assessment,
                stagnation_assessment=stagnation_assessment,
                contraction_reason=contraction_reason,
                capability_lesson_candidates=capability_lesson_candidates,
                information_gain_assessment="Verifier evidence adds little new discrimination for the current hypothesis.",
                gap_trend="The main gap is not shrinking materially after verifier.",
                stagnation_detected=stagnation_detected,
            )
        else:
            confidence = round(min(0.95, current_confidence + 0.08 + support_count * 0.02), 3)
            conflict_status = "none"
            hypothesis_uncertainty_note = (
                "Some residual scientific uncertainty remains, but the Planner now reads the verifier evidence as aligned "
                "with the current hypothesis."
            )
            capability_assessment = (
                "Current specialized-agent limitations no longer block case closure because verifier support aligned with "
                "the internal evidence chain."
            )
            stagnation_assessment = (
                "No stagnation remains after verifier support; the key gap has been closed sufficiently for this stage."
            )
            contraction_reason = "Conservatively contract to case closure because further internal expansion is unnecessary."
            main_gap = "No critical evidence gap remains in the current workflow."
            diagnosis = (
                f"Planner interpretation of verifier evidence supports the current hypothesis {current_hypothesis}. "
                f"The verifier returned {len(verifier_cards)} raw evidence card(s) covering {topic_summary}. "
                f"The Planner reads {support_count} card(s) as supportive and no meaningful competing signal remains. "
                f"Hypothesis uncertainty: {hypothesis_uncertainty_note} "
                f"Capability assessment: {capability_assessment} "
                f"Stagnation assessment: {stagnation_assessment} "
                f"Contraction reason: {contraction_reason} "
                "A hypothesis switch is not necessary. The Planner can now finalize because the internal evidence and "
                "verifier check are aligned."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="finalize",
                current_hypothesis=current_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=True,
                planned_agents=[],
                hypothesis_uncertainty_note=hypothesis_uncertainty_note,
                capability_assessment=capability_assessment,
                stagnation_assessment=stagnation_assessment,
                contraction_reason=contraction_reason,
                information_gain_assessment="Verifier evidence provides the decisive incremental information needed for closure.",
                gap_trend="The main gap is closed.",
                stagnation_detected=False,
            )

        return {
            "decision": decision,
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": conflict_status,
            "hypothesis_uncertainty_note": decision.hypothesis_uncertainty_note,
            "capability_assessment": decision.capability_assessment,
            "stagnation_assessment": decision.stagnation_assessment,
            "contraction_reason": decision.contraction_reason,
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
        }


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
            if decision.finalize:
                decision.finalize = False
            if confidence >= self._verifier_threshold or decision.stagnation_detected:
                decision.action = "verifier"
                decision.needs_verifier = True
                decision.finalize = False
                # keep the Planner's global reasoning explicit when verifier is forced
                if not decision.contraction_reason:
                    decision.contraction_reason = (
                        "The Planner is conservatively contracting to verifier because internal confidence or "
                        "stagnation indicates that more internal expansion would be lower value."
                    )
                if not decision.stagnation_assessment and decision.stagnation_detected:
                    decision.stagnation_assessment = (
                        "Recent rounds indicate stagnation or low information gain, so verifier should break the deadlock."
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
                if decision.stagnation_detected and main_gap == response.main_gap:
                    main_gap = "Recent rounds indicate stagnation, so external supervision is needed."
            decision.planned_agents = self._planned_agents_for_action(decision.action)
            if decision.action != "verifier":
                decision.needs_verifier = False
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
            "capability_assessment": decision.capability_assessment,
            "stagnation_assessment": decision.stagnation_assessment,
            "contraction_reason": decision.contraction_reason,
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
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
        else:
            decision.finalize = False
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
        return action if action in {"macro", "microscopic", "verifier"} else "microscopic"

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
        if config.planner_backend == "openai_sdk":
            return OpenAIPlannerBackend(
                config=config,
                verifier_threshold=config.verifier_threshold,
                client=llm_client,
            )
        return MockPlannerBackend(verifier_threshold=config.verifier_threshold)
