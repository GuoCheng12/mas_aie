#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def configure_environment(root: Path) -> dict[str, str]:
    amesp_root = Path(
        os.environ.get("AIE_MAS_AMESP_ROOT", str(root / "third_party" / "Amesp"))
    ).resolve()
    pyamesp_root = Path(
        os.environ.get("AIE_MAS_PYAMESP_ROOT", str(root / "third_party" / "PyAmesp"))
    ).resolve()
    amesp_bin = Path(
        os.environ.get("AIE_MAS_AMESP_BIN", str(amesp_root / "Bin" / "amesp"))
    ).resolve()

    os.environ.setdefault("AIE_MAS_AMESP_ROOT", str(amesp_root))
    os.environ.setdefault("AIE_MAS_PYAMESP_ROOT", str(pyamesp_root))
    os.environ.setdefault("AIE_MAS_AMESP_BIN", str(amesp_bin))
    os.environ.setdefault("KMP_STACKSIZE", "4g")
    os.environ.setdefault("ASE_AMESP_COMMAND", f"{amesp_bin} PREFIX.aip PREFIX.aop")

    return {
        "project_root": str(root),
        "amesp_root": str(amesp_root),
        "pyamesp_root": str(pyamesp_root),
        "amesp_bin": str(amesp_bin),
        "ase_amesp_command": os.environ["ASE_AMESP_COMMAND"],
        "kmp_stacksize": os.environ["KMP_STACKSIZE"],
    }


def raise_stack_limit() -> str:
    try:
        import resource

        soft, hard = resource.getrlimit(resource.RLIMIT_STACK)
        target = hard if hard != resource.RLIM_INFINITY else resource.RLIM_INFINITY
        resource.setrlimit(resource.RLIMIT_STACK, (target, hard))
        return f"stack_limit: soft={soft} hard={hard} updated"
    except Exception as exc:  # pragma: no cover - platform dependent
        return f"stack_limit: unchanged ({type(exc).__name__}: {exc})"


def ensure_import_path(pyamesp_root: str) -> None:
    if pyamesp_root not in sys.path:
        sys.path.insert(0, pyamesp_root)


def parse_aop_summary(text: str) -> dict[str, Any]:
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
    current_geometries = re.findall(
        r"Current Geometry\(angstroms\):\n\s*x\s*y\s*z\n(.*?)\n\s*\n",
        text,
        re.S,
    )
    final_geometry_match = re.findall(
        r"Final Geometry\(angstroms\):\s*\n\s*\n\s*(\d+)\n(.*?)\n\s*Final Energy:",
        text,
        re.S,
    )

    forces_shape = None
    if force_match:
        rows = [line for line in force_match[-1].splitlines() if line.strip()]
        forces_shape = (len(rows), 3)

    final_atom_count = None
    if final_geometry_match:
        final_atom_count = int(final_geometry_match[-1][0])

    return {
        "terminated_normally": "Normal termination of Amesp!" in text,
        "energy_hartree": float(energy_match[-1]) if energy_match else None,
        "dipole_debye": tuple(float(value) for value in dipole_match[-1])
        if dipole_match
        else None,
        "forces_shape": forces_shape,
        "current_geometry_blocks": len(current_geometries),
        "final_atom_count": final_atom_count,
    }


def known_parser_diagnosis(exc: BaseException, summary: dict[str, Any]) -> str | None:
    if not isinstance(exc, IndexError):
        return None
    if not summary.get("terminated_normally"):
        return None
    if summary.get("current_geometry_blocks", 0) != 0:
        return None
    return (
        "Amesp execution completed, but PyAmesp.read_results() indexed an empty parsed "
        "image list. This indicates a parser mismatch for the current .aop layout, not "
        "an Amesp runtime failure."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Minimal PyAmesp smoke test.")
    parser.add_argument("--label", default="nh3_py")
    parser.add_argument("--molecule", default="NH3")
    parser.add_argument("--workdir", type=Path, default=None)
    parser.add_argument("--maxcore", type=int, default=512)
    parser.add_argument("--npara", type=int, default=2)
    parser.add_argument("--charge", type=int, default=0)
    parser.add_argument("--mult", type=int, default=1)
    parser.add_argument("--keywords", nargs="+", default=["hf", "3-21g", "force"])
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = project_root()
    env_info = configure_environment(root)
    ensure_import_path(env_info["pyamesp_root"])

    print(f"project_root: {env_info['project_root']}")
    print(f"amesp_bin: {env_info['amesp_bin']}")
    print(f"pyamesp_root: {env_info['pyamesp_root']}")
    print(f"ase_amesp_command: {env_info['ase_amesp_command']}")
    print(f"kmp_stacksize: {env_info['kmp_stacksize']}")
    print(raise_stack_limit())

    try:
        from ase.build import molecule
        from PyAmesp import Amesp
    except Exception as exc:
        print(f"import_status: failed ({type(exc).__name__}: {exc})")
        return 2

    workdir = args.workdir or (root / "var" / "runtime" / "pyamesp_smoke")
    workdir.mkdir(parents=True, exist_ok=True)
    os.chdir(workdir)
    print(f"workdir: {workdir}")

    atoms = molecule(args.molecule)
    calc = Amesp(
        atoms=atoms,
        label=args.label,
        maxcore=args.maxcore,
        npara=args.npara,
        charge=args.charge,
        mult=args.mult,
        keywords=args.keywords,
    )
    atoms.calc = calc

    standard_ok = False
    standard_error: BaseException | None = None
    energy_ev = None
    forces_shape = None

    try:
        energy_ev = atoms.get_potential_energy()
        forces_shape = atoms.get_forces().shape
        standard_ok = True
    except Exception as exc:
        standard_error = exc

    aip_path = workdir / f"{args.label}.aip"
    aop_path = workdir / f"{args.label}.aop"
    mo_path = workdir / f"{args.label}.mo"

    print(f"aip_exists: {aip_path.exists()}")
    print(f"aop_exists: {aop_path.exists()}")
    print(f"mo_exists: {mo_path.exists()}")

    if standard_ok:
        print("standard_calculator_status: ok")
        print(f"energy_eV: {energy_ev}")
        print(f"forces_shape: {forces_shape}")
        print(f"result_keys: {sorted(calc.results.keys())}")
        print(f"dipole: {calc.results.get('dipole')}")
        return 0

    print("standard_calculator_status: failed")
    assert standard_error is not None
    print(f"exception_type: {type(standard_error).__name__}")
    print(f"exception_message: {standard_error}")

    if not aop_path.exists():
        return 2

    summary = parse_aop_summary(aop_path.read_text(encoding="utf-8", errors="replace"))
    print(f"terminated_normally: {summary['terminated_normally']}")
    print(f"energy_hartree: {summary['energy_hartree']}")
    print(f"dipole_debye: {summary['dipole_debye']}")
    print(f"forces_shape_from_aop: {summary['forces_shape']}")
    print(f"current_geometry_blocks: {summary['current_geometry_blocks']}")
    print(f"final_atom_count: {summary['final_atom_count']}")

    diagnosis = known_parser_diagnosis(standard_error, summary)
    if diagnosis:
        print(f"diagnosis: {diagnosis}")
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
