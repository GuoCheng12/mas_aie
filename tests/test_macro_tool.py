from __future__ import annotations

import json
from pathlib import Path

from aie_mas.graph.state import MacroExecutionPlan
from aie_mas.tools.macro import DeterministicMacroStructureTool
from aie_mas.graph.state import SharedStructureContext


def _shared_structure_context(tmp_path: Path) -> SharedStructureContext:
    xyz_path = tmp_path / "prepared.xyz"
    sdf_path = tmp_path / "prepared.sdf"
    summary_path = tmp_path / "summary.json"
    xyz_path.write_text(
        "5\nmacro_geometry\n"
        "O 0.0 0.0 0.0\n"
        "H 0.98 0.0 0.0\n"
        "C -1.32 0.0 0.0\n"
        "N 2.55 0.2 0.0\n"
        "C 3.72 0.2 0.0\n",
        encoding="utf-8",
    )
    sdf_path.write_text("macro geometry sdf\n", encoding="utf-8")
    summary_path.write_text(json.dumps({"ok": True}), encoding="utf-8")
    return SharedStructureContext(
        input_smiles="OCC=N",
        canonical_smiles="OCC=N",
        charge=0,
        multiplicity=1,
        atom_count=5,
        conformer_count=3,
        selected_conformer_id=1,
        prepared_xyz_path=str(xyz_path),
        prepared_sdf_path=str(sdf_path),
        summary_path=str(summary_path),
        rotatable_bond_count=2,
        aromatic_ring_count=1,
        ring_system_count=1,
        hetero_atom_count=2,
        branch_point_count=1,
        donor_acceptor_partition_proxy=0.7,
        planarity_proxy=0.84,
        compactness_proxy=0.52,
        torsion_candidate_count=2,
        principal_span_proxy=7.2,
        conformer_dispersion_proxy=0.45,
    )


def test_macro_tool_executes_registry_backed_planarity_capability(tmp_path: Path) -> None:
    tool = DeterministicMacroStructureTool()
    result = tool.execute(
        plan=MacroExecutionPlan(
            local_goal="Summarize planarity and compactness proxies only.",
            requested_deliverables=["planarity and torsion summary", "compactness and contact proxies"],
            structure_source="shared_prepared_structure",
            selected_capability="screen_planarity_compactness",
            binding_mode="preferred",
            requested_observable_tags=["planarity_proxy", "compactness_proxy", "conformer_geometry_proxy"],
        ),
        smiles="OCC=N",
        shared_structure_context=_shared_structure_context(tmp_path),
    )

    assert result["executed_capability"] == "screen_planarity_compactness"
    assert result["performed_new_calculations"] is False
    assert result["route_summary"]["capability"] == "screen_planarity_compactness"
    assert result["covered_observable_tags"] == [
        "planarity_proxy",
        "compactness_proxy",
        "conformer_geometry_proxy",
    ]
    assert result["missing_deliverables"] == []


def test_macro_tool_hbond_preorganization_returns_typed_geometry_summary(tmp_path: Path) -> None:
    tool = DeterministicMacroStructureTool()
    result = tool.execute(
        plan=MacroExecutionPlan(
            local_goal="Screen intramolecular H-bond preorganization only.",
            requested_deliverables=["typed donor/acceptor preorganization summary"],
            structure_source="shared_prepared_structure",
            selected_capability="screen_intramolecular_hbond_preorganization",
            binding_mode="preferred",
            requested_observable_tags=["intramolecular_hbond_preorganization", "geometry_precondition"],
        ),
        smiles="OCC=N",
        shared_structure_context=_shared_structure_context(tmp_path),
    )

    summary = result["intramolecular_hbond_preorganization_summary"]
    assert result["executed_capability"] == "screen_intramolecular_hbond_preorganization"
    assert summary["role_typing_mode"] in {"connectivity_heuristic", "rdkit_bond_roles"}
    assert "phenolic_oh_to_imine_n_proximity" in summary
    assert "phenolic_oh_to_imine_n_orientation" in summary
    assert result["missing_deliverables"] == []


def test_macro_tool_hbond_preorganization_contracts_on_smiles_only_fallback() -> None:
    tool = DeterministicMacroStructureTool()
    result = tool.execute(
        plan=MacroExecutionPlan(
            local_goal="Screen intramolecular H-bond preorganization only.",
            requested_deliverables=["typed donor/acceptor preorganization summary"],
            structure_source="smiles_only_fallback",
            selected_capability="screen_intramolecular_hbond_preorganization",
            binding_mode="preferred",
            requested_observable_tags=["intramolecular_hbond_preorganization", "geometry_precondition"],
        ),
        smiles="OCC=N",
        shared_structure_context=None,
    )

    assert result["executed_capability"] == "screen_intramolecular_hbond_preorganization"
    assert result["missing_deliverables"] == ["intramolecular H-bond preorganization geometry"]
    assert result["covered_observable_tags"] == []
    assert result["fulfillment_mode"] == "proxy"
