from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "pyamesp_smoke.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("pyamesp_smoke", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_aop_summary_extracts_core_fields() -> None:
    module = _load_module()
    text = """
Current Geometry(angstroms):
                    x               y               z
 O              0.0000000       0.0000000       0.0000000
 H              0.0000000       0.0000000       0.9600000

 ETot =      -75.310013547          Ekin =      74.587633672

 Dipole moment (field-independent basis, Debye):
   X=     1.3446    Y=    -0.0000    Z=     0.9502    Tot=     1.6464

 Cartesian Force (Hartree/Bohr):
                    x               y               z
  O             -0.0000001       0.0000002       0.0000003
  H              0.0000004      -0.0000005       0.0000006

 Final Geometry(angstroms):

  3
  O            0.00000000    0.00000000    0.00000000
  H            0.00000000    0.00000000    0.96000000
  H            0.90493583    0.00000000   -0.32045458

 Final Energy:      -75.3100135471
 Normal termination of Amesp!
"""
    summary = module.parse_aop_summary(text)

    assert summary["terminated_normally"] is True
    assert summary["energy_hartree"] == -75.3100135471
    assert summary["dipole_debye"] == (1.3446, -0.0, 0.9502, 1.6464)
    assert summary["forces_shape"] == (2, 3)
    assert summary["current_geometry_blocks"] == 1
    assert summary["final_atom_count"] == 3


def test_known_parser_diagnosis_detects_zero_image_case() -> None:
    module = _load_module()

    diagnosis = module.known_parser_diagnosis(
        IndexError("list index out of range"),
        {
            "terminated_normally": True,
            "current_geometry_blocks": 0,
        },
    )

    assert diagnosis is not None
    assert "parser mismatch" in diagnosis
