from __future__ import annotations

from pathlib import Path

import pytest

from aie_mas.cli.run_case import run_case_workflow
from aie_mas.chem.structure_prep import PreparedStructure
from aie_mas.config import AieMasConfig
from aie_mas.graph.builder import AieMasWorkflow
from aie_mas.graph.state import AieMasState, SharedStructureContext
from aie_mas.tools import shared_structure as shared_structure_module
from aie_mas.tools.amesp import AmespBaselineRunResult, AmespExcitedState, AmespExcitedStateResult, AmespGroundStateResult
from aie_mas.tools.shared_structure import SharedStructurePrepTool


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "src" / "aie_mas" / "prompts"


class _SuccessfulSharedStructureTool:
    name = "shared_structure_prep"

    def invoke(self, *, smiles: str, label: str, workdir: Path) -> SharedStructureContext:
        del smiles, label
        workdir.mkdir(parents=True, exist_ok=True)
        xyz_path = workdir / "prepared_structure.xyz"
        sdf_path = workdir / "prepared_structure.sdf"
        summary_path = workdir / "structure_prep_summary.json"
        xyz_path.write_text("1\nX\nC 0.0 0.0 0.0\n", encoding="utf-8")
        sdf_path.write_text("fake sdf\n", encoding="utf-8")
        summary_path.write_text("{}", encoding="utf-8")
        return SharedStructureContext(
            input_smiles="C1=CC=CC=C1",
            canonical_smiles="c1ccccc1",
            charge=0,
            multiplicity=1,
            atom_count=12,
            conformer_count=3,
            selected_conformer_id=1,
            prepared_xyz_path=str(xyz_path),
            prepared_sdf_path=str(sdf_path),
            summary_path=str(summary_path),
            rotatable_bond_count=2,
            aromatic_ring_count=2,
            ring_system_count=1,
            hetero_atom_count=1,
            branch_point_count=3,
            donor_acceptor_partition_proxy=0.5,
            planarity_proxy=0.75,
            compactness_proxy=0.4,
            torsion_candidate_count=2,
            principal_span_proxy=8.0,
            conformer_dispersion_proxy=0.6,
        )


class _SharedStructureFailure(Exception):
    def __init__(self) -> None:
        super().__init__("shared structure prep failed")

    def to_payload(self) -> dict[str, str]:
        return {"code": "shared_structure_failed", "message": "shared structure prep failed"}


class _FailingSharedStructureTool:
    name = "shared_structure_prep"

    def invoke(self, *, smiles: str, label: str, workdir: Path) -> SharedStructureContext:
        del smiles, label, workdir
        raise _SharedStructureFailure()


class _FallbackAmespTool:
    name = "amesp_baseline_microscopic"

    def __init__(self) -> None:
        self.called = False
        self.structure_sources: list[str] = []

    def execute(
        self,
        *,
        plan,
        smiles,
        label,
        workdir,
        available_artifacts,
        progress_callback=None,
        round_index=1,
        case_id=None,
        current_hypothesis=None,
    ):
        del progress_callback, round_index, case_id, current_hypothesis
        self.called = True
        self.structure_sources.append(plan.structure_source)
        workdir.mkdir(parents=True, exist_ok=True)
        structure_dir = workdir / "structure_prep"
        structure_dir.mkdir(parents=True, exist_ok=True)
        xyz_path = structure_dir / "prepared_structure.xyz"
        sdf_path = structure_dir / "prepared_structure.sdf"
        summary_path = structure_dir / "structure_prep_summary.json"
        xyz_path.write_text("1\nX\nC 0.0 0.0 0.0\n", encoding="utf-8")
        sdf_path.write_text("fake sdf\n", encoding="utf-8")
        summary_path.write_text("{}", encoding="utf-8")
        del smiles, label
        return AmespBaselineRunResult(
            structure=PreparedStructure(
                input_smiles="C1=CC=CC=C1",
                canonical_smiles="c1ccccc1",
                charge=0,
                multiplicity=1,
                heavy_atom_count=6,
                atom_count=12,
                conformer_count=3,
                selected_conformer_id=1,
                force_field="MMFF94",
                xyz_path=xyz_path,
                sdf_path=sdf_path,
                summary_path=summary_path,
            ),
            s0=AmespGroundStateResult(
                final_energy_hartree=-100.0,
                dipole_debye=(0.0, 0.0, 0.0, 0.0),
                mulliken_charges=[0.0],
                homo_lumo_gap_ev=2.5,
                geometry_atom_count=12,
                geometry_xyz_path=str(workdir / "s0.xyz"),
                rmsd_from_prepared_structure_angstrom=0.1,
            ),
            s1=AmespExcitedStateResult(
                excited_states=[
                    AmespExcitedState(
                        state_index=1,
                        total_energy_hartree=-99.8,
                        oscillator_strength=0.2,
                        spin_square=0.0,
                        excitation_energy_ev=3.1,
                    )
                ],
                first_excitation_energy_ev=3.1,
                first_oscillator_strength=0.2,
                state_count=1,
            ),
            raw_step_results={"s0_optimization": {"exit_code": 0}, "s1_vertical_excitation": {"exit_code": 0}},
            generated_artifacts={"prepared_xyz_path": str(xyz_path), "s0_aop_path": str(workdir / "s0.aop")},
        )


def test_prepare_shared_structure_context_populates_state(tmp_path: Path) -> None:
    config = AieMasConfig(project_root=tmp_path, execution_profile="local-dev", prompts_dir=PROMPTS_DIR)
    workflow = AieMasWorkflow(config)
    workflow.shared_structure_tool = _SuccessfulSharedStructureTool()

    state = AieMasState(
        case_id="case123",
        user_query="Assess the likely AIE mechanism for this molecule.",
        smiles="C1=CC=CC=C1",
    )

    updated = workflow.prepare_shared_structure_context(state)

    assert updated.shared_structure_status == "ready"
    assert updated.shared_structure_context is not None
    assert updated.shared_structure_context.canonical_smiles == "c1ccccc1"
    assert updated.shared_structure_context.prepared_xyz_path.endswith("prepared_structure.xyz")


def test_shared_structure_failure_does_not_break_workflow_and_macro_falls_back(
    tmp_path: Path,
    install_specialized_test_doubles,
) -> None:
    fallback_tool = _FallbackAmespTool()
    install_specialized_test_doubles(
        shared_structure_tool=_FailingSharedStructureTool(),
        amesp_tool=fallback_tool,
    )

    state = run_case_workflow(
        smiles="C1=CC=CC=C1",
        user_query="Assess the likely AIE mechanism for this molecule.",
        execution_profile="local-dev",
        tool_backend="real",
        prompts_dir=PROMPTS_DIR,
        data_dir=tmp_path / "data",
        memory_dir=tmp_path / "memory",
        log_dir=tmp_path / "log",
        runtime_dir=tmp_path / "runtime",
    )

    assert state.shared_structure_status == "failed"
    assert state.shared_structure_error == {
        "code": "shared_structure_failed",
        "message": "shared structure prep failed",
    }
    assert state.current_hypothesis is not None
    assert state.macro_reports[0].structured_results["structure_source"] == "smiles_only_fallback"
    assert fallback_tool.called is True
    assert fallback_tool.structure_sources[0] == "prepared_from_smiles"
    assert state.microscopic_reports[0].status == "success"
    assert state.microscopic_reports[0].structured_results["structure_source"] == "prepared_from_smiles"
    assert state.microscopic_reports[0].structured_results["s1"]["first_excitation_energy_ev"] == 3.1


def test_shared_structure_tool_success_schema_is_serializable(tmp_path: Path) -> None:
    pytest.importorskip("rdkit", reason="RDKit is required for shared structure descriptor checks")

    tool = SharedStructurePrepTool(structure_preparer=lambda request: (_FakeAtoms(), _FakePreparedStructure(request, tmp_path)))

    context = tool.invoke(smiles="C1=CC=CC=C1", label="case123", workdir=tmp_path / "shared")

    assert context.atom_count == 12
    assert context.summary_path.endswith("structure_prep_summary.json")
    assert context.rotatable_bond_count >= 0


def test_shared_structure_descriptor_computation_supports_rdkit_api_variants(monkeypatch) -> None:
    class _FakeAtom:
        def __init__(self, atomic_num: int, degree: int, aromatic: bool = False) -> None:
            self._atomic_num = atomic_num
            self._degree = degree
            self._aromatic = aromatic

        def GetAtomicNum(self):
            return self._atomic_num

        def GetDegree(self):
            return self._degree

        def GetIsAromatic(self):
            return self._aromatic

    class _FakeMol:
        def __init__(self) -> None:
            self._atoms = [
                _FakeAtom(6, 2, aromatic=True),
                _FakeAtom(6, 2, aromatic=True),
                _FakeAtom(8, 1, aromatic=False),
            ]

        def GetAtoms(self):
            return self._atoms

        def GetAtomWithIdx(self, idx: int):
            return self._atoms[idx]

    class _FakeChem:
        @staticmethod
        def MolFromSmiles(smiles: str):
            del smiles
            return _FakeMol()

        @staticmethod
        def GetSymmSSSR(mol):
            del mol
            return [(0, 1)]

    class _FakeLipinski:
        @staticmethod
        def NumHDonors(mol):
            del mol
            return 1

        @staticmethod
        def NumHAcceptors(mol):
            del mol
            return 2

    class _FakeRdMolDescriptors:
        @staticmethod
        def CalcNumRotatableBonds(mol):
            del mol
            return 4

    monkeypatch.setattr(
        shared_structure_module,
        "_import_rdkit",
        lambda: {
            "Chem": _FakeChem,
            "Lipinski": _FakeLipinski,
            "rdMolDescriptors": _FakeRdMolDescriptors,
        },
    )

    prepared = type("Prepared", (), {"conformer_count": 3})()

    descriptors = shared_structure_module._compute_shared_descriptors(
        smiles="C1=CC=CC=C1",
        atoms=_FakeAtoms(),
        prepared=prepared,
    )

    assert descriptors["rotatable_bond_count"] == 4
    assert descriptors["donor_acceptor_partition_proxy"] == 1.0


class _FakePositions:
    def __init__(self) -> None:
        self._rows = [
            [0.0, 0.0, 0.0],
            [1.2, 0.0, 0.1],
            [2.4, 0.1, 0.0],
        ]

    def tolist(self):
        return self._rows


class _FakeAtoms:
    def get_positions(self):
        return _FakePositions()


class _FakePreparedStructure:
    def __new__(cls, request, tmp_path: Path):
        workdir = request.workdir
        workdir.mkdir(parents=True, exist_ok=True)
        xyz_path = workdir / "prepared_structure.xyz"
        sdf_path = workdir / "prepared_structure.sdf"
        summary_path = workdir / "structure_prep_summary.json"
        xyz_path.write_text("3\nfake\nC 0 0 0\nC 1 0 0\nC 2 0 0\n", encoding="utf-8")
        sdf_path.write_text("fake sdf\n", encoding="utf-8")
        summary_path.write_text("{}", encoding="utf-8")
        del tmp_path
        return type(
            "PreparedStructure",
            (),
            {
                "input_smiles": request.smiles,
                "canonical_smiles": "c1ccccc1",
                "charge": 0,
                "multiplicity": 1,
                "heavy_atom_count": 6,
                "atom_count": 12,
                "conformer_count": 3,
                "selected_conformer_id": 1,
                "force_field": "MMFF94",
                "xyz_path": xyz_path,
                "sdf_path": sdf_path,
                "summary_path": summary_path,
            },
        )()
