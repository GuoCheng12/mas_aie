from __future__ import annotations

import json
from pathlib import Path

import pytest

from aie_mas.chem.structure_prep import (
    PreparedStructure,
    StructurePrepError,
    StructurePrepRequest,
    prepare_structure_from_smiles,
    validate_closed_shell_support,
)


def test_structure_prep_error_exposes_code_and_message() -> None:
    error = StructurePrepError("invalid_smiles", "bad smiles")

    assert error.code == "invalid_smiles"
    assert error.message == "bad smiles"
    assert error.to_payload() == {"code": "invalid_smiles", "message": "bad smiles"}


def test_validate_closed_shell_support_allows_closed_shell_formal_charge() -> None:
    validate_closed_shell_support(formal_charge=1, radical_electrons=0)


def test_validate_closed_shell_support_rejects_radicals() -> None:
    with pytest.raises(StructurePrepError) as exc_info:
        validate_closed_shell_support(formal_charge=0, radical_electrons=1)

    assert exc_info.value.code == "unsupported_radical"


def test_prepared_structure_is_json_serializable(tmp_path: Path) -> None:
    prepared = PreparedStructure(
        input_smiles="C1=CCCCC1",
        canonical_smiles="C1=CCCCC1",
        charge=0,
        multiplicity=1,
        heavy_atom_count=6,
        atom_count=16,
        conformer_count=10,
        selected_conformer_id=3,
        force_field="MMFF94",
        xyz_path=tmp_path / "prepared_structure.xyz",
        sdf_path=tmp_path / "prepared_structure.sdf",
        summary_path=tmp_path / "structure_prep_summary.json",
    )

    payload = prepared.model_dump(mode="json")

    assert payload["canonical_smiles"] == "C1=CCCCC1"
    assert payload["force_field"] == "MMFF94"
    assert payload["xyz_path"].endswith("prepared_structure.xyz")


@pytest.mark.skipif(
    pytest.importorskip("rdkit", reason="RDKit is required for structure prep integration checks")
    is None,
    reason="unreachable",
)
def test_prepare_structure_from_smiles_generates_artifacts(tmp_path: Path) -> None:
    pytest.importorskip("ase", reason="ASE is required for structure prep integration checks")

    atoms, prepared = prepare_structure_from_smiles(
        StructurePrepRequest(
            smiles="C1=CCCCC1",
            label="cyclohexene",
            workdir=tmp_path,
        )
    )

    assert len(atoms) == prepared.atom_count
    assert prepared.charge == 0
    assert prepared.multiplicity == 1
    assert prepared.canonical_smiles
    assert prepared.conformer_count >= 1
    assert prepared.xyz_path.exists()
    assert prepared.sdf_path.exists()
    assert prepared.summary_path.exists()

    summary_payload = json.loads(prepared.summary_path.read_text(encoding="utf-8"))
    assert summary_payload["canonical_smiles"] == prepared.canonical_smiles
    assert summary_payload["charge"] == 0
    assert summary_payload["multiplicity"] == 1


@pytest.mark.skipif(
    pytest.importorskip("rdkit", reason="RDKit is required for structure prep integration checks")
    is None,
    reason="unreachable",
)
def test_prepare_structure_from_smiles_supports_closed_shell_cation(tmp_path: Path) -> None:
    pytest.importorskip("ase", reason="ASE is required for structure prep integration checks")

    atoms, prepared = prepare_structure_from_smiles(
        StructurePrepRequest(
            smiles="C[n+]1ccccc1",
            label="n_methyl_pyridinium",
            workdir=tmp_path,
        )
    )

    assert len(atoms) == prepared.atom_count
    assert prepared.charge == 1
    assert prepared.multiplicity == 1
    assert prepared.canonical_smiles
    assert prepared.conformer_count >= 1
    assert prepared.xyz_path.exists()
    assert prepared.sdf_path.exists()
    assert prepared.summary_path.exists()

    summary_payload = json.loads(prepared.summary_path.read_text(encoding="utf-8"))
    assert summary_payload["charge"] == 1
    assert summary_payload["multiplicity"] == 1


def test_prepare_structure_from_smiles_reports_missing_rdkit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "rdkit" or name.startswith("rdkit."):
            raise ModuleNotFoundError("No module named 'rdkit'")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(StructurePrepError) as exc_info:
        prepare_structure_from_smiles(
            StructurePrepRequest(
                smiles="C1=CCCCC1",
                label="cyclohexene",
                workdir=tmp_path,
            )
        )

    assert exc_info.value.code == "rdkit_unavailable"
