from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from aie_mas.chem.structure_prep import (
    PreparedStructure,
    StructurePrepRequest,
    prepare_structure_from_smiles,
)
from aie_mas.graph.state import MoleculeIdentityContext, SharedStructureContext

if TYPE_CHECKING:  # pragma: no cover
    from ase import Atoms


class SharedStructurePrepTool:
    name = "shared_structure_prep"

    def __init__(
        self,
        *,
        structure_preparer: Callable[[StructurePrepRequest], tuple["Atoms", PreparedStructure]] = prepare_structure_from_smiles,
    ) -> None:
        self._structure_preparer = structure_preparer

    def invoke(
        self,
        *,
        smiles: str,
        label: str,
        workdir: Path,
    ) -> dict[str, object]:
        atoms, prepared = self._structure_preparer(
            StructurePrepRequest(
                smiles=smiles,
                label=label,
                workdir=workdir,
            )
        )
        descriptors = _compute_shared_descriptors(smiles=smiles, atoms=atoms, prepared=prepared)
        shared_context = SharedStructureContext(
            input_smiles=prepared.input_smiles,
            canonical_smiles=prepared.canonical_smiles,
            charge=prepared.charge,
            multiplicity=prepared.multiplicity,
            atom_count=prepared.atom_count,
            conformer_count=prepared.conformer_count,
            selected_conformer_id=prepared.selected_conformer_id,
            prepared_xyz_path=str(prepared.xyz_path),
            prepared_sdf_path=str(prepared.sdf_path),
            summary_path=str(prepared.summary_path),
            **descriptors,
        )
        identity_context, identity_status, identity_error = _compute_identity_context(
            smiles=smiles,
            prepared=prepared,
        )
        return {
            "shared_structure_context": shared_context,
            "molecule_identity_context": identity_context,
            "molecule_identity_status": identity_status,
            "molecule_identity_error": identity_error,
        }


def _compute_shared_descriptors(
    *,
    smiles: str,
    atoms: "Atoms",
    prepared: PreparedStructure,
) -> dict[str, float | int]:
    rdkit = _import_rdkit()
    Chem = rdkit["Chem"]
    Lipinski = rdkit["Lipinski"]
    rdMolDescriptors = rdkit["rdMolDescriptors"]

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Failed to parse SMILES during shared descriptor computation: {smiles!r}")

    ring_sets = [set(ring) for ring in Chem.GetSymmSSSR(mol)]
    aromatic_ring_count = sum(
        1 for ring in ring_sets if all(mol.GetAtomWithIdx(atom_idx).GetIsAromatic() for atom_idx in ring)
    )
    branch_point_count = sum(1 for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1 and atom.GetDegree() >= 3)
    hetero_atom_count = sum(
        1
        for atom in mol.GetAtoms()
        if atom.GetAtomicNum() > 1 and atom.GetAtomicNum() != 6
    )
    rotatable_bond_count = _call_descriptor(
        mol,
        modules=(rdMolDescriptors, Lipinski),
        names=("CalcNumRotatableBonds", "NumRotatableBonds"),
    )
    donor_count = _call_descriptor(
        mol,
        modules=(rdMolDescriptors, Lipinski),
        names=("CalcNumHBD", "NumHDonors"),
    )
    acceptor_count = _call_descriptor(
        mol,
        modules=(rdMolDescriptors, Lipinski),
        names=("CalcNumHBA", "NumHAcceptors"),
    )

    import numpy as np

    coordinates = np.asarray(atoms.get_positions().tolist(), dtype=float)
    if coordinates.size == 0:
        planarity_proxy = 0.0
        compactness_proxy = 0.0
        principal_span_proxy = 0.0
    else:
        centered = coordinates - coordinates.mean(axis=0)
        covariance = np.cov(centered.T) if len(centered) > 1 else np.zeros((3, 3))
        eigenvalues = np.sort(np.linalg.eigvalsh(covariance))
        total_variance = float(max(eigenvalues.sum(), 1e-9))
        planarity_proxy = round(max(0.0, min(1.0, 1.0 - float(eigenvalues[0]) / total_variance)), 6)

        _, singular_values, _ = np.linalg.svd(centered, full_matrices=False)
        span = float(max(singular_values) * 2.0) if singular_values.size else 0.0
        principal_span_proxy = round(span, 6)

        radii = np.linalg.norm(centered, axis=1)
        mean_radius = float(radii.mean()) if radii.size else 0.0
        compactness_proxy = round(
            max(0.0, min(1.0, 1.0 - (mean_radius / max(span, 1e-9)))),
            6,
        )

    return {
        "rotatable_bond_count": rotatable_bond_count,
        "aromatic_ring_count": aromatic_ring_count,
        "ring_system_count": _count_ring_systems(ring_sets),
        "hetero_atom_count": hetero_atom_count,
        "branch_point_count": branch_point_count,
        "donor_acceptor_partition_proxy": round(
            min(1.0, 0.5 * int(donor_count > 0) + 0.5 * int(acceptor_count > 0)),
            6,
        ),
        "planarity_proxy": planarity_proxy,
        "compactness_proxy": compactness_proxy,
        "torsion_candidate_count": rotatable_bond_count,
        "principal_span_proxy": principal_span_proxy,
        "conformer_dispersion_proxy": round(
            min(1.0, math.log1p(prepared.conformer_count) / math.log(11.0)),
            6,
        ),
    }


def _count_ring_systems(ring_sets: list[set[int]]) -> int:
    if not ring_sets:
        return 0
    remaining = [set(ring) for ring in ring_sets]
    ring_systems = 0
    while remaining:
        seed = remaining.pop()
        merged = True
        while merged:
            merged = False
            next_remaining: list[set[int]] = []
            for ring in remaining:
                if seed & ring:
                    seed |= ring
                    merged = True
                else:
                    next_remaining.append(ring)
            remaining = next_remaining
        ring_systems += 1
    return ring_systems


def _call_descriptor(
    mol,
    *,
    modules: tuple[object, ...],
    names: tuple[str, ...],
) -> int:
    for module in modules:
        for name in names:
            func = getattr(module, name, None)
            if callable(func):
                return int(func(mol))
    raise AttributeError(
        f"RDKit descriptor function not found for candidates {', '.join(names)}."
    )


def _import_rdkit() -> dict[str, object]:
    from rdkit import Chem
    from rdkit.Chem import Lipinski
    from rdkit.Chem import rdMolDescriptors

    inchi_module = None
    try:
        from rdkit.Chem import inchi as rdkit_inchi

        inchi_module = rdkit_inchi
    except Exception:  # pragma: no cover - depends on RDKit build
        inchi_module = None

    return {
        "Chem": Chem,
        "Lipinski": Lipinski,
        "rdMolDescriptors": rdMolDescriptors,
        "inchi": inchi_module,
    }


def _compute_identity_context(
    *,
    smiles: str,
    prepared: PreparedStructure,
) -> tuple[MoleculeIdentityContext, str, dict[str, str] | None]:
    rdkit = _import_rdkit()
    Chem = rdkit["Chem"]
    rdMolDescriptors = rdkit["rdMolDescriptors"]
    inchi_module = rdkit["inchi"]

    base_mol = Chem.MolFromSmiles(smiles)
    if base_mol is None:
        return (
            MoleculeIdentityContext(input_smiles=smiles),
            "failed",
            {
                "code": "identity_invalid_smiles",
                "message": f"Failed to parse SMILES during identity generation: {smiles!r}",
            },
        )

    canonical_smiles = prepared.canonical_smiles or Chem.MolToSmiles(base_mol, canonical=True)
    formula = None
    inchi = None
    inchikey = None
    errors: list[str] = []

    try:
        formula = str(rdMolDescriptors.CalcMolFormula(base_mol))
    except Exception as exc:  # pragma: no cover - defensive
        errors.append(f"molecular_formula: {exc}")

    if inchi_module is not None:
        try:
            inchi = str(inchi_module.MolToInchi(base_mol))
        except Exception as exc:  # pragma: no cover - depends on RDKit build
            errors.append(f"inchi: {exc}")
        if inchi:
            try:
                inchikey = str(inchi_module.InchiToInchiKey(inchi))
            except Exception as exc:  # pragma: no cover - depends on RDKit build
                errors.append(f"inchikey: {exc}")
    else:
        errors.append("inchi: RDKit InChI module unavailable")

    context = MoleculeIdentityContext(
        input_smiles=smiles,
        canonical_smiles=canonical_smiles,
        molecular_formula=formula,
        inchi=inchi,
        inchikey=inchikey,
    )
    if formula and inchi and inchikey:
        return context, "ready", None
    if any([formula, inchi, inchikey, canonical_smiles]):
        return (
            context,
            "partial",
            {
                "code": "identity_partial",
                "message": "; ".join(errors) if errors else "Identity context is only partially available.",
            },
        )
    return (
        context,
        "failed",
        {
            "code": "identity_generation_failed",
            "message": "; ".join(errors) if errors else "Identity context could not be generated.",
        },
    )
