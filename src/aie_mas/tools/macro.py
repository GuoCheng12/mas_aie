from __future__ import annotations

from typing import Any

from aie_mas.utils.smiles import extract_smiles_features


class MockMacroStructureTool:
    name = "mock_macro_structure_scan"

    def invoke(self, smiles: str) -> dict[str, Any]:
        features = extract_smiles_features(smiles)
        return {
            "aromatic_atom_count": features.aromatic_atom_count,
            "hetero_atom_count": features.hetero_atom_count,
            "branch_point_count": features.branch_point_count,
            "conjugation_proxy": features.conjugation_proxy,
            "flexibility_proxy": features.flexibility_proxy,
            "ring_digit_count": features.ring_digit_count,
        }
