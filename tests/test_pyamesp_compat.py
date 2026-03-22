from __future__ import annotations

from aie_mas.compat.pyamesp import (
    _parse_geometry_series,
    known_parser_diagnosis,
    summarize_aop_text,
)


def test_summarize_aop_text_extracts_core_fields() -> None:
    text = """
Current Geometry(angstroms):
                    x               y               z
 O              0.0000000       0.0000000       0.0000000
 H              0.0000000       0.0000000       0.9600000

 ----------------------------------------------------------------

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
    summary = summarize_aop_text(text)

    assert summary["terminated_normally"] is True
    assert summary["energy_hartree"] == -75.3100135471
    assert summary["dipole_debye"] == (1.3446, -0.0, 0.9502, 1.6464)
    assert summary["forces_shape"] == (2, 3)
    assert summary["current_geometry_blocks"] == 1
    assert summary["final_atom_count"] == 3


def test_parse_geometry_series_falls_back_to_final_geometry() -> None:
    text = """
Final Geometry(angstroms):

  2
  H            0.00000000    0.00000000    0.00000000
  H            0.00000000    0.00000000    0.74000000

 Final Energy:      -1.1000000000
"""
    geometry_series = _parse_geometry_series(text)

    assert len(geometry_series) == 1
    assert geometry_series[0][0] == ["H", "H"]
    assert geometry_series[0][1][1] == [0.0, 0.0, 0.74]


def test_known_parser_diagnosis_detects_parser_failure_after_normal_termination() -> None:
    diagnosis = known_parser_diagnosis(
        IndexError("list index out of range"),
        {
            "terminated_normally": True,
            "energy_hartree": -55.87,
        },
    )

    assert diagnosis is not None
    assert "compatibility problem" in diagnosis
