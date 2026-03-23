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
    PreparedStructure,
    StructurePrepRequest,
    prepare_structure_from_smiles,
)
from aie_mas.graph.state import MicroscopicExecutionPlan

if TYPE_CHECKING:  # pragma: no cover
    from ase import Atoms

AmespFailureCode = Literal[
    "amesp_binary_missing",
    "structure_unavailable",
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
    structure: PreparedStructure
    s0: AmespGroundStateResult
    s1: AmespExcitedStateResult
    raw_step_results: dict[str, Any] = Field(default_factory=dict)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)


class AmespBaselineMicroscopicTool:
    name = "amesp_baseline_microscopic"

    def __init__(
        self,
        *,
        amesp_bin: Path | None = None,
        structure_preparer: Callable[[StructurePrepRequest], tuple["Atoms", PreparedStructure]] = prepare_structure_from_smiles,
        subprocess_runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._amesp_bin = self._resolve_amesp_bin(amesp_bin)
        self._structure_preparer = structure_preparer
        self._subprocess_runner = subprocess_runner

    def execute(
        self,
        *,
        plan: MicroscopicExecutionPlan,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None = None,
    ) -> AmespBaselineRunResult:
        if not self._amesp_bin.exists():
            raise AmespExecutionError(
                "amesp_binary_missing",
                f"Amesp binary was not found at {self._amesp_bin}.",
            )

        workdir.mkdir(parents=True, exist_ok=True)
        generated_artifacts: dict[str, Any] = {}
        raw_results: dict[str, Any] = {}

        atoms, prepared = self._resolve_structure(
            smiles=smiles,
            label=label,
            workdir=workdir,
            available_artifacts=available_artifacts,
        )
        generated_artifacts.update(
            {
                "prepared_xyz_path": str(prepared.xyz_path),
                "prepared_sdf_path": str(prepared.sdf_path),
                "prepared_summary_path": str(prepared.summary_path),
            }
        )

        symbols = list(atoms.get_chemical_symbols())
        initial_positions = [[float(value) for value in row] for row in atoms.get_positions().tolist()]

        s0_outcome, s0_text = self._run_step(
            step_id="s0_optimization",
            label=f"{label}_s0",
            workdir=workdir,
            keywords=["b3lyp", "sto-3g", "opt"],
            block_lines=[("ope", ["out 1"])],
            charge=prepared.charge,
            multiplicity=prepared.multiplicity,
            symbols=symbols,
            coordinates=initial_positions,
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

        try:
            s1_outcome, s1_text = self._run_step(
                step_id="s1_vertical_excitation",
                label=f"{label}_s1",
                workdir=workdir,
                keywords=["b3lyp", "sto-3g", "td"],
                block_lines=[("ope", ["out 1"]), ("posthf", ["nstates 3", "tout 2"])],
                charge=prepared.charge,
                multiplicity=prepared.multiplicity,
                symbols=s0_symbols,
                coordinates=s0_coordinates,
            )
        except AmespExecutionError as exc:
            partial_structured = {
                "structure": prepared.model_dump(mode="json"),
                "s0": s0_result.model_dump(mode="json"),
            }
            partial_raw = dict(raw_results)
            partial_generated = dict(generated_artifacts)
            partial_generated.update(exc.generated_artifacts)
            raise AmespExecutionError(
                exc.code,
                exc.message,
                generated_artifacts=partial_generated,
                raw_results={**partial_raw, **exc.raw_results},
                structured_results=partial_structured,
                status="partial",
            ) from exc

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

        excited_states = _parse_excited_states(
            s1_text,
            reference_energy_hartree=s0_result.final_energy_hartree,
        )
        if not excited_states:
            raise AmespExecutionError(
                "parse_failed",
                "Amesp TD output did not expose parseable excited states.",
                generated_artifacts=generated_artifacts,
                raw_results=raw_results,
                structured_results={
                    "structure": prepared.model_dump(mode="json"),
                    "s0": s0_result.model_dump(mode="json"),
                },
                status="partial",
            )

        s1_result = AmespExcitedStateResult(
            excited_states=excited_states,
            first_excitation_energy_ev=excited_states[0].excitation_energy_ev,
            first_oscillator_strength=excited_states[0].oscillator_strength,
            state_count=len(excited_states),
        )

        return AmespBaselineRunResult(
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

    def _resolve_structure(
        self,
        *,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None,
    ) -> tuple["Atoms", PreparedStructure]:
        reusable = self._try_load_prepared_structure(available_artifacts)
        if reusable is not None:
            return reusable
        structure_dir = workdir / "structure_prep"
        return self._structure_preparer(
            StructurePrepRequest(
                smiles=smiles,
                label=label,
                workdir=structure_dir,
            )
        )

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
    ) -> tuple[AmespStepOutcome, str]:
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
        )

        _raise_stack_limit()
        env = os.environ.copy()
        env.setdefault("KMP_STACKSIZE", "4g")

        start = time.perf_counter()
        completed = self._subprocess_runner(
            [str(self._amesp_bin), str(aip_path.name), str(aop_path.name)],
            cwd=str(workdir),
            env=env,
            capture_output=True,
            text=True,
        )
        elapsed = round(time.perf_counter() - start, 4)
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")

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
        return outcome, aop_text


def _write_amesp_input(
    *,
    aip_path: Path,
    keywords: Sequence[str],
    charge: int,
    multiplicity: int,
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    block_lines: Sequence[tuple[str, Sequence[str]]],
) -> None:
    lines = [f"! {' '.join(keywords)}"]
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
    matches = re.findall(
        r"E\(TD\)\s*=\s*([-+]?\d+\.\d+)\s+<S\*\*2>=\s*([-+]?\d+\.\d+)\s+f=\s*([-+]?\d+\.\d+)",
        text,
    )
    states: list[AmespExcitedState] = []
    for index, (energy, spin_square, oscillator) in enumerate(matches, start=1):
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
