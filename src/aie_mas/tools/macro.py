from __future__ import annotations

from typing import Any, Sequence

from aie_mas.graph.state import SharedStructureContext
from aie_mas.utils.smiles import extract_smiles_features


class DeterministicMacroStructureTool:
    name = "deterministic_macro_structure_scan"

    def invoke(
        self,
        *,
        smiles: str,
        shared_structure_context: SharedStructureContext | None = None,
        focus_areas: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        focus_areas = list(focus_areas or [])
        if shared_structure_context is None:
            return self._fallback_smiles_scan(smiles=smiles, focus_areas=focus_areas)
        return self._shared_structure_scan(
            smiles=smiles,
            shared_structure_context=shared_structure_context,
            focus_areas=focus_areas,
        )

    def _shared_structure_scan(
        self,
        *,
        smiles: str,
        shared_structure_context: SharedStructureContext,
        focus_areas: list[str],
    ) -> dict[str, Any]:
        smiles_features = extract_smiles_features(smiles)
        aromatic_atom_count = max(
            smiles_features.aromatic_atom_count,
            shared_structure_context.aromatic_ring_count * 6,
        )
        flexibility_proxy = round(
            shared_structure_context.rotatable_bond_count
            + shared_structure_context.branch_point_count * 0.5
            + shared_structure_context.conformer_dispersion_proxy,
            3,
        )
        conjugation_proxy = round(
            shared_structure_context.aromatic_ring_count * 1.5
            + shared_structure_context.planarity_proxy
            + shared_structure_context.donor_acceptor_partition_proxy,
            3,
        )
        return {
            "structure_source": "shared_prepared_structure",
            "focus_areas": focus_areas,
            "canonical_smiles": shared_structure_context.canonical_smiles,
            "atom_count": shared_structure_context.atom_count,
            "prepared_xyz_path": shared_structure_context.prepared_xyz_path,
            "prepared_sdf_path": shared_structure_context.prepared_sdf_path,
            "summary_path": shared_structure_context.summary_path,
            "aromatic_atom_count": aromatic_atom_count,
            "hetero_atom_count": shared_structure_context.hetero_atom_count,
            "branch_point_count": shared_structure_context.branch_point_count,
            "conjugation_proxy": conjugation_proxy,
            "flexibility_proxy": flexibility_proxy,
            "ring_digit_count": smiles_features.ring_digit_count,
            "rotor_topology": {
                "rotatable_bond_count": shared_structure_context.rotatable_bond_count,
                "torsion_candidate_count": shared_structure_context.torsion_candidate_count,
                "branch_point_count": shared_structure_context.branch_point_count,
            },
            "ring_and_conjugation_summary": {
                "aromatic_ring_count": shared_structure_context.aromatic_ring_count,
                "ring_system_count": shared_structure_context.ring_system_count,
                "hetero_atom_count": shared_structure_context.hetero_atom_count,
                "conjugation_proxy": conjugation_proxy,
            },
            "donor_acceptor_layout": {
                "donor_acceptor_partition_proxy": shared_structure_context.donor_acceptor_partition_proxy,
                "hetero_atom_count": shared_structure_context.hetero_atom_count,
            },
            "planarity_and_torsion_summary": {
                "planarity_proxy": shared_structure_context.planarity_proxy,
                "rotatable_bond_count": shared_structure_context.rotatable_bond_count,
                "torsion_candidate_count": shared_structure_context.torsion_candidate_count,
            },
            "compactness_and_contact_proxies": {
                "compactness_proxy": shared_structure_context.compactness_proxy,
                "principal_span_proxy": shared_structure_context.principal_span_proxy,
            },
            "conformer_dispersion_summary": {
                "conformer_count": shared_structure_context.conformer_count,
                "selected_conformer_id": shared_structure_context.selected_conformer_id,
                "conformer_dispersion_proxy": shared_structure_context.conformer_dispersion_proxy,
            },
        }

    def _fallback_smiles_scan(self, *, smiles: str, focus_areas: list[str]) -> dict[str, Any]:
        features = extract_smiles_features(smiles)
        aromatic_ring_proxy = max(0, features.aromatic_atom_count // 6)
        return {
            "structure_source": "smiles_only_fallback",
            "focus_areas": focus_areas,
            "canonical_smiles": smiles,
            "atom_count": None,
            "prepared_xyz_path": None,
            "prepared_sdf_path": None,
            "summary_path": None,
            "aromatic_atom_count": features.aromatic_atom_count,
            "hetero_atom_count": features.hetero_atom_count,
            "branch_point_count": features.branch_point_count,
            "conjugation_proxy": features.conjugation_proxy,
            "flexibility_proxy": features.flexibility_proxy,
            "ring_digit_count": features.ring_digit_count,
            "rotor_topology": {
                "rotatable_bond_count": max(0, features.branch_point_count // 2),
                "torsion_candidate_count": features.branch_point_count,
                "branch_point_count": features.branch_point_count,
            },
            "ring_and_conjugation_summary": {
                "aromatic_ring_count": aromatic_ring_proxy,
                "ring_system_count": max(0, features.ring_digit_count // 2),
                "hetero_atom_count": features.hetero_atom_count,
                "conjugation_proxy": features.conjugation_proxy,
            },
            "donor_acceptor_layout": {
                "donor_acceptor_partition_proxy": float(min(1, features.donor_acceptor_proxy)),
                "hetero_atom_count": features.hetero_atom_count,
            },
            "planarity_and_torsion_summary": {
                "planarity_proxy": round(min(1.0, features.conjugation_proxy / 10.0), 3),
                "rotatable_bond_count": max(0, features.branch_point_count // 2),
                "torsion_candidate_count": features.branch_point_count,
            },
            "compactness_and_contact_proxies": {
                "compactness_proxy": round(max(0.0, 1.0 - min(features.length / 120.0, 1.0)), 3),
                "principal_span_proxy": round(min(features.length / 10.0, 20.0), 3),
            },
            "conformer_dispersion_summary": {
                "conformer_count": 0,
                "selected_conformer_id": None,
                "conformer_dispersion_proxy": 0.0,
            },
        }
