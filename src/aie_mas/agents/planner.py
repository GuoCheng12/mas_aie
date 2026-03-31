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
    verifier_supplement_target_pair: str = ""
    verifier_supplement_status: str = "missing"
    verifier_information_gain: str = "none"
    verifier_evidence_relation: str = "no_new_info"
    verifier_supplement_summary: str = ""
    closure_justification_target_pair: str = ""
    closure_justification_status: str = "missing"
    closure_justification_evidence_source: str = ""
    closure_justification_basis: str = ""
    closure_justification_summary: str = ""
    pairwise_task_agent: str = ""
    pairwise_task_completed_for_pair: str = ""
    pairwise_task_outcome: str = "not_run"
    pairwise_task_rationale: str = ""
    finalization_mode: str = "none"


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
    verifier_supplement_target_pair: str = ""
    verifier_supplement_status: str = "missing"
    verifier_information_gain: str = "none"
    verifier_evidence_relation: str = "no_new_info"
    verifier_supplement_summary: str = ""
    closure_justification_target_pair: str = ""
    closure_justification_status: str = "missing"
    closure_justification_evidence_source: str = ""
    closure_justification_basis: str = ""
    closure_justification_summary: str = ""
    pairwise_task_agent: str = ""
    pairwise_task_completed_for_pair: str = ""
    pairwise_task_outcome: str = "not_run"
    pairwise_task_rationale: str = ""
    finalization_mode: str = "none"


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
_MICROSCOPIC_SINGLE_ACTION_CAPABILITIES = (
    "run_baseline_bundle",
    "run_conformer_bundle",
    "run_torsion_snapshots",
    "parse_snapshot_outputs",
    "extract_ct_descriptors_from_bundle",
    "inspect_raw_artifact_bundle",
)
_MICROSCOPIC_STRUCTURE_BLOCK_CODES = {
    "unsupported_formal_charge",
    "unsupported_radical",
    "embedding_failed",
    "forcefield_failed",
    "rdkit_unavailable",
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


def _mentioned_microscopic_capabilities(text: str) -> list[str]:
    ordered_matches: list[tuple[int, str]] = []
    for capability in _MICROSCOPIC_SINGLE_ACTION_CAPABILITIES:
        match = re.search(rf"\b{re.escape(capability)}\b", text)
        if match is not None:
            ordered_matches.append((match.start(), capability))
    ordered_matches.sort(key=lambda item: item[0])
    return [capability for _, capability in ordered_matches]


def _extract_first_artifact_bundle_id(text: str) -> str | None:
    match = re.search(r"\b(round_\d+_(?:baseline_bundle|torsion_snapshots|conformer_bundle))\b", text)
    return match.group(1) if match is not None else None


def _extract_first_dihedral_id(text: str) -> str | None:
    match = re.search(r"\b(dih_(?:\d+_){3}\d+)\b", text)
    return match.group(1) if match is not None else None


def _append_unique_detail(existing: str | None, addition: str) -> str:
    normalized_existing = (existing or "").strip()
    normalized_addition = addition.strip()
    if not normalized_existing:
        return normalized_addition
    if normalized_addition in normalized_existing:
        return normalized_existing
    separator = " " if normalized_existing.endswith((".", "!", "?")) else ". "
    return f"{normalized_existing}{separator}{normalized_addition}"


def _structured_results_from_report(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    structured = report.get("structured_results")
    return structured if isinstance(structured, dict) else {}


def _raw_results_from_report(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict):
        return {}
    raw = report.get("raw_results")
    return raw if isinstance(raw, dict) else {}


def _normalize_structure_prep_error(error_payload: Any) -> dict[str, str] | None:
    if not isinstance(error_payload, dict):
        return None
    code = str(error_payload.get("code") or "").strip()
    message = str(error_payload.get("message") or "").strip()
    if code not in _MICROSCOPIC_STRUCTURE_BLOCK_CODES:
        return None
    if not message:
        message = code
    return {"code": code, "message": message}


def _microscopic_structure_block_reason(payload: dict[str, Any]) -> str | None:
    shared_error = _normalize_structure_prep_error(payload.get("shared_structure_error"))
    if shared_error is not None:
        return f"{shared_error['code']}: {shared_error['message']}"

    latest_microscopic_report = payload.get("latest_microscopic_report")
    structured = _structured_results_from_report(latest_microscopic_report)
    raw = _raw_results_from_report(latest_microscopic_report)

    structured_error = _normalize_structure_prep_error(structured.get("structure_prep_error"))
    if structured_error is not None:
        return f"{structured_error['code']}: {structured_error['message']}"

    raw_error = _normalize_structure_prep_error(raw.get("structure_prep_error"))
    if raw_error is not None:
        return f"{raw_error['code']}: {raw_error['message']}"

    return None


def _single_action_microscopic_task_instruction(
    *,
    capability_name: str,
    current_hypothesis: str,
    main_gap: str,
    original_task_instruction: str,
) -> str:
    artifact_bundle_id = _extract_first_artifact_bundle_id(original_task_instruction)
    dihedral_id = _extract_first_dihedral_id(original_task_instruction)
    gap_note = f"Focus on the current gap: {main_gap}".strip()
    if capability_name == "run_baseline_bundle":
        return (
            f"Execute ONLY `run_baseline_bundle` as one bounded microscopic action for the current working hypothesis "
            f"'{current_hypothesis}'. Reuse the shared prepared structure if available. {gap_note} "
            "Return only the baseline S0/S1 outputs needed for the current discriminator."
        )
    if capability_name == "run_conformer_bundle":
        return (
            f"Execute ONLY `run_conformer_bundle` as one bounded microscopic action for the current working hypothesis "
            f"'{current_hypothesis}'. Reuse the shared prepared structure if available. {gap_note} "
            "Select a bounded conformer subset consistent with current microscopic capability and return only local conformer-sensitivity evidence."
        )
    if capability_name == "run_torsion_snapshots":
        target_note = (
            f"Honor the explicit dihedral target `{dihedral_id}` if it remains available. "
            if dihedral_id
            else "Select one highest-relevance unresolved dihedral target from the current context. "
        )
        return (
            f"Execute ONLY `run_torsion_snapshots` as one bounded microscopic action for the current working hypothesis "
            f"'{current_hypothesis}'. Reuse the shared prepared structure or existing baseline geometry if available. "
            f"{target_note}{gap_note} Return the generated torsion snapshot bundle and a compact per-snapshot vertical-state summary."
        )
    if capability_name == "parse_snapshot_outputs":
        bundle_note = (
            f" for bundle_id=`{artifact_bundle_id}`" if artifact_bundle_id is not None else " for one explicitly referenced reusable artifact bundle"
        )
        return (
            f"Execute ONLY `parse_snapshot_outputs`{bundle_note} in parse-only mode (no new calculations). "
            f"{gap_note} Return only the parsed per-snapshot vertical-state summaries needed for the current discriminator."
        )
    if capability_name == "extract_ct_descriptors_from_bundle":
        bundle_note = (
            f" for bundle_id=`{artifact_bundle_id}`" if artifact_bundle_id is not None else " for one explicitly referenced reusable artifact bundle"
        )
        return (
            f"Execute ONLY `extract_ct_descriptors_from_bundle`{bundle_note} using reusable artifacts only. "
            f"{gap_note} Return bounded CT-surrogate availability and any available local CT-related summary fields without launching new calculations."
        )
    if capability_name == "inspect_raw_artifact_bundle":
        bundle_note = (
            f" for bundle_id=`{artifact_bundle_id}`" if artifact_bundle_id is not None else " for one explicitly referenced reusable artifact bundle"
        )
        return (
            f"Execute ONLY `inspect_raw_artifact_bundle`{bundle_note} using reusable artifacts only. "
            f"{gap_note} Return raw-file coverage and extractable-observable inventory relevant to the current discriminator without launching new calculations."
        )
    return (
        f"Collect additional microscopic evidence for the current working hypothesis '{current_hypothesis}'. "
        f"{gap_note} Keep the task low-cost and bounded to current microscopic capability."
    )


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


def _normalize_pairwise_task_agent(raw_agent: str | None) -> str | None:
    if raw_agent in {"macro", "microscopic"}:
        return raw_agent
    return None


def _normalize_pairwise_task_outcome(raw_outcome: str | None) -> str:
    if raw_outcome in {"not_run", "decisive", "inconclusive", "failed"}:
        return raw_outcome
    return "not_run"


def _normalize_finalization_mode(raw_mode: str | None) -> str:
    if raw_mode in {"none", "decisive", "best_available"}:
        return raw_mode
    return "none"


def _normalize_verifier_supplement_status(raw_status: str | None) -> str:
    if raw_status in {"missing", "partial", "sufficient"}:
        return raw_status
    return "missing"


def _normalize_verifier_information_gain(raw_gain: str | None) -> str:
    if raw_gain in {"none", "low", "medium", "high"}:
        return raw_gain
    return "none"


def _normalize_verifier_evidence_relation(raw_relation: str | None) -> str:
    if raw_relation in {"supports_top1", "challenges_top1", "mixed", "no_new_info"}:
        return raw_relation
    return "no_new_info"


def _normalize_closure_justification_status(raw_status: str | None) -> str:
    if raw_status in {"missing", "collecting", "sufficient", "blocked"}:
        return raw_status
    return "missing"


def _normalize_closure_justification_evidence_source(raw_source: str | None) -> str | None:
    if raw_source in {"internal", "external", "mixed"}:
        return raw_source
    return None


def _normalize_closure_justification_basis(raw_basis: str | None) -> str | None:
    if raw_basis in {"existing_evidence", "new_targeted_task"}:
        return raw_basis
    return None


def _default_pairwise_task_agent(main_gap: str, preferred_action: str | None = None) -> str:
    if preferred_action in {"macro", "microscopic"}:
        return preferred_action
    lower_gap = main_gap.lower()
    if any(
        token in lower_gap
        for token in (
            "topology",
            "rotor",
            "planarity",
            "structural proxy",
            "compactness",
            "donor-acceptor layout",
            "ring system",
        )
    ):
        return "macro"
    return "microscopic"


def _default_pairwise_task_rationale(
    champion_hypothesis: str,
    challenger_hypothesis: str,
    main_gap: str,
    pairwise_task_agent: str,
) -> str:
    return (
        f"A bounded {pairwise_task_agent} task is needed to discriminate '{champion_hypothesis}' "
        f"from '{challenger_hypothesis}' on the unresolved point: {main_gap}"
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
    payload["verifier_supplement_target_pair"] = decision.verifier_supplement_target_pair
    payload["verifier_supplement_status"] = decision.verifier_supplement_status
    payload["verifier_information_gain"] = decision.verifier_information_gain
    payload["verifier_evidence_relation"] = decision.verifier_evidence_relation
    payload["verifier_supplement_summary"] = decision.verifier_supplement_summary
    payload["closure_justification_target_pair"] = decision.closure_justification_target_pair
    payload["closure_justification_status"] = decision.closure_justification_status
    payload["closure_justification_evidence_source"] = decision.closure_justification_evidence_source
    payload["closure_justification_basis"] = decision.closure_justification_basis
    payload["closure_justification_summary"] = decision.closure_justification_summary
    payload["pairwise_task_agent"] = decision.pairwise_task_agent
    payload["pairwise_task_completed_for_pair"] = decision.pairwise_task_completed_for_pair
    payload["pairwise_task_outcome"] = decision.pairwise_task_outcome
    payload["pairwise_task_rationale"] = decision.pairwise_task_rationale
    payload["finalization_mode"] = decision.finalization_mode
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
    challenger_hypothesis = str(payload.get("challenger_hypothesis") or "unknown")
    pairwise_question = str(
        payload.get("pairwise_decision_question")
        or _pairwise_decision_question(current_hypothesis, challenger_hypothesis, main_gap)
    )
    pairwise_task_rationale = str(payload.get("pairwise_task_rationale") or "").strip()
    if action == "macro":
        if payload.get("is_pairwise_discriminative_task"):
            return (
                f"Run a bounded macro-level discriminative task to distinguish '{current_hypothesis}' from "
                f"'{challenger_hypothesis}'. Current unresolved discriminator: {main_gap} "
                f"Decision question: {pairwise_question} "
                f"Only collect low-cost structural evidence and report whether the requested structural discriminator was actually resolved. "
                f"{pairwise_task_rationale or capability_assessment}"
            )
        return (
            f"Collect additional macro-level structural evidence for the current working hypothesis "
            f"'{current_hypothesis}'. Focus on the current gap: {main_gap} "
            f"{shared_structure_note} "
            f"Only use low-cost structural proxies; do not attempt excited-state adjudication. "
            f"Capability note: {capability_assessment}"
        )
    if action == "microscopic":
        if payload.get("is_pairwise_discriminative_task"):
            return (
                f"Run a bounded microscopic discriminative task to distinguish '{current_hypothesis}' from "
                f"'{challenger_hypothesis}'. Current unresolved discriminator: {main_gap} "
                f"Decision question: {pairwise_question} "
                f"Collect only low-cost internal evidence and explicitly report whether the requested discriminator remained decisive, inconclusive, or failed locally. "
                f"{pairwise_task_rationale or contraction_reason or capability_assessment}"
            )
        return (
            f"Collect additional microscopic evidence for the current working hypothesis "
            f"'{current_hypothesis}'. Focus on the current gap: {main_gap} "
            f"{shared_structure_note} "
            f"Keep the task low-cost and bounded to current microscopic capability. "
            f"{contraction_reason or capability_assessment}"
        )
    if action == "verifier":
        return (
            f"Run a high-confidence external verification between champion hypothesis '{current_hypothesis}' and "
            f"challenger hypothesis '{challenger_hypothesis}'. Current gap: {main_gap} "
            f"Decision question: {pairwise_question} "
            f"Focus on external discriminator criteria, family precedents, and whether the remaining internal gap is usually considered decisive. "
            f"Do not use verifier evidence as a substitute for an unexecuted internal discriminative task."
        )
    return None


def _contract_microscopic_decision_to_single_action(
    decision: PlannerDecision,
    *,
    main_gap: str,
) -> PlannerDecision:
    if decision.action != "microscopic":
        return decision
    microscopic_instruction = (
        decision.agent_task_instructions.get("microscopic")
        or decision.task_instruction
        or ""
    ).strip()
    mentioned_capabilities = _mentioned_microscopic_capabilities(microscopic_instruction)
    if len(mentioned_capabilities) <= 1:
        return decision
    contracted_capability = mentioned_capabilities[0]
    contracted_instruction = _single_action_microscopic_task_instruction(
        capability_name=contracted_capability,
        current_hypothesis=decision.current_hypothesis,
        main_gap=main_gap,
        original_task_instruction=microscopic_instruction,
    )
    contraction_note = (
        f"Planner microscopic task was contracted to a single registry-backed action "
        f"(`{contracted_capability}`) because one microscopic decision may execute only one Amesp action."
    )
    existing_reason = (decision.contraction_reason or "").strip()
    if contraction_note not in existing_reason:
        decision.contraction_reason = (
            f"{existing_reason} {contraction_note}".strip()
            if existing_reason
            else contraction_note
        )
    decision.task_instruction = contracted_instruction
    decision.agent_task_instructions = _normalize_agent_task_instructions(
        {"microscopic": contracted_instruction}
    )
    return decision


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
            verifier_supplement_target_pair=_decision_pair_key(_decision_pair_from_pool(hypothesis_pool)),
            verifier_supplement_status="missing",
            verifier_information_gain="none",
            verifier_evidence_relation="no_new_info",
            verifier_supplement_summary=None,
            closure_justification_target_pair=_decision_pair_key(_decision_pair_from_pool(hypothesis_pool)),
            closure_justification_status="missing",
            closure_justification_evidence_source=None,
            closure_justification_basis=None,
            closure_justification_summary=None,
            pairwise_task_agent=None,
            pairwise_task_completed_for_pair=None,
            pairwise_task_outcome="not_run",
            pairwise_task_rationale=None,
            finalization_mode="none",
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
        pairwise_task_agent = _normalize_pairwise_task_agent(response.pairwise_task_agent) or _normalize_pairwise_task_agent(
            str(payload.get("pairwise_task_agent") or "")
        )
        pairwise_task_rationale = response.pairwise_task_rationale.strip() or str(
            payload.get("pairwise_task_rationale") or ""
        ).strip() or None
        pairwise_task_completed_for_pair = response.pairwise_task_completed_for_pair.strip() or str(
            payload.get("pairwise_task_completed_for_pair") or ""
        ).strip() or None
        pairwise_task_outcome = (
            _normalize_pairwise_task_outcome(response.pairwise_task_outcome)
            if response.pairwise_task_outcome != "not_run"
            else _normalize_pairwise_task_outcome(str(payload.get("pairwise_task_outcome") or "not_run"))
        )
        finalization_mode = (
            _normalize_finalization_mode(response.finalization_mode)
            if response.finalization_mode != "none"
            else _normalize_finalization_mode(str(payload.get("finalization_mode") or "none"))
        )
        decision = PlannerDecision(
            diagnosis=response.diagnosis,
            action=self._normalize_action(
                response.action,
                post_verifier=post_verifier,
                task_instruction=task_instruction,
                agent_task_instructions=agent_task_instructions,
            ),
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
            verifier_supplement_target_pair=response.verifier_supplement_target_pair.strip()
            or str(payload.get("verifier_supplement_target_pair") or "").strip()
            or _decision_pair_key(_decision_pair_from_pool(hypothesis_pool)),
            verifier_supplement_status=_normalize_verifier_supplement_status(
                response.verifier_supplement_status
            ),
            verifier_information_gain=_normalize_verifier_information_gain(
                response.verifier_information_gain
            ),
            verifier_evidence_relation=_normalize_verifier_evidence_relation(
                response.verifier_evidence_relation
            ),
            verifier_supplement_summary=response.verifier_supplement_summary.strip()
            or str(payload.get("verifier_supplement_summary") or "").strip()
            or None,
            closure_justification_target_pair=response.closure_justification_target_pair.strip()
            or str(payload.get("closure_justification_target_pair") or "").strip()
            or _decision_pair_key(_decision_pair_from_pool(hypothesis_pool)),
            closure_justification_status=_normalize_closure_justification_status(
                response.closure_justification_status
            ),
            closure_justification_evidence_source=_normalize_closure_justification_evidence_source(
                response.closure_justification_evidence_source.strip() or None
            )
            or _normalize_closure_justification_evidence_source(
                str(payload.get("closure_justification_evidence_source") or "").strip() or None
            ),
            closure_justification_basis=_normalize_closure_justification_basis(
                response.closure_justification_basis.strip() or None
            )
            or _normalize_closure_justification_basis(
                str(payload.get("closure_justification_basis") or "").strip() or None
            ),
            closure_justification_summary=response.closure_justification_summary.strip()
            or str(payload.get("closure_justification_summary") or "").strip()
            or None,
            pairwise_task_agent=pairwise_task_agent,
            pairwise_task_completed_for_pair=pairwise_task_completed_for_pair,
            pairwise_task_outcome=pairwise_task_outcome,
            pairwise_task_rationale=pairwise_task_rationale,
            finalization_mode=finalization_mode,
        )
        decision = _contract_microscopic_decision_to_single_action(
            decision,
            main_gap=response.main_gap,
        )
        decision = self._hydrate_verifier_and_closure_state(
            decision=decision,
            latest_verifier_report=payload.get("verifier_report") or payload.get("latest_verifier_report"),
            main_gap=payload.get("main_gap") or response.main_gap,
        )

        evidence_summary = response.evidence_summary
        main_gap = response.main_gap
        conflict_status = response.conflict_status

        if not post_verifier:
            decision = self._apply_pre_decision_gate(
                decision=decision,
                main_gap=main_gap,
                latest_microscopic_report=payload.get("latest_microscopic_report"),
            )
            decision = self._apply_microscopic_structure_block_gate(
                decision=decision,
                payload=payload,
                main_gap=main_gap,
            )
            decision.planned_agents = self._planned_agents_for_action(decision.action)
            if decision.action in {"macro", "microscopic", "verifier"} and not decision.agent_task_instructions:
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
            decision = self._apply_microscopic_structure_block_gate(
                decision=decision,
                payload=payload,
                main_gap=main_gap,
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
        decision = self._hydrate_verifier_and_closure_state(
            decision=decision,
            latest_verifier_report=payload.get("verifier_report"),
            main_gap=main_gap,
        )
        decision.planned_agents = self._planned_agents_for_action(decision.action)
        if decision.action != "finalize":
            decision.finalize = False
            decision.final_hypothesis_rationale = None
            if decision.action == "verifier":
                decision.needs_verifier = True
                decision.decision_gate_status = "needs_high_confidence_verifier"
            elif decision.action in {"macro", "microscopic"}:
                decision.needs_verifier = False
                decision.finalization_mode = "none"
                if decision.action in {"macro", "microscopic"} and not decision.task_instruction:
                    decision.task_instruction = _default_follow_up_task_instruction(
                        decision.action,
                        decision.current_hypothesis,
                        {
                            "main_gap": main_gap,
                            "challenger_hypothesis": decision.runner_up_hypothesis,
                            "capability_assessment": decision.capability_assessment,
                            "contraction_reason": decision.contraction_reason,
                        },
                    )
                if decision.closure_justification_status in {"collecting", "blocked"}:
                    decision.decision_gate_status = "needs_pairwise_discriminative_task"
                else:
                    decision.decision_gate_status = "not_ready"
            if decision.action in {"macro", "microscopic", "verifier"} and not decision.agent_task_instructions:
                decision.agent_task_instructions = _normalize_agent_task_instructions(
                    {decision.action: decision.task_instruction or ""}
                )  # type: ignore[assignment]
            return decision, conflict_status, main_gap

        finalization_mode = self._finalization_mode_for_decision(decision)
        if decision.verifier_supplement_status != "sufficient":
            decision = self._require_high_confidence_verifier(
                decision=decision,
                main_gap=main_gap,
            )
            return decision, conflict_status, main_gap
        if finalization_mode == "none":
            decision = self._require_closure_justification_task(
                decision=decision,
                main_gap=main_gap,
            )
            if decision.action == "finalize":
                decision.decision_gate_status = "blocked_by_missing_decisive_evidence"
            return decision, conflict_status, main_gap
        decision.finalize = True
        decision.task_instruction = None
        decision.agent_task_instructions = {}  # type: ignore[assignment]
        decision.planned_agents = []
        if finalization_mode == "decisive":
            decision.finalization_mode = "decisive"
            decision.decision_gate_status = "ready_to_finalize_decisive"
            decision.final_hypothesis_rationale = _normalize_final_hypothesis_rationale(
                raw_rationale=decision.final_hypothesis_rationale,
                diagnosis=decision.diagnosis,
                finalize=True,
            )
        else:
            decision.finalization_mode = "best_available"
            decision.decision_gate_status = "ready_to_finalize_best_available"
            trailing_rationale = (decision.final_hypothesis_rationale or "").strip()
            decision.final_hypothesis_rationale = (
                f"Best-available closure keeps '{decision.current_hypothesis}' ahead of "
                f"'{decision.runner_up_hypothesis or 'unknown'}', but the main unresolved gap remains: {main_gap}"
            )
            if trailing_rationale:
                decision.final_hypothesis_rationale += f" {trailing_rationale}"
        return decision, conflict_status, main_gap

    def _apply_microscopic_structure_block_gate(
        self,
        *,
        decision: PlannerDecision,
        payload: dict[str, Any],
        main_gap: str,
    ) -> PlannerDecision:
        block_reason = _microscopic_structure_block_reason(payload)
        if block_reason is None or decision.action != "microscopic":
            return decision

        block_note = (
            "Microscopic 3D structure preparation is blocked for this molecule "
            f"({block_reason}). Do not schedule additional microscopic structure-dependent tasks; "
            "fall back to macro/verifier-only routing until a compatible route exists."
        )
        decision.capability_assessment = _append_unique_detail(decision.capability_assessment, block_note)
        decision.contraction_reason = _append_unique_detail(decision.contraction_reason, block_note)

        existing_lessons = {
            (lesson.agent_name, lesson.blocked_task_pattern, lesson.observed_limitation)
            for lesson in decision.capability_lesson_candidates
        }
        lesson_key = (
            "microscopic",
            "Structure-dependent microscopic follow-up after 3D structure preparation is blocked",
            "Microscopic 3D structure preparation is unavailable for this molecule under the current runtime/tooling constraints.",
        )
        if lesson_key not in existing_lessons:
            decision.capability_lesson_candidates.append(
                CapabilityLessonEntry(
                    agent_name="microscopic",
                    blocked_task_pattern=lesson_key[1],
                    observed_limitation=lesson_key[2],
                    recommended_contraction="Use macro structural discriminators and verifier evidence instead of additional microscopic tasks until a compatible 3D structure route exists.",
                )
            )

        if decision.verifier_supplement_status != "sufficient":
            redirected = self._require_high_confidence_verifier(
                decision=decision,
                main_gap=main_gap,
            )
            redirected.capability_assessment = _append_unique_detail(redirected.capability_assessment, block_note)
            redirected.contraction_reason = _append_unique_detail(redirected.contraction_reason, block_note)
            return redirected

        decision.action = "macro"
        decision.needs_verifier = False
        decision.finalize = False
        decision.finalization_mode = "none"
        decision.planned_agents = ["macro"]
        decision.task_instruction = _default_follow_up_task_instruction(
            "macro",
            decision.current_hypothesis,
            {
                "main_gap": main_gap,
                "challenger_hypothesis": decision.runner_up_hypothesis,
                "capability_assessment": decision.capability_assessment,
                "contraction_reason": decision.contraction_reason,
                "shared_structure_note": "Shared 3D structure preparation is unavailable; use SMILES/topology-grounded macro evidence only.",
                "pairwise_task_rationale": decision.pairwise_task_rationale,
                "is_pairwise_discriminative_task": decision.decision_gate_status == "needs_pairwise_discriminative_task",
            },
        )
        decision.agent_task_instructions = _normalize_agent_task_instructions(
            {"macro": decision.task_instruction or ""}
        )  # type: ignore[assignment]
        if decision.closure_justification_status in {"collecting", "blocked"}:
            decision.decision_gate_status = "needs_pairwise_discriminative_task"
        else:
            decision.decision_gate_status = "not_ready"
        decision.final_hypothesis_rationale = None
        return decision

    def _apply_pre_decision_gate(
        self,
        *,
        decision: PlannerDecision,
        main_gap: str,
        latest_microscopic_report: Any,
    ) -> PlannerDecision:
        del latest_microscopic_report
        decision = self._hydrate_verifier_and_closure_state(
            decision=decision,
            latest_verifier_report=None,
            main_gap=main_gap,
        )
        if decision.action in {"macro", "microscopic"}:
            decision.needs_verifier = False
            decision.finalize = False
            decision.final_hypothesis_rationale = None
            decision.finalization_mode = "none"
            if decision.closure_justification_status in {"collecting", "blocked"}:
                decision.decision_gate_status = "needs_pairwise_discriminative_task"
            else:
                decision.decision_gate_status = "not_ready"
            return decision
        if decision.action == "verifier":
            decision.needs_verifier = True
            decision.finalize = False
            decision.finalization_mode = "none"
            decision.decision_gate_status = "needs_high_confidence_verifier"
            if not decision.task_instruction:
                decision.task_instruction = _default_follow_up_task_instruction(
                    "verifier",
                    decision.current_hypothesis,
                    {
                        "main_gap": main_gap,
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
            return decision
        if decision.action != "finalize":
            return decision
        if decision.verifier_supplement_status != "sufficient":
            return self._require_high_confidence_verifier(
                decision=decision,
                main_gap=main_gap,
            )
        finalization_mode = self._finalization_mode_for_decision(decision)
        if finalization_mode == "none":
            return self._require_closure_justification_task(
                decision=decision,
                main_gap=main_gap,
            )
        decision.finalize = True
        decision.finalization_mode = finalization_mode
        decision.decision_gate_status = (
            "ready_to_finalize_decisive" if finalization_mode == "decisive" else "ready_to_finalize_best_available"
        )
        decision.planned_agents = []
        decision.task_instruction = None
        decision.agent_task_instructions = {}  # type: ignore[assignment]
        return decision

    def _decision_margin(self, decision: PlannerDecision) -> float:
        runner_up = decision.runner_up_confidence or 0.0
        return round((decision.confidence or 0.0) - runner_up, 6)

    def _latest_verifier_supplement_state(
        self,
        latest_verifier_report: Any,
        decision_pair: list[str],
    ) -> dict[str, str | None]:
        default_state: dict[str, str | None] = {
            "pair_key": None,
            "status": "missing",
            "information_gain": "none",
            "evidence_relation": "no_new_info",
            "summary": None,
            "specificity": None,
        }
        current_pair_key = _decision_pair_key(decision_pair)
        if not isinstance(latest_verifier_report, dict):
            return default_state
        structured = latest_verifier_report.get("structured_results")
        if not isinstance(structured, dict):
            return default_state
        pair_key = str(
            structured.get("verifier_target_pair")
            or structured.get("pairwise_verifier_completed_for_pair")
            or current_pair_key
            or ""
        ).strip() or None
        specificity = str(structured.get("pairwise_verifier_evidence_specificity") or "").strip() or None
        status = _normalize_verifier_supplement_status(
            str(structured.get("verifier_supplement_status") or "").strip() or None
        )
        if status == "missing":
            tool_status = str(structured.get("status") or "").strip()
            if tool_status == "partial":
                status = "partial"
            elif tool_status == "success" and pair_key == current_pair_key:
                status = "sufficient"
        if pair_key is None and status in {"partial", "sufficient"}:
            pair_key = current_pair_key
        info_gain = _normalize_verifier_information_gain(
            str(structured.get("verifier_information_gain") or "").strip() or None
        )
        if info_gain == "none":
            if status == "partial":
                info_gain = "low"
            elif specificity == "generic_review":
                info_gain = "medium"
            elif specificity in {"close_family", "exact_compound"}:
                info_gain = "high"
        evidence_relation = _normalize_verifier_evidence_relation(
            str(structured.get("verifier_evidence_relation") or "").strip() or None
        )
        summary = str(
            structured.get("verifier_supplement_summary")
            or structured.get("retrieval_note")
            or ""
        ).strip() or None
        return {
            "pair_key": pair_key,
            "status": status,
            "information_gain": info_gain,
            "evidence_relation": evidence_relation,
            "summary": summary,
            "specificity": specificity,
        }

    def _hydrate_verifier_and_closure_state(
        self,
        *,
        decision: PlannerDecision,
        latest_verifier_report: Any,
        main_gap: str,
    ) -> PlannerDecision:
        current_pair_key = _decision_pair_key(decision.decision_pair)
        verifier_state = self._latest_verifier_supplement_state(
            latest_verifier_report,
            decision.decision_pair,
        )
        decision.verifier_supplement_target_pair = (
            decision.verifier_supplement_target_pair or current_pair_key
        )
        if verifier_state["pair_key"] == current_pair_key and verifier_state["status"] != "missing":
            decision.verifier_supplement_target_pair = current_pair_key
            decision.verifier_supplement_status = verifier_state["status"] or "missing"
            decision.verifier_information_gain = verifier_state["information_gain"] or "none"
            decision.verifier_evidence_relation = verifier_state["evidence_relation"] or "no_new_info"
            decision.verifier_supplement_summary = (
                decision.verifier_supplement_summary or verifier_state["summary"]
            )
            decision.pairwise_verifier_completed_for_pair = current_pair_key
            decision.pairwise_verifier_evidence_specificity = verifier_state["specificity"]  # type: ignore[assignment]
        else:
            decision.pairwise_verifier_completed_for_pair = None
            decision.pairwise_verifier_evidence_specificity = verifier_state["specificity"]  # type: ignore[assignment]

        if not decision.closure_justification_target_pair:
            decision.closure_justification_target_pair = current_pair_key
        if current_pair_key is None:
            decision.closure_justification_status = "missing"
            decision.closure_justification_evidence_source = None
            decision.closure_justification_basis = None
            decision.closure_justification_summary = None
            return decision

        if decision.pairwise_task_completed_for_pair == current_pair_key:
            if decision.pairwise_task_outcome == "decisive":
                decision.closure_justification_status = "sufficient"
                if decision.verifier_supplement_status == "sufficient":
                    decision.closure_justification_evidence_source = "mixed"
                else:
                    decision.closure_justification_evidence_source = "internal"
                decision.closure_justification_basis = "existing_evidence"
                decision.closure_justification_summary = (
                    decision.closure_justification_summary
                    or decision.pairwise_task_rationale
                    or f"Existing internal evidence already separates '{decision.current_hypothesis}' from '{decision.runner_up_hypothesis or 'unknown'}'."
                )
                return decision
            if decision.pairwise_task_outcome == "inconclusive":
                if decision.closure_justification_status == "missing":
                    decision.closure_justification_status = "collecting"
                decision.closure_justification_evidence_source = (
                    decision.closure_justification_evidence_source or "internal"
                )
                decision.closure_justification_basis = decision.closure_justification_basis or "existing_evidence"
                decision.closure_justification_summary = (
                    decision.closure_justification_summary
                    or decision.pairwise_task_rationale
                    or f"Existing internal evidence narrowed '{decision.current_hypothesis}' versus '{decision.runner_up_hypothesis or 'unknown'}' but did not fully close the gap: {main_gap}"
                )
                return decision
            if decision.pairwise_task_outcome == "failed":
                decision.closure_justification_status = "blocked"
                decision.closure_justification_evidence_source = "internal"
                decision.closure_justification_basis = "new_targeted_task"
                decision.closure_justification_summary = (
                    decision.closure_justification_summary
                    or decision.pairwise_task_rationale
                    or f"The previous internal closure task failed on the unresolved gap: {main_gap}"
                )
                return decision

        return decision

    def _finalization_mode_for_decision(self, decision: PlannerDecision) -> str:
        if decision.verifier_supplement_status != "sufficient":
            return "none"
        if decision.closure_justification_status == "sufficient":
            if self._decision_margin(decision) >= self._config.finalize_margin_threshold:
                return "decisive"
            return "best_available"
        if decision.closure_justification_status in {"collecting", "blocked"}:
            return "best_available"
        return "none"

    def _require_pairwise_discriminative_task(
        self,
        *,
        decision: PlannerDecision,
        main_gap: str,
    ) -> PlannerDecision:
        pairwise_task_agent = decision.pairwise_task_agent or _default_pairwise_task_agent(main_gap, decision.action)
        decision.action = pairwise_task_agent
        decision.needs_verifier = False
        decision.finalize = False
        decision.finalization_mode = "none"
        decision.planned_agents = [pairwise_task_agent]
        decision.decision_gate_status = "needs_pairwise_discriminative_task"
        decision.pairwise_task_agent = pairwise_task_agent  # type: ignore[assignment]
        decision.pairwise_task_rationale = decision.pairwise_task_rationale or _default_pairwise_task_rationale(
            decision.current_hypothesis,
            decision.runner_up_hypothesis or "unknown",
            main_gap,
            pairwise_task_agent,
        )
        decision.task_instruction = _default_follow_up_task_instruction(
            pairwise_task_agent,
            decision.current_hypothesis,
            {
                "main_gap": main_gap,
                "challenger_hypothesis": decision.runner_up_hypothesis,
                "pairwise_decision_question": _pairwise_decision_question(
                    decision.current_hypothesis,
                    decision.runner_up_hypothesis or "unknown",
                    main_gap,
                ),
                "capability_assessment": decision.capability_assessment,
                "contraction_reason": decision.contraction_reason,
                "pairwise_task_rationale": decision.pairwise_task_rationale,
                "is_pairwise_discriminative_task": True,
            },
        )
        decision.agent_task_instructions = _normalize_agent_task_instructions(
            {pairwise_task_agent: decision.task_instruction or ""}
        )  # type: ignore[assignment]
        decision.final_hypothesis_rationale = None
        return decision

    def _require_closure_justification_task(
        self,
        *,
        decision: PlannerDecision,
        main_gap: str,
    ) -> PlannerDecision:
        if decision.action not in {"macro", "microscopic"}:
            decision = self._require_pairwise_discriminative_task(
                decision=decision,
                main_gap=main_gap,
            )
        else:
            decision = self._require_pairwise_discriminative_task(
                decision=decision,
                main_gap=main_gap,
            )
        decision.closure_justification_target_pair = _decision_pair_key(decision.decision_pair)
        decision.closure_justification_status = "collecting"
        decision.closure_justification_evidence_source = None
        decision.closure_justification_basis = "new_targeted_task"
        decision.closure_justification_summary = (
            f"A final closure-justification task is still needed to explain why '{decision.current_hypothesis}' "
            f"stays ahead of '{decision.runner_up_hypothesis or 'unknown'}' on: {main_gap}"
        )
        return decision

    def _require_high_confidence_verifier(
        self,
        *,
        decision: PlannerDecision,
        main_gap: str,
    ) -> PlannerDecision:
        decision.action = "verifier"
        decision.needs_verifier = True
        decision.finalize = False
        decision.finalization_mode = "none"
        decision.planned_agents = ["verifier"]
        decision.decision_gate_status = "needs_high_confidence_verifier"
        decision.verifier_supplement_target_pair = _decision_pair_key(decision.decision_pair)
        decision.verifier_supplement_status = "missing"
        decision.verifier_information_gain = "none"
        decision.verifier_evidence_relation = "no_new_info"
        decision.closure_justification_target_pair = _decision_pair_key(decision.decision_pair)
        decision.task_instruction = _default_follow_up_task_instruction(
            "verifier",
            decision.current_hypothesis,
            {
                "main_gap": main_gap,
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
        decision.final_hypothesis_rationale = None
        return decision

    def _normalize_action(
        self,
        action: str,
        *,
        post_verifier: bool,
        task_instruction: str | None = None,
        agent_task_instructions: dict[str, str] | None = None,
    ) -> str:
        del post_verifier
        normalized_action = (action or "").strip()
        if normalized_action in {"macro", "microscopic", "verifier", "finalize", "macro_and_microscopic"}:
            return normalized_action

        lowered_action = normalized_action.lower()
        action_aliases = {
            "request_verifier_supplement": "verifier",
            "request_verifier": "verifier",
            "verifier_supplement": "verifier",
            "high_confidence_verifier": "verifier",
            "request_high_confidence_verifier": "verifier",
            "finalize_best_available": "finalize",
            "best_available_finalize": "finalize",
            "finalize_decisive": "finalize",
            "decisive_finalize": "finalize",
            "prepare_finalization": "finalize",
            "planner_synthesis": "finalize",
            "closure_writeup": "finalize",
            "closure_write_up": "finalize",
        }
        aliased_action = action_aliases.get(lowered_action)
        if aliased_action is not None:
            return aliased_action

        normalized_task_instruction = (task_instruction or "").strip()
        normalized_instruction_lower = normalized_task_instruction.lower()
        normalized_agent_keys = set((agent_task_instructions or {}).keys())
        if normalized_task_instruction.startswith("Verifier:") or (
            "verifier" in normalized_agent_keys and "microscopic" not in normalized_agent_keys
        ):
            return "verifier"
        if normalized_task_instruction.startswith("No further agent execution.") or (
            "prepare final closure write-up" in normalized_instruction_lower
            or "prepare finalization" in normalized_instruction_lower
            or "planner-level closure" in normalized_instruction_lower
        ):
            return "finalize"
        return "microscopic"

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
                    "first-round microscopic work must stay low-cost and bounded; request exactly one baseline-only "
                    "S0/S1 action on the shared prepared structure and do not bundle conformer sensitivity, torsion "
                    "sensitivity, or multi-step follow-ups into the initial microscopic task"
                ),
                "microscopic_supported_scope": (
                    "first-round scope is a single run_baseline_bundle-style route: shared-structure reuse, low-cost "
                    "Amesp aTB S0 optimization, and a bounded S1 vertical excitation; conformer/torsion follow-ups "
                    "must be separate later actions"
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
            "verifier_supplement_target_pair": state.verifier_supplement_target_pair,
            "verifier_supplement_status": state.verifier_supplement_status,
            "verifier_information_gain": state.verifier_information_gain,
            "verifier_evidence_relation": state.verifier_evidence_relation,
            "verifier_supplement_summary": state.verifier_supplement_summary,
            "closure_justification_target_pair": state.closure_justification_target_pair,
            "closure_justification_status": state.closure_justification_status,
            "closure_justification_evidence_source": state.closure_justification_evidence_source,
            "closure_justification_basis": state.closure_justification_basis,
            "closure_justification_summary": state.closure_justification_summary,
            "pairwise_task_agent": state.pairwise_task_agent,
            "pairwise_task_completed_for_pair": state.pairwise_task_completed_for_pair,
            "pairwise_task_outcome": state.pairwise_task_outcome,
            "pairwise_task_rationale": state.pairwise_task_rationale,
            "finalization_mode": state.finalization_mode,
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
            "shared_structure_error": state.shared_structure_error,
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
        latest_microscopic = (
            state.microscopic_reports[-1].model_dump(mode="json") if state.microscopic_reports else None
        )
        payload = {
            "smiles": state.smiles,
            "current_hypothesis": state.current_hypothesis,
            "current_confidence": state.confidence,
            "runner_up_hypothesis": state.runner_up_hypothesis,
            "runner_up_confidence": state.runner_up_confidence,
            "decision_pair": list(state.decision_pair),
            "decision_gate_status": state.decision_gate_status,
            "verifier_supplement_target_pair": state.verifier_supplement_target_pair,
            "verifier_supplement_status": state.verifier_supplement_status,
            "verifier_information_gain": state.verifier_information_gain,
            "verifier_evidence_relation": state.verifier_evidence_relation,
            "verifier_supplement_summary": state.verifier_supplement_summary,
            "closure_justification_target_pair": state.closure_justification_target_pair,
            "closure_justification_status": state.closure_justification_status,
            "closure_justification_evidence_source": state.closure_justification_evidence_source,
            "closure_justification_basis": state.closure_justification_basis,
            "closure_justification_summary": state.closure_justification_summary,
            "pairwise_task_agent": state.pairwise_task_agent,
            "pairwise_task_completed_for_pair": state.pairwise_task_completed_for_pair,
            "pairwise_task_outcome": state.pairwise_task_outcome,
            "pairwise_task_rationale": state.pairwise_task_rationale,
            "finalization_mode": state.finalization_mode,
            "pairwise_verifier_completed_for_pair": state.pairwise_verifier_completed_for_pair,
            "pairwise_verifier_evidence_specificity": state.pairwise_verifier_evidence_specificity,
            "working_memory_summary": [entry.model_dump(mode="json") for entry in state.working_memory],
            "recent_rounds_context": self._working_memory.build_recent_rounds_context(state),
            "recent_capability_context": self._working_memory.build_capability_context(state),
            "verifier_report": state.verifier_reports[-1].model_dump(mode="json")
            if state.verifier_reports
            else None,
            "latest_microscopic_report": latest_microscopic,
            "recent_internal_evidence_summary": state.latest_evidence_summary,
            "hypothesis_pool": [entry.model_dump(mode="json") for entry in state.hypothesis_pool],
            "shared_structure_status": state.shared_structure_status,
            "shared_structure_error": state.shared_structure_error,
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
