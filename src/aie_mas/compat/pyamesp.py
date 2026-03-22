from __future__ import annotations

import importlib
import os
import re
from typing import Any


def _to_float_triplet(parts: list[str]) -> list[float] | None:
    if len(parts) < 4:
        return None
    try:
        return [float(parts[1]), float(parts[2]), float(parts[3])]
    except ValueError:
        return None


def _parse_geometry_lines(block_text: str) -> tuple[list[str], list[list[float]]]:
    elements: list[str] = []
    positions: list[list[float]] = []

    for raw_line in block_text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        if stripped.split()[:3] == ["x", "y", "z"]:
            continue
        if stripped.isdigit():
            continue
        parts = stripped.split()
        coords = _to_float_triplet(parts)
        if coords is None:
            continue
        elements.append(parts[0])
        positions.append(coords)

    return elements, positions


def _parse_geometry_series(text: str) -> list[tuple[list[str], list[list[float]]]]:
    current_blocks = re.findall(
        r"Current Geometry\(angstroms\):\s*\n(.*?)(?=\n\s*-{5,}|\n\s*Final Geometry\(angstroms\):|\Z)",
        text,
        re.S,
    )
    parsed_current = []
    for block in current_blocks:
        elements, positions = _parse_geometry_lines(block)
        if elements:
            parsed_current.append((elements, positions))
    if parsed_current:
        return parsed_current

    final_blocks = re.findall(
        r"Final Geometry\(angstroms\):\s*\n(.*?)(?=\n\s*Final Energy:|\n\s*=+|\Z)",
        text,
        re.S,
    )
    parsed_final = []
    for block in final_blocks:
        elements, positions = _parse_geometry_lines(block)
        if elements:
            parsed_final.append((elements, positions))
    return parsed_final


def summarize_aop_text(text: str) -> dict[str, Any]:
    energy_match = re.findall(r"Final Energy:\s*([-+0-9.Ee]+)", text)
    if not energy_match:
        energy_match = re.findall(r"ETot =\s*([-+0-9.Ee]+)\s*Ekin", text)

    dipole_match = re.findall(
        r"Dipole moment \(.*?\):\s*X=\s*([-+0-9.Ee]+)\s*Y=\s*([-+0-9.Ee]+)\s*Z=\s*([-+0-9.Ee]+)\s*Tot=\s*([-+0-9.Ee]+)",
        text,
        re.S,
    )
    force_match = re.findall(
        r"Cartesian Force \(.*?\):\n\s*x\s*y\s*z\n(.*?)\n\s*\n",
        text,
        re.S,
    )
    geometry_series = _parse_geometry_series(text)
    final_geometry_blocks = re.findall(
        r"Final Geometry\(angstroms\):\s*\n(.*?)(?=\n\s*Final Energy:|\n\s*=+|\Z)",
        text,
        re.S,
    )

    forces_shape = None
    if force_match:
        rows = [line for line in force_match[-1].splitlines() if line.strip()]
        forces_shape = (len(rows), 3)

    final_atom_count = None
    if final_geometry_blocks:
        final_elements, _ = _parse_geometry_lines(final_geometry_blocks[-1])
        final_atom_count = len(final_elements)
    elif geometry_series:
        final_atom_count = len(geometry_series[-1][0])

    return {
        "terminated_normally": "Normal termination of Amesp!" in text,
        "energy_hartree": float(energy_match[-1]) if energy_match else None,
        "dipole_debye": tuple(float(value) for value in dipole_match[-1])
        if dipole_match
        else None,
        "forces_shape": forces_shape,
        "current_geometry_blocks": len(geometry_series),
        "final_atom_count": final_atom_count,
    }


def known_parser_diagnosis(exc: BaseException, summary: dict[str, Any]) -> str | None:
    if not isinstance(exc, (IndexError, ValueError)):
        return None
    if not summary.get("terminated_normally"):
        return None
    if summary.get("energy_hartree") is None:
        return None
    return (
        "Amesp execution completed and wrote usable output, but PyAmesp failed while "
        "parsing the .aop file. This is a PyAmesp compatibility problem, not an Amesp "
        "runtime failure."
    )


def _pad_or_trim_from_right(items: list[Any], n: int, fill_value: Any = None) -> list[Any]:
    if n <= 0:
        return []
    if not items:
        return [fill_value for _ in range(n)]
    if len(items) >= n:
        return items[-n:]
    return items + [items[-1] for _ in range(n - len(items))]


def patch_pyamesp() -> Any:
    module = importlib.import_module("PyAmesp.amesp")
    if getattr(module, "_aie_mas_compat_patched", False):
        return module

    np = module.np
    Atoms = module.Atoms
    Hartree = module.Hartree
    Bohr = module.Bohr
    re_mod = module.re

    def parse_aop_xyz(text: str):
        geometry_series = _parse_geometry_series(text)
        elements = [np.array(item[0]) for item in geometry_series]
        positions = [np.array(item[1], dtype=float) for item in geometry_series]
        return elements, positions

    def parse_aop_charge(text: str, n: int):
        pattern = r"\w+ charges:\n\s*\n(.*?)\n\s*Sum of \w+ charges"
        charge_array = re_mod.findall(pattern, text, re_mod.S)
        parsed = [
            np.array([line.split()[-1] for line in block.split("\n") if line.strip()], dtype=float)
            for block in charge_array
        ]
        return _pad_or_trim_from_right(parsed, n, None)

    def parse_aop_spin(text: str, n: int):
        pattern = r"Spin densities:\n\s*\n(.*?)\n\s*\n"
        spin_array = re_mod.findall(pattern, text, re_mod.S)
        parsed = [
            np.array([line.split()[-1] for line in block.split("\n") if line.strip()], dtype=float)
            for block in spin_array
        ]
        return _pad_or_trim_from_right(parsed, n, None)

    def parse_aop_dipole(text: str, n: int):
        pattern = r"Dipole moment \(.*?\):\n\s*X=\s*(.*?)\s*Y=\s*(.*?)\s*Z=\s*(.*?)\s*Tot="
        dipole = re_mod.findall(pattern, text, re_mod.S)
        parsed = [np.array(item, float) * Bohr for item in dipole]
        return _pad_or_trim_from_right(parsed, n, None)

    def parse_aop_energy(text: str, n: int):
        pattern = r"ETot =\s*(.*?)\s*Ekin"
        energy = re_mod.findall(pattern, text)
        parsed = [float(value) * Hartree for value in energy]
        return _pad_or_trim_from_right(parsed, n, None)

    def parse_aop_gradient(text: str, n: int):
        pattern = r"Cartesian Gradient \(.*?\):\n\s*x\s*y\s*z\n(.*?)\n\s*\n"
        blocks = re_mod.findall(pattern, text, re_mod.S)
        parsed = [
            np.array([line.split()[1:] for line in block.split("\n") if line.strip()], float)
            * Hartree
            / Bohr
            * (-1)
            for block in blocks
        ]
        return _pad_or_trim_from_right(parsed, n, None)

    def parse_aop_force(text: str):
        pattern = r"Cartesian Force \(.*?\):\n\s*x\s*y\s*z\n(.*?)\n\s*\n"
        blocks = re_mod.findall(pattern, text, re_mod.S)
        if blocks:
            block = blocks[-1]
            return (
                np.array([line.split()[1:] for line in block.split("\n") if line.strip()], float)
                * Hartree
                / Bohr
            )
        gradients = parse_aop_gradient(text, 1)
        return gradients[-1] if gradients else None

    def _last_or_none(values: list[Any]) -> Any:
        return values[-1] if values else None

    def read_results(self):
        with open(self.label + ".aop") as fd:
            text = fd.read()
        element, position = parse_aop_xyz(text)
        nimage = max(len(element), 1)
        charges = parse_aop_charge(text, nimage)
        magmoms = parse_aop_spin(text, nimage)
        dipoles = parse_aop_dipole(text, nimage)
        energies = parse_aop_energy(text, nimage)
        self.results["charges"] = _last_or_none(charges)
        self.results["charge"] = self.results["charges"]
        self.results["magmoms"] = _last_or_none(magmoms)
        self.results["dipole"] = _last_or_none(dipoles)
        self.results["energy"] = _last_or_none(energies)
        self.results["forces"] = parse_aop_force(text)

    @module.reader
    def iread_aop(fd):
        text = fd.read()
        element, position = parse_aop_xyz(text)
        nimage = len(element)
        charge = parse_aop_charge(text, nimage)
        magmom = parse_aop_spin(text, nimage)
        dipole = parse_aop_dipole(text, nimage)
        energy = parse_aop_energy(text, nimage)
        force = parse_aop_gradient(text, nimage)
        images = []
        for i in range(nimage):
            atoms = Atoms(element[i], position[i])
            amesp = module.Amesp(atoms=atoms)
            amesp.results = {
                "energy": energy[i] if i < len(energy) else None,
                "forces": force[i] if i < len(force) else None,
                "dipole": dipole[i] if i < len(dipole) else None,
                "charges": charge[i] if i < len(charge) else None,
                "magmoms": magmom[i] if i < len(magmom) else None,
            }
            atoms.calc = amesp
            images.append(atoms)
        return (image for image in images)

    def read_aop(fd, index: int = -1):
        atoms = list(iread_aop(fd))[index]
        return atoms

    module.parse_aop_xyz = parse_aop_xyz
    module.parse_aop_charge = parse_aop_charge
    module.parse_aop_spin = parse_aop_spin
    module.parse_aop_dipole = parse_aop_dipole
    module.parse_aop_energy = parse_aop_energy
    module.parse_aop_gradient = parse_aop_gradient
    module.parse_aop_force = parse_aop_force
    module.Amesp.read_results = read_results
    module.iread_aop = iread_aop
    module.read_aop = read_aop

    if "ASE_AMESP_COMMAND" in os.environ:
        module.Amesp.command = os.environ["ASE_AMESP_COMMAND"]
    elif "AMESP_COMMAND" in os.environ:
        module.Amesp.command = os.environ["AMESP_COMMAND"]

    module._aie_mas_compat_patched = True
    return module
