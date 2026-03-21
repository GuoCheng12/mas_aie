from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AieMasState, HypothesisEntry, PlannerDecision
from aie_mas.llm.openai_compatible import OpenAICompatiblePlannerClient
from aie_mas.memory.working import WorkingMemoryManager
from aie_mas.utils.prompts import PromptRepository
from aie_mas.utils.smiles import extract_smiles_features


class PlannerInitialResponse(BaseModel):
    hypothesis_pool: list[HypothesisEntry]
    current_hypothesis: str
    confidence: float
    diagnosis: str
    action: str = "macro_and_microscopic"
    task_instruction: str = ""
    agent_task_instructions: dict[str, str] = Field(default_factory=dict)


class PlannerRoundResponse(BaseModel):
    diagnosis: str
    action: str
    current_hypothesis: str
    confidence: float
    needs_verifier: bool = False
    finalize: bool = False
    task_instruction: str = ""
    agent_task_instructions: dict[str, str] = Field(default_factory=dict)
    evidence_summary: str = "No additional evidence summary was provided."
    main_gap: str = "No main gap was provided."
    conflict_status: str = "none"
    information_gain_assessment: str = "Information gain has not been assessed."
    gap_trend: str = "Gap trend has not been assessed."
    stagnation_detected: bool = False


def _normalize_agent_task_instructions(raw_mapping: dict[str, str]) -> dict[str, str]:
    allowed_agents = {"macro", "microscopic", "verifier"}
    return {
        agent_name: instruction.strip()
        for agent_name, instruction in raw_mapping.items()
        if agent_name in allowed_agents and instruction.strip()
    }


def _default_initial_agent_task_instructions(current_hypothesis: str) -> dict[str, str]:
    return {
        "macro": (
            f"Assess macro-level structural evidence relevant to the current working hypothesis "
            f"'{current_hypothesis}'. Summarize low-cost structural indicators only."
        ),
        "microscopic": (
            f"Run the first-round fixed S0/S1 microscopic proxy task for the current working hypothesis "
            f"'{current_hypothesis}'. Report local excited-state proxy results only."
        ),
    }


def _default_follow_up_task_instruction(
    action: str,
    current_hypothesis: str,
    payload: dict[str, Any],
) -> str | None:
    if action == "macro":
        return (
            f"Collect additional macro-level structural evidence for the current working hypothesis "
            f"'{current_hypothesis}'. Focus on the current gap: "
            f"{payload.get('main_gap') or 'clarify the unresolved macro signal.'}"
        )
    if action == "microscopic":
        return (
            f"Collect additional microscopic evidence for the current working hypothesis "
            f"'{current_hypothesis}'. Focus on the current gap: "
            f"{payload.get('main_gap') or 'refine the unresolved microscopic signal.'}"
        )
    if action == "verifier":
        return (
            f"Retrieve external supervision evidence for the current working hypothesis "
            f"'{current_hypothesis}' and clarify the current gap: "
            f"{payload.get('main_gap') or 'check whether the internal signal is externally consistent.'}"
        )
    return None


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
        features = extract_smiles_features(payload["smiles"])
        if features.hetero_atom_count >= 3 and features.donor_acceptor_proxy >= 1:
            hypothesis_pool = [
                HypothesisEntry(
                    name="ICT-assisted emission with aggregation-enabled rigidification",
                    confidence=0.46,
                    rationale="The scaffold contains multiple hetero atoms and a donor/acceptor proxy.",
                ),
                HypothesisEntry(
                    name="restriction of intramolecular motion (RIM)-dominated AIE",
                    confidence=0.38,
                    rationale="The molecule is still conjugated and could benefit from motion restriction.",
                ),
                HypothesisEntry(
                    name="packing-assisted excimer or aggregate-state emission",
                    confidence=0.16,
                    rationale="Conjugated surfaces can still create aggregate-state pathways.",
                ),
            ]
        else:
            hypothesis_pool = [
                HypothesisEntry(
                    name="restriction of intramolecular motion (RIM)-dominated AIE",
                    confidence=0.44,
                    rationale="Bulky aromatic and branched fragments suggest motion restriction is relevant.",
                ),
                HypothesisEntry(
                    name="ICT-assisted emission with aggregation-enabled rigidification",
                    confidence=0.28,
                    rationale="Conjugation plus hetero atoms can still contribute through charge redistribution.",
                ),
                HypothesisEntry(
                    name="packing-assisted excimer or aggregate-state emission",
                    confidence=0.18,
                    rationale="Extended aromatic fragments could also enable packing-driven emission.",
                ),
            ]
        current_hypothesis = hypothesis_pool[0].name
        confidence = hypothesis_pool[0].confidence or 0.4
        agent_task_instructions = _default_initial_agent_task_instructions(current_hypothesis)
        diagnosis = (
            f"Current task: assess the likely emission mechanism for SMILES {payload['smiles']}. "
            f"The leading working hypothesis is {current_hypothesis}. "
            "This remains preliminary because only the user query and raw SMILES are available so far. "
            "The first round should therefore collect both macro structural evidence and microscopic S0/S1 "
            "optimization evidence before any external verification or finalization."
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
            ),
        }

    def plan_diagnosis(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _ = rendered_prompt
        macro_report = payload["latest_macro_report"] or {}
        microscopic_report = payload["latest_microscopic_report"] or {}
        macro_results = macro_report.get("structured_results", {})
        micro_results = microscopic_report.get("structured_results", {})
        macro_task_understanding = str(macro_report.get("task_understanding") or "").strip()
        macro_execution_plan = str(macro_report.get("execution_plan") or "").strip()
        macro_result_summary = str(macro_report.get("result_summary") or "").strip()
        micro_task_understanding = str(microscopic_report.get("task_understanding") or "").strip()
        micro_execution_plan = str(microscopic_report.get("execution_plan") or "").strip()
        micro_result_summary = str(microscopic_report.get("result_summary") or "").strip()
        local_uncertainty_bits = [
            str(macro_report.get("remaining_local_uncertainty") or "").strip(),
            str(microscopic_report.get("remaining_local_uncertainty") or "").strip(),
        ]

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
            if micro_execution_plan:
                evidence_bits.append(f"microscopic execution plan: {micro_execution_plan}")
            if micro_result_summary:
                evidence_bits.append(f"microscopic agent summary: {micro_result_summary}")

        confidence = round(min(0.89, confidence + support_score), 3)
        evidence_impact = "strengthens" if support_score >= 0.22 else "is still insufficient for"
        evidence_summary = "; ".join(evidence_bits) if evidence_bits else "no new internal evidence was added"
        unresolved_fragments = [
            fragment
            for fragment in local_uncertainty_bits
            if fragment and fragment != "Remaining local uncertainty was not provided."
        ]
        unresolved = (
            " ".join(unresolved_fragments)
            if unresolved_fragments
            else "External supervision has not checked whether the current internal signal is consistent."
        )
        main_gap = "Verifier evidence is required before a temporary conclusion can be trusted."
        information_gain_assessment = "The current round adds substantive new information."
        gap_trend = "The main gap is shrinking."
        stagnation_detected = False

        recent_rounds_context = payload.get("recent_rounds_context", [])
        if len(recent_rounds_context) >= 2:
            latest_recent = recent_rounds_context[-1]
            previous_recent = recent_rounds_context[-2]
            repeated_gap = latest_recent.get("main_gap") == previous_recent.get("main_gap")
            repeated_action = latest_recent.get("action_taken") == previous_recent.get("action_taken")
            if repeated_gap and repeated_action:
                information_gain_assessment = (
                    "Compared with the recent rounds, the current loop is adding limited new information."
                )
                gap_trend = "The main gap is not shrinking."
                stagnation_detected = True

        if confidence >= self._verifier_threshold or stagnation_detected:
            action = "verifier"
            needs_verifier = True
            planned_agents = ["verifier"]
            if stagnation_detected:
                main_gap = "Recent rounds indicate stagnation, so external supervision is needed."
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
            {"main_gap": main_gap},
        )
        agent_task_instructions = (
            {action: task_instruction}
            if action in {"macro", "microscopic", "verifier"} and task_instruction
            else {}
        )

        diagnosis = (
            f"Current leading hypothesis: {payload['current_hypothesis']}. "
            f"New evidence added: {evidence_summary}. "
            f"This new evidence {evidence_impact} the current hypothesis at confidence {confidence:.2f}. "
            f"What remains unresolved: {unresolved} "
            f"Relative to the recent rounds, {information_gain_assessment} "
            f"The current gap trend is: {gap_trend} "
            f"Stagnation status: {'stagnation detected.' if stagnation_detected else 'no stagnation detected.'} "
            f"The main gap is {main_gap} "
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
                information_gain_assessment=information_gain_assessment,
                gap_trend=gap_trend,
                stagnation_detected=stagnation_detected,
            ),
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": "none",
            "information_gain_assessment": information_gain_assessment,
            "gap_trend": gap_trend,
        }

    def plan_reweight_or_finalize(self, rendered_prompt: Any, payload: dict[str, Any]) -> dict[str, Any]:
        _ = rendered_prompt
        verifier_report = payload["verifier_report"] or {}
        verifier_cards = verifier_report.get("structured_results", {}).get("evidence_cards", [])
        verifier_result_summary = str(verifier_report.get("result_summary") or "").strip()
        support_count = sum(card.get("relation_to_hypothesis") == "support" for card in verifier_cards)
        conflict_count = sum(card.get("relation_to_hypothesis") == "conflict" for card in verifier_cards)
        current_confidence = float(payload["current_confidence"] or 0.5)
        current_hypothesis = payload["current_hypothesis"]
        next_hypothesis = current_hypothesis
        if len(payload["hypothesis_pool"]) > 1:
            next_hypothesis = payload["hypothesis_pool"][1]["name"]

        if conflict_count > support_count:
            confidence = round(max(0.42, current_confidence - 0.18), 3)
            conflict_status = "strong"
            main_gap = "The switched hypothesis needs fresh internal evidence."
            diagnosis = (
                f"Verifier evidence conflicts with the current hypothesis {current_hypothesis}. "
                "The conflict is strong because conflicting cards outnumber supportive cards. "
                f"A hypothesis switch is necessary, so the leading hypothesis becomes {next_hypothesis}. "
                "The case cannot be finalized yet because the new leading hypothesis has not been re-tested."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="macro",
                current_hypothesis=next_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["macro"],
                task_instruction=_default_follow_up_task_instruction(
                    "macro",
                    next_hypothesis,
                    {"main_gap": main_gap},
                ),
                agent_task_instructions=_normalize_agent_task_instructions(
                    {
                        "macro": _default_follow_up_task_instruction(
                            "macro",
                            next_hypothesis,
                            {"main_gap": main_gap},
                        )
                        or ""
                    }
                ),
            )
        elif support_count > 0 and conflict_count > 0:
            confidence = round(max(0.48, current_confidence - 0.03), 3)
            conflict_status = "weak"
            main_gap = "Weak verifier conflict remains, so one more internal refinement step is needed."
            diagnosis = (
                f"Verifier evidence both supports and conflicts with the current hypothesis {current_hypothesis}. "
                "The conflict is weak because supportive cards are still present and conflict does not dominate. "
                "A hypothesis switch is not necessary, but the case cannot be finalized yet. "
                "Further targeted microscopic refinement is needed to resolve the weak conflict."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="microscopic",
                current_hypothesis=current_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["microscopic"],
                task_instruction=_default_follow_up_task_instruction(
                    "microscopic",
                    current_hypothesis,
                    {"main_gap": main_gap},
                ),
                agent_task_instructions=_normalize_agent_task_instructions(
                    {
                        "microscopic": _default_follow_up_task_instruction(
                            "microscopic",
                            current_hypothesis,
                            {"main_gap": main_gap},
                        )
                        or ""
                    }
                ),
            )
        elif support_count == 0 and conflict_count == 0:
            confidence = round(max(0.45, current_confidence - 0.04), 3)
            conflict_status = "uncertain"
            main_gap = "Verifier evidence is neutral, so one more internal refinement step is needed."
            diagnosis = (
                f"Verifier evidence is neutral for the current hypothesis {current_hypothesis}. "
                "There is no strong support and no strong conflict, so a hypothesis switch is not necessary. "
                "The case cannot be finalized yet because verifier evidence is insufficient."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="microscopic",
                current_hypothesis=current_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["microscopic"],
                task_instruction=_default_follow_up_task_instruction(
                    "microscopic",
                    current_hypothesis,
                    {"main_gap": main_gap},
                ),
                agent_task_instructions=_normalize_agent_task_instructions(
                    {
                        "microscopic": _default_follow_up_task_instruction(
                            "microscopic",
                            current_hypothesis,
                            {"main_gap": main_gap},
                        )
                        or ""
                    }
                ),
            )
        else:
            confidence = round(min(0.95, current_confidence + 0.08 + support_count * 0.02), 3)
            conflict_status = "none"
            main_gap = "No critical evidence gap remains in the current workflow."
            diagnosis = (
                f"Verifier evidence supports the current hypothesis {current_hypothesis}. "
                f"The verifier returned {support_count} supportive card(s) and {conflict_count} conflicting card(s). "
                "A hypothesis switch is not necessary. "
                "The case can now be finalized because the internal evidence and verifier check are aligned."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="finalize",
                current_hypothesis=current_hypothesis,
                confidence=confidence,
                needs_verifier=False,
                finalize=True,
                planned_agents=[],
            )

        return {
            "decision": decision,
            "evidence_summary": verifier_result_summary
            or f"Verifier returned {support_count} support card(s) and {conflict_count} conflict card(s).",
            "main_gap": main_gap,
            "conflict_status": conflict_status,
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
                _default_initial_agent_task_instructions(response.current_hypothesis)
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
                decision.task_instruction = _default_follow_up_task_instruction(
                    "verifier",
                    decision.current_hypothesis,
                    {"main_gap": main_gap},
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
            decision, conflict_status, main_gap = self._postprocess_reweight(payload, decision, conflict_status, main_gap)

        return {
            "decision": decision,
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": conflict_status,
            "information_gain_assessment": decision.information_gain_assessment,
            "gap_trend": decision.gap_trend,
        }

    def _postprocess_reweight(
        self,
        payload: dict[str, Any],
        decision: PlannerDecision,
        conflict_status: str,
        main_gap: str,
    ) -> tuple[PlannerDecision, str, str]:
        verifier_report = payload["verifier_report"] or {}
        verifier_cards = verifier_report.get("structured_results", {}).get("evidence_cards", [])
        support_count = sum(card.get("relation_to_hypothesis") == "support" for card in verifier_cards)
        conflict_count = sum(card.get("relation_to_hypothesis") == "conflict" for card in verifier_cards)
        current_hypothesis = payload["current_hypothesis"]
        fallback_switch = current_hypothesis
        if len(payload["hypothesis_pool"]) > 1:
            fallback_switch = payload["hypothesis_pool"][1]["name"]

        if conflict_count > support_count:
            conflict_status = "strong"
            decision.finalize = False
            decision.needs_verifier = False
            decision.action = "macro"
            decision.current_hypothesis = (
                decision.current_hypothesis
                if decision.current_hypothesis != current_hypothesis
                else fallback_switch
            )
            decision.planned_agents = ["macro"]
            decision.task_instruction = _default_follow_up_task_instruction(
                "macro",
                decision.current_hypothesis,
                {"main_gap": main_gap},
            )
            decision.agent_task_instructions = _normalize_agent_task_instructions(
                {"macro": decision.task_instruction or ""}
            )  # type: ignore[assignment]
            main_gap = "The switched hypothesis needs fresh internal evidence."
        elif support_count > 0 and conflict_count > 0:
            conflict_status = "weak"
            decision.finalize = False
            decision.needs_verifier = False
            decision.action = "microscopic"
            decision.current_hypothesis = current_hypothesis
            decision.planned_agents = ["microscopic"]
            decision.task_instruction = _default_follow_up_task_instruction(
                "microscopic",
                decision.current_hypothesis,
                {"main_gap": main_gap},
            )
            decision.agent_task_instructions = _normalize_agent_task_instructions(
                {"microscopic": decision.task_instruction or ""}
            )  # type: ignore[assignment]
            main_gap = "Weak verifier conflict remains, so one more internal refinement step is needed."
        elif support_count == 0 and conflict_count == 0:
            conflict_status = "uncertain"
            decision.finalize = False
            decision.needs_verifier = False
            decision.action = "microscopic"
            decision.current_hypothesis = current_hypothesis
            decision.planned_agents = ["microscopic"]
            decision.task_instruction = _default_follow_up_task_instruction(
                "microscopic",
                decision.current_hypothesis,
                {"main_gap": main_gap},
            )
            decision.agent_task_instructions = _normalize_agent_task_instructions(
                {"microscopic": decision.task_instruction or ""}
            )  # type: ignore[assignment]
            main_gap = "Verifier evidence is neutral, so one more internal refinement step is needed."
        else:
            conflict_status = "none"
            decision.action = "finalize"
            decision.finalize = True
            decision.needs_verifier = False
            decision.current_hypothesis = current_hypothesis
            decision.planned_agents = []
            decision.task_instruction = None
            decision.agent_task_instructions = {}  # type: ignore[assignment]
            main_gap = "No critical evidence gap remains in the current workflow."

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
        payload = {"user_query": state.user_query, "smiles": state.smiles}
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
            "current_hypothesis": state.current_hypothesis,
            "current_confidence": state.confidence,
            "working_memory_summary": [entry.model_dump(mode="json") for entry in state.working_memory],
            "recent_rounds_context": self._working_memory.build_recent_rounds_context(state),
            "latest_macro_report": latest_macro,
            "latest_microscopic_report": latest_microscopic,
            "latest_verifier_report": latest_verifier,
            "hypothesis_pool": [entry.model_dump(mode="json") for entry in state.hypothesis_pool],
        }
        rendered_prompt = self._prompts.render("planner_diagnosis", payload)
        return self._backend.plan_diagnosis(rendered_prompt, payload)

    def plan_reweight_or_finalize(self, state: AieMasState) -> dict[str, Any]:
        payload = {
            "current_hypothesis": state.current_hypothesis,
            "current_confidence": state.confidence,
            "working_memory_summary": [entry.model_dump(mode="json") for entry in state.working_memory],
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
