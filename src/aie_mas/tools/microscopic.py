from __future__ import annotations

from typing import Any

from aie_mas.utils.smiles import extract_smiles_features


class MockS0OptimizationTool:
    name = "mock_s0_optimization"

    def invoke(self, smiles: str) -> dict[str, Any]:
        features = extract_smiles_features(smiles)
        energy = round(-0.120 * features.length - 0.015 * features.conjugation_proxy, 4)
        rigidity_proxy = round(features.conjugation_proxy / max(features.flexibility_proxy, 1.0), 4)
        return {
            "state": "S0",
            "optimized_energy": energy,
            "rigidity_proxy": rigidity_proxy,
        }


class MockS1OptimizationTool:
    name = "mock_s1_optimization"

    def invoke(self, smiles: str) -> dict[str, Any]:
        features = extract_smiles_features(smiles)
        energy = round(-0.106 * features.length - 0.010 * features.conjugation_proxy, 4)
        geometry_change_proxy = round(
            features.flexibility_proxy / max(features.conjugation_proxy, 1.0),
            4,
        )
        oscillator_strength_proxy = round(
            min(0.95, 0.25 + features.conjugation_proxy * 0.04 + features.hetero_atom_count * 0.02),
            4,
        )
        return {
            "state": "S1",
            "optimized_energy": energy,
            "geometry_change_proxy": geometry_change_proxy,
            "oscillator_strength_proxy": oscillator_strength_proxy,
        }


class MockTargetedMicroscopicTool:
    name = "mock_targeted_microscopic_followup"

    def invoke(self, smiles: str, objective: str, target_property: str | None = None) -> dict[str, Any]:
        features = extract_smiles_features(smiles)
        consistency_proxy = round(
            min(0.97, 0.35 + features.conjugation_proxy * 0.03 + features.aromatic_atom_count * 0.01),
            4,
        )
        constraint_sensitivity = round(
            max(0.08, features.flexibility_proxy / max(features.conjugation_proxy + 1.0, 1.0)),
            4,
        )
        return {
            "objective": objective,
            "target_property": target_property or "follow_up_consistency",
            "consistency_proxy": consistency_proxy,
            "constraint_sensitivity": constraint_sensitivity,
        }
