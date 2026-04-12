from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from aie_mas.chem.structure_prep import PreparedStructure
from aie_mas.graph.state import (
    MacroActionDefinition,
    MacroCapabilityDefinition,
    MacroCapabilityName,
    MacroExecutionPlan,
    SharedStructureContext,
)
from aie_mas.tools.amesp import _extract_intramolecular_geometry_record, _read_xyz_symbols_and_coordinates
from aie_mas.utils.smiles import extract_smiles_features

MACRO_CAPABILITY_REGISTRY: dict[MacroCapabilityName, MacroCapabilityDefinition] = {
    "screen_donor_acceptor_layout": MacroCapabilityDefinition(
        name="screen_donor_acceptor_layout",
        purpose="Summarize donor-acceptor segmentation and conjugation-level layout from bounded structural evidence.",
        structure_target="smiles_only_fallback",
        supported_deliverables=[
            "donor-acceptor layout",
            "conjugation summary",
            "donor-acceptor partition proxy",
        ],
        evidence_goal_tags=["donor_acceptor_layout", "charge_separation_proxy"],
        exact_observable_tags=["donor_acceptor_layout", "conjugation_summary"],
    ),
    "screen_rotor_torsion_topology": MacroCapabilityDefinition(
        name="screen_rotor_torsion_topology",
        purpose="Summarize rotor density, torsion candidates, and branching topology from bounded structural evidence.",
        structure_target="smiles_only_fallback",
        supported_deliverables=[
            "rotor topology summary",
            "torsion candidate summary",
            "branching/peripheral rotor summary",
        ],
        evidence_goal_tags=["rotor_topology", "torsion_topology"],
        exact_observable_tags=["rotor_topology", "torsion_topology"],
    ),
    "screen_planarity_compactness": MacroCapabilityDefinition(
        name="screen_planarity_compactness",
        purpose="Summarize planarity, compactness, principal span, and conformer-dispersion proxies.",
        structure_target="smiles_only_fallback",
        supported_deliverables=[
            "planarity and torsion summary",
            "compactness and contact proxies",
            "conformer dispersion summary",
        ],
        evidence_goal_tags=["planarity_proxy", "compactness_proxy", "conformer_geometry_proxy"],
        exact_observable_tags=["planarity_proxy", "compactness_proxy", "conformer_geometry_proxy"],
    ),
    "screen_intramolecular_hbond_preorganization": MacroCapabilityDefinition(
        name="screen_intramolecular_hbond_preorganization",
        purpose="Inspect reusable prepared geometry for intramolecular H-bond and typed donor/acceptor preorganization cues.",
        structure_target="shared_prepared_structure",
        supported_deliverables=[
            "intramolecular H-bond candidate summary",
            "typed donor/acceptor preorganization summary",
            "local preorganization geometry status",
        ],
        evidence_goal_tags=["intramolecular_hbond_preorganization", "geometry_precondition"],
        exact_observable_tags=["intramolecular_hbond_preorganization", "geometry_precondition"],
        unsupported_requests_note="Without shared prepared geometry, only motif-level fallback screening is available.",
    ),
    "screen_conformer_geometry_proxy": MacroCapabilityDefinition(
        name="screen_conformer_geometry_proxy",
        purpose="Summarize available conformer-level geometry proxies and single-conformer limitations.",
        structure_target="smiles_only_fallback",
        supported_deliverables=[
            "conformer geometry proxy summary",
            "conformer dispersion summary",
            "single-conformer limitation note",
        ],
        evidence_goal_tags=["conformer_geometry_proxy"],
        exact_observable_tags=["conformer_geometry_proxy"],
    ),
    "screen_neutral_aromatic_structure": MacroCapabilityDefinition(
        name="screen_neutral_aromatic_structure",
        purpose="Summarize aromatic-core dominance, ring-system rigidity, and neutral-aromatic structural cues.",
        structure_target="smiles_only_fallback",
        supported_deliverables=[
            "aromatic core dominance summary",
            "ring-system rigidity summary",
            "neutral-aromatic structural cue summary",
        ],
        evidence_goal_tags=["aromatic_core_dominance", "ring_system_rigidity"],
        exact_observable_tags=["aromatic_core_dominance", "ring_system_rigidity"],
    ),
}

MACRO_ACTION_REGISTRY: dict[MacroCapabilityName, MacroActionDefinition] = {
    name: MacroActionDefinition(
        action_name=name,
        purpose=definition.purpose,
        structure_target=definition.structure_target,
        default_deliverables=list(definition.supported_deliverables),
        evidence_goal_tags=list(definition.evidence_goal_tags),
        exact_observable_tags=list(definition.exact_observable_tags),
    )
    for name, definition in MACRO_CAPABILITY_REGISTRY.items()
}


class DeterministicMacroStructureTool:
    name = "deterministic_macro_structure_scan"

    def invoke(
        self,
        *,
        smiles: str,
        shared_structure_context: SharedStructureContext | None = None,
        focus_areas: Sequence[str] | None = None,
    ) -> dict[str, Any]:
        del focus_areas
        return self._full_structure_scan(
            smiles=smiles,
            shared_structure_context=shared_structure_context,
        )

    def execute(
        self,
        *,
        plan: MacroExecutionPlan,
        smiles: str,
        shared_structure_context: SharedStructureContext | None = None,
    ) -> dict[str, Any]:
        return self.execute_local(
            plan=plan,
            smiles=smiles,
            shared_structure_context=shared_structure_context,
        )

    def execute_local(
        self,
        *,
        plan: MacroExecutionPlan,
        smiles: str,
        shared_structure_context: SharedStructureContext | None = None,
    ) -> dict[str, Any]:
        selected_capability = plan.selected_capability or "screen_planarity_compactness"
        if selected_capability not in MACRO_CAPABILITY_REGISTRY:
            raise ValueError(f"Unsupported macro capability: {selected_capability}")
        base_scan = self._full_structure_scan(
            smiles=smiles,
            shared_structure_context=shared_structure_context,
        )
        capability_payload = self._execute_capability(
            selected_capability,
            base_scan=base_scan,
            smiles=smiles,
            shared_structure_context=shared_structure_context,
        )
        requested_capability = (
            plan.macro_tool_request.capability_name
            if plan.macro_tool_request is not None
            else selected_capability
        )
        missing_deliverables = list(capability_payload.get("missing_deliverables") or [])
        covered_observable_tags = list(
            capability_payload.get("covered_observable_tags")
            or MACRO_CAPABILITY_REGISTRY[selected_capability].exact_observable_tags
        )
        substitution_reason = ""
        translation_substituted_action = requested_capability != selected_capability
        if translation_substituted_action:
            substitution_reason = (
                f"Planner-requested macro capability `{requested_capability}` was normalized to "
                f"`{selected_capability}` within the bounded macro registry."
            )
        return {
            **base_scan,
            **capability_payload,
            "requested_capability": requested_capability,
            "selected_capability": selected_capability,
            "executed_capability": selected_capability,
            "performed_new_calculations": False,
            "reused_existing_artifacts": shared_structure_context is not None,
            "binding_mode": plan.binding_mode,
            "requested_observable_tags": list(plan.requested_observable_tags),
            "covered_observable_tags": covered_observable_tags,
            "missing_deliverables": missing_deliverables,
            "resolved_target_ids": self._resolved_target_ids(shared_structure_context),
            "planner_requested_capability": requested_capability,
            "translation_substituted_action": translation_substituted_action,
            "translation_substitution_reason": substitution_reason,
            "fulfillment_mode": "proxy" if missing_deliverables else "exact",
        }

    def _full_structure_scan(
        self,
        *,
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        if shared_structure_context is None:
            return self._fallback_smiles_scan(smiles=smiles, focus_areas=[])
        return self._shared_structure_scan(
            smiles=smiles,
            shared_structure_context=shared_structure_context,
            focus_areas=[],
        )

    def _execute_capability(
        self,
        capability_name: MacroCapabilityName,
        *,
        base_scan: dict[str, Any],
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        handler = getattr(self, f"_{capability_name}")
        return handler(
            base_scan=base_scan,
            smiles=smiles,
            shared_structure_context=shared_structure_context,
        )

    def _screen_donor_acceptor_layout(
        self,
        *,
        base_scan: dict[str, Any],
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        del smiles, shared_structure_context
        summary = {
            **dict(base_scan["donor_acceptor_layout"]),
            "conjugation_proxy": base_scan["conjugation_proxy"],
            "hetero_atom_count": base_scan["hetero_atom_count"],
            "aromatic_atom_count": base_scan["aromatic_atom_count"],
            "branch_point_count": base_scan["branch_point_count"],
        }
        return {
            "donor_acceptor_layout_summary": summary,
            "capability_result_summary": (
                "Bounded donor-acceptor layout screening summarized donor/acceptor partition, hetero-atom burden, "
                "and conjugation-level layout from the available structural context."
            ),
            "route_summary": {
                "capability": "screen_donor_acceptor_layout",
                "structure_source": base_scan["structure_source"],
                "summary_fields": sorted(summary.keys()),
            },
            "covered_observable_tags": ["donor_acceptor_layout", "conjugation_summary"],
            "missing_deliverables": [],
        }

    def _screen_rotor_torsion_topology(
        self,
        *,
        base_scan: dict[str, Any],
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        del smiles, shared_structure_context
        summary = {
            **dict(base_scan["rotor_topology"]),
            "flexibility_proxy": base_scan["flexibility_proxy"],
            "branch_point_count": base_scan["branch_point_count"],
        }
        return {
            "rotor_torsion_topology_summary": summary,
            "capability_result_summary": (
                "Bounded rotor/torsion topology screening summarized rotatable-bond count, torsion candidates, "
                "and branching-level flexibility cues from the available structural context."
            ),
            "route_summary": {
                "capability": "screen_rotor_torsion_topology",
                "structure_source": base_scan["structure_source"],
                "summary_fields": sorted(summary.keys()),
            },
            "covered_observable_tags": ["rotor_topology", "torsion_topology"],
            "missing_deliverables": [],
        }

    def _screen_planarity_compactness(
        self,
        *,
        base_scan: dict[str, Any],
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        del smiles, shared_structure_context
        summary = {
            **dict(base_scan["planarity_and_torsion_summary"]),
            **dict(base_scan["compactness_and_contact_proxies"]),
            **dict(base_scan["conformer_dispersion_summary"]),
        }
        return {
            "planarity_compactness_summary": summary,
            "capability_result_summary": (
                "Bounded planarity/compactness screening summarized planarity, compactness, principal span, and "
                "conformer-dispersion proxies from the available structural context."
            ),
            "route_summary": {
                "capability": "screen_planarity_compactness",
                "structure_source": base_scan["structure_source"],
                "summary_fields": sorted(summary.keys()),
            },
            "covered_observable_tags": ["planarity_proxy", "compactness_proxy", "conformer_geometry_proxy"],
            "missing_deliverables": [],
        }

    def _screen_intramolecular_hbond_preorganization(
        self,
        *,
        base_scan: dict[str, Any],
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        if shared_structure_context is None:
            return {
                "intramolecular_hbond_preorganization_summary": {
                    "preorganization_status": "fallback_proxy_only",
                    "structure_source": "smiles_only_fallback",
                    "typed_contact_available": False,
                },
                "capability_result_summary": (
                    "Shared prepared geometry was unavailable, so only motif-level fallback screening for "
                    "intramolecular H-bond preorganization was possible."
                ),
                "route_summary": {
                    "capability": "screen_intramolecular_hbond_preorganization",
                    "structure_source": "smiles_only_fallback",
                    "typed_contact_available": False,
                },
                "covered_observable_tags": [],
                "missing_deliverables": ["intramolecular H-bond preorganization geometry"],
            }
        prepared = self._prepared_from_shared_context(shared_structure_context, smiles=smiles)
        symbols, coordinates = _read_xyz_symbols_and_coordinates(prepared.xyz_path)
        if not symbols or not coordinates:
            return {
                "intramolecular_hbond_preorganization_summary": {
                    "preorganization_status": "geometry_unavailable",
                    "structure_source": base_scan["structure_source"],
                    "typed_contact_available": False,
                },
                "capability_result_summary": (
                    "Shared geometry descriptors could not be loaded from the prepared structure paths, so the "
                    "intramolecular H-bond preorganization screen could not complete."
                ),
                "route_summary": {
                    "capability": "screen_intramolecular_hbond_preorganization",
                    "structure_source": base_scan["structure_source"],
                    "typed_contact_available": False,
                },
                "covered_observable_tags": [],
                "missing_deliverables": ["intramolecular H-bond preorganization geometry"],
            }
        geometry_record = _extract_intramolecular_geometry_record(
            prepared=prepared,
            symbols=symbols,
            coordinates=coordinates,
        )
        typed_contact = geometry_record["best_phenolic_oh_to_imine_n_contact"]
        generic_contact = geometry_record["best_intramolecular_hbond"]
        if typed_contact is not None:
            preorganization_status = "typed_contact_available"
        elif geometry_record["phenolic_oh_donor_count"] > 0 and geometry_record["imine_hydrazone_n_acceptor_count"] > 0:
            preorganization_status = "checked_absent"
        elif generic_contact is not None:
            preorganization_status = "generic_hbond_only"
        else:
            preorganization_status = "no_intramolecular_hbond_candidate"
        summary = {
            "preorganization_status": preorganization_status,
            "role_typing_mode": geometry_record["role_typing_mode"],
            "phenolic_oh_donor_count": geometry_record["phenolic_oh_donor_count"],
            "imine_hydrazone_n_acceptor_count": geometry_record["imine_hydrazone_n_acceptor_count"],
            "best_intramolecular_hbond": geometry_record["best_intramolecular_hbond"],
            "best_phenolic_oh_to_imine_n_contact": geometry_record["best_phenolic_oh_to_imine_n_contact"],
            "phenolic_oh_to_imine_n_proximity": geometry_record["phenolic_oh_to_imine_n_proximity"],
            "phenolic_oh_to_imine_n_orientation": geometry_record["phenolic_oh_to_imine_n_orientation"],
            "local_planarity_proxy": geometry_record["local_planarity_proxy"],
        }
        return {
            "intramolecular_hbond_preorganization_summary": summary,
            "capability_result_summary": (
                "Bounded intramolecular H-bond preorganization screening inspected reusable prepared geometry for "
                "generic H-bond candidates and typed donor/acceptor contact cues without making any mechanism judgment."
            ),
            "route_summary": {
                "capability": "screen_intramolecular_hbond_preorganization",
                "structure_source": base_scan["structure_source"],
                "preorganization_status": preorganization_status,
                "role_typing_mode": geometry_record["role_typing_mode"],
                "typed_contact_available": typed_contact is not None,
                "generic_hbond_candidate_count": len(geometry_record["intramolecular_hbond_candidates"]),
                "typed_candidate_count": len(geometry_record["phenolic_oh_to_imine_n_candidates"]),
            },
            "covered_observable_tags": ["intramolecular_hbond_preorganization", "geometry_precondition"],
            "missing_deliverables": [],
        }

    def _screen_conformer_geometry_proxy(
        self,
        *,
        base_scan: dict[str, Any],
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        del smiles
        summary = {
            **dict(base_scan["conformer_dispersion_summary"]),
            "structure_source": base_scan["structure_source"],
        }
        missing_deliverables: list[str] = []
        if shared_structure_context is None:
            summary["single_conformer_limit_note"] = "Shared conformer geometry context is unavailable in SMILES-only fallback."
            missing_deliverables = ["shared conformer geometry context"]
        else:
            summary["single_conformer_limit_note"] = (
                "Only the selected prepared conformer is directly available to the bounded macro capability."
            )
        return {
            "conformer_geometry_proxy_summary": summary,
            "capability_result_summary": (
                "Bounded conformer-geometry proxy screening summarized conformer count, selected conformer, and "
                "dispersion-level limitations from the available structural context."
            ),
            "route_summary": {
                "capability": "screen_conformer_geometry_proxy",
                "structure_source": base_scan["structure_source"],
                "conformer_count": summary.get("conformer_count"),
                "selected_conformer_id": summary.get("selected_conformer_id"),
            },
            "covered_observable_tags": ["conformer_geometry_proxy"] if not missing_deliverables else [],
            "missing_deliverables": missing_deliverables,
        }

    def _screen_neutral_aromatic_structure(
        self,
        *,
        base_scan: dict[str, Any],
        smiles: str,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        del smiles, shared_structure_context
        aromatic_atom_count = int(base_scan["aromatic_atom_count"])
        atom_count = base_scan.get("atom_count") or aromatic_atom_count
        aromatic_fraction = round(aromatic_atom_count / max(float(atom_count), 1.0), 6)
        summary = {
            "aromatic_atom_count": aromatic_atom_count,
            "aromatic_fraction": aromatic_fraction,
            "aromatic_ring_count": base_scan["ring_and_conjugation_summary"]["aromatic_ring_count"],
            "ring_system_count": base_scan["ring_and_conjugation_summary"]["ring_system_count"],
            "planarity_proxy": base_scan["planarity_and_torsion_summary"]["planarity_proxy"],
            "compactness_proxy": base_scan["compactness_and_contact_proxies"]["compactness_proxy"],
        }
        return {
            "neutral_aromatic_structure_summary": summary,
            "capability_result_summary": (
                "Bounded neutral-aromatic structural screening summarized aromatic-core dominance, ring-system "
                "organization, and rigid-core geometry proxies from the available structural context."
            ),
            "route_summary": {
                "capability": "screen_neutral_aromatic_structure",
                "structure_source": base_scan["structure_source"],
                "summary_fields": sorted(summary.keys()),
            },
            "covered_observable_tags": ["aromatic_core_dominance", "ring_system_rigidity"],
            "missing_deliverables": [],
        }

    def _resolved_target_ids(
        self,
        shared_structure_context: SharedStructureContext | None,
    ) -> dict[str, Any]:
        if shared_structure_context is None:
            return {"structure_source": "smiles_only_fallback"}
        return {
            "structure_source": "shared_prepared_structure",
            "prepared_xyz_path": shared_structure_context.prepared_xyz_path,
            "prepared_sdf_path": shared_structure_context.prepared_sdf_path,
            "selected_conformer_id": shared_structure_context.selected_conformer_id,
        }

    def _prepared_from_shared_context(
        self,
        shared_structure_context: SharedStructureContext,
        *,
        smiles: str,
    ) -> PreparedStructure:
        xyz_path = Path(shared_structure_context.prepared_xyz_path)
        sdf_path = Path(shared_structure_context.prepared_sdf_path)
        summary_path = Path(shared_structure_context.summary_path)
        symbols, _ = _read_xyz_symbols_and_coordinates(xyz_path)
        atom_count = len(symbols) or shared_structure_context.atom_count
        heavy_atom_count = sum(1 for symbol in symbols if symbol != "H") or atom_count
        return PreparedStructure(
            input_smiles=shared_structure_context.input_smiles or smiles,
            canonical_smiles=shared_structure_context.canonical_smiles or smiles,
            charge=shared_structure_context.charge,
            multiplicity=shared_structure_context.multiplicity,
            heavy_atom_count=heavy_atom_count,
            atom_count=atom_count,
            conformer_count=shared_structure_context.conformer_count,
            selected_conformer_id=shared_structure_context.selected_conformer_id,
            force_field="MMFF94",
            xyz_path=xyz_path,
            sdf_path=sdf_path,
            summary_path=summary_path,
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
