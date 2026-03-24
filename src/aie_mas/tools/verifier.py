from __future__ import annotations

from typing import Any

from aie_mas.graph.state import VerifierEvidenceCard
from aie_mas.utils.smiles import extract_smiles_features


class MockVerifierEvidenceTool:
    name = "mock_verifier_evidence_lookup"

    def invoke(self, smiles: str, current_hypothesis: str) -> dict[str, Any]:
        features = extract_smiles_features(smiles)
        restriction_signal = features.aromatic_atom_count >= 6 and features.branch_point_count >= 1
        charge_transfer_signal = features.hetero_atom_count >= 3
        aggregation_signal = features.aromatic_atom_count >= 6 and features.double_bond_count >= 1
        evidence_cards: list[VerifierEvidenceCard] = []

        if restriction_signal:
            evidence_cards.append(
                VerifierEvidenceCard(
                    card_id="case-memory-restriction",
                    source="mock_case_memory_card",
                    observation=(
                        "Bulky aromatic fragments with branch points are frequently discussed in motion-restriction "
                        "explanations of aggregation-enhanced emission."
                    ),
                    topic_tags=["restriction", "branching"],
                    evidence_kind="case_memory",
                )
            )
        if charge_transfer_signal:
            evidence_cards.append(
                VerifierEvidenceCard(
                    card_id="external-summary-ict",
                    source="mock_external_summary_card",
                    observation=(
                        "Hetero-atom-rich conjugated systems are often discussed alongside ICT-like excited-state "
                        "redistribution that can compete with purely restriction-driven stories."
                    ),
                    topic_tags=["ict", "heteroatom"],
                    evidence_kind="external_summary",
                )
            )
        if aggregation_signal:
            evidence_cards.append(
                VerifierEvidenceCard(
                    card_id="mechanistic-note-aggregation",
                    source="mock_mechanistic_note_card",
                    observation=(
                        "Large conjugated aromatic surfaces are frequently discussed in aggregate-state packing and "
                        "intermolecular-contact explanations of emission changes."
                    ),
                    topic_tags=["aggregation", "packing", "planarity"],
                    evidence_kind="mechanistic_note",
                )
            )
        if not evidence_cards:
            evidence_cards.append(
                VerifierEvidenceCard(
                    card_id="mechanistic-note-generic",
                    source="mock_generic_note_card",
                    observation=(
                        "The current mock verifier retrieved only generic mechanistic context and did not surface a "
                        "more specific external explanation for this molecule."
                    ),
                    topic_tags=["mechanistic_note"],
                    evidence_kind="mechanistic_note",
                )
            )
        return {
            "source_count": len(evidence_cards),
            "evidence_cards": [card.model_dump(mode="json") for card in evidence_cards],
            "queried_hypothesis": current_hypothesis,
        }
