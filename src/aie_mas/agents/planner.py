from __future__ import annotations

from typing import Any

from aie_mas.compat.langchain import RunnableLambda, prompt_value_to_text
from aie_mas.graph.state import AieMasState, HypothesisEntry, PlannerDecision
from aie_mas.utils.prompts import PromptRepository
from aie_mas.utils.smiles import extract_smiles_features


class PlannerAgent:
    def __init__(self, prompts: PromptRepository, verifier_threshold: float) -> None:
        self._prompts = prompts
        self._verifier_threshold = verifier_threshold
        self._initial_model = RunnableLambda(self._run_initial_model)
        self._diagnosis_model = RunnableLambda(self._run_diagnosis_model)
        self._reweight_model = RunnableLambda(self._run_reweight_model)

    def plan_initial(self, state: AieMasState) -> dict[str, Any]:
        payload = {"user_query": state.user_query, "smiles": state.smiles}
        rendered_prompt = self._prompts.render("planner_initial", payload)
        return self._initial_model.invoke(
            {"prompt_text": prompt_value_to_text(rendered_prompt), "context": payload}
        )

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
            "latest_macro_report": latest_macro,
            "latest_microscopic_report": latest_microscopic,
            "latest_verifier_report": latest_verifier,
            "hypothesis_pool": [entry.model_dump(mode="json") for entry in state.hypothesis_pool],
        }
        rendered_prompt = self._prompts.render("planner_diagnosis", payload)
        return self._diagnosis_model.invoke(
            {"prompt_text": prompt_value_to_text(rendered_prompt), "context": payload}
        )

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
        return self._reweight_model.invoke(
            {"prompt_text": prompt_value_to_text(rendered_prompt), "context": payload}
        )

    def _run_initial_model(self, input_value: dict[str, Any]) -> dict[str, Any]:
        context = input_value["context"]
        features = extract_smiles_features(context["smiles"])
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
        diagnosis = (
            f"Current task: assess the likely emission mechanism for SMILES {context['smiles']}. "
            f"The leading working hypothesis is {current_hypothesis}. "
            "This remains preliminary because only the user query and raw SMILES are available so far. "
            "The first round should therefore collect both macro structural evidence and microscopic S0/S1 "
            "optimization evidence before any external verification or finalization."
        )
        decision = PlannerDecision(
            diagnosis=diagnosis,
            action="macro_and_microscopic",
            current_hypothesis=current_hypothesis,
            confidence=confidence,
            needs_verifier=False,
            finalize=False,
            planned_agents=["macro", "microscopic"],
        )
        return {"hypothesis_pool": hypothesis_pool, "decision": decision}

    def _run_diagnosis_model(self, input_value: dict[str, Any]) -> dict[str, Any]:
        context = input_value["context"]
        macro_report = context["latest_macro_report"] or {}
        microscopic_report = context["latest_microscopic_report"] or {}
        macro_results = macro_report.get("structured_results", {})
        micro_results = microscopic_report.get("structured_results", {})

        confidence = float(context["current_confidence"] or 0.4)
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

        confidence = round(min(0.89, confidence + support_score), 3)
        evidence_impact = "strengthens" if support_score >= 0.22 else "is still insufficient for"
        evidence_summary = "; ".join(evidence_bits) if evidence_bits else "no new internal evidence was added"
        unresolved = "External supervision has not checked whether the current internal signal is consistent."
        main_gap = "Verifier evidence is required before a temporary conclusion can be trusted."

        if confidence >= self._verifier_threshold:
            action = "verifier"
            needs_verifier = True
            planned_agents = ["verifier"]
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

        diagnosis = (
            f"Current leading hypothesis: {context['current_hypothesis']}. "
            f"New evidence added: {evidence_summary}. "
            f"This new evidence {evidence_impact} the current hypothesis at confidence {confidence:.2f}. "
            f"What remains unresolved: {unresolved} "
            f"The main gap is {main_gap} "
            f"The chosen next action is {action} because it addresses the highest-value missing evidence now."
        )
        decision = PlannerDecision(
            diagnosis=diagnosis,
            action=action,
            current_hypothesis=context["current_hypothesis"],
            confidence=confidence,
            needs_verifier=needs_verifier,
            finalize=False,
            planned_agents=planned_agents,
        )
        return {
            "decision": decision,
            "evidence_summary": evidence_summary,
            "main_gap": main_gap,
            "conflict_status": "none",
        }

    def _run_reweight_model(self, input_value: dict[str, Any]) -> dict[str, Any]:
        context = input_value["context"]
        verifier_report = context["verifier_report"] or {}
        verifier_cards = verifier_report.get("structured_results", {}).get("evidence_cards", [])
        support_count = sum(card.get("relation_to_hypothesis") == "support" for card in verifier_cards)
        conflict_count = sum(card.get("relation_to_hypothesis") == "conflict" for card in verifier_cards)
        current_confidence = float(context["current_confidence"] or 0.5)

        if conflict_count > support_count:
            next_hypothesis = context["hypothesis_pool"][1]["name"]
            confidence = round(max(0.42, current_confidence - 0.18), 3)
            conflict_status = "strong"
            main_gap = "The switched hypothesis needs fresh internal evidence."
            diagnosis = (
                f"Verifier evidence conflicts with the current hypothesis {context['current_hypothesis']}. "
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
            )
        elif support_count == 0 and conflict_count == 0:
            confidence = round(max(0.45, current_confidence - 0.04), 3)
            conflict_status = "uncertain"
            main_gap = "Verifier evidence is neutral, so one more internal refinement step is needed."
            diagnosis = (
                f"Verifier evidence is neutral for the current hypothesis {context['current_hypothesis']}. "
                "There is no strong support and no strong conflict, so a hypothesis switch is not necessary. "
                "The case cannot be finalized yet because verifier evidence is insufficient."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="microscopic",
                current_hypothesis=context["current_hypothesis"],
                confidence=confidence,
                needs_verifier=False,
                finalize=False,
                planned_agents=["microscopic"],
            )
        else:
            confidence = round(min(0.95, current_confidence + 0.08 + support_count * 0.02), 3)
            conflict_status = "weak" if conflict_count else "none"
            main_gap = "No critical evidence gap remains in the mock first-stage workflow."
            diagnosis = (
                f"Verifier evidence supports the current hypothesis {context['current_hypothesis']}. "
                f"The verifier returned {support_count} supportive card(s) and {conflict_count} conflicting card(s). "
                f"The conflict level is {conflict_status}, so a hypothesis switch is not necessary. "
                "The case can now be finalized because the internal evidence and verifier check are aligned."
            )
            decision = PlannerDecision(
                diagnosis=diagnosis,
                action="finalize",
                current_hypothesis=context["current_hypothesis"],
                confidence=confidence,
                needs_verifier=False,
                finalize=True,
                planned_agents=[],
            )

        return {
            "decision": decision,
            "evidence_summary": (
                f"Verifier returned {support_count} support card(s) and {conflict_count} conflict card(s)."
            ),
            "main_gap": main_gap,
            "conflict_status": conflict_status,
        }
