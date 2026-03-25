from __future__ import annotations

import json
import math
import os
import re
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Literal, Optional, Sequence, Tuple

from pydantic import BaseModel, Field

from aie_mas.chem.structure_prep import (
    PreparedConformerBundleMember,
    PreparedStructure,
    StructurePrepRequest,
    prepare_conformer_bundle_from_smiles,
    prepare_structure_from_smiles,
)
from aie_mas.graph.state import MicroscopicExecutionPlan, WorkflowProgressEvent

if TYPE_CHECKING:  # pragma: no cover
    from ase import Atoms

AmespFailureCode = Literal[
    "amesp_binary_missing",
    "structure_unavailable",
    "capability_unsupported",
    "precondition_missing",
    "resource_budget_exceeded",
    "subprocess_failed",
    "normal_termination_missing",
    "parse_failed",
]


class AmespExecutionError(RuntimeError):
    def __init__(
        self,
        code: AmespFailureCode,
        message: str,
        *,
        generated_artifacts: Optional[dict[str, Any]] = None,
        raw_results: Optional[dict[str, Any]] = None,
        structured_results: Optional[dict[str, Any]] = None,
        status: Literal["partial", "failed"] = "failed",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.generated_artifacts = generated_artifacts or {}
        self.raw_results = raw_results or {}
        self.structured_results = structured_results or {}
        self.status = status

    def to_payload(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "generated_artifacts": self.generated_artifacts,
            "raw_results": self.raw_results,
            "structured_results": self.structured_results,
            "status": self.status,
        }


class AmespExcitedState(BaseModel):
    state_index: int
    total_energy_hartree: float
    oscillator_strength: float
    spin_square: Optional[float] = None
    excitation_energy_ev: Optional[float] = None


class AmespGroundStateResult(BaseModel):
    final_energy_hartree: float
    dipole_debye: Optional[Tuple[float, float, float, float]] = None
    mulliken_charges: list[float] = Field(default_factory=list)
    homo_lumo_gap_ev: Optional[float] = None
    geometry_atom_count: int
    geometry_xyz_path: str
    rmsd_from_prepared_structure_angstrom: Optional[float] = None


class AmespExcitedStateResult(BaseModel):
    excited_states: list[AmespExcitedState] = Field(default_factory=list)
    first_excitation_energy_ev: Optional[float] = None
    first_oscillator_strength: Optional[float] = None
    state_count: int = 0


class AmespStepOutcome(BaseModel):
    step_id: str
    aip_path: str
    aop_path: str
    mo_path: Optional[str] = None
    stdout_path: str
    stderr_path: str
    exit_code: int
    terminated_normally: bool
    elapsed_seconds: float


class AmespBaselineRunResult(BaseModel):
    route: str = "baseline_bundle"
    structure: PreparedStructure
    s0: AmespGroundStateResult
    s1: AmespExcitedStateResult
    route_records: list[dict[str, Any]] = Field(default_factory=list)
    route_summary: dict[str, Any] = Field(default_factory=dict)
    raw_step_results: dict[str, Any] = Field(default_factory=dict)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)


class AmespMicroscopicTool:
    name = "amesp_microscopic"

    def __init__(
        self,
        *,
        amesp_bin: Path | None = None,
        npara: int = 1,
        maxcore_mb: int = 1000,
        use_ricosx: bool = False,
        s1_nstates: int = 1,
        td_tout: int = 1,
        follow_up_max_conformers: int = 3,
        follow_up_max_torsion_snapshots_total: int = 6,
        probe_interval_seconds: float = 15.0,
        structure_preparer: Callable[[StructurePrepRequest], tuple["Atoms", PreparedStructure]] = prepare_structure_from_smiles,
        subprocess_runner: Optional[Callable[..., subprocess.CompletedProcess[str]]] = None,
        subprocess_popen_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._amesp_bin = self._resolve_amesp_bin(amesp_bin)
        self._npara = max(1, int(npara))
        self._maxcore_mb = max(1000, int(maxcore_mb))
        self._use_ricosx = bool(use_ricosx)
        self._s1_nstates = max(1, int(s1_nstates))
        self._td_tout = max(1, int(td_tout))
        self._follow_up_max_conformers = max(1, int(follow_up_max_conformers))
        self._follow_up_max_torsion_snapshots_total = max(1, int(follow_up_max_torsion_snapshots_total))
        self._probe_interval_seconds = max(0.0, float(probe_interval_seconds))
        self._structure_preparer = structure_preparer
        self._subprocess_runner = subprocess_runner
        self._subprocess_popen_factory = subprocess_popen_factory or subprocess.Popen

    def execute(
        self,
        *,
        plan: MicroscopicExecutionPlan,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None = None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
        round_index: int = 1,
        case_id: Optional[str] = None,
        current_hypothesis: Optional[str] = None,
    ) -> AmespBaselineRunResult:
        if not self._amesp_bin.exists():
            raise AmespExecutionError(
                "amesp_binary_missing",
                f"Amesp binary was not found at {self._amesp_bin}.",
            )

        workdir.mkdir(parents=True, exist_ok=True)

        if plan.capability_route == "baseline_bundle":
            result = self._execute_baseline_route(
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
            result.route = "baseline_bundle"
            result.route_summary = _build_vertical_state_manifold_summary(result.s1)
            return result

        if plan.capability_route == "conformer_bundle_follow_up":
            return self._execute_conformer_bundle_route(
                smiles=smiles,
                label=label,
                workdir=workdir,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )

        if plan.capability_route == "torsion_snapshot_follow_up":
            return self._execute_torsion_snapshot_route(
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )

        raise AmespExecutionError(
            "capability_unsupported",
            "A low-cost excited-state relaxation route has not been validated for Amesp yet.",
            status="failed",
        )

    def _execute_baseline_route(
        self,
        *,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> AmespBaselineRunResult:
        atoms, prepared = self._resolve_structure(
            smiles=smiles,
            label=label,
            workdir=workdir,
            available_artifacts=available_artifacts,
            progress_callback=progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
        )
        return self._run_single_low_cost_bundle(
            atoms=atoms,
            prepared=prepared,
            label=label,
            workdir=workdir,
            progress_callback=progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            optimize_ground_state=True,
            route="baseline_bundle",
        )

    def _execute_conformer_bundle_route(
        self,
        *,
        smiles: str,
        label: str,
        workdir: Path,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> AmespBaselineRunResult:
        bundle = prepare_conformer_bundle_from_smiles(
            StructurePrepRequest(
                smiles=smiles,
                label=label,
                workdir=workdir / "conformer_bundle",
                num_conformers=max(self._follow_up_max_conformers, 3),
            ),
            max_members=self._follow_up_max_conformers,
        )
        if len(bundle) < 2:
            raise AmespExecutionError(
                "precondition_missing",
                "Conformer follow-up requires at least two prepared conformers, but only one reusable conformer was available.",
                status="failed",
            )

        route_records: list[dict[str, Any]] = []
        primary_result: AmespBaselineRunResult | None = None
        for member in bundle:
            member_result = self._run_single_low_cost_bundle(
                atoms=member.atoms,
                prepared=member.prepared,
                label=f"{label}_conf_{member.rank:02d}",
                workdir=workdir / f"conformer_{member.rank:02d}",
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
                optimize_ground_state=True,
                route="conformer_bundle_follow_up",
            )
            route_records.append(
                {
                    "conformer_rank": member.rank,
                    "conformer_id": member.conformer_id,
                    "force_field_energy": member.force_field_energy,
                    "final_energy_hartree": member_result.s0.final_energy_hartree,
                    "first_excitation_energy_ev": member_result.s1.first_excitation_energy_ev,
                    "first_oscillator_strength": member_result.s1.first_oscillator_strength,
                    "state_count": member_result.s1.state_count,
                }
            )
            if primary_result is None or member_result.s0.final_energy_hartree < primary_result.s0.final_energy_hartree:
                primary_result = member_result

        assert primary_result is not None
        primary_result.route = "conformer_bundle_follow_up"
        primary_result.route_records = route_records
        primary_result.route_summary = _build_conformer_bundle_summary(route_records)
        primary_result.generated_artifacts["conformer_bundle_member_count"] = len(route_records)
        return primary_result

    def _execute_torsion_snapshot_route(
        self,
        *,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> AmespBaselineRunResult:
        atoms, prepared = self._resolve_structure(
            smiles=smiles,
            label=label,
            workdir=workdir,
            available_artifacts=available_artifacts,
            progress_callback=progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
        )
        snapshots = _generate_torsion_snapshot_bundle(
            smiles=smiles,
            prepared=prepared,
            max_total=self._follow_up_max_torsion_snapshots_total,
            output_dir=workdir / "torsion_snapshots",
        )
        if not snapshots:
            raise AmespExecutionError(
                "precondition_missing",
                "Torsion snapshot follow-up requires at least one rotatable dihedral, but none could be generated from the prepared structure.",
                status="failed",
            )

        route_records: list[dict[str, Any]] = []
        primary_result: AmespBaselineRunResult | None = None
        for snapshot in snapshots:
            snapshot_result = self._run_single_low_cost_bundle(
                atoms=snapshot["atoms"],
                prepared=snapshot["prepared"],
                label=f"{label}_{snapshot['snapshot_label']}",
                workdir=workdir / snapshot["snapshot_label"],
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
                optimize_ground_state=True,
                route="torsion_snapshot_follow_up",
            )
            route_records.append(
                {
                    "snapshot_label": snapshot["snapshot_label"],
                    "dihedral_atoms": snapshot["dihedral_atoms"],
                    "target_angle_deg": snapshot["target_angle_deg"],
                    "final_energy_hartree": snapshot_result.s0.final_energy_hartree,
                    "first_excitation_energy_ev": snapshot_result.s1.first_excitation_energy_ev,
                    "first_oscillator_strength": snapshot_result.s1.first_oscillator_strength,
                }
            )
            if primary_result is None or snapshot_result.s0.final_energy_hartree < primary_result.s0.final_energy_hartree:
                primary_result = snapshot_result

        assert primary_result is not None
        primary_result.route = "torsion_snapshot_follow_up"
        primary_result.route_records = route_records
        primary_result.route_summary = _build_torsion_snapshot_summary(route_records)
        primary_result.generated_artifacts["torsion_snapshot_count"] = len(route_records)
        return primary_result

    def _run_single_low_cost_bundle(
        self,
        *,
        atoms: "Atoms",
        prepared: PreparedStructure,
        label: str,
        workdir: Path,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
        optimize_ground_state: bool,
        route: str,
    ) -> AmespBaselineRunResult:
        generated_artifacts: dict[str, Any] = {
            "prepared_xyz_path": str(prepared.xyz_path),
            "prepared_sdf_path": str(prepared.sdf_path),
            "prepared_summary_path": str(prepared.summary_path),
        }
        raw_results: dict[str, Any] = {}

        symbols = list(atoms.get_chemical_symbols())
        initial_positions = [[float(value) for value in row] for row in atoms.get_positions().tolist()]
        if optimize_ground_state:
            s0_result, s0_coordinates, s0_raw_results, s0_artifacts = self._run_ground_state_optimization(
                prepared=prepared,
                label=label,
                workdir=workdir,
                symbols=symbols,
                initial_positions=initial_positions,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
        else:
            s0_result, s0_coordinates, s0_raw_results, s0_artifacts = self._run_ground_state_singlepoint(
                prepared=prepared,
                label=label,
                workdir=workdir,
                symbols=symbols,
                initial_positions=initial_positions,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
        raw_results.update(s0_raw_results)
        generated_artifacts.update(s0_artifacts)
        try:
            s1_result, s1_raw_results, s1_artifacts = self._run_vertical_excitation(
                prepared=prepared,
                label=label,
                workdir=workdir,
                symbols=symbols,
                coordinates=s0_coordinates,
                reference_energy=s0_result.final_energy_hartree,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
        except AmespExecutionError as exc:
            raise AmespExecutionError(
                exc.code,
                exc.message,
                generated_artifacts={**generated_artifacts, **exc.generated_artifacts},
                raw_results={**raw_results, **exc.raw_results},
                structured_results={
                    "structure": prepared.model_dump(mode="json"),
                    "s0": s0_result.model_dump(mode="json"),
                },
                status="partial",
            ) from exc
        raw_results.update(s1_raw_results)
        generated_artifacts.update(s1_artifacts)
        return AmespBaselineRunResult(
            route=route,
            structure=prepared,
            s0=s0_result,
            s1=s1_result,
            raw_step_results=raw_results,
            generated_artifacts=generated_artifacts,
        )

    def _resolve_amesp_bin(self, amesp_bin: Path | None) -> Path:
        if amesp_bin is not None:
            return amesp_bin.expanduser().resolve()
        env_bin = os.environ.get("AIE_MAS_AMESP_BIN")
        if env_bin:
            return Path(env_bin).expanduser().resolve()
        return (Path(__file__).resolve().parents[3] / "third_party" / "Amesp" / "Bin" / "amesp").resolve()

    def _build_s0_keywords(self) -> list[str]:
        return ["atb", "opt", "force"]

    def _build_s0_block_lines(self) -> list[tuple[str, list[str]]]:
        return [
            ("opt", ["maxcyc 2000", "gediis off", "maxstep 0.3"]),
            ("scf", ["maxcyc 2000", "vshift 500"]),
        ]

    def _build_s1_keywords(self) -> list[str]:
        keywords = ["b3lyp", "sto-3g", "td"]
        if self._use_ricosx:
            keywords.append("RICOSX")
        return keywords

    def _run_ground_state_optimization(
        self,
        *,
        prepared: PreparedStructure,
        label: str,
        workdir: Path,
        symbols: Sequence[str],
        initial_positions: Sequence[Sequence[float]],
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> tuple[AmespGroundStateResult, list[list[float]], dict[str, Any], dict[str, Any]]:
        raw_results: dict[str, Any] = {}
        generated_artifacts: dict[str, Any] = {}
        s0_outcome, s0_text = self._run_step(
            step_id="s0_optimization",
            label=f"{label}_s0",
            workdir=workdir,
            keywords=self._build_s0_keywords(),
            block_lines=self._build_s0_block_lines(),
            charge=prepared.charge,
            multiplicity=prepared.multiplicity,
            symbols=symbols,
            coordinates=initial_positions,
            progress_callback=progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
        )
        raw_results["s0_optimization"] = s0_outcome.model_dump(mode="json")
        generated_artifacts.update(
            {
                "s0_aip_path": s0_outcome.aip_path,
                "s0_aop_path": s0_outcome.aop_path,
                "s0_stdout_path": s0_outcome.stdout_path,
                "s0_stderr_path": s0_outcome.stderr_path,
                "s0_mo_path": s0_outcome.mo_path,
            }
        )
        s0_symbols, s0_coordinates = _parse_final_geometry(s0_text)
        if not s0_symbols or not s0_coordinates:
            raise AmespExecutionError(
                "parse_failed",
                "Amesp S0 optimization did not expose a parseable final geometry.",
                generated_artifacts=generated_artifacts,
                raw_results=raw_results,
            )
        s0_xyz_path = workdir / "s0_optimized.xyz"
        _write_xyz(s0_xyz_path, label=f"{label}_s0_optimized", symbols=s0_symbols, coordinates=s0_coordinates)
        generated_artifacts["s0_optimized_xyz_path"] = str(s0_xyz_path)
        s0_result = AmespGroundStateResult(
            final_energy_hartree=_parse_final_energy(s0_text),
            dipole_debye=_parse_last_dipole(s0_text),
            mulliken_charges=_parse_last_mulliken_charges(s0_text),
            homo_lumo_gap_ev=_parse_homo_lumo_gap_ev(s0_text),
            geometry_atom_count=len(s0_symbols),
            geometry_xyz_path=str(s0_xyz_path),
            rmsd_from_prepared_structure_angstrom=_compute_rmsd(initial_positions, s0_coordinates),
        )
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage="s0_parse",
            status="end",
            details=s0_result.model_dump(mode="json"),
        )
        return s0_result, [[float(v) for v in row] for row in s0_coordinates], raw_results, generated_artifacts

    def _run_ground_state_singlepoint(
        self,
        *,
        prepared: PreparedStructure,
        label: str,
        workdir: Path,
        symbols: Sequence[str],
        initial_positions: Sequence[Sequence[float]],
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> tuple[AmespGroundStateResult, list[list[float]], dict[str, Any], dict[str, Any]]:
        raw_results: dict[str, Any] = {}
        generated_artifacts: dict[str, Any] = {}
        s0_outcome, s0_text = self._run_step(
            step_id="s0_singlepoint",
            label=f"{label}_s0sp",
            workdir=workdir,
            keywords=["atb", "force"],
            block_lines=[("scf", ["maxcyc 2000", "vshift 500"])],
            charge=prepared.charge,
            multiplicity=prepared.multiplicity,
            symbols=symbols,
            coordinates=initial_positions,
            progress_callback=progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
        )
        raw_results["s0_singlepoint"] = s0_outcome.model_dump(mode="json")
        generated_artifacts.update(
            {
                "s0_singlepoint_aip_path": s0_outcome.aip_path,
                "s0_singlepoint_aop_path": s0_outcome.aop_path,
                "s0_singlepoint_stdout_path": s0_outcome.stdout_path,
                "s0_singlepoint_stderr_path": s0_outcome.stderr_path,
                "s0_singlepoint_mo_path": s0_outcome.mo_path,
            }
        )
        s0_xyz_path = workdir / "s0_singlepoint.xyz"
        _write_xyz(s0_xyz_path, label=f"{label}_s0_singlepoint", symbols=symbols, coordinates=initial_positions)
        generated_artifacts["s0_singlepoint_xyz_path"] = str(s0_xyz_path)
        s0_result = AmespGroundStateResult(
            final_energy_hartree=_parse_final_energy(s0_text),
            dipole_debye=_parse_last_dipole(s0_text),
            mulliken_charges=_parse_last_mulliken_charges(s0_text),
            homo_lumo_gap_ev=_parse_homo_lumo_gap_ev(s0_text),
            geometry_atom_count=len(symbols),
            geometry_xyz_path=str(s0_xyz_path),
            rmsd_from_prepared_structure_angstrom=_compute_rmsd(initial_positions, initial_positions),
        )
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage="s0_singlepoint_parse",
            status="end",
            details=s0_result.model_dump(mode="json"),
        )
        return s0_result, [[float(v) for v in row] for row in initial_positions], raw_results, generated_artifacts

    def _run_vertical_excitation(
        self,
        *,
        prepared: PreparedStructure,
        label: str,
        workdir: Path,
        symbols: Sequence[str],
        coordinates: Sequence[Sequence[float]],
        reference_energy: float,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> tuple[AmespExcitedStateResult, dict[str, Any], dict[str, Any]]:
        raw_results: dict[str, Any] = {}
        generated_artifacts: dict[str, Any] = {}
        s1_outcome, s1_text = self._run_step(
            step_id="s1_vertical_excitation",
            label=f"{label}_s1",
            workdir=workdir,
            keywords=self._build_s1_keywords(),
            block_lines=[
                ("ope", ["out 1"]),
                ("posthf", [f"nstates {self._s1_nstates}", f"tout {self._td_tout}"]),
            ],
            charge=prepared.charge,
            multiplicity=prepared.multiplicity,
            symbols=symbols,
            coordinates=coordinates,
            progress_callback=progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
        )
        raw_results["s1_vertical_excitation"] = s1_outcome.model_dump(mode="json")
        generated_artifacts.update(
            {
                "s1_aip_path": s1_outcome.aip_path,
                "s1_aop_path": s1_outcome.aop_path,
                "s1_stdout_path": s1_outcome.stdout_path,
                "s1_stderr_path": s1_outcome.stderr_path,
                "s1_mo_path": s1_outcome.mo_path,
            }
        )
        excited_states = _parse_excited_states(s1_text, reference_energy_hartree=reference_energy)
        if not excited_states:
            raise AmespExecutionError(
                "parse_failed",
                "Amesp TD output did not expose parseable excited states.",
                generated_artifacts=generated_artifacts,
                raw_results=raw_results,
                status="partial",
            )
        s1_result = AmespExcitedStateResult(
            excited_states=excited_states,
            first_excitation_energy_ev=excited_states[0].excitation_energy_ev,
            first_oscillator_strength=excited_states[0].oscillator_strength,
            state_count=len(excited_states),
        )
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage="s1_parse",
            status="end",
            details=s1_result.model_dump(mode="json"),
        )
        return s1_result, raw_results, generated_artifacts

    def _resolve_structure(
        self,
        *,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
        round_index: int = 1,
        case_id: Optional[str] = None,
        current_hypothesis: Optional[str] = None,
    ) -> tuple["Atoms", PreparedStructure]:
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage="structure_prep",
            status="start",
            details={"workdir": str(workdir)},
        )
        reusable = self._try_load_prepared_structure(available_artifacts)
        if reusable is not None:
            atoms, prepared = reusable
            self._emit_probe(
                progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
                stage="structure_prep",
                status="end",
                details={
                    "prepared_xyz_path": str(prepared.xyz_path),
                    "prepared_sdf_path": str(prepared.sdf_path),
                    "prepared_summary_path": str(prepared.summary_path),
                    "atom_count": prepared.atom_count,
                    "charge": prepared.charge,
                    "multiplicity": prepared.multiplicity,
                    "source": "available_artifacts",
                },
            )
            return reusable
        structure_dir = workdir / "structure_prep"
        atoms, prepared = self._structure_preparer(
            StructurePrepRequest(
                smiles=smiles,
                label=label,
                workdir=structure_dir,
            )
        )
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage="structure_prep",
            status="end",
            details={
                "prepared_xyz_path": str(prepared.xyz_path),
                "prepared_sdf_path": str(prepared.sdf_path),
                "prepared_summary_path": str(prepared.summary_path),
                "atom_count": prepared.atom_count,
                "charge": prepared.charge,
                "multiplicity": prepared.multiplicity,
                "source": "smiles_to_3d",
            },
        )
        return atoms, prepared

    def _try_load_prepared_structure(
        self,
        available_artifacts: dict[str, Any] | None,
    ) -> tuple["Atoms", PreparedStructure] | None:
        if not available_artifacts:
            return None
        summary_path_raw = available_artifacts.get("prepared_summary_path")
        xyz_path_raw = available_artifacts.get("prepared_xyz_path")
        if not summary_path_raw or not xyz_path_raw:
            return None
        summary_path = Path(str(summary_path_raw))
        xyz_path = Path(str(xyz_path_raw))
        if not summary_path.exists() or not xyz_path.exists():
            return None

        from ase.io import read

        atoms = read(str(xyz_path))
        prepared = PreparedStructure.model_validate(
            json.loads(summary_path.read_text(encoding="utf-8"))
        )
        return atoms, prepared

    def _run_step(
        self,
        *,
        step_id: str,
        label: str,
        workdir: Path,
        keywords: Sequence[str],
        block_lines: Sequence[tuple[str, Sequence[str]]],
        charge: int,
        multiplicity: int,
        symbols: Sequence[str],
        coordinates: Sequence[Sequence[float]],
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
        round_index: int = 1,
        case_id: Optional[str] = None,
        current_hypothesis: Optional[str] = None,
    ) -> tuple[AmespStepOutcome, str]:
        workdir.mkdir(parents=True, exist_ok=True)
        aip_path = workdir / f"{label}.aip"
        aop_path = workdir / f"{label}.aop"
        stdout_path = workdir / f"{label}.stdout.log"
        stderr_path = workdir / f"{label}.stderr.log"
        _write_amesp_input(
            aip_path=aip_path,
            keywords=keywords,
            charge=charge,
            multiplicity=multiplicity,
            symbols=symbols,
            coordinates=coordinates,
            block_lines=block_lines,
            npara=self._npara,
            maxcore_mb=self._maxcore_mb,
        )
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage=step_id,
            status="start",
            details={
                "aip_path": str(aip_path),
                "aop_path": str(aop_path),
                "keywords": list(keywords),
                "npara": self._npara,
                "maxcore_mb": self._maxcore_mb,
                "use_ricosx": self._use_ricosx,
            },
        )

        _raise_stack_limit()
        env = os.environ.copy()
        env.setdefault("KMP_STACKSIZE", "4g")

        start = time.perf_counter()
        if self._subprocess_runner is not None:
            completed = self._subprocess_runner(
                [str(self._amesp_bin), str(aip_path.name), str(aop_path.name)],
                cwd=str(workdir),
                env=env,
                capture_output=True,
                text=True,
            )
        else:
            completed = self._run_subprocess_with_heartbeat(
                cmd=[str(self._amesp_bin), str(aip_path.name), str(aop_path.name)],
                workdir=workdir,
                env=env,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                aop_path=aop_path,
                step_id=step_id,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
        elapsed = round(time.perf_counter() - start, 4)
        if self._subprocess_runner is not None:
            stdout_path.write_text(completed.stdout or "", encoding="utf-8")
            stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage=f"{step_id}_subprocess",
            status="end",
            details={
                "exit_code": completed.returncode,
                "elapsed_seconds": elapsed,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            },
        )

        mo_path = workdir / f"{label}.mo"
        outcome = AmespStepOutcome(
            step_id=step_id,
            aip_path=str(aip_path),
            aop_path=str(aop_path),
            mo_path=str(mo_path) if mo_path.exists() else None,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            exit_code=completed.returncode,
            terminated_normally=False,
            elapsed_seconds=elapsed,
        )

        if completed.returncode != 0:
            raise AmespExecutionError(
                "subprocess_failed",
                f"Amesp step '{step_id}' exited with code {completed.returncode}.",
                generated_artifacts=outcome.model_dump(mode="json"),
                raw_results={"stdout": completed.stdout, "stderr": completed.stderr},
            )
        if not aop_path.exists():
            raise AmespExecutionError(
                "subprocess_failed",
                f"Amesp step '{step_id}' finished without producing {aop_path.name}.",
                generated_artifacts=outcome.model_dump(mode="json"),
                raw_results={"stdout": completed.stdout, "stderr": completed.stderr},
            )

        aop_text = aop_path.read_text(encoding="utf-8", errors="replace")
        outcome.terminated_normally = "Normal termination of Amesp!" in aop_text
        if not outcome.terminated_normally:
            raise AmespExecutionError(
                "normal_termination_missing",
                f"Amesp step '{step_id}' did not report normal termination.",
                generated_artifacts=outcome.model_dump(mode="json"),
                raw_results={"stdout": completed.stdout, "stderr": completed.stderr},
            )
        self._emit_probe(
            progress_callback,
            round_index=round_index,
            case_id=case_id,
            current_hypothesis=current_hypothesis,
            stage=step_id,
            status="end",
            details=outcome.model_dump(mode="json"),
        )
        return outcome, aop_text

    def _run_subprocess_with_heartbeat(
        self,
        *,
        cmd: list[str],
        workdir: Path,
        env: dict[str, str],
        stdout_path: Path,
        stderr_path: Path,
        aop_path: Path,
        step_id: str,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> subprocess.CompletedProcess[str]:
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            process = self._subprocess_popen_factory(
                cmd,
                cwd=str(workdir),
                env=env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
            )
            self._emit_probe(
                progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
                stage=f"{step_id}_subprocess",
                status="start",
                details={
                    "pid": getattr(process, "pid", None),
                    "stdout_path": str(stdout_path),
                    "stderr_path": str(stderr_path),
                },
            )

            start = time.perf_counter()
            next_probe_at = start + self._probe_interval_seconds
            return_code: Optional[int] = None
            while return_code is None:
                return_code = process.poll()
                if return_code is not None:
                    break
                now = time.perf_counter()
                if now >= next_probe_at:
                    self._emit_probe(
                        progress_callback,
                        round_index=round_index,
                        case_id=case_id,
                        current_hypothesis=current_hypothesis,
                        stage=f"{step_id}_subprocess",
                        status="running",
                        details={
                            "pid": getattr(process, "pid", None),
                            "elapsed_seconds": round(now - start, 2),
                            **_build_runtime_probe_details(
                                aop_path=aop_path,
                                stdout_path=stdout_path,
                                stderr_path=stderr_path,
                            ),
                        },
                    )
                    next_probe_at = now + self._probe_interval_seconds
                time.sleep(0.5)

        stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
        return subprocess.CompletedProcess(cmd, int(return_code), stdout=stdout_text, stderr=stderr_text)

    def _emit_probe(
        self,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        *,
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
        stage: str,
        status: str,
        details: dict[str, Any],
    ) -> None:
        if progress_callback is None:
            return
        event: WorkflowProgressEvent = {
            "phase": "probe",
            "node": "run_microscopic",
            "round": round_index,
            "agent": "microscopic",
            "case_id": case_id,
            "current_hypothesis": current_hypothesis,
            "details": {
                "probe_stage": stage,
                "probe_status": status,
                **details,
            },
        }
        progress_callback(event)


def _write_amesp_input(
    *,
    aip_path: Path,
    keywords: Sequence[str],
    charge: int,
    multiplicity: int,
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    block_lines: Sequence[tuple[str, Sequence[str]]],
    npara: int,
    maxcore_mb: int,
) -> None:
    lines = [f"% npara {npara}", f"% maxcore {maxcore_mb}", f"! {' '.join(keywords)}"]
    if len(symbols) != len(coordinates):
        raise AmespExecutionError(
            "structure_unavailable",
            "The Amesp input writer received mismatched symbols and coordinates.",
        )
    for block_name, block_body in block_lines:
        lines.append(f">{block_name}")
        lines.extend(f"  {line}" for line in block_body)
        lines.append("end")
    lines.append(f">xyz {charge} {multiplicity}")
    for symbol, coordinate in zip(symbols, coordinates):
        x, y, z = coordinate
        lines.append(f" {symbol:<2} {x: .8f} {y: .8f} {z: .8f}")
    lines.append("end")
    aip_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_xyz(
    xyz_path: Path,
    *,
    label: str,
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
) -> None:
    lines = [str(len(symbols)), label]
    if len(symbols) != len(coordinates):
        raise AmespExecutionError(
            "structure_unavailable",
            "The XYZ writer received mismatched symbols and coordinates.",
        )
    for symbol, coordinate in zip(symbols, coordinates):
        x, y, z = coordinate
        lines.append(f"{symbol:<2} {x: .8f} {y: .8f} {z: .8f}")
    xyz_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _raise_stack_limit() -> None:
    try:  # pragma: no cover - platform dependent
        import resource

        soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
        target = hard if hard != resource.RLIM_INFINITY else resource.RLIM_INFINITY
        resource.setrlimit(resource.RLIMIT_STACK, (target, hard))
        _ = soft
    except Exception:
        return


def _build_runtime_probe_details(
    *,
    aop_path: Path,
    stdout_path: Path,
    stderr_path: Path,
) -> dict[str, Any]:
    details: dict[str, Any] = {
        "aop_exists": aop_path.exists(),
        "aop_size_bytes": aop_path.stat().st_size if aop_path.exists() else 0,
        "stdout_size_bytes": stdout_path.stat().st_size if stdout_path.exists() else 0,
        "stderr_size_bytes": stderr_path.stat().st_size if stderr_path.exists() else 0,
    }
    aop_tail = _read_last_nonempty_line(aop_path)
    if aop_tail is not None:
        details["aop_tail"] = aop_tail
    return details


def _read_last_nonempty_line(path: Path, *, max_bytes: int = 4096) -> str | None:
    if not path.exists() or path.stat().st_size == 0:
        return None
    with path.open("rb") as handle:
        handle.seek(max(-max_bytes, -path.stat().st_size), os.SEEK_END)
        chunk = handle.read().decode("utf-8", errors="replace")
    for line in reversed(chunk.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped[:200]
    return None


def _parse_final_energy(text: str) -> float:
    matches = re.findall(r"Final Energy:\s*([-+]?\d+\.\d+)", text)
    if not matches:
        raise AmespExecutionError("parse_failed", "Final Energy could not be parsed from Amesp output.")
    return float(matches[-1])


def _parse_last_dipole(text: str) -> tuple[float, float, float, float] | None:
    matches = re.findall(
        r"X=\s*([-+]?\d+\.\d+)\s+Y=\s*([-+]?\d+\.\d+)\s+Z=\s*([-+]?\d+\.\d+)\s+Tot=\s*([-+]?\d+\.\d+)",
        text,
    )
    if not matches:
        return None
    x, y, z, total = matches[-1]
    return (float(x), float(y), float(z), float(total))


def _parse_last_mulliken_charges(text: str) -> list[float]:
    matches = re.findall(
        r"Mulliken charges:\s*(.*?)Sum of Mulliken charges\s*=\s*[-+]?\d+\.\d+",
        text,
        flags=re.DOTALL,
    )
    if not matches:
        return []
    block = matches[-1]
    charges: list[float] = []
    for line in block.splitlines():
        match = re.match(r"\s*\d+\s+\S+\s+([-+]?\d+\.\d+)", line)
        if match:
            charges.append(float(match.group(1)))
    return charges


def _parse_homo_lumo_gap_ev(text: str) -> float | None:
    match = re.search(
        r"HOMO-LUMO gap:.*?=\s*([-+]?\d+\.\d+)\s*eV",
        text,
        flags=re.DOTALL,
    )
    if match is None:
        return None
    return float(match.group(1))


def _parse_final_geometry(text: str) -> tuple[list[str], list[list[float]]]:
    matches = re.findall(
        r"Final Geometry\(angstroms\):\s*(\d+)\s*(.*?)\n\s*Final Energy:",
        text,
        flags=re.DOTALL,
    )
    if not matches:
        return ([], [])
    atom_count = int(matches[-1][0])
    block = matches[-1][1]
    symbols: list[str] = []
    coordinates: list[list[float]] = []
    for line in block.splitlines():
        parts = line.split()
        if len(parts) != 4:
            continue
        symbol = parts[0]
        try:
            xyz = [float(parts[1]), float(parts[2]), float(parts[3])]
        except ValueError:
            continue
        symbols.append(symbol)
        coordinates.append(xyz)
    if len(symbols) != atom_count:
        return ([], [])
    return symbols, coordinates


def _parse_excited_states(
    text: str,
    *,
    reference_energy_hartree: float,
) -> list[AmespExcitedState]:
    state_matches = re.findall(
        r"State\s+(\d+)\s*:\s*E\s*=\s*([-+]?\d+\.\d+)\s+eV",
        text,
    )
    td_matches = re.findall(
        r"E\(TD\)\s*=\s*([-+]?\d+\.\d+)\s+<S\*\*2>=\s*([-+]?\d+\.\d+)\s+f=\s*([-+]?\d+\.\d+)",
        text,
    )
    states: list[AmespExcitedState] = []
    if state_matches:
        for offset, (state_index, excitation_energy_ev) in enumerate(state_matches):
            if offset < len(td_matches):
                total_energy, spin_square, oscillator = td_matches[offset]
                parsed_total_energy = float(total_energy)
                parsed_spin_square: float | None = float(spin_square)
                parsed_oscillator = float(oscillator)
            else:
                parsed_total_energy = reference_energy_hartree + (
                    float(excitation_energy_ev) / 27.211386245988
                )
                parsed_spin_square = None
                parsed_oscillator = 0.0
            states.append(
                AmespExcitedState(
                    state_index=int(state_index),
                    total_energy_hartree=parsed_total_energy,
                    oscillator_strength=parsed_oscillator,
                    spin_square=parsed_spin_square,
                    excitation_energy_ev=round(float(excitation_energy_ev), 6),
                )
            )
        return states

    for index, (energy, spin_square, oscillator) in enumerate(td_matches, start=1):
        total_energy = float(energy)
        excitation_energy_ev = (total_energy - reference_energy_hartree) * 27.211386245988
        states.append(
            AmespExcitedState(
                state_index=index,
                total_energy_hartree=total_energy,
                oscillator_strength=float(oscillator),
                spin_square=float(spin_square),
                excitation_energy_ev=round(excitation_energy_ev, 6),
            )
        )
    return states


def _compute_rmsd(
    reference_coordinates: Sequence[Sequence[float]],
    new_coordinates: Sequence[Sequence[float]],
) -> float | None:
    if len(reference_coordinates) != len(new_coordinates):
        return None
    squared_distance = 0.0
    atom_count = 0
    for reference_row, new_row in zip(reference_coordinates, new_coordinates):
        if len(reference_row) != 3 or len(new_row) != 3:
            return None
        dx = float(reference_row[0]) - float(new_row[0])
        dy = float(reference_row[1]) - float(new_row[1])
        dz = float(reference_row[2]) - float(new_row[2])
        squared_distance += dx * dx + dy * dy + dz * dz
        atom_count += 1
    if atom_count == 0:
        return None
    return round(math.sqrt(squared_distance / atom_count), 6)


def _build_vertical_state_manifold_summary(s1_result: AmespExcitedStateResult) -> dict[str, Any]:
    lowest_state_energy = s1_result.excited_states[0].excitation_energy_ev if s1_result.excited_states else None
    bright_states = [
        state
        for state in s1_result.excited_states
        if state.excitation_energy_ev is not None and state.oscillator_strength > 0.05
    ]
    first_bright = bright_states[0] if bright_states else None
    oscillator_sum = round(sum(state.oscillator_strength for state in s1_result.excited_states), 6)
    return {
        "state_count": s1_result.state_count,
        "lowest_state_energy_ev": lowest_state_energy,
        "first_bright_state_index": first_bright.state_index if first_bright is not None else None,
        "first_bright_state_energy_ev": first_bright.excitation_energy_ev if first_bright is not None else None,
        "first_bright_state_oscillator_strength": (
            first_bright.oscillator_strength if first_bright is not None else None
        ),
        "lowest_state_to_brightest_pattern": (
            "lowest_state_is_bright"
            if first_bright is not None and first_bright.state_index == 1
            else "lowest_state_is_dark_then_bright"
            if first_bright is not None
            else "no_bright_state_detected"
        ),
        "oscillator_strength_summary": {
            "sum": oscillator_sum,
            "max": max((state.oscillator_strength for state in s1_result.excited_states), default=None),
        },
    }


def _build_conformer_bundle_summary(route_records: list[dict[str, Any]]) -> dict[str, Any]:
    excitation_values = [
        float(record["first_excitation_energy_ev"])
        for record in route_records
        if record.get("first_excitation_energy_ev") is not None
    ]
    oscillator_values = [
        float(record["first_oscillator_strength"])
        for record in route_records
        if record.get("first_oscillator_strength") is not None
    ]
    spread = max(excitation_values) - min(excitation_values) if len(excitation_values) >= 2 else 0.0
    bright_spread = max(oscillator_values) - min(oscillator_values) if len(oscillator_values) >= 2 else 0.0
    return {
        "member_count": len(route_records),
        "excitation_spread_ev": round(spread, 6),
        "bright_state_sensitivity": round(bright_spread, 6),
        "conformer_dependent_uncertainty_note": (
            "Vertical-state proxies vary across bounded conformers."
            if spread > 0.05 or bright_spread > 0.05
            else "Bounded conformer follow-up shows limited variation across sampled conformers."
        ),
    }


def _build_torsion_snapshot_summary(route_records: list[dict[str, Any]]) -> dict[str, Any]:
    excitation_values = [
        float(record["first_excitation_energy_ev"])
        for record in route_records
        if record.get("first_excitation_energy_ev") is not None
    ]
    oscillator_values = [
        float(record["first_oscillator_strength"])
        for record in route_records
        if record.get("first_oscillator_strength") is not None
    ]
    spread = max(excitation_values) - min(excitation_values) if len(excitation_values) >= 2 else 0.0
    bright_spread = max(oscillator_values) - min(oscillator_values) if len(oscillator_values) >= 2 else 0.0
    return {
        "snapshot_count": len(route_records),
        "torsion_sensitivity_summary": {
            "excitation_spread_ev": round(spread, 6),
            "oscillator_spread": round(bright_spread, 6),
        },
        "torsion_sensitive": spread > 0.05 or bright_spread > 0.05,
    }


def _generate_torsion_snapshot_bundle(
    *,
    smiles: str,
    prepared: PreparedStructure,
    max_total: int,
    output_dir: Path,
) -> list[dict[str, Any]]:
    try:
        from rdkit import Chem
        from rdkit.Chem import rdMolTransforms
        from ase import Atoms
    except ModuleNotFoundError:
        return []

    mol = Chem.MolFromMolFile(str(prepared.sdf_path), removeHs=False)
    if mol is None or mol.GetNumConformers() == 0:
        return []
    conformer = mol.GetConformer()
    output_dir.mkdir(parents=True, exist_ok=True)

    dihedrals = _find_rotatable_dihedrals(mol)
    if not dihedrals:
        return []

    target_angles = [-120.0, 0.0, 120.0]
    snapshots: list[dict[str, Any]] = []
    snapshot_index = 1
    for dihedral in dihedrals:
        if len(snapshots) >= max_total:
            break
        atom_a, atom_b, atom_c, atom_d = dihedral
        for angle in target_angles:
            if len(snapshots) >= max_total:
                break
            snapshot_mol = Chem.Mol(mol)
            snapshot_conf = snapshot_mol.GetConformer()
            rdMolTransforms.SetDihedralDeg(snapshot_conf, atom_a, atom_b, atom_c, atom_d, float(angle))
            snapshot_label = f"torsion_{snapshot_index:02d}"
            snapshot_dir = output_dir / snapshot_label
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            xyz_path = snapshot_dir / "prepared_structure.xyz"
            sdf_path = snapshot_dir / "prepared_structure.sdf"
            summary_path = snapshot_dir / "structure_prep_summary.json"
            _write_rdkit_xyz(snapshot_mol, xyz_path, snapshot_label)
            writer = Chem.SDWriter(str(sdf_path))
            try:
                writer.write(snapshot_mol)
            finally:
                writer.close()
            snapshot_prepared = prepared.model_copy(
                update={
                    "input_smiles": smiles,
                    "xyz_path": xyz_path,
                    "sdf_path": sdf_path,
                    "summary_path": summary_path,
                }
            )
            summary_path.write_text(
                json.dumps(snapshot_prepared.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            atoms = Atoms(
                symbols=[atom.GetSymbol() for atom in snapshot_mol.GetAtoms()],
                positions=snapshot_conf.GetPositions(),
            )
            snapshots.append(
                {
                    "snapshot_label": snapshot_label,
                    "dihedral_atoms": [atom_a, atom_b, atom_c, atom_d],
                    "target_angle_deg": float(angle),
                    "prepared": snapshot_prepared,
                    "atoms": atoms,
                }
            )
            snapshot_index += 1
    return snapshots


def _find_rotatable_dihedrals(mol: Any) -> list[tuple[int, int, int, int]]:
    dihedrals: list[tuple[int, int, int, int]] = []
    for bond in mol.GetBonds():
        if bond.GetBondTypeAsDouble() != 1.0 or bond.IsInRing():
            continue
        atom_b = bond.GetBeginAtom()
        atom_c = bond.GetEndAtom()
        if atom_b.GetAtomicNum() == 1 or atom_c.GetAtomicNum() == 1:
            continue
        neighbors_a = [nbr.GetIdx() for nbr in atom_b.GetNeighbors() if nbr.GetIdx() != atom_c.GetIdx()]
        neighbors_d = [nbr.GetIdx() for nbr in atom_c.GetNeighbors() if nbr.GetIdx() != atom_b.GetIdx()]
        if not neighbors_a or not neighbors_d:
            continue
        dihedrals.append((neighbors_a[0], atom_b.GetIdx(), atom_c.GetIdx(), neighbors_d[0]))
    return dihedrals


def _write_rdkit_xyz(mol: Any, xyz_path: Path, label: str) -> None:
    conformer = mol.GetConformer()
    lines = [str(mol.GetNumAtoms()), label]
    for atom_idx, atom in enumerate(mol.GetAtoms()):
        position = conformer.GetAtomPosition(atom_idx)
        lines.append(
            f"{atom.GetSymbol():<2} {position.x: .8f} {position.y: .8f} {position.z: .8f}"
        )
    xyz_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


AmespBaselineMicroscopicTool = AmespMicroscopicTool
