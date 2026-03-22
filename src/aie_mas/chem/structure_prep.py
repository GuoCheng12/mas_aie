from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:  # pragma: no cover
    from ase import Atoms

StructurePrepErrorCode = Literal[
    "rdkit_unavailable",
    "invalid_smiles",
    "unsupported_formal_charge",
    "unsupported_radical",
    "embedding_failed",
    "forcefield_failed",
]


class StructurePrepError(RuntimeError):
    def __init__(self, code: StructurePrepErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_payload(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


class StructurePrepRequest(BaseModel):
    smiles: str
    label: str
    workdir: Path
    num_conformers: int = 10
    max_force_field_steps: int = 200

    def model_post_init(self, __context: object) -> None:
        self.workdir = self.workdir.expanduser().resolve()


class PreparedStructure(BaseModel):
    input_smiles: str
    canonical_smiles: str
    charge: int
    multiplicity: int
    heavy_atom_count: int
    atom_count: int
    conformer_count: int
    selected_conformer_id: int
    force_field: Literal["MMFF94", "UFF"]
    xyz_path: Path
    sdf_path: Path
    summary_path: Path


def validate_closed_shell_support(formal_charge: int, radical_electrons: int) -> None:
    if formal_charge != 0:
        raise StructurePrepError(
            "unsupported_formal_charge",
            f"Only neutral closed-shell molecules are supported in the first version; got formal_charge={formal_charge}.",
        )
    if radical_electrons != 0:
        raise StructurePrepError(
            "unsupported_radical",
            "Only neutral closed-shell molecules are supported in the first version; radical electrons were detected.",
        )


def prepare_structure_from_smiles(
    request: StructurePrepRequest,
) -> tuple["Atoms", PreparedStructure]:
    rdkit = _import_rdkit()
    Chem = rdkit["Chem"]
    AllChem = rdkit["AllChem"]
    Atoms = _import_ase_atoms()

    request.workdir.mkdir(parents=True, exist_ok=True)

    base_mol = Chem.MolFromSmiles(request.smiles)
    if base_mol is None:
        raise StructurePrepError(
            "invalid_smiles",
            f"RDKit failed to parse the SMILES string: {request.smiles!r}.",
        )

    canonical_smiles = Chem.MolToSmiles(base_mol, canonical=True)
    mol = Chem.AddHs(base_mol)

    formal_charge = sum(atom.GetFormalCharge() for atom in mol.GetAtoms())
    radical_electrons = sum(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms())
    validate_closed_shell_support(formal_charge, radical_electrons)

    conformer_ids = _embed_conformers(AllChem, mol, request)
    force_field = _select_force_field(AllChem, mol)
    selected_conformer_id = _optimize_and_select_conformer(
        AllChem,
        mol,
        conformer_ids,
        force_field,
        request.max_force_field_steps,
    )

    xyz_path = request.workdir / "prepared_structure.xyz"
    sdf_path = request.workdir / "prepared_structure.sdf"
    summary_path = request.workdir / "structure_prep_summary.json"

    _write_xyz(mol, selected_conformer_id, xyz_path, request.label)
    _write_sdf(Chem, mol, selected_conformer_id, sdf_path)

    prepared = PreparedStructure(
        input_smiles=request.smiles,
        canonical_smiles=canonical_smiles,
        charge=formal_charge,
        multiplicity=1,
        heavy_atom_count=mol.GetNumHeavyAtoms(),
        atom_count=mol.GetNumAtoms(),
        conformer_count=len(conformer_ids),
        selected_conformer_id=selected_conformer_id,
        force_field=force_field,
        xyz_path=xyz_path,
        sdf_path=sdf_path,
        summary_path=summary_path,
    )
    summary_path.write_text(
        json.dumps(prepared.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conformer = mol.GetConformer(selected_conformer_id)
    atoms = Atoms(
        symbols=[atom.GetSymbol() for atom in mol.GetAtoms()],
        positions=conformer.GetPositions(),
    )
    return atoms, prepared


def _import_rdkit() -> dict[str, object]:
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ModuleNotFoundError as exc:
        raise StructurePrepError(
            "rdkit_unavailable",
            "RDKit is required for SMILES-to-3D preparation. On Linux install it with: conda install -c conda-forge rdkit",
        ) from exc
    return {"Chem": Chem, "AllChem": AllChem}


def _import_ase_atoms():
    from ase import Atoms

    return Atoms


def _embed_conformers(AllChem, mol, request: StructurePrepRequest) -> list[int]:
    params = AllChem.ETKDGv3()
    params.randomSeed = 0xA1E
    conformer_ids = list(AllChem.EmbedMultipleConfs(mol, numConfs=request.num_conformers, params=params))
    if conformer_ids:
        return conformer_ids

    retry_params = AllChem.ETKDGv3()
    retry_params.randomSeed = 0xA1E
    retry_params.useRandomCoords = True
    conformer_ids = list(
        AllChem.EmbedMultipleConfs(mol, numConfs=request.num_conformers, params=retry_params)
    )
    if conformer_ids:
        return conformer_ids

    raise StructurePrepError(
        "embedding_failed",
        f"RDKit failed to embed any 3D conformer for SMILES {request.smiles!r}.",
    )


def _select_force_field(AllChem, mol) -> Literal["MMFF94", "UFF"]:
    if AllChem.MMFFHasAllMoleculeParams(mol):
        return "MMFF94"
    if AllChem.UFFHasAllMoleculeParams(mol):
        return "UFF"
    raise StructurePrepError(
        "forcefield_failed",
        "Neither MMFF94 nor UFF parameters are available for this molecule.",
    )


def _optimize_and_select_conformer(
    AllChem,
    mol,
    conformer_ids: list[int],
    force_field: Literal["MMFF94", "UFF"],
    max_steps: int,
) -> int:
    best_conf_id: int | None = None
    best_energy: float | None = None

    mmff_props = None
    if force_field == "MMFF94":
        mmff_props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
        if mmff_props is None:
            raise StructurePrepError(
                "forcefield_failed",
                "MMFF94 parameters were expected but could not be constructed for this molecule.",
            )

    for conf_id in conformer_ids:
        if force_field == "MMFF94":
            forcefield = AllChem.MMFFGetMoleculeForceField(mol, mmff_props, confId=conf_id)
        else:
            forcefield = AllChem.UFFGetMoleculeForceField(mol, confId=conf_id)
        if forcefield is None:
            raise StructurePrepError(
                "forcefield_failed",
                f"Failed to build {force_field} force field for conformer {conf_id}.",
            )
        forcefield.Minimize(maxIts=max_steps)
        energy = float(forcefield.CalcEnergy())
        if best_energy is None or energy < best_energy:
            best_energy = energy
            best_conf_id = conf_id

    if best_conf_id is None:
        raise StructurePrepError(
            "forcefield_failed",
            f"{force_field} optimization did not produce any valid conformer energy.",
        )
    return best_conf_id


def _write_xyz(mol, conf_id: int, xyz_path: Path, label: str) -> None:
    conformer = mol.GetConformer(conf_id)
    lines = [str(mol.GetNumAtoms()), label]
    for atom_idx, atom in enumerate(mol.GetAtoms()):
        position = conformer.GetAtomPosition(atom_idx)
        lines.append(
            f"{atom.GetSymbol():<2} {position.x: .8f} {position.y: .8f} {position.z: .8f}"
        )
    xyz_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_sdf(Chem, mol, conf_id: int, sdf_path: Path) -> None:
    writer = Chem.SDWriter(str(sdf_path))
    try:
        writer.write(mol, confId=conf_id)
    finally:
        writer.close()
