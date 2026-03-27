from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import AgentReport, MoleculeIdentityContext, VerifierEvidenceCard
from aie_mas.llm.openai_compatible import OpenAICompatibleVerifierClient
from aie_mas.utils.prompts import PromptRepository

_EVIDENCE_SPECIFICITY_ORDER = {
    "no_direct_hit": 0,
    "generic_review": 1,
    "close_family": 2,
    "exact_compound": 3,
}


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


def _pairwise_key(champion_hypothesis: str, challenger_hypothesis: str) -> str:
    return f"{champion_hypothesis}__vs__{challenger_hypothesis}"


class VerifierRetrievedCardDraft(BaseModel):
    card_id: str = ""
    source: str = ""
    title: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    observation: str = ""
    topic_tags: list[str] = Field(default_factory=list)
    evidence_kind: str = "external_summary"
    why_relevant: Optional[str] = None
    query_group: str = "similar_family"
    match_level: str = "generic_mechanistic_context"
    mechanism_claim: Optional[str] = None
    experimental_context: Optional[str] = None
    comparison_bucket: str = ""
    relevant_hypotheses: list[str] = Field(default_factory=list)
    criterion_type: Optional[str] = None
    evidence_specificity: str = "generic_review"


class VerifierRetrievalResponse(BaseModel):
    retrieval_note: str = "No retrieval note was provided."
    evidence_cards: list[VerifierRetrievedCardDraft] = Field(default_factory=list)


class OpenAIVerifierEvidenceTool:
    name = "verifier_evidence_lookup"

    def __init__(
        self,
        config: Optional[AieMasConfig] = None,
        client: Optional[OpenAICompatibleVerifierClient] = None,
        prompts: Optional[PromptRepository] = None,
    ) -> None:
        self._config = config or AieMasConfig()
        self._client = client or OpenAICompatibleVerifierClient(self._config)
        self._prompts = prompts or _default_prompt_repository()

    def invoke(
        self,
        *,
        smiles: str,
        current_hypothesis: str,
        champion_hypothesis: str | None = None,
        challenger_hypothesis: str | None = None,
        pairwise_decision_question: str | None = None,
        task_received: str,
        main_gap: str,
        molecule_identity_context: MoleculeIdentityContext | None,
        latest_macro_report: AgentReport | None,
        latest_microscopic_report: AgentReport | None,
    ) -> dict[str, Any]:
        champion_hypothesis = champion_hypothesis or current_hypothesis
        challenger_hypothesis = challenger_hypothesis or "unknown"
        pairwise_decision_question = pairwise_decision_question or (
            f"Distinguish '{champion_hypothesis}' versus '{challenger_hypothesis}' for the current molecule. "
            f"The unresolved discriminator is: {main_gap}"
        )
        query_bundle = self._build_query_bundle(
            current_hypothesis=current_hypothesis,
            champion_hypothesis=champion_hypothesis,
            challenger_hypothesis=challenger_hypothesis,
            pairwise_decision_question=pairwise_decision_question,
            main_gap=main_gap,
            molecule_identity_context=molecule_identity_context,
            latest_macro_report=latest_macro_report,
            latest_microscopic_report=latest_microscopic_report,
        )
        payload = {
            "smiles": smiles,
            "current_hypothesis": current_hypothesis,
            "champion_hypothesis": champion_hypothesis,
            "challenger_hypothesis": challenger_hypothesis,
            "pairwise_decision_question": pairwise_decision_question,
            "task_received": task_received,
            "main_gap": main_gap,
            "molecule_identity_context": (
                molecule_identity_context.model_dump(mode="json")
                if molecule_identity_context is not None
                else None
            ),
            "latest_macro_summary": latest_macro_report.result_summary if latest_macro_report else None,
            "latest_microscopic_summary": (
                latest_microscopic_report.result_summary if latest_microscopic_report else None
            ),
            "query_bundle": query_bundle,
            "runtime_context": {
                "verifier_model": self._config.verifier_model,
                "verifier_base_url": self._config.verifier_base_url,
                "verifier_timeout_seconds": self._config.verifier_timeout_seconds,
                "verifier_api_key_configured": bool(self._config.verifier_api_key),
            },
        }
        rendered_prompt = self._prompts.render("verifier_retrieval", payload)
        try:
            response = self._client.invoke_json_schema(
                messages=prompt_value_to_messages(rendered_prompt),
                response_model=VerifierRetrievalResponse,
                schema_name="verifier_retrieval_response",
            )
        except Exception as exc:
            pair_key = _pairwise_key(champion_hypothesis, challenger_hypothesis)
            return {
                "status": "failed",
                "error": str(exc),
                "source_count": 0,
                "evidence_cards": [],
                "queried_hypothesis": current_hypothesis,
                "champion_hypothesis": champion_hypothesis,
                "challenger_hypothesis": challenger_hypothesis,
                "retrieval_note": "Verifier retrieval failed before any evidence cards could be returned.",
                "queries_executed": query_bundle["queries_executed"],
                "query_groups_attempted": query_bundle["query_groups_attempted"],
                "query_groups_with_hits": [],
                "verifier_target_pair": pair_key,
                "verifier_supplement_status": "missing",
                "verifier_information_gain": "none",
                "verifier_evidence_relation": "no_new_info",
                "verifier_supplement_summary": "External verification failed before any usable evidence could be returned.",
                "pairwise_verifier_completed_for_pair": pair_key,
                "pairwise_verifier_evidence_specificity": "no_direct_hit",
            }

        evidence_cards = self._normalize_cards(response.evidence_cards)
        has_non_limitation = any(card.comparison_bucket != "limitation" for card in evidence_cards)
        if not evidence_cards:
            evidence_cards = [
                self._generic_limitation_card(
                    champion_hypothesis=champion_hypothesis,
                    challenger_hypothesis=challenger_hypothesis,
                )
            ]
        query_groups_with_hits = self._query_groups_with_hits(evidence_cards)
        retrieval_status = "success" if has_non_limitation else "partial"
        pairwise_specificity = self._pairwise_evidence_specificity(evidence_cards)
        pair_key = _pairwise_key(champion_hypothesis, challenger_hypothesis)
        supplement_status = self._verifier_supplement_status(retrieval_status, evidence_cards)
        information_gain = self._verifier_information_gain(
            supplement_status,
            pairwise_specificity,
            evidence_cards,
        )
        evidence_relation = self._verifier_evidence_relation(
            champion_hypothesis,
            challenger_hypothesis,
            evidence_cards,
        )

        return {
            "status": retrieval_status,
            "source_count": len(evidence_cards),
            "evidence_cards": [card.model_dump(mode="json") for card in evidence_cards],
            "queried_hypothesis": current_hypothesis,
            "champion_hypothesis": champion_hypothesis,
            "challenger_hypothesis": challenger_hypothesis,
            "retrieval_note": response.retrieval_note,
            "raw_response": response.model_dump(mode="json"),
            "queries_executed": query_bundle["queries_executed"],
            "query_groups_attempted": query_bundle["query_groups_attempted"],
            "query_groups_with_hits": query_groups_with_hits,
            "verifier_target_pair": pair_key,
            "verifier_supplement_status": supplement_status,
            "verifier_information_gain": information_gain,
            "verifier_evidence_relation": evidence_relation,
            "verifier_supplement_summary": response.retrieval_note,
            "pairwise_verifier_completed_for_pair": pair_key,
            "pairwise_verifier_evidence_specificity": pairwise_specificity,
        }

    def _normalize_cards(
        self,
        cards: list[VerifierRetrievedCardDraft],
    ) -> list[VerifierEvidenceCard]:
        normalized: list[VerifierEvidenceCard] = []
        for idx, card in enumerate(cards, start=1):
            observation = (card.observation or "").strip()
            source = (card.source or "").strip() or "external_retrieval"
            if not observation:
                continue
            normalized.append(
                VerifierEvidenceCard(
                    card_id=self._normalize_card_id(card.card_id, idx, observation),
                    source=source,
                    title=self._clean_optional(card.title),
                    doi=self._clean_optional(card.doi),
                    url=self._clean_optional(card.url),
                    observation=observation,
                    topic_tags=self._normalize_topic_tags(card.topic_tags),
                    evidence_kind=self._normalize_evidence_kind(card.evidence_kind),
                    why_relevant=self._clean_optional(card.why_relevant),
                    query_group=self._normalize_query_group(card.query_group),
                    match_level=self._normalize_match_level(card.match_level),
                    mechanism_claim=self._clean_optional(card.mechanism_claim),
                    experimental_context=self._clean_optional(card.experimental_context),
                    comparison_bucket=self._normalize_comparison_bucket(
                        card.comparison_bucket or card.query_group
                    ),
                    relevant_hypotheses=self._normalize_relevant_hypotheses(card.relevant_hypotheses),
                    criterion_type=self._clean_optional(card.criterion_type),
                    evidence_specificity=self._normalize_evidence_specificity(
                        card.evidence_specificity,
                        card.match_level,
                    ),
                )
            )
        return normalized[:4]

    def _normalize_card_id(self, raw_card_id: str, idx: int, observation: str) -> str:
        candidate = raw_card_id.strip().lower().replace(" ", "-")
        if candidate:
            return candidate
        digest = hashlib.sha1(observation.encode("utf-8")).hexdigest()[:8]
        return f"verifier-card-{idx}-{digest}"

    def _normalize_topic_tags(self, topic_tags: list[str]) -> list[str]:
        normalized: list[str] = []
        for tag in topic_tags:
            tag_text = str(tag).strip().lower().replace(" ", "_")
            if tag_text and tag_text not in normalized:
                normalized.append(tag_text)
        return normalized

    def _normalize_evidence_kind(self, evidence_kind: str) -> str:
        kind = evidence_kind.strip().lower()
        if kind in {"case_memory", "external_summary", "mechanistic_note"}:
            return kind
        return "external_summary"

    def _normalize_query_group(self, query_group: str) -> str:
        normalized = query_group.strip().lower()
        if normalized == "similar_family":
            return "champion_family"
        if normalized == "mechanistic_discriminator":
            return "pairwise_discriminator"
        if normalized in {
            "exact_identity",
            "champion_family",
            "challenger_family",
            "pairwise_discriminator",
            "limitation",
        }:
            return normalized
        return "champion_family"

    def _normalize_match_level(self, match_level: str) -> str:
        normalized = match_level.strip().lower()
        if normalized in {
            "exact_molecule",
            "same_family",
            "specific_test_criterion",
            "similar_structural_class",
            "generic_mechanistic_context",
            "retrieval_limitation",
        }:
            return normalized
        return "generic_mechanistic_context"

    def _normalize_comparison_bucket(self, comparison_bucket: str) -> str:
        normalized = comparison_bucket.strip().lower()
        if normalized in {
            "exact_identity",
            "champion_family",
            "challenger_family",
            "pairwise_discriminator",
            "limitation",
        }:
            return normalized
        normalized_query_group = self._normalize_query_group(comparison_bucket)
        if normalized_query_group == "similar_family":
            return "champion_family"
        if normalized_query_group == "mechanistic_discriminator":
            return "pairwise_discriminator"
        return normalized_query_group

    def _normalize_relevant_hypotheses(self, relevant_hypotheses: list[str]) -> list[str]:
        normalized: list[str] = []
        for hypothesis in relevant_hypotheses:
            text = str(hypothesis).strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized

    def _normalize_evidence_specificity(self, specificity: str, match_level: str) -> str:
        normalized = specificity.strip().lower()
        match_level_normalized = self._normalize_match_level(match_level)
        if normalized == "exact_compound":
            return "exact_compound"
        if normalized == "close_family":
            return "close_family"
        if normalized == "no_direct_hit":
            return "no_direct_hit"
        if normalized == "generic_review" and match_level_normalized == "generic_mechanistic_context":
            return "generic_review"
        if match_level_normalized == "exact_molecule":
            return "exact_compound"
        if match_level_normalized in {"same_family", "similar_structural_class"}:
            return "close_family"
        if match_level_normalized == "retrieval_limitation":
            return "no_direct_hit"
        return "generic_review"

    def _clean_optional(self, value: Optional[str]) -> Optional[str]:
        text = (value or "").strip()
        return text or None

    def _generic_limitation_card(
        self,
        *,
        champion_hypothesis: str,
        challenger_hypothesis: str,
    ) -> VerifierEvidenceCard:
        return VerifierEvidenceCard(
            card_id="verifier-limitation-card",
            source="verifier_runtime",
            title="Verifier retrieval limitation",
            observation=(
                f"No source-backed external material specific enough to distinguish '{champion_hypothesis}' "
                f"from '{challenger_hypothesis}' was retrieved in this verifier run."
            ),
            topic_tags=["limitation"],
            evidence_kind="mechanistic_note",
            why_relevant=(
                "This card records that external retrieval was attempted but did not surface a more specific external discriminator."
            ),
            query_group="limitation",
            match_level="retrieval_limitation",
            comparison_bucket="limitation",
            relevant_hypotheses=[champion_hypothesis, challenger_hypothesis],
            criterion_type="state_assignment",
            evidence_specificity="no_direct_hit",
        )

    def _query_groups_with_hits(self, cards: list[VerifierEvidenceCard]) -> list[str]:
        groups: list[str] = []
        for card in cards:
            if card.comparison_bucket not in groups:
                groups.append(card.comparison_bucket)
        return groups

    def _pairwise_evidence_specificity(self, cards: list[VerifierEvidenceCard]) -> str:
        best_specificity = "no_direct_hit"
        for card in cards:
            if _EVIDENCE_SPECIFICITY_ORDER[card.evidence_specificity] > _EVIDENCE_SPECIFICITY_ORDER[best_specificity]:
                best_specificity = card.evidence_specificity
        return best_specificity

    def _verifier_supplement_status(
        self,
        retrieval_status: str,
        cards: list[VerifierEvidenceCard],
    ) -> str:
        if retrieval_status == "failed" or not cards:
            return "missing"
        if all(card.comparison_bucket == "limitation" for card in cards):
            return "partial"
        return "sufficient"

    def _verifier_information_gain(
        self,
        supplement_status: str,
        pairwise_specificity: str,
        cards: list[VerifierEvidenceCard],
    ) -> str:
        if supplement_status == "missing":
            return "none"
        if supplement_status == "partial":
            return "low"
        if any(card.comparison_bucket == "pairwise_discriminator" for card in cards):
            if pairwise_specificity in {"close_family", "exact_compound"}:
                return "high"
            return "medium"
        if pairwise_specificity in {"close_family", "exact_compound"}:
            return "high"
        return "medium"

    def _verifier_evidence_relation(
        self,
        champion_hypothesis: str,
        challenger_hypothesis: str,
        cards: list[VerifierEvidenceCard],
    ) -> str:
        usable_cards = [card for card in cards if card.comparison_bucket != "limitation"]
        if not usable_cards:
            return "no_new_info"
        champion_hits = False
        challenger_hits = False
        mixed_hits = False
        for card in usable_cards:
            relevant = set(card.relevant_hypotheses)
            if card.comparison_bucket == "pairwise_discriminator":
                mixed_hits = True
            if champion_hypothesis in relevant:
                champion_hits = True
            if challenger_hypothesis in relevant:
                challenger_hits = True
            if card.comparison_bucket == "exact_identity":
                champion_hits = True
            if card.comparison_bucket == "champion_family":
                champion_hits = True
            if card.comparison_bucket == "challenger_family":
                challenger_hits = True
        if mixed_hits or (champion_hits and challenger_hits):
            return "mixed"
        if champion_hits:
            return "supports_top1"
        if challenger_hits:
            return "challenges_top1"
        return "no_new_info"

    def _build_query_bundle(
        self,
        *,
        current_hypothesis: str,
        champion_hypothesis: str,
        challenger_hypothesis: str,
        pairwise_decision_question: str,
        main_gap: str,
        molecule_identity_context: MoleculeIdentityContext | None,
        latest_macro_report: AgentReport | None,
        latest_microscopic_report: AgentReport | None,
    ) -> dict[str, object]:
        exact_identity_queries = self._exact_identity_queries(molecule_identity_context)
        champion_family_queries = self._family_queries(
            focus_hypothesis=champion_hypothesis,
            latest_macro_report=latest_macro_report,
            latest_microscopic_report=latest_microscopic_report,
        )
        challenger_family_queries = self._family_queries(
            focus_hypothesis=challenger_hypothesis,
            latest_macro_report=latest_macro_report,
            latest_microscopic_report=latest_microscopic_report,
        )
        pairwise_discriminator_queries = self._pairwise_discriminator_queries(
            champion_hypothesis=champion_hypothesis,
            challenger_hypothesis=challenger_hypothesis,
            pairwise_decision_question=pairwise_decision_question,
            main_gap=main_gap,
            latest_macro_report=latest_macro_report,
            latest_microscopic_report=latest_microscopic_report,
        )
        query_groups_attempted = [
            "exact_identity",
            "champion_family",
            "challenger_family",
            "pairwise_discriminator",
        ]
        queries_executed = [
            *[
                {"query_group": "exact_identity", "query": query}
                for query in exact_identity_queries
            ],
            *[
                {"query_group": "champion_family", "query": query}
                for query in champion_family_queries
            ],
            *[
                {"query_group": "challenger_family", "query": query}
                for query in challenger_family_queries
            ],
            *[
                {"query_group": "pairwise_discriminator", "query": query}
                for query in pairwise_discriminator_queries
            ],
        ]
        return {
            "exact_identity_queries": exact_identity_queries,
            "champion_family_queries": champion_family_queries,
            "challenger_family_queries": challenger_family_queries,
            "pairwise_discriminator_queries": pairwise_discriminator_queries,
            "query_groups_attempted": query_groups_attempted,
            "queries_executed": queries_executed,
        }

    def _exact_identity_queries(
        self,
        molecule_identity_context: MoleculeIdentityContext | None,
    ) -> list[str]:
        if molecule_identity_context is None:
            return []
        queries: list[str] = []
        if molecule_identity_context.inchikey:
            queries.append(f'"{molecule_identity_context.inchikey}" aggregation induced emission')
            queries.append(f'"{molecule_identity_context.inchikey}" photoluminescence mechanism')
        if molecule_identity_context.inchi:
            queries.append(f'"{molecule_identity_context.inchi}" emission mechanism')
        if molecule_identity_context.molecular_formula:
            queries.append(
                f'"{molecule_identity_context.molecular_formula}" "{molecule_identity_context.canonical_smiles or molecule_identity_context.input_smiles}"'
            )
        if molecule_identity_context.canonical_smiles:
            queries.append(
                f'"{molecule_identity_context.canonical_smiles}" aggregation induced emission'
            )
        return queries[:4]

    def _family_queries(
        self,
        *,
        focus_hypothesis: str,
        latest_macro_report: AgentReport | None,
        latest_microscopic_report: AgentReport | None,
    ) -> list[str]:
        descriptors: list[str] = []
        if latest_macro_report is not None:
            macro_structured = latest_macro_report.structured_results
            if int(macro_structured.get("rotor_topology", {}).get("rotatable_bond_count", 0)) >= 6:
                descriptors.append("multi-rotor aromatic luminogen")
            if int(macro_structured.get("hetero_atom_count", 0)) >= 2:
                descriptors.append("heteroatom-rich conjugated emitter")
            if float(macro_structured.get("planarity_and_torsion_summary", {}).get("planarity_proxy", 0.0)) >= 0.8:
                descriptors.append("high-planarity conjugated system")
        if not descriptors:
            descriptors.append("conjugated AIE-active aromatic system")
        if latest_microscopic_report is not None:
            s1 = latest_microscopic_report.structured_results.get("s1", {})
            if float(s1.get("first_oscillator_strength", 0.0)) >= 0.5:
                descriptors.append("bright emissive excited state")
        descriptor_text = ", ".join(dict.fromkeys(descriptors))
        return [
            f'{descriptor_text} reported AIE mechanism review',
            f'{descriptor_text} "{focus_hypothesis}" literature example',
            f'{descriptor_text} aggregation induced emission related case',
        ]

    def _pairwise_discriminator_queries(
        self,
        *,
        champion_hypothesis: str,
        challenger_hypothesis: str,
        pairwise_decision_question: str,
        main_gap: str,
        latest_macro_report: AgentReport | None,
        latest_microscopic_report: AgentReport | None,
    ) -> list[str]:
        competition_terms: list[str] = []
        combined_text = " ".join(
            filter(
                None,
                [
                    champion_hypothesis,
                    challenger_hypothesis,
                    pairwise_decision_question,
                    main_gap,
                    latest_macro_report.result_summary if latest_macro_report else "",
                    latest_microscopic_report.result_summary if latest_microscopic_report else "",
                ],
            )
        ).lower()
        keyword_mapping = {
            "ict": ["ict", "charge transfer"],
            "aggregation": ["aggregation", "aggregate"],
            "packing": ["packing", "intermolecular"],
            "excited-state relaxation": ["excited-state", "relaxation"],
        }
        for label, tokens in keyword_mapping.items():
            if any(token in combined_text for token in tokens):
                competition_terms.append(label)
        if not competition_terms:
            competition_terms = ["ict", "aggregation", "excited-state relaxation"]
        queries = [
            f'"{champion_hypothesis}" versus "{challenger_hypothesis}" decisive photophysical discriminator',
            f'{champion_hypothesis} {challenger_hypothesis} {competition_terms[-1]} decisive evidence review',
            pairwise_decision_question,
        ]
        return queries[:3]
