from __future__ import annotations

from typing import Any

from aie_mas.utils.smiles import extract_smiles_features


class MockVerifierEvidenceTool:
    name = "mock_verifier_evidence_lookup"

    def invoke(self, smiles: str, current_hypothesis: str) -> dict[str, Any]:
        features = extract_smiles_features(smiles)
        restriction_signal = (
            features.aromatic_atom_count >= 6 and features.branch_point_count >= 1
        )
        charge_transfer_signal = features.hetero_atom_count >= 3
        evidence_cards = [
            {
                "source": "mock_case_memory_card",
                "observation": (
                    "Bulky aromatic fragments with branch points often show stronger emission "
                    "after motion restriction."
                ),
                "relation_to_hypothesis": "support" if restriction_signal else "neutral",
            },
            {
                "source": "mock_external_summary_card",
                "observation": (
                    "Hetero-atom-rich conjugated systems can display ICT contributions that compete "
                    "with purely restriction-driven explanations."
                ),
                "relation_to_hypothesis": "conflict" if charge_transfer_signal else "neutral",
            },
        ]
        return {
            "source_count": len(evidence_cards),
            "evidence_cards": evidence_cards,
            "queried_hypothesis": current_hypothesis,
        }
