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
    StructurePrepError,
    StructurePrepRequest,
    prepare_conformer_bundle_from_smiles,
    prepare_structure_from_smiles,
)
from aie_mas.graph.state import (
    ArtifactBundle,
    ArtifactBundleCompletionStatus,
    ArtifactBundleDescriptor,
    ArtifactBundleKind,
    ArtifactBundleRegistryEntry,
    ConformerDescriptor,
    DihedralBondType,
    DihedralDescriptor,
    MicroscopicCapabilityName,
    MicroscopicExecutionPlan,
    MicroscopicToolCall,
    MicroscopicToolPlan,
    MicroscopicToolRequest,
    SelectionPolicy,
    WorkflowProgressEvent,
)

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
    dominant_transitions: list[dict[str, Any]] = Field(default_factory=list)


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


class AmespCapabilityDefinition(BaseModel):
    name: MicroscopicCapabilityName
    purpose: str
    requires_new_calculation: bool
    required_inputs: list[str] = Field(default_factory=list)
    optional_inputs: list[str] = Field(default_factory=list)
    supported_deliverables: list[str] = Field(default_factory=list)
    unsupported_requests_note: Optional[str] = None
    default_budget_behavior: str


AmespActionKind = Literal["discovery", "execution"]
AmespActionParamType = Literal[
    "bool",
    "int",
    "float_list",
    "int_list",
    "text",
    "text_list",
    "bond_type_list",
    "min_relevance",
    "artifact_kind",
    "source_round_selector",
    "dihedral_id",
    "conformer_id",
    "conformer_ids",
    "artifact_bundle_id",
]


class AmespActionParameterDefinition(BaseModel):
    name: str
    param_type: AmespActionParamType
    description: str
    required: bool = False
    enum_values: list[str] = Field(default_factory=list)
    default: Any = None


class AmespActionDefinition(BaseModel):
    action_name: MicroscopicCapabilityName
    action_kind: AmespActionKind
    purpose: str
    allowed_llm_params: list[str] = Field(default_factory=list)
    python_owned_params: list[str] = Field(default_factory=list)
    required_params: list[str] = Field(default_factory=list)
    param_types: dict[str, AmespActionParameterDefinition] = Field(default_factory=dict)
    defaults: dict[str, Any] = Field(default_factory=dict)
    allowed_discovery_actions: list[MicroscopicCapabilityName] = Field(default_factory=list)
    default_deliverables: list[str] = Field(default_factory=list)
    unsupported_note: Optional[str] = None


class AmespBaselineRunResult(BaseModel):
    route: str = "baseline_bundle"
    executed_capability: MicroscopicCapabilityName = "run_baseline_bundle"
    performed_new_calculations: bool = True
    reused_existing_artifacts: bool = False
    requested_capability: Optional[MicroscopicCapabilityName] = None
    resolved_target_ids: dict[str, Any] = Field(default_factory=dict)
    honored_constraints: list[str] = Field(default_factory=list)
    unmet_constraints: list[str] = Field(default_factory=list)
    missing_deliverables: list[str] = Field(default_factory=list)
    structure: PreparedStructure
    s0: Optional[AmespGroundStateResult] = None
    s1: Optional[AmespExcitedStateResult] = None
    parsed_snapshot_records: list[dict[str, Any]] = Field(default_factory=list)
    route_records: list[dict[str, Any]] = Field(default_factory=list)
    route_summary: dict[str, Any] = Field(default_factory=dict)
    raw_step_results: dict[str, Any] = Field(default_factory=dict)
    generated_artifacts: dict[str, Any] = Field(default_factory=dict)


AMESP_CAPABILITY_REGISTRY: dict[MicroscopicCapabilityName, AmespCapabilityDefinition] = {
    "list_rotatable_dihedrals": AmespCapabilityDefinition(
        name="list_rotatable_dihedrals",
        purpose="List reusable rotatable dihedrals and expose stable dihedral IDs for later execution.",
        requires_new_calculation=False,
        required_inputs=["prepared structure or reusable structure artifacts"],
        optional_inputs=["structure_source", "min_relevance", "include_peripheral"],
        supported_deliverables=["stable dihedral descriptors"],
        default_budget_behavior="Never launches new Amesp calculations; discovery only.",
    ),
    "list_available_conformers": AmespCapabilityDefinition(
        name="list_available_conformers",
        purpose="List reusable conformers and expose stable conformer IDs for later execution.",
        requires_new_calculation=False,
        required_inputs=["available prepared structure or conformer artifacts"],
        optional_inputs=["source_round_preference"],
        supported_deliverables=["stable conformer descriptors"],
        default_budget_behavior="Never launches new Amesp calculations; discovery only.",
    ),
    "list_artifact_bundles": AmespCapabilityDefinition(
        name="list_artifact_bundles",
        purpose="List reusable microscopic artifact bundles and expose stable artifact bundle IDs for parse-only reuse.",
        requires_new_calculation=False,
        required_inputs=["available microscopic artifacts"],
        optional_inputs=["artifact_kind", "source_round_preference"],
        supported_deliverables=["artifact bundle descriptors"],
        default_budget_behavior="Never launches new Amesp calculations; discovery only.",
    ),
    "run_baseline_bundle": AmespCapabilityDefinition(
        name="run_baseline_bundle",
        purpose="Run a single-conformer low-cost S0 optimization plus vertical excited-state manifold.",
        requires_new_calculation=True,
        required_inputs=["prepared structure or SMILES"],
        optional_inputs=["state_window", "optimize_ground_state"],
        supported_deliverables=[
            "S0 optimized geometry",
            "S0 final energy",
            "S0 dipole",
            "S0 Mulliken charges",
            "S0 HOMO-LUMO gap",
            "vertical excited-state manifold",
        ],
        default_budget_behavior="Use the configured balanced vertical-state count for first-round baseline execution.",
    ),
    "run_conformer_bundle": AmespCapabilityDefinition(
        name="run_conformer_bundle",
        purpose="Run a bounded conformer bundle follow-up with the same low-cost S0 plus vertical excited-state workflow.",
        requires_new_calculation=True,
        required_inputs=["SMILES or reusable prepared structure"],
        optional_inputs=["snapshot_count", "state_window", "optimize_ground_state"],
        supported_deliverables=[
            "bounded conformer vertical-state records",
            "excitation spread",
            "bright-state sensitivity",
        ],
        default_budget_behavior="Use configured follow-up conformer cap unless the request explicitly supplies a smaller count.",
    ),
    "run_torsion_snapshots": AmespCapabilityDefinition(
        name="run_torsion_snapshots",
        purpose="Run bounded torsion snapshot calculations from a prepared structure.",
        requires_new_calculation=True,
        required_inputs=["prepared structure or reusable structure artifacts"],
        optional_inputs=["snapshot_count", "angle_offsets_deg", "state_window", "optimize_ground_state"],
        supported_deliverables=[
            "snapshot vertical-state records",
            "torsion sensitivity summary",
        ],
        default_budget_behavior="Use configured torsion snapshot cap unless the request explicitly supplies a smaller count or angle set.",
    ),
    "parse_snapshot_outputs": AmespCapabilityDefinition(
        name="parse_snapshot_outputs",
        purpose="Parse existing snapshot artifacts and return per-snapshot excited-state summaries without new calculations.",
        requires_new_calculation=False,
        required_inputs=["existing snapshot artifacts"],
        optional_inputs=["artifact_source_round", "artifact_scope", "state_window"],
        supported_deliverables=[
            "per-snapshot excitation energies",
            "per-snapshot oscillator strengths",
            "state-ordering summaries",
        ],
        unsupported_requests_note="Dominant transition and CT/localization proxy extraction may be unavailable from existing files.",
        default_budget_behavior="Reuse only the latest available microscopic snapshot artifacts and never generate new inputs.",
    ),
    "extract_ct_descriptors_from_bundle": AmespCapabilityDefinition(
        name="extract_ct_descriptors_from_bundle",
        purpose="Inspect a reusable artifact bundle and extract bounded CT-descriptor surrogates without launching new calculations.",
        requires_new_calculation=False,
        required_inputs=["existing microscopic artifact bundle"],
        optional_inputs=["artifact_source_round", "artifact_scope", "artifact_bundle_id", "state_window", "descriptor_scope"],
        supported_deliverables=[
            "CT-descriptor availability summary",
            "bounded CT descriptor records",
            "artifact-backed CT surrogate summary",
        ],
        unsupported_requests_note="Some requested CT descriptors may remain unavailable even when raw Amesp artifacts exist.",
        default_budget_behavior="Reuse only existing artifact bundles and return partial observables when raw-file coverage is insufficient.",
    ),
    "extract_geometry_descriptors_from_bundle": AmespCapabilityDefinition(
        name="extract_geometry_descriptors_from_bundle",
        purpose="Inspect a reusable artifact bundle and extract bounded intramolecular geometry descriptors without launching new calculations.",
        requires_new_calculation=False,
        required_inputs=["existing microscopic artifact bundle"],
        optional_inputs=["artifact_source_round", "artifact_scope", "artifact_bundle_id", "descriptor_scope"],
        supported_deliverables=[
            "geometry-descriptor availability summary",
            "bounded geometry descriptor records",
            "artifact-backed geometry summary",
        ],
        unsupported_requests_note="Geometry extraction is limited to descriptors measurable from reusable optimized or prepared coordinates already present in the artifact bundle.",
        default_budget_behavior="Reuse only existing artifact bundles and return partial observables when coordinate coverage is insufficient.",
    ),
    "inspect_raw_artifact_bundle": AmespCapabilityDefinition(
        name="inspect_raw_artifact_bundle",
        purpose="Inspect a reusable artifact bundle and report which raw Amesp files and observable families are available.",
        requires_new_calculation=False,
        required_inputs=["existing microscopic artifact bundle"],
        optional_inputs=["artifact_source_round", "artifact_scope", "artifact_bundle_id", "requested_observable_scope"],
        supported_deliverables=[
            "raw artifact file inventory",
            "extractable observable inventory",
            "raw inspection notes",
        ],
        unsupported_requests_note="Raw-file inspection reports file coverage and extractable observable families; it does not by itself guarantee complete descriptor extraction.",
        default_budget_behavior="Reuse only existing artifact bundles and never launch new calculations.",
    ),
    "unsupported_excited_state_relaxation": AmespCapabilityDefinition(
        name="unsupported_excited_state_relaxation",
        purpose="Return a structured capability-unsupported result for excited-state relaxation requests.",
        requires_new_calculation=False,
        required_inputs=[],
        optional_inputs=[],
        supported_deliverables=[],
        unsupported_requests_note="Low-cost excited-state relaxation has not been validated for Amesp yet.",
        default_budget_behavior="Do not execute; fail fast with capability_unsupported.",
    ),
}


def _action_param(
    name: str,
    param_type: AmespActionParamType,
    description: str,
    *,
    required: bool = False,
    enum_values: Optional[list[str]] = None,
    default: Any = None,
) -> AmespActionParameterDefinition:
    return AmespActionParameterDefinition(
        name=name,
        param_type=param_type,
        description=description,
        required=required,
        enum_values=list(enum_values or []),
        default=default,
    )


_DEFAULT_PYTHON_OWNED_ACTION_PARAMS = [
    "capability_route",
    "structure_source",
    "structure_strategy",
    "source_round_preference",
    "resolved_target_ids",
]


AMESP_ACTION_REGISTRY: dict[MicroscopicCapabilityName, AmespActionDefinition] = {
    "list_rotatable_dihedrals": AmespActionDefinition(
        action_name="list_rotatable_dihedrals",
        action_kind="discovery",
        purpose="Discover stable rotatable-dihedral IDs before bounded torsion execution.",
        allowed_llm_params=["min_relevance", "include_peripheral", "preferred_bond_types"],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "min_relevance": _action_param(
                "min_relevance",
                "min_relevance",
                "Requested relevance bucket for dihedral discovery.",
                enum_values=["high", "medium", "low"],
            ),
            "include_peripheral": _action_param(
                "include_peripheral",
                "bool",
                "Whether peripheral dihedrals may be included in discovery results.",
                default=False,
            ),
            "preferred_bond_types": _action_param(
                "preferred_bond_types",
                "bond_type_list",
                "Preferred bond-type classes for dihedral selection.",
                enum_values=["aryl-aryl", "aryl-vinyl", "heteroaryl-linkage", "other"],
            ),
        },
        defaults={"include_peripheral": False},
    ),
    "list_available_conformers": AmespActionDefinition(
        action_name="list_available_conformers",
        action_kind="discovery",
        purpose="Discover stable conformer IDs before bounded conformer execution.",
        allowed_llm_params=["source_round_selector"],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested artifact round selector for conformer reuse.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
        },
        defaults={"source_round_selector": "latest_available"},
    ),
    "list_artifact_bundles": AmespActionDefinition(
        action_name="list_artifact_bundles",
        action_kind="discovery",
        purpose="Discover canonical reusable microscopic artifact bundles before parse-only execution.",
        allowed_llm_params=["artifact_kind", "source_round_selector"],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "artifact_kind": _action_param(
                "artifact_kind",
                "artifact_kind",
                "Requested artifact bundle kind.",
                enum_values=["baseline_bundle", "torsion_snapshots", "conformer_bundle"],
            ),
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested artifact round selector.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
        },
        defaults={"source_round_selector": "latest_available"},
    ),
    "run_baseline_bundle": AmespActionDefinition(
        action_name="run_baseline_bundle",
        action_kind="execution",
        purpose="Run a low-cost baseline S0 optimization plus vertical excited-state manifold.",
        allowed_llm_params=["perform_new_calculation", "optimize_ground_state", "reuse_existing_artifacts_only", "state_window"],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "perform_new_calculation": _action_param(
                "perform_new_calculation",
                "bool",
                "Whether to launch a new baseline calculation.",
                default=True,
            ),
            "optimize_ground_state": _action_param(
                "optimize_ground_state",
                "bool",
                "Whether to perform the low-cost S0 optimization before vertical excitations.",
                default=True,
            ),
            "reuse_existing_artifacts_only": _action_param(
                "reuse_existing_artifacts_only",
                "bool",
                "Whether only reusable artifacts may be used.",
                default=False,
            ),
            "state_window": _action_param(
                "state_window",
                "int_list",
                "Requested vertical-state window.",
            ),
        },
        defaults={
            "perform_new_calculation": True,
            "optimize_ground_state": True,
            "reuse_existing_artifacts_only": False,
        },
        default_deliverables=[
            "low-cost aTB S0 geometry optimization",
            "vertical excited-state manifold characterization",
        ],
    ),
    "run_conformer_bundle": AmespActionDefinition(
        action_name="run_conformer_bundle",
        action_kind="execution",
        purpose="Run a bounded conformer bundle follow-up.",
        allowed_llm_params=[
            "perform_new_calculation",
            "optimize_ground_state",
            "reuse_existing_artifacts_only",
            "snapshot_count",
            "max_conformers",
            "state_window",
            "honor_exact_target",
            "allow_fallback",
            "conformer_id",
            "conformer_ids",
            "source_round_selector",
        ],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "perform_new_calculation": _action_param("perform_new_calculation", "bool", "Whether to launch new conformer calculations.", default=True),
            "optimize_ground_state": _action_param("optimize_ground_state", "bool", "Whether to optimize each conformer at S0.", default=True),
            "reuse_existing_artifacts_only": _action_param("reuse_existing_artifacts_only", "bool", "Whether to reuse only existing artifacts.", default=False),
            "snapshot_count": _action_param("snapshot_count", "int", "Requested bounded conformer count."),
            "max_conformers": _action_param("max_conformers", "int", "Maximum conformer count for the bounded bundle."),
            "state_window": _action_param("state_window", "int_list", "Requested vertical-state window."),
            "honor_exact_target": _action_param("honor_exact_target", "bool", "Whether the exact conformer target must be honored.", default=True),
            "allow_fallback": _action_param("allow_fallback", "bool", "Whether bounded fallback is permitted.", default=False),
            "conformer_id": _action_param("conformer_id", "conformer_id", "Explicit stable conformer target ID."),
            "conformer_ids": _action_param("conformer_ids", "conformer_ids", "Explicit stable conformer target IDs."),
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested artifact round selector for conformer reuse.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
        },
        defaults={
            "perform_new_calculation": True,
            "optimize_ground_state": True,
            "reuse_existing_artifacts_only": False,
            "honor_exact_target": True,
            "allow_fallback": False,
            "source_round_selector": "latest_available",
        },
        allowed_discovery_actions=["list_available_conformers"],
        default_deliverables=[
            "bounded conformer vertical-state records",
            "conformer-sensitivity summary",
        ],
    ),
    "run_torsion_snapshots": AmespActionDefinition(
        action_name="run_torsion_snapshots",
        action_kind="execution",
        purpose="Run bounded torsion snapshots and vertical excitations from a prepared structure.",
        allowed_llm_params=[
            "perform_new_calculation",
            "optimize_ground_state",
            "reuse_existing_artifacts_only",
            "snapshot_count",
            "angle_offsets_deg",
            "state_window",
            "honor_exact_target",
            "allow_fallback",
            "dihedral_id",
            "exclude_dihedral_ids",
            "prefer_adjacent_to_nsnc_core",
            "min_relevance",
            "include_peripheral",
            "preferred_bond_types",
            "source_round_selector",
        ],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "perform_new_calculation": _action_param("perform_new_calculation", "bool", "Whether to launch new torsion snapshot calculations.", default=True),
            "optimize_ground_state": _action_param("optimize_ground_state", "bool", "Whether to re-optimize the ground state for each snapshot.", default=False),
            "reuse_existing_artifacts_only": _action_param("reuse_existing_artifacts_only", "bool", "Whether only reusable artifacts may be used.", default=False),
            "snapshot_count": _action_param("snapshot_count", "int", "Requested bounded snapshot count."),
            "angle_offsets_deg": _action_param("angle_offsets_deg", "float_list", "Requested torsion-angle offsets in degrees."),
            "state_window": _action_param("state_window", "int_list", "Requested vertical-state window."),
            "honor_exact_target": _action_param("honor_exact_target", "bool", "Whether the exact dihedral target must be honored.", default=True),
            "allow_fallback": _action_param("allow_fallback", "bool", "Whether bounded fallback is permitted.", default=False),
            "dihedral_id": _action_param("dihedral_id", "dihedral_id", "Explicit stable dihedral target ID."),
            "exclude_dihedral_ids": _action_param("exclude_dihedral_ids", "text_list", "Dihedral IDs that must be excluded from selection."),
            "prefer_adjacent_to_nsnc_core": _action_param("prefer_adjacent_to_nsnc_core", "bool", "Prefer torsions adjacent to the NSNC core.", default=None),
            "min_relevance": _action_param("min_relevance", "min_relevance", "Requested relevance bucket for dihedral selection.", enum_values=["high", "medium", "low"]),
            "include_peripheral": _action_param("include_peripheral", "bool", "Whether peripheral dihedrals may be considered.", default=False),
            "preferred_bond_types": _action_param("preferred_bond_types", "bond_type_list", "Preferred bond-type classes for torsion selection.", enum_values=["aryl-aryl", "aryl-vinyl", "heteroaryl-linkage", "other"]),
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested source round selector for reusable optimized geometries.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
        },
        defaults={
            "perform_new_calculation": True,
            "optimize_ground_state": False,
            "reuse_existing_artifacts_only": False,
            "honor_exact_target": True,
            "allow_fallback": False,
            "include_peripheral": False,
            "source_round_selector": "latest_available",
        },
        allowed_discovery_actions=["list_rotatable_dihedrals"],
        default_deliverables=[
            "snapshot vertical-state records",
            "torsion sensitivity summary",
        ],
    ),
    "parse_snapshot_outputs": AmespActionDefinition(
        action_name="parse_snapshot_outputs",
        action_kind="execution",
        purpose="Parse existing snapshot artifacts without launching new calculations.",
        allowed_llm_params=[
            "perform_new_calculation",
            "reuse_existing_artifacts_only",
            "artifact_kind",
            "artifact_bundle_id",
            "source_round_selector",
            "state_window",
        ],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "perform_new_calculation": _action_param("perform_new_calculation", "bool", "Whether to launch new calculations. Must remain false for parse-only reuse.", default=False),
            "reuse_existing_artifacts_only": _action_param("reuse_existing_artifacts_only", "bool", "Whether only reusable artifacts may be used.", default=True),
            "artifact_kind": _action_param("artifact_kind", "artifact_kind", "Requested artifact bundle kind.", enum_values=["baseline_bundle", "torsion_snapshots", "conformer_bundle"]),
            "artifact_bundle_id": _action_param("artifact_bundle_id", "artifact_bundle_id", "Explicit artifact bundle ID."),
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested artifact round selector.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
            "state_window": _action_param("state_window", "int_list", "Requested state window for parsed records."),
        },
        defaults={
            "perform_new_calculation": False,
            "reuse_existing_artifacts_only": True,
            "source_round_selector": "latest_available",
        },
        allowed_discovery_actions=["list_artifact_bundles"],
        default_deliverables=[
            "per-snapshot excitation energies",
            "per-snapshot oscillator strengths",
            "state-ordering summaries",
        ],
        unsupported_note="Dominant transition and CT/localization proxy extraction may be unavailable from existing files.",
    ),
    "extract_ct_descriptors_from_bundle": AmespActionDefinition(
        action_name="extract_ct_descriptors_from_bundle",
        action_kind="execution",
        purpose="Extract bounded CT-descriptor surrogates from an existing artifact bundle without launching new calculations.",
        allowed_llm_params=[
            "perform_new_calculation",
            "reuse_existing_artifacts_only",
            "artifact_kind",
            "artifact_bundle_id",
            "source_round_selector",
            "state_window",
            "descriptor_scope",
        ],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "perform_new_calculation": _action_param("perform_new_calculation", "bool", "Whether to launch new calculations. Must remain false for bundle-based CT extraction.", default=False),
            "reuse_existing_artifacts_only": _action_param("reuse_existing_artifacts_only", "bool", "Whether only reusable artifacts may be used.", default=True),
            "artifact_kind": _action_param("artifact_kind", "artifact_kind", "Requested artifact bundle kind.", enum_values=["baseline_bundle", "torsion_snapshots", "conformer_bundle"]),
            "artifact_bundle_id": _action_param("artifact_bundle_id", "artifact_bundle_id", "Explicit artifact bundle ID."),
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested artifact round selector.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
            "state_window": _action_param("state_window", "int_list", "Requested state window for CT-oriented descriptor extraction."),
            "descriptor_scope": _action_param("descriptor_scope", "text_list", "Requested CT-descriptor families to inspect from available artifacts."),
        },
        defaults={
            "perform_new_calculation": False,
            "reuse_existing_artifacts_only": True,
            "source_round_selector": "latest_available",
        },
        allowed_discovery_actions=["list_artifact_bundles"],
        default_deliverables=[
            "CT-descriptor availability summary",
            "bounded CT descriptor records",
            "artifact-backed CT surrogate summary",
        ],
        unsupported_note="Unavailable CT descriptors must be reported explicitly rather than inferred from unsupported raw-file parsing.",
    ),
    "extract_geometry_descriptors_from_bundle": AmespActionDefinition(
        action_name="extract_geometry_descriptors_from_bundle",
        action_kind="execution",
        purpose="Extract bounded intramolecular geometry descriptors from an existing artifact bundle without launching new calculations.",
        allowed_llm_params=[
            "perform_new_calculation",
            "reuse_existing_artifacts_only",
            "artifact_kind",
            "artifact_bundle_id",
            "source_round_selector",
            "descriptor_scope",
        ],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "perform_new_calculation": _action_param("perform_new_calculation", "bool", "Whether to launch new calculations. Must remain false for bundle-based geometry extraction.", default=False),
            "reuse_existing_artifacts_only": _action_param("reuse_existing_artifacts_only", "bool", "Whether only reusable artifacts may be used.", default=True),
            "artifact_kind": _action_param("artifact_kind", "artifact_kind", "Requested artifact bundle kind.", enum_values=["baseline_bundle", "torsion_snapshots", "conformer_bundle"]),
            "artifact_bundle_id": _action_param("artifact_bundle_id", "artifact_bundle_id", "Explicit artifact bundle ID."),
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested artifact round selector.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
            "descriptor_scope": _action_param("descriptor_scope", "text_list", "Requested geometry-descriptor families to inspect from available artifacts."),
        },
        defaults={
            "perform_new_calculation": False,
            "reuse_existing_artifacts_only": True,
            "source_round_selector": "latest_available",
        },
        allowed_discovery_actions=["list_artifact_bundles"],
        default_deliverables=[
            "geometry-descriptor availability summary",
            "bounded geometry descriptor records",
            "artifact-backed geometry summary",
        ],
        unsupported_note="Unavailable geometry descriptors must be reported explicitly rather than inferred from unsupported chemistry-specific heuristics.",
    ),
    "inspect_raw_artifact_bundle": AmespActionDefinition(
        action_name="inspect_raw_artifact_bundle",
        action_kind="execution",
        purpose="Inspect a reusable artifact bundle and report raw-file coverage plus extractable observable families.",
        allowed_llm_params=[
            "perform_new_calculation",
            "reuse_existing_artifacts_only",
            "artifact_kind",
            "artifact_bundle_id",
            "source_round_selector",
            "requested_observable_scope",
        ],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        param_types={
            "perform_new_calculation": _action_param("perform_new_calculation", "bool", "Whether to launch new calculations. Must remain false for raw artifact inspection.", default=False),
            "reuse_existing_artifacts_only": _action_param("reuse_existing_artifacts_only", "bool", "Whether only reusable artifacts may be used.", default=True),
            "artifact_kind": _action_param("artifact_kind", "artifact_kind", "Requested artifact bundle kind.", enum_values=["baseline_bundle", "torsion_snapshots", "conformer_bundle"]),
            "artifact_bundle_id": _action_param("artifact_bundle_id", "artifact_bundle_id", "Explicit artifact bundle ID."),
            "source_round_selector": _action_param(
                "source_round_selector",
                "source_round_selector",
                "Requested artifact round selector.",
                enum_values=["current_run", "latest_available", "round_02"],
                default="latest_available",
            ),
            "requested_observable_scope": _action_param("requested_observable_scope", "text_list", "Requested raw-observable families to inspect from the bundle."),
        },
        defaults={
            "perform_new_calculation": False,
            "reuse_existing_artifacts_only": True,
            "source_round_selector": "latest_available",
        },
        allowed_discovery_actions=["list_artifact_bundles"],
        default_deliverables=[
            "raw artifact file inventory",
            "extractable observable inventory",
            "raw inspection notes",
        ],
        unsupported_note="Raw inspection reports available files and extractable observables, but does not guarantee complete chemistry-specific descriptor extraction.",
    ),
    "unsupported_excited_state_relaxation": AmespActionDefinition(
        action_name="unsupported_excited_state_relaxation",
        action_kind="execution",
        purpose="Return a structured capability-unsupported result for excited-state relaxation requests.",
        allowed_llm_params=[],
        python_owned_params=list(_DEFAULT_PYTHON_OWNED_ACTION_PARAMS),
        defaults={},
        default_deliverables=[],
        unsupported_note="Low-cost excited-state relaxation has not been validated for Amesp yet.",
    ),
}


def render_amesp_capability_registry() -> str:
    lines: list[str] = []
    for capability in AMESP_CAPABILITY_REGISTRY.values():
        lines.append(
            f"- `{capability.name}`: {capability.purpose} "
            f"(requires_new_calculation={str(capability.requires_new_calculation).lower()}; "
            f"supported_deliverables={', '.join(capability.supported_deliverables) or 'none'})"
        )
    return "\n".join(lines)


def render_amesp_action_registry() -> str:
    lines: list[str] = []
    for action in AMESP_ACTION_REGISTRY.values():
        lines.append(f"- {action.action_name} [{action.action_kind}]: {action.purpose}")
        if action.allowed_discovery_actions:
            lines.append(f"  allowed_discovery_actions={', '.join(action.allowed_discovery_actions)}")
        if action.allowed_llm_params:
            lines.append(f"  allowed_llm_params={', '.join(action.allowed_llm_params)}")
        if action.default_deliverables:
            lines.append(f"  default_deliverables={'; '.join(action.default_deliverables)}")
        for param_name in action.allowed_llm_params:
            param = action.param_types[param_name]
            enum_suffix = f" enum={','.join(param.enum_values)}" if param.enum_values else ""
            default_suffix = f" default={param.default}" if param.default is not None else ""
            required_suffix = " required" if param.required else ""
            lines.append(
                f"    - param.{param_name}: {param.param_type}{required_suffix}{enum_suffix}{default_suffix} -- {param.description}"
            )
        if action.unsupported_note:
            lines.append(f"  unsupported_note={action.unsupported_note}")
    return "\n".join(lines)


def render_amesp_interface_catalog() -> str:
    lines = [
        "Current AIE-MAS worker-exposed Amesp actions:",
        render_amesp_action_registry(),
        "",
        "Official Amesp manual highlights that are broader than the current worker surface:",
        "- excited-state method families include CIS, TDHF, TDDFT, TDA, TDDFT-ris, TDA-ris, SOC, NAC, and TDA-aTB",
        "- geometry optimization families include HF/DFT/MP2/CIS/TDHF/TDDFT/TDA/aTB/TDA-aTB and related low-cost solvation options",
        "- wavefunction/property analysis includes Mulliken/Lowdin/Hirshfeld/CM5 charges, natural orbitals, orbital localization, dipole, quadrupole, and atomic polarizability",
        "- additional workflow families include rigid/relaxed PES scan, IRC, AIMD, charge transport integral, and EDA",
        "",
        "Current worker boundary rules:",
        "- Microscopic may execute only registry-backed actions listed above",
        "- If the Planner task depends on a manual-level Amesp feature not exposed by the worker registry, return unsupported",
        "- Current parse_snapshot_outputs does not guarantee explicit CT descriptors, geometry descriptors, or raw-file inspection semantics by itself; use the dedicated artifact-analysis actions when appropriate",
    ]
    return "\n".join(lines)


def render_registry_backed_microscopic_examples() -> dict[str, str]:
    return {
        "baseline": json.dumps(
            {
                "status": "supported",
                "execution_action": "run_baseline_bundle",
                "discovery_actions": [],
                "params": {
                    "perform_new_calculation": True,
                    "optimize_ground_state": True,
                },
                "unsupported_parts": [],
                "local_execution_rationale": "Run the default low-cost baseline bundle.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        "torsion": json.dumps(
            {
                "status": "supported",
                "execution_action": "run_torsion_snapshots",
                "discovery_actions": ["list_rotatable_dihedrals"],
                "params": {
                    "perform_new_calculation": True,
                    "optimize_ground_state": False,
                    "snapshot_count": 2,
                    "angle_offsets_deg": [35, 70],
                    "state_window": [1, 2, 3],
                    "honor_exact_target": True,
                    "allow_fallback": False,
                    "exclude_dihedral_ids": ["dih_0_1_2_3"],
                    "prefer_adjacent_to_nsnc_core": True,
                    "min_relevance": "high",
                    "include_peripheral": False,
                    "preferred_bond_types": ["aryl-vinyl", "heteroaryl-linkage"],
                    "source_round_selector": "latest_available",
                },
                "unsupported_parts": ["excited-state relaxation", "solvent response"],
                "local_execution_rationale": (
                    "Run a bounded torsion snapshot screen on one high-relevance dihedral near the NSNC core."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ),
    }


def render_reasoned_microscopic_examples() -> dict[str, str]:
    action_examples = render_registry_backed_microscopic_examples()
    return {
        "baseline": (
            "<task_understanding>\n"
            "Interpret the Planner instruction as a bounded first-round microscopic baseline task.\n"
            "</task_understanding>\n"
            "<reasoning_summary>\n"
            "The task is exactly representable by the baseline Amesp route, so select the registry-backed baseline action.\n"
            "</reasoning_summary>\n"
            "<action_decision_json>\n"
            f"{action_examples['baseline']}\n"
            "</action_decision_json>"
        ),
        "torsion": (
            "<task_understanding>\n"
            "Interpret the Planner instruction as a bounded torsion-sensitivity follow-up on one high-relevance dihedral.\n"
            "</task_understanding>\n"
            "<reasoning_summary>\n"
            "The task is best represented by bounded torsion snapshots with dihedral discovery before execution.\n"
            "</reasoning_summary>\n"
            "<action_decision_json>\n"
            f"{action_examples['torsion']}\n"
            "</action_decision_json>"
        ),
    }


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
        workdir.mkdir(parents=True, exist_ok=True)
        tool_plan = self._tool_plan_from_execution_plan(plan)
        discovery_results: dict[str, dict[str, Any]] = {}
        execution_call: MicroscopicToolCall | None = None

        for call in tool_plan.calls:
            if call.call_kind == "discovery":
                discovery_results[call.call_id] = self._execute_discovery_call(
                    call.request,
                    smiles=smiles,
                    available_artifacts=available_artifacts,
                    workdir=workdir,
                    case_id=case_id,
                    round_index=round_index,
                )
                continue
            execution_call = call
            break

        if execution_call is None:
            raise AmespExecutionError(
                "precondition_missing",
                "Microscopic tool plan did not contain an execution call.",
                status="failed",
            )

        resolved_request, resolution_payload = self._resolve_execution_request(
            execution_call.request,
            selection_policy=tool_plan.selection_policy,
            discovery_results=discovery_results,
            available_artifacts=available_artifacts,
        )
        try:
            result = self._dispatch_execution_request(
                request=resolved_request,
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
        except AmespExecutionError as exc:
            exc.generated_artifacts = dict(exc.generated_artifacts)
            exc.generated_artifacts["source_round"] = round_index
            exc.generated_artifacts["resolved_target_ids"] = dict(
                resolution_payload.get("resolved_target_ids", {})
            )
            if exc.status == "partial":
                exc.generated_artifacts.setdefault("bundle_completion_status", "partial")
            if isinstance(exc.structured_results, dict):
                exc.structured_results.setdefault(
                    "resolved_target_ids",
                    dict(resolution_payload.get("resolved_target_ids", {})),
                )
                exc.structured_results.setdefault(
                    "honored_constraints",
                    list(resolution_payload.get("honored_constraints", [])),
                )
                exc.structured_results.setdefault(
                    "unmet_constraints",
                    list(resolution_payload.get("unmet_constraints", [])),
                )
            artifact_bundle_entry = _artifact_bundle_entry_from_generated_artifacts(
                source_capability=resolved_request.capability_name,
                source_round=round_index,
                generated_artifacts=exc.generated_artifacts,
            )
            if artifact_bundle_entry is not None:
                exc.generated_artifacts["artifact_bundle_id"] = artifact_bundle_entry.artifact_bundle.bundle_id
                exc.generated_artifacts["artifact_bundle_kind"] = artifact_bundle_entry.artifact_bundle.bundle_kind
                exc.generated_artifacts["artifact_bundle_registry_entries"] = [
                    artifact_bundle_entry.model_dump(mode="json")
                ]
                if isinstance(exc.structured_results, dict):
                    exc.structured_results.setdefault(
                        "artifact_bundle_id",
                        artifact_bundle_entry.artifact_bundle.bundle_id,
                    )
                    exc.structured_results.setdefault(
                        "artifact_bundle_kind",
                        artifact_bundle_entry.artifact_bundle.bundle_kind,
                    )
            raise
        result.requested_capability = execution_call.request.capability_name
        result.resolved_target_ids = dict(resolution_payload.get("resolved_target_ids", {}))
        result.honored_constraints = list(resolution_payload.get("honored_constraints", []))
        result.unmet_constraints = list(resolution_payload.get("unmet_constraints", []))
        result.generated_artifacts["resolved_target_ids"] = dict(result.resolved_target_ids)
        result.generated_artifacts["source_round"] = round_index
        result.generated_artifacts.setdefault("bundle_completion_status", "complete")
        artifact_bundle_entry = _artifact_bundle_entry_from_generated_artifacts(
            source_capability=result.executed_capability,
            source_round=round_index,
            generated_artifacts=result.generated_artifacts,
        )
        if artifact_bundle_entry is not None:
            result.generated_artifacts["artifact_bundle_id"] = artifact_bundle_entry.artifact_bundle.bundle_id
            result.generated_artifacts["artifact_bundle_kind"] = artifact_bundle_entry.artifact_bundle.bundle_kind
            result.generated_artifacts["artifact_bundle_registry_entries"] = [
                artifact_bundle_entry.model_dump(mode="json")
            ]
        return result

    def _tool_plan_from_execution_plan(self, plan: MicroscopicExecutionPlan) -> MicroscopicToolPlan:
        if getattr(plan, "microscopic_tool_plan", None) is not None and plan.microscopic_tool_plan.calls:
            return plan.microscopic_tool_plan
        if plan.microscopic_tool_request is None:
            return MicroscopicToolPlan()
        return MicroscopicToolPlan(
            calls=[
                MicroscopicToolCall(
                    call_id="compat_execution",
                    call_kind="execution",
                    request=plan.microscopic_tool_request,
                )
            ],
            requested_route_summary=plan.requested_route_summary,
            requested_deliverables=list(plan.requested_deliverables),
            selection_policy=SelectionPolicy(),
            failure_reporting=plan.failure_reporting,
        )

    def _dispatch_execution_request(
        self,
        *,
        request: MicroscopicToolRequest,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> AmespBaselineRunResult:
        capability = AMESP_CAPABILITY_REGISTRY[request.capability_name]
        if capability.requires_new_calculation and not self._amesp_bin.exists():
            raise AmespExecutionError(
                "amesp_binary_missing",
                f"Amesp binary was not found at {self._amesp_bin}.",
            )

        if request.capability_name == "run_baseline_bundle":
            result = self._execute_baseline_route(
                request=request,
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
            result.executed_capability = "run_baseline_bundle"
            result.performed_new_calculations = True
            result.route_summary = _build_vertical_state_manifold_summary(result.s1)
            return result

        if request.capability_name == "run_conformer_bundle":
            return self._execute_conformer_bundle_route(
                request=request,
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )

        if request.capability_name == "run_torsion_snapshots":
            return self._execute_torsion_snapshot_route(
                request=request,
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                progress_callback=progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )

        if request.capability_name == "parse_snapshot_outputs":
            return self._execute_parse_snapshot_outputs_route(
                request=request,
                available_artifacts=available_artifacts,
            )
        if request.capability_name == "extract_ct_descriptors_from_bundle":
            return self._execute_extract_ct_descriptors_from_bundle_route(
                request=request,
                available_artifacts=available_artifacts,
            )
        if request.capability_name == "extract_geometry_descriptors_from_bundle":
            return self._execute_extract_geometry_descriptors_from_bundle_route(
                request=request,
                available_artifacts=available_artifacts,
            )
        if request.capability_name == "inspect_raw_artifact_bundle":
            return self._execute_inspect_raw_artifact_bundle_route(
                request=request,
                available_artifacts=available_artifacts,
            )

        raise AmespExecutionError(
            "capability_unsupported",
            "A low-cost excited-state relaxation route has not been validated for Amesp yet.",
            status="failed",
            structured_results={
                "executed_capability": "unsupported_excited_state_relaxation",
                "performed_new_calculations": False,
                "reused_existing_artifacts": False,
            },
        )

    def _execute_discovery_call(
        self,
        request: MicroscopicToolRequest,
        *,
        smiles: str,
        available_artifacts: dict[str, Any] | None,
        workdir: Path,
        case_id: Optional[str],
        round_index: int,
    ) -> dict[str, Any]:
        if request.capability_name == "list_rotatable_dihedrals":
            prepared = self._resolve_prepared_structure_for_discovery(
                request=request,
                smiles=smiles,
                available_artifacts=available_artifacts,
                workdir=workdir / "discovery_dihedrals",
                case_id=case_id,
                round_index=round_index,
            )
            descriptors = _list_rotatable_dihedral_descriptors(prepared)
            return {
                "capability_name": request.capability_name,
                "items": [item.model_dump(mode="json") for item in descriptors],
            }
        if request.capability_name == "list_available_conformers":
            descriptors = self._list_available_conformer_descriptors(
                request=request,
                available_artifacts=available_artifacts,
            )
            return {
                "capability_name": request.capability_name,
                "items": [item.model_dump(mode="json") for item in descriptors],
            }
        if request.capability_name == "list_artifact_bundles":
            descriptors = self._list_artifact_bundle_descriptors(
                request=request,
                available_artifacts=available_artifacts,
            )
            return {
                "capability_name": request.capability_name,
                "items": [item.model_dump(mode="json") for item in descriptors],
            }
        raise AmespExecutionError(
            "capability_unsupported",
            f"Discovery capability '{request.capability_name}' is not supported by AmespMicroscopicTool.",
            status="failed",
        )

    def _resolve_execution_request(
        self,
        request: MicroscopicToolRequest,
        *,
        selection_policy: SelectionPolicy,
        discovery_results: dict[str, dict[str, Any]],
        available_artifacts: dict[str, Any] | None,
    ) -> tuple[MicroscopicToolRequest, dict[str, Any]]:
        resolved_request = request.model_copy(deep=True)
        resolved_target_ids: dict[str, Any] = {}
        honored_constraints: list[str] = []
        unmet_constraints: list[str] = []

        if resolved_request.dihedral_id and not resolved_request.dihedral_atom_indices:
            parsed_atoms = _dihedral_atoms_from_id(resolved_request.dihedral_id)
            if parsed_atoms:
                resolved_request.dihedral_atom_indices = parsed_atoms
        if resolved_request.dihedral_id:
            resolved_target_ids["dihedral_id"] = resolved_request.dihedral_id
            honored_constraints.append(
                f"Execution request honored explicit dihedral target `{resolved_request.dihedral_id}`."
            )
        if not resolved_request.optimize_ground_state and request.capability_name in {
            "run_torsion_snapshots",
            "run_conformer_bundle",
        }:
            honored_constraints.append(
                "Execution request honored `optimize_ground_state=false` and skipped geometry re-optimization."
            )

        if resolved_request.artifact_bundle_id:
            descriptor = self._artifact_bundle_descriptor_by_id(
                artifact_bundle_id=resolved_request.artifact_bundle_id,
                available_artifacts=available_artifacts,
            )
            if descriptor is None:
                raise AmespExecutionError(
                    "precondition_missing",
                    f"The requested artifact bundle `{resolved_request.artifact_bundle_id}` is not a discoverable canonical bundle ID for the current case run.",
                    status="failed",
                    structured_results={
                        "executed_capability": request.capability_name,
                        "performed_new_calculations": request.perform_new_calculation,
                        "reused_existing_artifacts": request.reuse_existing_artifacts_only,
                    },
                )
            resolved_request.artifact_bundle_id = descriptor.artifact_bundle_id
            resolved_request.artifact_kind = descriptor.artifact_kind
            resolved_request.artifact_source_round = descriptor.source_round
            resolved_target_ids["artifact_bundle_id"] = descriptor.artifact_bundle_id
            honored_constraints.append(
                f"Execution request honored explicit canonical artifact bundle `{descriptor.artifact_bundle_id}`."
            )

        if request.capability_name == "run_torsion_snapshots" and not resolved_request.dihedral_id:
            dihedral_items = self._collect_discovery_items(discovery_results, "list_rotatable_dihedrals")
            descriptor = _select_dihedral_descriptor(dihedral_items, selection_policy)
            if descriptor is None:
                raise AmespExecutionError(
                    "precondition_missing",
                    "No discovery-listed rotatable dihedral satisfied the requested selection policy for torsion snapshots.",
                    status="failed",
                    structured_results={
                        "executed_capability": "run_torsion_snapshots",
                        "performed_new_calculations": True,
                        "reused_existing_artifacts": False,
                    },
                )
            resolved_request.dihedral_id = descriptor.dihedral_id
            resolved_request.dihedral_atom_indices = list(descriptor.atom_indices)
            resolved_target_ids["dihedral_id"] = descriptor.dihedral_id
            honored_constraints.extend(
                _describe_dihedral_constraints(descriptor=descriptor, policy=selection_policy)
            )

        if request.capability_name in {
            "parse_snapshot_outputs",
            "extract_ct_descriptors_from_bundle",
            "extract_geometry_descriptors_from_bundle",
            "inspect_raw_artifact_bundle",
        } and not resolved_request.artifact_bundle_id:
            bundle_items = self._collect_discovery_items(discovery_results, "list_artifact_bundles")
            descriptor = _select_artifact_bundle_descriptor(bundle_items, selection_policy)
            if descriptor is None:
                raise AmespExecutionError(
                    "precondition_missing",
                    "No reusable artifact bundle satisfied the requested artifact-analysis selection policy.",
                    status="failed",
                    structured_results={
                        "executed_capability": request.capability_name,
                        "performed_new_calculations": False,
                        "reused_existing_artifacts": True,
                    },
                )
            resolved_request.artifact_bundle_id = descriptor.artifact_bundle_id
            resolved_request.artifact_kind = descriptor.artifact_kind
            resolved_request.artifact_source_round = descriptor.source_round
            resolved_target_ids["artifact_bundle_id"] = descriptor.artifact_bundle_id
            honored_constraints.append(
                f"Resolved artifact bundle to `{descriptor.artifact_bundle_id}` (kind={descriptor.artifact_kind}, round={descriptor.source_round})."
            )

        if request.capability_name == "run_conformer_bundle" and request.conformer_ids:
            resolved_target_ids["conformer_ids"] = list(request.conformer_ids)
        elif request.capability_name == "run_conformer_bundle" and request.conformer_id:
            resolved_target_ids["conformer_id"] = request.conformer_id

        if resolved_request.dihedral_id and selection_policy.exclude_dihedral_ids:
            if resolved_request.dihedral_id in selection_policy.exclude_dihedral_ids:
                unmet_constraints.append(
                    f"Resolved dihedral `{resolved_request.dihedral_id}` violated exclude_dihedral_ids."
                )
                if not resolved_request.allow_fallback:
                    raise AmespExecutionError(
                        "precondition_missing",
                        f"The requested dihedral `{resolved_request.dihedral_id}` is explicitly excluded by the selection policy.",
                        status="failed",
                        structured_results={
                            "executed_capability": request.capability_name,
                            "performed_new_calculations": request.perform_new_calculation,
                            "reused_existing_artifacts": request.reuse_existing_artifacts_only,
                        },
                    )

        if request.capability_name == "run_conformer_bundle" and request.conformer_ids:
            available_ids = {
                descriptor.conformer_id
                for descriptor in self._list_available_conformer_descriptors(
                    request=MicroscopicToolRequest(capability_name="list_available_conformers"),
                    available_artifacts=available_artifacts,
                )
            }
            missing_ids = [conf_id for conf_id in request.conformer_ids if conf_id not in available_ids]
            if missing_ids:
                raise AmespExecutionError(
                    "precondition_missing",
                    "The requested conformer IDs were not available for conformer follow-up: "
                    + ", ".join(missing_ids),
                    status="failed",
                    structured_results={
                        "executed_capability": "run_conformer_bundle",
                        "performed_new_calculations": True,
                        "reused_existing_artifacts": False,
                    },
                )

        return resolved_request, {
            "resolved_target_ids": resolved_target_ids,
            "honored_constraints": honored_constraints,
            "unmet_constraints": unmet_constraints,
        }

    def _collect_discovery_items(
        self,
        discovery_results: dict[str, dict[str, Any]],
        capability_name: MicroscopicCapabilityName,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for result in discovery_results.values():
            if result.get("capability_name") == capability_name:
                items.extend(list(result.get("items") or []))
        return items

    def _resolve_prepared_structure_for_discovery(
        self,
        *,
        request: MicroscopicToolRequest,
        smiles: str,
        available_artifacts: dict[str, Any] | None,
        workdir: Path,
        case_id: Optional[str],
        round_index: int,
    ) -> PreparedStructure:
        available_artifacts = available_artifacts or {}
        prepared_xyz_path = available_artifacts.get("prepared_xyz_path")
        prepared_summary_path = available_artifacts.get("prepared_summary_path")
        prepared_sdf_path = available_artifacts.get("prepared_sdf_path")
        if prepared_xyz_path and prepared_summary_path and prepared_sdf_path:
            return self._load_prepared_structure_from_paths(
                summary_path=Path(str(prepared_summary_path)),
                xyz_path=Path(str(prepared_xyz_path)),
                sdf_path=Path(str(prepared_sdf_path)),
            )
        _, prepared = self._structure_preparer(
            StructurePrepRequest(
                smiles=smiles,
                label=f"{case_id or 'ad_hoc_case'}_round_{round_index:02d}_discovery",
                workdir=workdir,
            )
        )
        return prepared

    def _list_available_conformer_descriptors(
        self,
        *,
        request: MicroscopicToolRequest,
        available_artifacts: dict[str, Any] | None,
    ) -> list[ConformerDescriptor]:
        available_artifacts = available_artifacts or {}
        descriptors: list[ConformerDescriptor] = []
        conformer_artifacts = list(available_artifacts.get("conformer_artifacts") or [])
        for index, artifact in enumerate(conformer_artifacts, start=1):
            prepared_xyz_path = artifact.get("prepared_xyz_path")
            if not prepared_xyz_path:
                continue
            descriptors.append(
                ConformerDescriptor(
                    conformer_id=f"conf_{index:02d}",
                    source="microscopic_follow_up",
                    rank=int(artifact.get("conformer_rank") or index),
                    prepared_xyz_path=str(prepared_xyz_path),
                    summary_label=f"Reusable conformer {index:02d}",
                )
            )
        if descriptors:
            return descriptors
        prepared_xyz_path = available_artifacts.get("prepared_xyz_path")
        if prepared_xyz_path:
            return [
                ConformerDescriptor(
                    conformer_id="shared_conf_01",
                    source="shared_structure",
                    rank=1,
                    prepared_xyz_path=str(prepared_xyz_path),
                    summary_label="Shared prepared conformer",
                )
            ]
        return []

    def _list_artifact_bundle_descriptors(
        self,
        *,
        request: MicroscopicToolRequest,
        available_artifacts: dict[str, Any] | None,
    ) -> list[ArtifactBundleDescriptor]:
        available_artifacts = available_artifacts or {}
        descriptors = self._available_artifact_bundle_descriptors(available_artifacts)
        if request.artifact_kind is None:
            return descriptors
        return [descriptor for descriptor in descriptors if descriptor.artifact_kind == request.artifact_kind]

    def _available_artifact_bundle_descriptors(
        self,
        available_artifacts: dict[str, Any] | None,
    ) -> list[ArtifactBundleDescriptor]:
        available_artifacts = available_artifacts or {}
        descriptors_by_id: dict[str, ArtifactBundleDescriptor] = {}
        registry_entries = list(available_artifacts.get("artifact_bundle_registry_entries") or [])
        if registry_entries:
            for item in registry_entries:
                entry = ArtifactBundleRegistryEntry.model_validate(item)
                bundle = entry.artifact_bundle
                snapshot_count = 1 if bundle.bundle_kind == "baseline_bundle" else len(
                    list(entry.generated_artifacts.get("snapshot_artifacts") or entry.generated_artifacts.get("conformer_artifacts") or [])
                )
                descriptors_by_id[bundle.bundle_id] = ArtifactBundleDescriptor(
                    artifact_bundle_id=bundle.bundle_id,
                    source_round=bundle.source_round,
                    source_capability=bundle.source_capability,
                    artifact_kind=bundle.bundle_kind,
                    bundle_completion_status=bundle.bundle_completion_status,
                    snapshot_count=snapshot_count,
                    available_files=list(bundle.available_files),
                    available_deliverables=list(bundle.available_deliverables),
                )
        registry_sources = list(available_artifacts.get("artifact_bundle_registry_sources") or [])
        if registry_sources:
            for source in registry_sources:
                source_artifacts = dict(source.get("generated_artifacts") or {})
                source_round = int(source.get("source_round") or source_artifacts.get("source_round") or 0)
                source_artifacts["source_round"] = source_round
                for descriptor in self._artifact_bundle_descriptors_from_source(source_artifacts):
                    descriptors_by_id[descriptor.artifact_bundle_id] = descriptor
        else:
            for descriptor in self._artifact_bundle_descriptors_from_source(available_artifacts):
                descriptors_by_id[descriptor.artifact_bundle_id] = descriptor
        return sorted(descriptors_by_id.values(), key=lambda item: (-int(item.source_round), item.artifact_bundle_id))

    def _artifact_bundle_descriptors_from_source(
        self,
        source_artifacts: dict[str, Any],
    ) -> list[ArtifactBundleDescriptor]:
        descriptors: list[ArtifactBundleDescriptor] = []
        source_round = int(source_artifacts.get("source_round") or 0)
        bundle_completion_status = _bundle_completion_status_from_generated_artifacts(source_artifacts)
        if source_artifacts.get("snapshot_artifacts"):
            descriptors.append(
                ArtifactBundleDescriptor(
                    artifact_bundle_id=f"round_{source_round:02d}_torsion_snapshots",
                    source_round=source_round,
                    source_capability="run_torsion_snapshots",
                    artifact_kind="torsion_snapshots",
                    bundle_completion_status=bundle_completion_status,
                    snapshot_count=len(list(source_artifacts.get("snapshot_artifacts") or [])),
                    available_files=_collect_available_file_keys(source_artifacts, "snapshot_artifacts"),
                    available_deliverables=[
                        "per-snapshot excitation energies",
                        "per-snapshot oscillator strengths",
                        "state-ordering summaries",
                    ],
                )
            )
        if source_artifacts.get("conformer_artifacts"):
            descriptors.append(
                ArtifactBundleDescriptor(
                    artifact_bundle_id=f"round_{source_round:02d}_conformer_bundle",
                    source_round=source_round,
                    source_capability="run_conformer_bundle",
                    artifact_kind="conformer_bundle",
                    bundle_completion_status=bundle_completion_status,
                    snapshot_count=len(list(source_artifacts.get("conformer_artifacts") or [])),
                    available_files=_collect_available_file_keys(source_artifacts, "conformer_artifacts"),
                    available_deliverables=[
                        "bounded conformer vertical-state records",
                        "excitation spread",
                        "bright-state sensitivity",
                    ],
                )
            )
        if source_artifacts.get("s0_aop_path") or source_artifacts.get("s1_aop_path"):
            descriptors.append(
                ArtifactBundleDescriptor(
                    artifact_bundle_id=f"round_{source_round:02d}_baseline_bundle",
                    source_round=source_round,
                    source_capability="run_baseline_bundle",
                    artifact_kind="baseline_bundle",
                    bundle_completion_status=bundle_completion_status,
                    snapshot_count=1,
                    available_files=_collect_scalar_artifact_files(source_artifacts),
                    available_deliverables=[
                        "S0 optimized geometry",
                        "vertical excited-state manifold",
                    ],
                )
            )
        return descriptors

    def _artifact_bundle_descriptor_by_id(
        self,
        *,
        artifact_bundle_id: str,
        available_artifacts: dict[str, Any] | None,
    ) -> Optional[ArtifactBundleDescriptor]:
        for descriptor in self._available_artifact_bundle_descriptors(available_artifacts):
            if descriptor.artifact_bundle_id == artifact_bundle_id:
                return descriptor
        return None

    def _artifact_bundle_source_by_id(
        self,
        *,
        artifact_bundle_id: str,
        available_artifacts: dict[str, Any] | None,
    ) -> Optional[tuple[ArtifactBundleDescriptor, dict[str, Any]]]:
        available_artifacts = available_artifacts or {}
        registry_entries = list(available_artifacts.get("artifact_bundle_registry_entries") or [])
        if registry_entries:
            for item in registry_entries:
                entry = ArtifactBundleRegistryEntry.model_validate(item)
                bundle = entry.artifact_bundle
                if bundle.bundle_id != artifact_bundle_id:
                    continue
                snapshot_count = 1 if bundle.bundle_kind == "baseline_bundle" else len(
                    list(entry.generated_artifacts.get("snapshot_artifacts") or entry.generated_artifacts.get("conformer_artifacts") or [])
                )
                return (
                    ArtifactBundleDescriptor(
                        artifact_bundle_id=bundle.bundle_id,
                        source_round=bundle.source_round,
                        source_capability=bundle.source_capability,
                        artifact_kind=bundle.bundle_kind,
                        bundle_completion_status=bundle.bundle_completion_status,
                        snapshot_count=snapshot_count,
                        available_files=list(bundle.available_files),
                        available_deliverables=list(bundle.available_deliverables),
                    ),
                    dict(entry.generated_artifacts),
                )
        registry_sources = list(available_artifacts.get("artifact_bundle_registry_sources") or [])
        if registry_sources:
            for source in registry_sources:
                source_artifacts = dict(source.get("generated_artifacts") or {})
                source_round = int(source.get("source_round") or source_artifacts.get("source_round") or 0)
                source_artifacts["source_round"] = source_round
                for descriptor in self._artifact_bundle_descriptors_from_source(source_artifacts):
                    if descriptor.artifact_bundle_id == artifact_bundle_id:
                        return descriptor, source_artifacts
            return None
        descriptor = self._artifact_bundle_descriptor_by_id(
            artifact_bundle_id=artifact_bundle_id,
            available_artifacts=available_artifacts,
        )
        if descriptor is None:
            return None
        return descriptor, available_artifacts

    def _resolve_artifact_bundle_records_for_analysis(
        self,
        *,
        request: MicroscopicToolRequest,
        available_artifacts: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], str, Optional[int], list[dict[str, Any]]]:
        if not available_artifacts:
            raise AmespExecutionError(
                "precondition_missing",
                "Artifact-backed microscopic analysis requires reusable microscopic artifacts, but none were available.",
                status="failed",
                structured_results={
                    "executed_capability": request.capability_name,
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": False,
                },
            )

        selected_artifacts = available_artifacts
        artifact_scope = request.artifact_scope or request.artifact_kind or "latest_bundle"
        source_round = available_artifacts.get("source_round")
        if request.artifact_bundle_id is not None:
            resolved_bundle = self._artifact_bundle_source_by_id(
                artifact_bundle_id=request.artifact_bundle_id,
                available_artifacts=available_artifacts,
            )
            if resolved_bundle is None:
                raise AmespExecutionError(
                    "precondition_missing",
                    f"Artifact-backed follow-up requested canonical artifact bundle `{request.artifact_bundle_id}`, but it was not discoverable in the current case run.",
                    status="failed",
                    structured_results={
                        "executed_capability": request.capability_name,
                        "performed_new_calculations": False,
                        "reused_existing_artifacts": True,
                    },
                )
            descriptor, selected_artifacts = resolved_bundle
            artifact_scope = descriptor.artifact_kind
            source_round = descriptor.source_round
        if request.artifact_source_round is not None and source_round not in {None, request.artifact_source_round}:
            raise AmespExecutionError(
                "precondition_missing",
                f"Artifact-backed follow-up requested artifacts from round_{request.artifact_source_round:02d}, "
                f"but only round_{int(source_round):02d} artifacts were available."
                if isinstance(source_round, int)
                else "Artifact-backed follow-up requested a specific artifact round, but the available artifacts did not expose a matching round marker.",
                status="failed",
                structured_results={
                    "executed_capability": request.capability_name,
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": True,
                },
            )

        artifact_records: list[dict[str, Any]] = []
        if artifact_scope == "conformer_bundle":
            artifact_records = list(selected_artifacts.get("conformer_artifacts") or [])
        elif artifact_scope == "baseline_bundle":
            baseline_record = _baseline_artifact_record(selected_artifacts)
            if baseline_record.get("s0_aop_path") or baseline_record.get("s1_aop_path"):
                artifact_records = [baseline_record]
        else:
            artifact_records = list(selected_artifacts.get("snapshot_artifacts") or [])
            if not artifact_records and artifact_scope in {"latest_bundle", "snapshot_outputs"}:
                artifact_records = list(selected_artifacts.get("conformer_artifacts") or [])
                if artifact_records:
                    artifact_scope = "conformer_bundle"
            if not artifact_records and artifact_scope in {"latest_bundle", "snapshot_outputs"}:
                baseline_record = _baseline_artifact_record(selected_artifacts)
                if baseline_record.get("s0_aop_path") or baseline_record.get("s1_aop_path"):
                    artifact_scope = "baseline_bundle"
                    artifact_records = [baseline_record]
        if not artifact_records:
            raise AmespExecutionError(
                "precondition_missing",
                f"Artifact-backed follow-up requested artifact scope '{artifact_scope}', but no reusable artifact records were recorded.",
                status="failed",
                structured_results={
                    "executed_capability": request.capability_name,
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": True,
                },
            )
        return selected_artifacts, artifact_scope, source_round, artifact_records

    def _load_prepared_structure_from_paths(
        self,
        *,
        summary_path: Path,
        xyz_path: Path,
        sdf_path: Path,
    ) -> PreparedStructure:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        payload["xyz_path"] = xyz_path
        payload["sdf_path"] = sdf_path
        payload["summary_path"] = summary_path
        return PreparedStructure.model_validate(payload)

    def _execute_baseline_route(
        self,
        *,
        request: MicroscopicToolRequest,
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
            optimize_ground_state=request.optimize_ground_state,
            route="baseline_bundle",
            state_window=request.state_window,
            executed_capability="run_baseline_bundle",
            performed_new_calculations=True,
            reused_existing_artifacts=False,
        )

    def _execute_conformer_bundle_route(
        self,
        *,
        request: MicroscopicToolRequest,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]],
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
    ) -> AmespBaselineRunResult:
        if request.conformer_ids:
            raise AmespExecutionError(
                "precondition_missing",
                "Explicit conformer-ID execution is not available unless reusable conformer artifacts are exposed to the current microscopic round.",
                status="failed",
                structured_results={
                    "executed_capability": "run_conformer_bundle",
                    "performed_new_calculations": True,
                    "reused_existing_artifacts": False,
                },
            )
        bundle = prepare_conformer_bundle_from_smiles(
            StructurePrepRequest(
                smiles=smiles,
                label=label,
                workdir=workdir / "conformer_bundle",
                num_conformers=max(request.max_conformers or request.snapshot_count or self._follow_up_max_conformers, 3),
            ),
            max_members=request.max_conformers or request.snapshot_count or self._follow_up_max_conformers,
        )
        if len(bundle) < 2:
            raise AmespExecutionError(
                "precondition_missing",
                "Conformer follow-up requires at least two prepared conformers, but only one reusable conformer was available.",
                status="failed",
            )

        route_records: list[dict[str, Any]] = []
        member_artifacts: list[dict[str, Any]] = []
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
                optimize_ground_state=request.optimize_ground_state,
                route="conformer_bundle_follow_up",
                state_window=request.state_window,
                executed_capability="run_conformer_bundle",
                performed_new_calculations=True,
                reused_existing_artifacts=False,
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
            member_artifacts.append(
                {
                    "member_label": f"conformer_{member.rank:02d}",
                    "conformer_rank": member.rank,
                    "prepared_xyz_path": member_result.generated_artifacts.get("prepared_xyz_path"),
                    "prepared_summary_path": member_result.generated_artifacts.get("prepared_summary_path"),
                    "s0_aop_path": member_result.generated_artifacts.get("s0_aop_path"),
                    "s1_aop_path": member_result.generated_artifacts.get("s1_aop_path"),
                    "s0_stdout_path": member_result.generated_artifacts.get("s0_stdout_path"),
                    "s1_stdout_path": member_result.generated_artifacts.get("s1_stdout_path"),
                    "s0_mo_path": member_result.generated_artifacts.get("s0_mo_path"),
                    "s1_mo_path": member_result.generated_artifacts.get("s1_mo_path"),
                }
            )
            if primary_result is None or member_result.s0.final_energy_hartree < primary_result.s0.final_energy_hartree:
                primary_result = member_result

        assert primary_result is not None
        primary_result.route = "conformer_bundle_follow_up"
        primary_result.executed_capability = "run_conformer_bundle"
        primary_result.performed_new_calculations = True
        primary_result.route_records = route_records
        primary_result.route_summary = _build_conformer_bundle_summary(route_records)
        primary_result.generated_artifacts["conformer_bundle_member_count"] = len(route_records)
        primary_result.generated_artifacts["conformer_artifacts"] = member_artifacts
        return primary_result

    def _execute_torsion_snapshot_route(
        self,
        *,
        request: MicroscopicToolRequest,
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
            max_total=request.snapshot_count or self._follow_up_max_torsion_snapshots_total,
            target_angles=request.angle_offsets_deg or None,
            target_dihedral_atoms=request.dihedral_atom_indices or None,
            output_dir=workdir / "torsion_snapshots",
        )
        if not snapshots:
            raise AmespExecutionError(
                "precondition_missing",
                "Torsion snapshot follow-up could not honor the requested dihedral target from the prepared structure.",
                status="failed",
                structured_results={
                    "executed_capability": "run_torsion_snapshots",
                    "performed_new_calculations": True,
                    "reused_existing_artifacts": False,
                },
            )

        route_records: list[dict[str, Any]] = []
        snapshot_artifacts: list[dict[str, Any]] = []
        primary_result: AmespBaselineRunResult | None = None
        for snapshot in snapshots:
            try:
                snapshot_result = self._run_single_low_cost_bundle(
                    atoms=snapshot["atoms"],
                    prepared=snapshot["prepared"],
                    label=f"{label}_{snapshot['snapshot_label']}",
                    workdir=workdir / snapshot["snapshot_label"],
                    progress_callback=progress_callback,
                    round_index=round_index,
                    case_id=case_id,
                    current_hypothesis=current_hypothesis,
                    optimize_ground_state=request.optimize_ground_state,
                    route="torsion_snapshot_follow_up",
                    state_window=request.state_window,
                    executed_capability="run_torsion_snapshots",
                    performed_new_calculations=True,
                    reused_existing_artifacts=False,
                )
            except AmespExecutionError as exc:
                snapshot_artifacts.append(
                    _snapshot_artifact_record_from_partial_error(
                        snapshot=snapshot,
                        generated_artifacts=exc.generated_artifacts,
                        failure_code=exc.code,
                        failure_message=exc.message,
                    )
                )
                partial_generated_artifacts = {
                    "prepared_xyz_path": str(prepared.xyz_path),
                    "prepared_sdf_path": str(prepared.sdf_path),
                    "prepared_summary_path": str(prepared.summary_path),
                    "torsion_snapshot_count": len(snapshot_artifacts),
                    "snapshot_artifacts": snapshot_artifacts,
                    "bundle_completion_status": "partial",
                    "bundle_partial_failure_code": exc.code,
                    "bundle_partial_failure_message": exc.message,
                }
                raise AmespExecutionError(
                    exc.code,
                    exc.message,
                    generated_artifacts={**partial_generated_artifacts, **exc.generated_artifacts},
                    raw_results=exc.raw_results,
                    structured_results=exc.structured_results,
                    status="partial",
                ) from exc
            route_records.append(
                {
                    "snapshot_label": snapshot["snapshot_label"],
                    "dihedral_atoms": snapshot["dihedral_atoms"],
                    "target_angle_deg": snapshot["target_angle_deg"],
                    "final_energy_hartree": snapshot_result.s0.final_energy_hartree,
                    "first_excitation_energy_ev": snapshot_result.s1.first_excitation_energy_ev,
                    "first_oscillator_strength": snapshot_result.s1.first_oscillator_strength,
                    "state_count": snapshot_result.s1.state_count,
                }
            )
            snapshot_artifacts.append(
                _snapshot_artifact_record_from_generated_artifacts(
                    snapshot=snapshot,
                    generated_artifacts=snapshot_result.generated_artifacts,
                )
            )
            if primary_result is None or snapshot_result.s0.final_energy_hartree < primary_result.s0.final_energy_hartree:
                primary_result = snapshot_result

        assert primary_result is not None
        primary_result.route = "torsion_snapshot_follow_up"
        primary_result.executed_capability = "run_torsion_snapshots"
        primary_result.performed_new_calculations = True
        primary_result.route_records = route_records
        primary_result.route_summary = _build_torsion_snapshot_summary(route_records)
        primary_result.route_summary["source_bundle_completion_status"] = "complete"
        primary_result.generated_artifacts["torsion_snapshot_count"] = len(route_records)
        primary_result.generated_artifacts["snapshot_artifacts"] = snapshot_artifacts
        primary_result.generated_artifacts["bundle_completion_status"] = "complete"
        return primary_result

    def _execute_parse_snapshot_outputs_route(
        self,
        *,
        request: MicroscopicToolRequest,
        available_artifacts: dict[str, Any] | None,
    ) -> AmespBaselineRunResult:
        selected_artifacts, artifact_scope, source_round, artifact_records = (
            self._resolve_artifact_bundle_records_for_analysis(
                request=request,
                available_artifacts=available_artifacts,
            )
        )

        parsed_records: list[dict[str, Any]] = []
        primary_structure: PreparedStructure | None = None
        primary_s0: AmespGroundStateResult | None = None
        primary_s1: AmespExcitedStateResult | None = None
        source_bundle_completion_status = _bundle_completion_status_from_generated_artifacts(selected_artifacts)
        for artifact in artifact_records:
            prepared = self._load_prepared_structure_from_record(artifact, selected_artifacts)
            s0_result = self._parse_s0_from_existing_artifacts(artifact, prepared)
            s1_result = self._parse_s1_from_existing_artifacts(
                artifact,
                reference_energy=s0_result.final_energy_hartree,
                state_window=request.state_window,
            )
            manifold = _build_vertical_state_manifold_summary(s1_result)
            dominant_transitions = _summarize_dominant_transitions(s1_result)
            parsed_records.append(
                {
                    "snapshot_label": artifact.get("snapshot_label") or artifact.get("member_label"),
                    "target_angle_deg": artifact.get("target_angle_deg"),
                    "dihedral_atoms": artifact.get("dihedral_atoms"),
                    "conformer_rank": artifact.get("conformer_rank"),
                    "source_snapshot_status": artifact.get("snapshot_status") or "success",
                    "final_energy_hartree": s0_result.final_energy_hartree,
                    "first_excitation_energy_ev": s1_result.first_excitation_energy_ev,
                    "first_oscillator_strength": s1_result.first_oscillator_strength,
                    "state_count": s1_result.state_count,
                    "state_ordering": manifold,
                    "dominant_transitions": dominant_transitions or "not_available",
                    "ct_localization_proxy": "not_available",
                }
            )
            if primary_s0 is None or (
                s0_result.final_energy_hartree is not None
                and primary_s0.final_energy_hartree is not None
                and s0_result.final_energy_hartree < primary_s0.final_energy_hartree
            ):
                primary_structure = prepared
                primary_s0 = s0_result
                primary_s1 = s1_result

        if primary_structure is None or primary_s0 is None or primary_s1 is None:
            raise AmespExecutionError(
                "parse_failed",
                "Parse-only follow-up could not construct a reusable snapshot summary from the available artifacts.",
                status="failed",
                structured_results={
                    "executed_capability": "parse_snapshot_outputs",
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": True,
                },
            )

        missing_deliverables = []
        requested_lower = [item.lower() for item in request.deliverables]
        dominant_transitions_available = any(
            _record_has_dominant_transitions(record) for record in parsed_records
        )
        if any("dominant transition" in item for item in requested_lower) and not dominant_transitions_available:
            missing_deliverables.append("dominant transitions")
        if any(
            any(token in item for token in ("ct proxy", "charge-transfer", "charge transfer", "ct/localization"))
            for item in requested_lower
        ):
            missing_deliverables.append("CT/localization proxy")
        available_ct_surrogates = ["dominant_transitions"] if dominant_transitions_available else []
        route_summary = {
            "snapshot_count": len(parsed_records),
            "artifact_scope": artifact_scope,
            "artifact_source_round": source_round,
            "source_bundle_completion_status": source_bundle_completion_status,
            "artifact_reuse_note": "Parsed existing microscopic snapshot artifacts without generating new Amesp inputs.",
            "ct_proxy_availability": "partial_observable_only" if dominant_transitions_available else "not_available",
            "available_ct_surrogates": available_ct_surrogates,
            "state_window": list(request.state_window),
        }
        return AmespBaselineRunResult(
            route="artifact_parse_only",
            executed_capability="parse_snapshot_outputs",
            performed_new_calculations=False,
            reused_existing_artifacts=True,
            missing_deliverables=missing_deliverables,
            structure=primary_structure,
            s0=primary_s0,
            s1=primary_s1,
            parsed_snapshot_records=parsed_records,
            route_records=parsed_records,
            route_summary=route_summary,
            raw_step_results={
                "parse_snapshot_outputs": {
                    "artifact_scope": artifact_scope,
                    "artifact_source_round": source_round,
                    "state_window": list(request.state_window),
                    "parsed_record_count": len(parsed_records),
                }
            },
            generated_artifacts={
                "prepared_xyz_path": str(primary_structure.xyz_path),
                "prepared_sdf_path": str(primary_structure.sdf_path),
                "prepared_summary_path": str(primary_structure.summary_path),
                "source_round": source_round,
                "artifact_bundle_id": request.artifact_bundle_id,
                "artifact_bundle_kind": artifact_scope,
                "parsed_snapshot_record_count": len(parsed_records),
                "reused_snapshot_artifacts": artifact_records,
            },
        )

    def _execute_extract_ct_descriptors_from_bundle_route(
        self,
        *,
        request: MicroscopicToolRequest,
        available_artifacts: dict[str, Any] | None,
    ) -> AmespBaselineRunResult:
        selected_artifacts, artifact_scope, source_round, artifact_records = (
            self._resolve_artifact_bundle_records_for_analysis(
                request=request,
                available_artifacts=available_artifacts,
            )
        )

        descriptor_scope = list(request.descriptor_scope) or [
            "dominant_transitions",
            "ct_localization_proxy",
            "delta_dipole",
        ]
        parsed_records: list[dict[str, Any]] = []
        available_ct_surrogates: set[str] = set()
        primary_structure: PreparedStructure | None = None
        primary_s0: AmespGroundStateResult | None = None
        primary_s1: AmespExcitedStateResult | None = None
        source_bundle_completion_status = _bundle_completion_status_from_generated_artifacts(selected_artifacts)

        for artifact in artifact_records:
            prepared = self._load_prepared_structure_from_record(artifact, selected_artifacts)
            file_inventory = _artifact_record_file_inventory(artifact)
            source_file_availability = _artifact_record_file_availability(artifact)
            s0_result: AmespGroundStateResult | None = None
            s1_result: AmespExcitedStateResult | None = None
            dominant_transitions: list[dict[str, Any]] = []
            parse_notes: list[str] = []
            if source_file_availability.get("s0_aop_path"):
                try:
                    s0_result = self._parse_s0_from_existing_artifacts(artifact, prepared)
                except AmespExecutionError as exc:
                    parse_notes.append(f"s0_parse_unavailable: {exc.message}")
            if source_file_availability.get("s1_aop_path") and s0_result is not None:
                try:
                    s1_result = self._parse_s1_from_existing_artifacts(
                        artifact,
                        reference_energy=s0_result.final_energy_hartree,
                        state_window=request.state_window,
                    )
                    dominant_transitions = _summarize_dominant_transitions(s1_result)
                except AmespExecutionError as exc:
                    parse_notes.append(f"s1_parse_unavailable: {exc.message}")
            record_surrogates = _ct_surrogate_observables_from_artifact(artifact)
            if dominant_transitions:
                record_surrogates = sorted({*record_surrogates, "dominant_transitions"})
            available_ct_surrogates.update(record_surrogates)
            parsed_records.append(
                {
                    "snapshot_label": artifact.get("snapshot_label") or artifact.get("member_label"),
                    "target_angle_deg": artifact.get("target_angle_deg"),
                    "dihedral_atoms": artifact.get("dihedral_atoms"),
                    "conformer_rank": artifact.get("conformer_rank"),
                    "source_snapshot_status": artifact.get("snapshot_status") or "success",
                    "state_count": s1_result.state_count if s1_result is not None else None,
                    "ground_state_dipole_debye": (
                        s0_result.dipole_debye[3]
                        if s0_result is not None and s0_result.dipole_debye is not None
                        else None
                    ),
                    "mulliken_charge_count": (
                        len(s0_result.mulliken_charges)
                        if s0_result is not None
                        else 0
                    ),
                    "dominant_transitions": dominant_transitions or "not_available",
                    "ct_localization_proxy": "not_available",
                    "source_file_availability": source_file_availability,
                    "available_ct_surrogates": record_surrogates,
                    "inspection_notes": parse_notes,
                }
            )
            if primary_structure is None:
                primary_structure = prepared
                primary_s0 = s0_result
                primary_s1 = s1_result

        if primary_structure is None:
            raise AmespExecutionError(
                "parse_failed",
                "CT-descriptor extraction could not load any reusable prepared structure from the selected bundle.",
                status="failed",
                structured_results={
                    "executed_capability": "extract_ct_descriptors_from_bundle",
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": True,
                },
            )

        missing_ct_descriptors = []
        dominant_transitions_available = any(
            _record_has_dominant_transitions(record) for record in parsed_records
        )
        for descriptor in descriptor_scope:
            normalized = descriptor.strip().lower().replace("-", "_").replace(" ", "_")
            if normalized == "dominant_transitions" and dominant_transitions_available:
                continue
            missing_ct_descriptors.append(descriptor)
        missing_ct_descriptors = list(dict.fromkeys(missing_ct_descriptors))
        missing_deliverables = [_humanize_descriptor_name(item) for item in missing_ct_descriptors]
        route_summary = {
            "artifact_scope": artifact_scope,
            "artifact_source_round": source_round,
            "source_bundle_completion_status": source_bundle_completion_status,
            "descriptor_scope": descriptor_scope,
            "ct_proxy_availability": "partial_observable_only" if available_ct_surrogates else "not_available",
            "available_ct_surrogates": sorted(available_ct_surrogates),
            "missing_ct_descriptors": missing_ct_descriptors,
            "artifact_reuse_note": "Inspected an existing artifact bundle for bounded CT-descriptor surrogates without generating new Amesp inputs.",
            "state_window": list(request.state_window),
        }
        return AmespBaselineRunResult(
            route="artifact_parse_only",
            executed_capability="extract_ct_descriptors_from_bundle",
            performed_new_calculations=False,
            reused_existing_artifacts=True,
            missing_deliverables=missing_deliverables,
            structure=primary_structure,
            s0=primary_s0,
            s1=primary_s1,
            parsed_snapshot_records=parsed_records,
            route_records=parsed_records,
            route_summary=route_summary,
            raw_step_results={
                "extract_ct_descriptors_from_bundle": {
                    "artifact_scope": artifact_scope,
                    "artifact_source_round": source_round,
                    "descriptor_scope": descriptor_scope,
                    "parsed_record_count": len(parsed_records),
                }
            },
            generated_artifacts={
                "prepared_xyz_path": str(primary_structure.xyz_path),
                "prepared_sdf_path": str(primary_structure.sdf_path),
                "prepared_summary_path": str(primary_structure.summary_path),
                "source_round": source_round,
                "artifact_bundle_id": request.artifact_bundle_id,
                "artifact_bundle_kind": artifact_scope,
                "parsed_snapshot_record_count": len(parsed_records),
                "reused_snapshot_artifacts": artifact_records,
            },
        )

    def _execute_extract_geometry_descriptors_from_bundle_route(
        self,
        *,
        request: MicroscopicToolRequest,
        available_artifacts: dict[str, Any] | None,
    ) -> AmespBaselineRunResult:
        selected_artifacts, artifact_scope, source_round, artifact_records = (
            self._resolve_artifact_bundle_records_for_analysis(
                request=request,
                available_artifacts=available_artifacts,
            )
        )

        descriptor_scope = list(request.descriptor_scope) or [
            "intramolecular_hbond_candidates",
            "local_planarity_proxy",
        ]
        parsed_records: list[dict[str, Any]] = []
        available_geometry_descriptors: set[str] = set()
        primary_structure: PreparedStructure | None = None
        geometry_source_families: set[str] = set()
        source_bundle_completion_status = _bundle_completion_status_from_generated_artifacts(selected_artifacts)

        for artifact in artifact_records:
            prepared = self._load_prepared_structure_from_record(artifact, selected_artifacts)
            geometry_payload = _geometry_payload_from_artifact_record(artifact, prepared)
            geometry_source_families.add(str(geometry_payload["geometry_source"]))
            geometry_record = _extract_intramolecular_geometry_record(
                prepared=prepared,
                symbols=geometry_payload["symbols"],
                coordinates=geometry_payload["coordinates"],
            )
            available_geometry_descriptors.update(geometry_record["available_geometry_descriptors"])
            parsed_records.append(
                {
                    "snapshot_label": artifact.get("snapshot_label") or artifact.get("member_label"),
                    "target_angle_deg": artifact.get("target_angle_deg"),
                    "dihedral_atoms": artifact.get("dihedral_atoms"),
                    "conformer_rank": artifact.get("conformer_rank"),
                    "source_snapshot_status": artifact.get("snapshot_status") or "success",
                    "geometry_source": geometry_payload["geometry_source"],
                    "donor_atom_count": geometry_record["donor_atom_count"],
                    "acceptor_atom_count": geometry_record["acceptor_atom_count"],
                    "intramolecular_hbond_candidates": geometry_record["intramolecular_hbond_candidates"],
                    "best_intramolecular_hbond": geometry_record["best_intramolecular_hbond"],
                    "local_planarity_proxy": geometry_record["local_planarity_proxy"],
                    "has_hbond_like_candidate": geometry_record["has_hbond_like_candidate"],
                    "available_geometry_descriptors": geometry_record["available_geometry_descriptors"],
                }
            )
            if primary_structure is None:
                primary_structure = prepared

        if primary_structure is None:
            raise AmespExecutionError(
                "parse_failed",
                "Geometry-descriptor extraction could not load any reusable prepared structure from the selected bundle.",
                status="failed",
                structured_results={
                    "executed_capability": "extract_geometry_descriptors_from_bundle",
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": True,
                },
            )

        missing_geometry_descriptors = []
        for descriptor in descriptor_scope:
            normalized = descriptor.strip().lower().replace("-", "_").replace(" ", "_")
            if normalized in available_geometry_descriptors:
                continue
            missing_geometry_descriptors.append(descriptor)
        missing_geometry_descriptors = list(dict.fromkeys(missing_geometry_descriptors))
        missing_deliverables = [_humanize_descriptor_name(item) for item in missing_geometry_descriptors]
        hbond_like_records = sum(1 for record in parsed_records if record.get("has_hbond_like_candidate"))
        total_candidates = sum(
            len(list(record.get("intramolecular_hbond_candidates") or []))
            for record in parsed_records
        )
        route_summary = {
            "artifact_scope": artifact_scope,
            "artifact_source_round": source_round,
            "source_bundle_completion_status": source_bundle_completion_status,
            "descriptor_scope": descriptor_scope,
            "geometry_proxy_availability": "available" if available_geometry_descriptors else "not_available",
            "available_geometry_descriptors": sorted(available_geometry_descriptors),
            "missing_geometry_descriptors": missing_geometry_descriptors,
            "geometry_source_families": sorted(geometry_source_families),
            "records_with_hbond_like_candidate": hbond_like_records,
            "intramolecular_hbond_candidate_count": total_candidates,
            "artifact_reuse_note": "Inspected an existing artifact bundle for bounded intramolecular geometry descriptors without generating new Amesp inputs.",
        }
        return AmespBaselineRunResult(
            route="artifact_parse_only",
            executed_capability="extract_geometry_descriptors_from_bundle",
            performed_new_calculations=False,
            reused_existing_artifacts=True,
            missing_deliverables=missing_deliverables,
            structure=primary_structure,
            s0=None,
            s1=None,
            parsed_snapshot_records=parsed_records,
            route_records=parsed_records,
            route_summary=route_summary,
            raw_step_results={
                "extract_geometry_descriptors_from_bundle": {
                    "artifact_scope": artifact_scope,
                    "artifact_source_round": source_round,
                    "descriptor_scope": descriptor_scope,
                    "parsed_record_count": len(parsed_records),
                }
            },
            generated_artifacts={
                "prepared_xyz_path": str(primary_structure.xyz_path),
                "prepared_sdf_path": str(primary_structure.sdf_path),
                "prepared_summary_path": str(primary_structure.summary_path),
                "source_round": source_round,
                "artifact_bundle_id": request.artifact_bundle_id,
                "artifact_bundle_kind": artifact_scope,
                "parsed_snapshot_record_count": len(parsed_records),
                "reused_snapshot_artifacts": artifact_records,
            },
        )

    def _execute_inspect_raw_artifact_bundle_route(
        self,
        *,
        request: MicroscopicToolRequest,
        available_artifacts: dict[str, Any] | None,
    ) -> AmespBaselineRunResult:
        selected_artifacts, artifact_scope, source_round, artifact_records = (
            self._resolve_artifact_bundle_records_for_analysis(
                request=request,
                available_artifacts=available_artifacts,
            )
        )

        requested_scope = list(request.requested_observable_scope)
        primary_structure: PreparedStructure | None = None
        file_inventory: set[str] = set()
        extractable_observables: set[str] = set()
        parsed_records: list[dict[str, Any]] = []
        source_bundle_completion_status = _bundle_completion_status_from_generated_artifacts(selected_artifacts)
        source_bundle_partial_message = str(selected_artifacts.get("bundle_partial_failure_message") or "").strip()
        for artifact in artifact_records:
            prepared = self._load_prepared_structure_from_record(artifact, selected_artifacts)
            if primary_structure is None:
                primary_structure = prepared
            record_files = _artifact_record_file_inventory(artifact)
            file_inventory.update(record_files)
            record_observables = _extractable_observables_from_artifact(artifact)
            extractable_observables.update(record_observables)
            inspection_notes: list[str] = []
            if source_bundle_completion_status == "partial":
                inspection_notes.append(
                    "Source artifact bundle is partial; raw-file coverage may be incomplete."
                )
            if artifact.get("snapshot_status") == "partial":
                inspection_notes.append(
                    "This snapshot record is partial and may expose only a subset of expected Amesp files."
                )
            parsed_records.append(
                {
                    "snapshot_label": artifact.get("snapshot_label") or artifact.get("member_label"),
                    "target_angle_deg": artifact.get("target_angle_deg"),
                    "dihedral_atoms": artifact.get("dihedral_atoms"),
                    "conformer_rank": artifact.get("conformer_rank"),
                    "source_snapshot_status": artifact.get("snapshot_status") or "success",
                    "available_raw_files": record_files,
                    "extractable_observables": record_observables,
                    "inspection_notes": inspection_notes,
                }
            )

        if primary_structure is None:
            raise AmespExecutionError(
                "parse_failed",
                "Raw artifact inspection could not load any reusable prepared structure from the selected bundle.",
                status="failed",
                structured_results={
                    "executed_capability": "inspect_raw_artifact_bundle",
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": True,
                },
            )

        missing_observables = [
            observable for observable in requested_scope if observable not in extractable_observables
        ]
        missing_deliverables = (
            [f"observable: {item}" for item in missing_observables]
            if missing_observables
            else []
        )
        route_summary = {
            "artifact_scope": artifact_scope,
            "artifact_source_round": source_round,
            "source_bundle_completion_status": source_bundle_completion_status,
            "inspection_status": "completed",
            "available_raw_files": sorted(file_inventory),
            "extractable_observables": sorted(extractable_observables),
            "missing_observables": missing_observables,
            "inspection_notes": (
                ["Requested observable scope exceeded current raw-file coverage."]
                if missing_observables
                else ["Requested observable scope is covered by current raw-file inventory."]
            ),
            "artifact_reuse_note": "Inspected an existing artifact bundle without generating new Amesp inputs.",
        }
        if source_bundle_completion_status == "partial":
            route_summary["inspection_notes"].append(
                "Source artifact bundle is partial; inspection results may reflect incomplete snapshot coverage."
            )
            if source_bundle_partial_message:
                route_summary["inspection_notes"].append(source_bundle_partial_message)
        return AmespBaselineRunResult(
            route="artifact_parse_only",
            executed_capability="inspect_raw_artifact_bundle",
            performed_new_calculations=False,
            reused_existing_artifacts=True,
            missing_deliverables=missing_deliverables,
            structure=primary_structure,
            s0=None,
            s1=None,
            parsed_snapshot_records=parsed_records,
            route_records=parsed_records,
            route_summary=route_summary,
            raw_step_results={
                "inspect_raw_artifact_bundle": {
                    "artifact_scope": artifact_scope,
                    "artifact_source_round": source_round,
                    "requested_observable_scope": requested_scope,
                    "parsed_record_count": len(parsed_records),
                }
            },
            generated_artifacts={
                "prepared_xyz_path": str(primary_structure.xyz_path),
                "prepared_sdf_path": str(primary_structure.sdf_path),
                "prepared_summary_path": str(primary_structure.summary_path),
                "source_round": source_round,
                "artifact_bundle_id": request.artifact_bundle_id,
                "artifact_bundle_kind": artifact_scope,
                "parsed_snapshot_record_count": len(parsed_records),
                "reused_snapshot_artifacts": artifact_records,
            },
        )

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
        state_window: Sequence[int] | None,
        executed_capability: MicroscopicCapabilityName,
        performed_new_calculations: bool,
        reused_existing_artifacts: bool,
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
                state_window=state_window,
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
            executed_capability=executed_capability,
            performed_new_calculations=performed_new_calculations,
            reused_existing_artifacts=reused_existing_artifacts,
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
        state_window: Sequence[int] | None = None,
    ) -> tuple[AmespExcitedStateResult, dict[str, Any], dict[str, Any]]:
        raw_results: dict[str, Any] = {}
        generated_artifacts: dict[str, Any] = {}
        requested_nstates = max((int(index) for index in state_window), default=self._s1_nstates)
        s1_outcome, s1_text = self._run_step(
            step_id="s1_vertical_excitation",
            label=f"{label}_s1",
            workdir=workdir,
            keywords=self._build_s1_keywords(),
            block_lines=[
                ("ope", ["out 1"]),
                ("posthf", [f"nstates {requested_nstates}", f"tout {self._td_tout}"]),
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
        if state_window:
            requested_state_indices = {int(index) for index in state_window}
            excited_states = [state for state in excited_states if state.state_index in requested_state_indices]
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
        try:
            atoms, prepared = self._structure_preparer(
                StructurePrepRequest(
                    smiles=smiles,
                    label=label,
                    workdir=structure_dir,
                )
            )
        except StructurePrepError as exc:
            error_payload = exc.to_payload()
            self._emit_probe(
                progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
                stage="structure_prep",
                status="failed",
                details={
                    "source": "smiles_to_3d",
                    "workdir": str(structure_dir),
                    "error": error_payload,
                },
            )
            raise AmespExecutionError(
                "precondition_missing",
                f"Structure preparation failed: {exc.message}",
                raw_results={"structure_prep_error": error_payload},
                structured_results={
                    "structure_prep_error": error_payload,
                    "performed_new_calculations": False,
                    "reused_existing_artifacts": False,
                    "missing_deliverables": ["prepared_structure"],
                },
                status="failed",
            ) from exc
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

    def _load_prepared_structure_from_record(
        self,
        artifact_record: dict[str, Any],
        available_artifacts: dict[str, Any],
    ) -> PreparedStructure:
        summary_path_raw = artifact_record.get("prepared_summary_path") or available_artifacts.get("prepared_summary_path")
        if not summary_path_raw:
            raise AmespExecutionError(
                "precondition_missing",
                "Reusable snapshot artifacts did not expose a prepared structure summary path.",
                status="failed",
            )
        summary_path = Path(str(summary_path_raw))
        if not summary_path.exists():
            raise AmespExecutionError(
                "precondition_missing",
                f"Reusable prepared structure summary was missing at {summary_path}.",
                status="failed",
            )
        return PreparedStructure.model_validate(json.loads(summary_path.read_text(encoding="utf-8")))

    def _parse_s0_from_existing_artifacts(
        self,
        artifact_record: dict[str, Any],
        prepared: PreparedStructure,
    ) -> AmespGroundStateResult:
        aop_path_raw = artifact_record.get("s0_aop_path")
        if not aop_path_raw:
            raise AmespExecutionError(
                "precondition_missing",
                "Reusable snapshot artifacts did not expose an S0 AOP path.",
                status="failed",
            )
        aop_path = Path(str(aop_path_raw))
        if not aop_path.exists():
            raise AmespExecutionError(
                "precondition_missing",
                f"Reusable S0 AOP file was missing at {aop_path}.",
                status="failed",
            )
        s0_text = aop_path.read_text(encoding="utf-8", errors="replace")
        symbols, coordinates = _parse_final_geometry(s0_text)
        if not symbols or not coordinates:
            raise AmespExecutionError(
                "parse_failed",
                f"Reusable S0 artifact {aop_path.name} did not expose a parseable final geometry.",
                status="failed",
            )
        prepared_coordinates = _read_xyz_coordinates(prepared.xyz_path)
        return AmespGroundStateResult(
            final_energy_hartree=_parse_final_energy(s0_text),
            dipole_debye=_parse_last_dipole(s0_text),
            mulliken_charges=_parse_last_mulliken_charges(s0_text),
            homo_lumo_gap_ev=_parse_homo_lumo_gap_ev(s0_text),
            geometry_atom_count=len(symbols),
            geometry_xyz_path=str(prepared.xyz_path),
            rmsd_from_prepared_structure_angstrom=_compute_rmsd(prepared_coordinates, coordinates),
        )

    def _parse_s1_from_existing_artifacts(
        self,
        artifact_record: dict[str, Any],
        *,
        reference_energy: float,
        state_window: Sequence[int] | None,
    ) -> AmespExcitedStateResult:
        aop_path_raw = artifact_record.get("s1_aop_path")
        if not aop_path_raw:
            raise AmespExecutionError(
                "precondition_missing",
                "Reusable snapshot artifacts did not expose an S1 AOP path.",
                status="failed",
            )
        aop_path = Path(str(aop_path_raw))
        if not aop_path.exists():
            raise AmespExecutionError(
                "precondition_missing",
                f"Reusable S1 AOP file was missing at {aop_path}.",
                status="failed",
            )
        s1_text = aop_path.read_text(encoding="utf-8", errors="replace")
        excited_states = _parse_excited_states(s1_text, reference_energy_hartree=reference_energy)
        if state_window:
            requested_state_indices = {int(index) for index in state_window}
            excited_states = [state for state in excited_states if state.state_index in requested_state_indices]
        if not excited_states:
            raise AmespExecutionError(
                "parse_failed",
                f"Reusable S1 artifact {aop_path.name} did not expose parseable excited states.",
                status="failed",
            )
        return AmespExcitedStateResult(
            excited_states=excited_states,
            first_excitation_energy_ev=excited_states[0].excitation_energy_ev,
            first_oscillator_strength=excited_states[0].oscillator_strength,
            state_count=len(excited_states),
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
    dominant_transition_map = _parse_dominant_transitions_by_state(text)
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
                    dominant_transitions=dominant_transition_map.get(int(state_index), []),
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
                dominant_transitions=dominant_transition_map.get(index, []),
            )
        )
    return states


def _parse_dominant_transitions_by_state(text: str) -> dict[int, list[dict[str, Any]]]:
    state_pattern = re.compile(
        r"State\s+(\d+)\s*:\s*E\s*=\s*[-+]?\d+\.\d+\s+eV(?P<body>.*?)(?=^\s*State\s+\d+\s*:|^\s*Time of TDDFT|^\s*=+\s*$|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    transition_pattern = re.compile(
        r"^\s*(\d+)\s*-->\s*(\d+)\s*([-+]?\d+\.\d+)",
        re.MULTILINE,
    )

    transitions_by_state: dict[int, list[dict[str, Any]]] = {}
    for match in state_pattern.finditer(text):
        state_index = int(match.group(1))
        transitions: list[dict[str, Any]] = []
        for occupied, virtual, coefficient in transition_pattern.findall(match.group("body")):
            transitions.append(
                {
                    "occupied_orbital": int(occupied),
                    "virtual_orbital": int(virtual),
                    "coefficient": round(float(coefficient), 7),
                }
            )
        if transitions:
            transitions_by_state[state_index] = transitions
    return transitions_by_state


def _summarize_dominant_transitions(
    s1_result: AmespExcitedStateResult,
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for state in s1_result.excited_states:
        if not state.dominant_transitions:
            continue
        summaries.append(
            {
                "state_index": state.state_index,
                "excitation_energy_ev": state.excitation_energy_ev,
                "oscillator_strength": state.oscillator_strength,
                "transitions": state.dominant_transitions,
            }
        )
    return summaries


def _record_has_dominant_transitions(record: dict[str, Any]) -> bool:
    value = record.get("dominant_transitions")
    return bool(value and value != "not_available")


_COVALENT_RADII_ANGSTROM: dict[str, float] = {
    "H": 0.31,
    "B": 0.85,
    "C": 0.76,
    "N": 0.71,
    "O": 0.66,
    "F": 0.57,
    "P": 1.07,
    "S": 1.05,
    "Cl": 1.02,
    "Br": 1.2,
    "I": 1.39,
}


def _geometry_payload_from_artifact_record(
    artifact_record: dict[str, Any],
    prepared: PreparedStructure,
) -> dict[str, Any]:
    s0_aop_path_raw = artifact_record.get("s0_aop_path")
    if s0_aop_path_raw:
        aop_path = Path(str(s0_aop_path_raw))
        if aop_path.exists():
            s0_text = aop_path.read_text(encoding="utf-8", errors="replace")
            symbols, coordinates = _parse_final_geometry(s0_text)
            if symbols and coordinates:
                return {
                    "symbols": symbols,
                    "coordinates": coordinates,
                    "geometry_source": "s0_optimized_aop",
                }
    symbols, coordinates = _read_xyz_symbols_and_coordinates(prepared.xyz_path)
    if symbols and coordinates:
        return {
            "symbols": symbols,
            "coordinates": coordinates,
            "geometry_source": "prepared_xyz",
        }
    raise AmespExecutionError(
        "parse_failed",
        "Reusable geometry-descriptor extraction could not load parseable coordinates from the selected artifact record.",
        status="failed",
    )


def _extract_intramolecular_geometry_record(
    *,
    prepared: PreparedStructure,
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
) -> dict[str, Any]:
    del prepared
    adjacency = _infer_bond_adjacency(symbols, coordinates)
    donor_indices = [
        atom_index
        for atom_index, symbol in enumerate(symbols)
        if symbol == "O" and any(symbols[neighbor] == "H" for neighbor in adjacency.get(atom_index, set()))
    ]
    acceptor_indices = [
        atom_index
        for atom_index, symbol in enumerate(symbols)
        if symbol in {"N", "O"}
    ]

    candidates: list[dict[str, Any]] = []
    for donor_index in donor_indices:
        hydrogen_neighbors = [neighbor for neighbor in adjacency.get(donor_index, set()) if symbols[neighbor] == "H"]
        for hydrogen_index in hydrogen_neighbors:
            for acceptor_index in acceptor_indices:
                if acceptor_index in {donor_index, hydrogen_index}:
                    continue
                path_length = _shortest_path_length(adjacency, donor_index, acceptor_index)
                if path_length is not None and path_length < 3:
                    continue
                donor_acceptor_distance = _distance(
                    coordinates[donor_index],
                    coordinates[acceptor_index],
                )
                hydrogen_acceptor_distance = _distance(
                    coordinates[hydrogen_index],
                    coordinates[acceptor_index],
                )
                dha_angle = _angle_degrees(
                    coordinates[donor_index],
                    coordinates[hydrogen_index],
                    coordinates[acceptor_index],
                )
                local_planarity_rmsd = _local_fragment_planarity_rmsd(
                    symbols=symbols,
                    coordinates=coordinates,
                    adjacency=adjacency,
                    donor_index=donor_index,
                    hydrogen_index=hydrogen_index,
                    acceptor_index=acceptor_index,
                )
                hbond_like_geometry = (
                    hydrogen_acceptor_distance <= 2.5
                    and donor_acceptor_distance <= 3.2
                    and dha_angle >= 110.0
                )
                candidates.append(
                    {
                        "donor_atom_index": donor_index,
                        "hydrogen_atom_index": hydrogen_index,
                        "acceptor_atom_index": acceptor_index,
                        "topological_separation_bonds": path_length,
                        "donor_acceptor_distance_angstrom": round(donor_acceptor_distance, 6),
                        "hydrogen_acceptor_distance_angstrom": round(hydrogen_acceptor_distance, 6),
                        "donor_hydrogen_acceptor_angle_deg": round(dha_angle, 6),
                        "local_planarity_rmsd_angstrom": (
                            round(local_planarity_rmsd, 6) if local_planarity_rmsd is not None else None
                        ),
                        "hbond_like_geometry": hbond_like_geometry,
                    }
                )

    candidates.sort(
        key=lambda item: (
            0 if item["hbond_like_geometry"] else 1,
            float(item["hydrogen_acceptor_distance_angstrom"]),
            float(item["donor_acceptor_distance_angstrom"]),
        )
    )
    best_candidate = candidates[0] if candidates else None
    available_geometry_descriptors = [
        "geometry_source",
        "intramolecular_hbond_candidates",
        "best_intramolecular_hbond",
    ]
    if best_candidate is not None and best_candidate.get("local_planarity_rmsd_angstrom") is not None:
        available_geometry_descriptors.append("local_planarity_proxy")
    return {
        "donor_atom_count": len(donor_indices),
        "acceptor_atom_count": len(acceptor_indices),
        "intramolecular_hbond_candidates": candidates,
        "best_intramolecular_hbond": best_candidate,
        "local_planarity_proxy": (
            best_candidate.get("local_planarity_rmsd_angstrom")
            if isinstance(best_candidate, dict)
            else None
        ),
        "has_hbond_like_candidate": bool(best_candidate and best_candidate.get("hbond_like_geometry")),
        "available_geometry_descriptors": available_geometry_descriptors,
    }


def _infer_bond_adjacency(
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
) -> dict[int, set[int]]:
    adjacency = {index: set() for index in range(len(symbols))}
    for left_index in range(len(symbols)):
        for right_index in range(left_index + 1, len(symbols)):
            cutoff = _bond_cutoff_angstrom(symbols[left_index], symbols[right_index])
            if cutoff is None:
                continue
            if _distance(coordinates[left_index], coordinates[right_index]) <= cutoff:
                adjacency[left_index].add(right_index)
                adjacency[right_index].add(left_index)
    return adjacency


def _bond_cutoff_angstrom(left_symbol: str, right_symbol: str) -> float | None:
    left_radius = _COVALENT_RADII_ANGSTROM.get(left_symbol)
    right_radius = _COVALENT_RADII_ANGSTROM.get(right_symbol)
    if left_radius is None or right_radius is None:
        return None
    return 1.25 * (left_radius + right_radius) + 0.15


def _shortest_path_length(
    adjacency: dict[int, set[int]],
    start_index: int,
    end_index: int,
) -> int | None:
    if start_index == end_index:
        return 0
    frontier = [(start_index, 0)]
    visited = {start_index}
    while frontier:
        current_index, depth = frontier.pop(0)
        for neighbor in adjacency.get(current_index, set()):
            if neighbor == end_index:
                return depth + 1
            if neighbor in visited:
                continue
            visited.add(neighbor)
            frontier.append((neighbor, depth + 1))
    return None


def _distance(left: Sequence[float], right: Sequence[float]) -> float:
    return math.sqrt(
        (float(left[0]) - float(right[0])) ** 2
        + (float(left[1]) - float(right[1])) ** 2
        + (float(left[2]) - float(right[2])) ** 2
    )


def _angle_degrees(
    left: Sequence[float],
    vertex: Sequence[float],
    right: Sequence[float],
) -> float:
    vector_a = [
        float(left[0]) - float(vertex[0]),
        float(left[1]) - float(vertex[1]),
        float(left[2]) - float(vertex[2]),
    ]
    vector_b = [
        float(right[0]) - float(vertex[0]),
        float(right[1]) - float(vertex[1]),
        float(right[2]) - float(vertex[2]),
    ]
    norm_a = math.sqrt(sum(component * component for component in vector_a))
    norm_b = math.sqrt(sum(component * component for component in vector_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    cosine = sum(a * b for a, b in zip(vector_a, vector_b)) / (norm_a * norm_b)
    cosine = max(-1.0, min(1.0, cosine))
    return math.degrees(math.acos(cosine))


def _local_fragment_planarity_rmsd(
    *,
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    adjacency: dict[int, set[int]],
    donor_index: int,
    hydrogen_index: int,
    acceptor_index: int,
) -> float | None:
    donor_neighbor = _nearest_heavy_neighbor(
        atom_index=donor_index,
        excluded_indices={hydrogen_index, acceptor_index},
        symbols=symbols,
        coordinates=coordinates,
        adjacency=adjacency,
    )
    acceptor_neighbor = _nearest_heavy_neighbor(
        atom_index=acceptor_index,
        excluded_indices={donor_index, hydrogen_index},
        symbols=symbols,
        coordinates=coordinates,
        adjacency=adjacency,
    )
    fragment_indices: list[int] = []
    for atom_index in (donor_neighbor, donor_index, acceptor_index, acceptor_neighbor):
        if atom_index is None or atom_index in fragment_indices:
            continue
        fragment_indices.append(atom_index)
    if len(fragment_indices) < 3:
        return None
    plane_points = [coordinates[index] for index in fragment_indices[:3]]
    normal = _plane_normal(plane_points[0], plane_points[1], plane_points[2])
    if normal is None:
        return None
    distances = [_point_to_plane_distance(coordinates[index], plane_points[0], normal) for index in fragment_indices]
    return math.sqrt(sum(distance * distance for distance in distances) / len(distances))


def _nearest_heavy_neighbor(
    *,
    atom_index: int,
    excluded_indices: set[int],
    symbols: Sequence[str],
    coordinates: Sequence[Sequence[float]],
    adjacency: dict[int, set[int]],
) -> int | None:
    best_index: int | None = None
    best_distance: float | None = None
    for neighbor in adjacency.get(atom_index, set()):
        if neighbor in excluded_indices or symbols[neighbor] == "H":
            continue
        distance = _distance(coordinates[atom_index], coordinates[neighbor])
        if best_distance is None or distance < best_distance:
            best_index = neighbor
            best_distance = distance
    return best_index


def _plane_normal(
    left: Sequence[float],
    middle: Sequence[float],
    right: Sequence[float],
) -> tuple[float, float, float] | None:
    vector_a = (
        float(middle[0]) - float(left[0]),
        float(middle[1]) - float(left[1]),
        float(middle[2]) - float(left[2]),
    )
    vector_b = (
        float(right[0]) - float(left[0]),
        float(right[1]) - float(left[1]),
        float(right[2]) - float(left[2]),
    )
    normal = (
        vector_a[1] * vector_b[2] - vector_a[2] * vector_b[1],
        vector_a[2] * vector_b[0] - vector_a[0] * vector_b[2],
        vector_a[0] * vector_b[1] - vector_a[1] * vector_b[0],
    )
    norm = math.sqrt(sum(component * component for component in normal))
    if norm <= 1e-8:
        return None
    return (normal[0] / norm, normal[1] / norm, normal[2] / norm)


def _point_to_plane_distance(
    point: Sequence[float],
    plane_point: Sequence[float],
    plane_normal: Sequence[float],
) -> float:
    return abs(
        (float(point[0]) - float(plane_point[0])) * float(plane_normal[0])
        + (float(point[1]) - float(plane_point[1])) * float(plane_normal[1])
        + (float(point[2]) - float(plane_point[2])) * float(plane_normal[2])
    )


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


def _artifact_record_file_availability(artifact_record: dict[str, Any]) -> dict[str, bool]:
    relevant_keys = [
        "prepared_xyz_path",
        "prepared_sdf_path",
        "prepared_summary_path",
        "s0_aop_path",
        "s1_aop_path",
        "s0_stdout_path",
        "s1_stdout_path",
        "s0_stderr_path",
        "s1_stderr_path",
        "s0_mo_path",
        "s1_mo_path",
    ]
    availability: dict[str, bool] = {}
    for key in relevant_keys:
        value = artifact_record.get(key)
        availability[key] = bool(value and Path(str(value)).exists())
    return availability


def _artifact_record_file_inventory(artifact_record: dict[str, Any]) -> list[str]:
    return sorted(key for key, present in _artifact_record_file_availability(artifact_record).items() if present)


def _extractable_observables_from_artifact(artifact_record: dict[str, Any]) -> list[str]:
    availability = _artifact_record_file_availability(artifact_record)
    observables: set[str] = set()
    if availability.get("s0_aop_path"):
        observables.update(
            {
                "ground_state_energy",
                "ground_state_dipole",
                "mulliken_charges",
                "homo_lumo_gap",
                "optimized_geometry",
            }
        )
    if availability.get("prepared_xyz_path"):
        observables.update(
            {
                "intramolecular_hbond_geometry",
                "local_planarity_proxy",
            }
        )
    if availability.get("s1_aop_path"):
        observables.update(
            {
                "vertical_excitation_energies",
                "oscillator_strengths",
                "state_ordering",
                "dominant_transitions",
            }
        )
    if availability.get("s0_mo_path") or availability.get("s1_mo_path"):
        observables.add("molecular_orbital_files")
    if availability.get("s0_stdout_path") or availability.get("s1_stdout_path"):
        observables.add("stdout_logs")
    return sorted(observables)


def _ct_surrogate_observables_from_artifact(artifact_record: dict[str, Any]) -> list[str]:
    observables = set(_extractable_observables_from_artifact(artifact_record))
    surrogates: set[str] = set()
    if "ground_state_dipole" in observables:
        surrogates.add("ground_state_dipole")
    if "mulliken_charges" in observables:
        surrogates.add("mulliken_charges")
    if "vertical_excitation_energies" in observables:
        surrogates.add("vertical_excitation_energies")
    if "oscillator_strengths" in observables:
        surrogates.add("oscillator_strengths")
    if "state_ordering" in observables:
        surrogates.add("state_ordering")
    if "dominant_transitions" in observables:
        surrogates.add("dominant_transitions")
    return sorted(surrogates)


def _humanize_descriptor_name(name: str) -> str:
    normalized = name.strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "dominant_transitions": "dominant transitions",
        "ct_localization_proxy": "CT/localization proxy",
        "delta_dipole": "delta dipole",
        "intramolecular_hbond_candidates": "intramolecular H-bond candidates",
        "best_intramolecular_hbond": "best intramolecular H-bond",
        "local_planarity_proxy": "local planarity proxy",
    }
    return mapping.get(normalized, name.replace("_", " "))


def _artifact_scope_from_bundle_id(bundle_id: str) -> str:
    lowered = bundle_id.lower()
    if lowered.endswith("_torsion_snapshots"):
        return "torsion_snapshots"
    if lowered.endswith("_conformer_bundle"):
        return "conformer_bundle"
    if lowered.endswith("_baseline_bundle"):
        return "baseline_bundle"
    return "latest_bundle"


def _bundle_completion_status_from_generated_artifacts(
    generated_artifacts: dict[str, Any],
) -> ArtifactBundleCompletionStatus:
    status = str(generated_artifacts.get("bundle_completion_status") or "").strip().lower()
    if status == "partial":
        return "partial"
    snapshot_artifacts = list(generated_artifacts.get("snapshot_artifacts") or [])
    if any(str(item.get("snapshot_status") or "").strip().lower() == "partial" for item in snapshot_artifacts):
        return "partial"
    return "complete"


def _snapshot_artifact_record_from_generated_artifacts(
    *,
    snapshot: dict[str, Any],
    generated_artifacts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "snapshot_label": snapshot["snapshot_label"],
        "dihedral_atoms": snapshot["dihedral_atoms"],
        "target_angle_deg": snapshot["target_angle_deg"],
        "snapshot_status": "success",
        "prepared_xyz_path": generated_artifacts.get("prepared_xyz_path"),
        "prepared_summary_path": generated_artifacts.get("prepared_summary_path"),
        "s0_aop_path": generated_artifacts.get("s0_aop_path") or generated_artifacts.get("s0_singlepoint_aop_path"),
        "s1_aop_path": generated_artifacts.get("s1_aop_path"),
        "s0_stdout_path": generated_artifacts.get("s0_stdout_path") or generated_artifacts.get("s0_singlepoint_stdout_path"),
        "s1_stdout_path": generated_artifacts.get("s1_stdout_path"),
        "s0_mo_path": generated_artifacts.get("s0_mo_path") or generated_artifacts.get("s0_singlepoint_mo_path"),
        "s1_mo_path": generated_artifacts.get("s1_mo_path"),
    }


def _snapshot_artifact_record_from_partial_error(
    *,
    snapshot: dict[str, Any],
    generated_artifacts: dict[str, Any],
    failure_code: str,
    failure_message: str,
) -> dict[str, Any]:
    step_id = str(generated_artifacts.get("step_id") or "").strip()
    s1_aop_path = generated_artifacts.get("s1_aop_path")
    s1_stdout_path = generated_artifacts.get("s1_stdout_path")
    s1_mo_path = generated_artifacts.get("s1_mo_path")
    if step_id == "s1_vertical_excitation":
        s1_aop_path = s1_aop_path or generated_artifacts.get("aop_path")
        s1_stdout_path = s1_stdout_path or generated_artifacts.get("stdout_path")
        s1_mo_path = s1_mo_path or generated_artifacts.get("mo_path")
    return {
        "snapshot_label": snapshot["snapshot_label"],
        "dihedral_atoms": snapshot["dihedral_atoms"],
        "target_angle_deg": snapshot["target_angle_deg"],
        "snapshot_status": "partial",
        "failure_code": failure_code,
        "failure_message": failure_message,
        "prepared_xyz_path": generated_artifacts.get("prepared_xyz_path"),
        "prepared_summary_path": generated_artifacts.get("prepared_summary_path"),
        "s0_aop_path": generated_artifacts.get("s0_aop_path") or generated_artifacts.get("s0_singlepoint_aop_path"),
        "s1_aop_path": s1_aop_path,
        "s0_stdout_path": generated_artifacts.get("s0_stdout_path") or generated_artifacts.get("s0_singlepoint_stdout_path"),
        "s1_stdout_path": s1_stdout_path,
        "s0_mo_path": generated_artifacts.get("s0_mo_path") or generated_artifacts.get("s0_singlepoint_mo_path"),
        "s1_mo_path": s1_mo_path,
    }


def _dihedral_atoms_from_id(dihedral_id: str) -> list[int]:
    if not dihedral_id.startswith("dih_"):
        return []
    parts = dihedral_id[4:].split("_")
    if len(parts) != 4:
        return []
    try:
        return [int(part) for part in parts]
    except ValueError:
        return []


def _collect_available_file_keys(
    available_artifacts: dict[str, Any] | None,
    artifact_list_key: str,
) -> list[str]:
    available_artifacts = available_artifacts or {}
    file_keys: set[str] = set()
    for artifact in list(available_artifacts.get(artifact_list_key) or []):
        if not isinstance(artifact, dict):
            continue
        for key, value in artifact.items():
            if value:
                file_keys.add(str(key))
    return sorted(file_keys)


def _collect_scalar_artifact_files(
    available_artifacts: dict[str, Any] | None,
) -> list[str]:
    available_artifacts = available_artifacts or {}
    candidate_keys = [
        "prepared_xyz_path",
        "prepared_sdf_path",
        "prepared_summary_path",
        "s0_aop_path",
        "s1_aop_path",
        "s0_stdout_path",
        "s1_stdout_path",
        "s0_stderr_path",
        "s1_stderr_path",
        "s0_mo_path",
        "s1_mo_path",
    ]
    return sorted(key for key in candidate_keys if available_artifacts.get(key))


def _baseline_artifact_record(
    available_artifacts: dict[str, Any] | None,
) -> dict[str, Any]:
    available_artifacts = available_artifacts or {}
    record: dict[str, Any] = {"member_label": "baseline_bundle"}
    for key in _collect_scalar_artifact_files(available_artifacts):
        value = available_artifacts.get(key)
        if value:
            record[key] = value
    return record


def _artifact_bundle_entry_from_generated_artifacts(
    *,
    source_capability: MicroscopicCapabilityName,
    source_round: int,
    generated_artifacts: dict[str, Any],
) -> Optional[ArtifactBundleRegistryEntry]:
    bundle_kind: ArtifactBundleKind | None = None
    snapshot_count = 0
    available_deliverables: list[str] = []
    bundle_completion_status = _bundle_completion_status_from_generated_artifacts(generated_artifacts)
    parse_capabilities_supported = [
        "parse_snapshot_outputs",
        "extract_ct_descriptors_from_bundle",
        "extract_geometry_descriptors_from_bundle",
        "inspect_raw_artifact_bundle",
    ]

    if source_capability == "run_baseline_bundle" and (
        generated_artifacts.get("s0_aop_path") or generated_artifacts.get("s1_aop_path")
    ):
        bundle_kind = "baseline_bundle"
        snapshot_count = 1
        available_deliverables = [
            "S0 optimized geometry",
            "vertical excited-state manifold",
        ]
    elif source_capability == "run_torsion_snapshots" and generated_artifacts.get("snapshot_artifacts"):
        bundle_kind = "torsion_snapshots"
        snapshot_count = len(list(generated_artifacts.get("snapshot_artifacts") or []))
        available_deliverables = [
            "per-snapshot excitation energies",
            "per-snapshot oscillator strengths",
            "state-ordering summaries",
        ]
    elif source_capability == "run_conformer_bundle" and generated_artifacts.get("conformer_artifacts"):
        bundle_kind = "conformer_bundle"
        snapshot_count = len(list(generated_artifacts.get("conformer_artifacts") or []))
        available_deliverables = [
            "bounded conformer vertical-state records",
            "excitation spread",
            "bright-state sensitivity",
        ]

    if bundle_kind is None:
        return None

    if bundle_kind == "baseline_bundle":
        available_files = _collect_scalar_artifact_files(generated_artifacts)
    elif bundle_kind == "torsion_snapshots":
        available_files = _collect_available_file_keys(generated_artifacts, "snapshot_artifacts")
    else:
        available_files = _collect_available_file_keys(generated_artifacts, "conformer_artifacts")

    return ArtifactBundleRegistryEntry(
        artifact_bundle=ArtifactBundle(
            bundle_id=f"round_{source_round:02d}_{bundle_kind}",
            bundle_kind=bundle_kind,
            source_round=source_round,
            source_capability=source_capability,
            bundle_completion_status=bundle_completion_status,
            available_files=available_files,
            available_deliverables=available_deliverables,
            parse_capabilities_supported=parse_capabilities_supported,
        ),
        generated_artifacts=dict(generated_artifacts),
    )


def _list_rotatable_dihedral_descriptors(prepared: PreparedStructure) -> list[DihedralDescriptor]:
    try:
        from rdkit import Chem
    except ModuleNotFoundError:
        return []

    mol = Chem.MolFromMolFile(str(prepared.sdf_path), removeHs=False)
    if mol is None:
        return []

    descriptors: list[DihedralDescriptor] = []
    for dihedral in _find_rotatable_dihedrals(mol):
        atom_a, atom_b, atom_c, atom_d = dihedral
        bond = mol.GetBondBetweenAtoms(atom_b, atom_c)
        if bond is None:
            continue
        atom_b_obj = mol.GetAtomWithIdx(atom_b)
        atom_c_obj = mol.GetAtomWithIdx(atom_c)
        bond_type = _classify_dihedral_bond_type(bond, atom_b_obj, atom_c_obj)
        descriptor = DihedralDescriptor(
            dihedral_id="dih_" + "_".join(str(atom) for atom in dihedral),
            atom_indices=[atom_a, atom_b, atom_c, atom_d],
            central_bond_indices=[atom_b, atom_c],
            label=_build_dihedral_label(mol, dihedral, bond_type),
            bond_type=bond_type,
            adjacent_to_nsnc_core=_adjacent_to_nsnc_core(mol, dihedral),
            central_conjugation_relevance=_dihedral_relevance(mol, dihedral, bond),
            peripheral=_is_peripheral_dihedral(mol, dihedral),
            rotatable=True,
        )
        descriptors.append(descriptor)

    descriptors.sort(
        key=lambda item: (
            _relevance_rank(item.central_conjugation_relevance),
            0 if item.adjacent_to_nsnc_core else 1,
            1 if item.peripheral else 0,
            item.dihedral_id,
        )
    )
    return descriptors


def _classify_dihedral_bond_type(bond: Any, atom_b: Any, atom_c: Any) -> DihedralBondType:
    if atom_b.GetIsAromatic() and atom_c.GetIsAromatic():
        return "aryl-aryl"
    if atom_b.GetIsAromatic() or atom_c.GetIsAromatic():
        return "aryl-vinyl"
    if atom_b.GetAtomicNum() in {7, 8, 16} or atom_c.GetAtomicNum() in {7, 8, 16}:
        return "heteroaryl-linkage"
    if bond.GetIsConjugated():
        return "aryl-vinyl"
    return "other"


def _build_dihedral_label(mol: Any, dihedral: Sequence[int], bond_type: DihedralBondType) -> str:
    atom_symbols = [mol.GetAtomWithIdx(index).GetSymbol() for index in dihedral]
    return f"{bond_type} dihedral {'-'.join(atom_symbols)} ({','.join(str(index) for index in dihedral)})"


def _adjacent_to_nsnc_core(mol: Any, dihedral: Sequence[int]) -> bool:
    for ring in mol.GetRingInfo().AtomRings():
        if not any(atom_idx in ring for atom_idx in dihedral):
            continue
        ring_atoms = [mol.GetAtomWithIdx(atom_idx) for atom_idx in ring]
        symbols = {atom.GetSymbol() for atom in ring_atoms}
        if "S" in symbols and list(symbols).count("N") >= 2:
            return True
        if "S" in symbols and sum(1 for atom in ring_atoms if atom.GetSymbol() == "N") >= 2:
            return True
    return False


def _dihedral_relevance(mol: Any, dihedral: Sequence[int], bond: Any) -> Literal["high", "medium", "low"]:
    atom_a, atom_b, atom_c, atom_d = [mol.GetAtomWithIdx(index) for index in dihedral]
    aromatic_count = sum(1 for atom in (atom_a, atom_b, atom_c, atom_d) if atom.GetIsAromatic())
    hetero_count = sum(1 for atom in (atom_a, atom_b, atom_c, atom_d) if atom.GetAtomicNum() not in {1, 6})
    if bond.GetIsConjugated() or aromatic_count >= 3 or hetero_count >= 2:
        return "high"
    if aromatic_count >= 1 or hetero_count >= 1:
        return "medium"
    return "low"


def _is_peripheral_dihedral(mol: Any, dihedral: Sequence[int]) -> bool:
    atom_a, atom_b, atom_c, atom_d = [mol.GetAtomWithIdx(index) for index in dihedral]
    left_degree = len([nbr for nbr in atom_b.GetNeighbors() if nbr.GetIdx() != atom_c.GetIdx()])
    right_degree = len([nbr for nbr in atom_c.GetNeighbors() if nbr.GetIdx() != atom_b.GetIdx()])
    aromatic_outer = atom_a.GetIsAromatic() and atom_d.GetIsAromatic()
    return aromatic_outer and left_degree <= 1 and right_degree <= 1


def _relevance_rank(relevance: Literal["high", "medium", "low"]) -> int:
    if relevance == "high":
        return 0
    if relevance == "medium":
        return 1
    return 2


def _select_dihedral_descriptor(
    items: list[dict[str, Any]],
    policy: SelectionPolicy,
) -> Optional[DihedralDescriptor]:
    descriptors = [DihedralDescriptor.model_validate(item) for item in items]
    filtered = [item for item in descriptors if item.dihedral_id not in policy.exclude_dihedral_ids]
    if policy.preferred_bond_types:
        preferred = [item for item in filtered if item.bond_type in policy.preferred_bond_types]
        if preferred:
            filtered = preferred
    filtered = [
        item
        for item in filtered
        if _relevance_rank(item.central_conjugation_relevance) <= _relevance_rank(policy.min_relevance)
    ]
    if not policy.include_peripheral:
        non_peripheral = [item for item in filtered if not item.peripheral]
        if non_peripheral:
            filtered = non_peripheral
    if policy.prefer_adjacent_to_nsnc_core:
        core_adjacent = [item for item in filtered if item.adjacent_to_nsnc_core]
        if core_adjacent:
            filtered = core_adjacent
    if not filtered:
        return None
    filtered.sort(
        key=lambda item: (
            _relevance_rank(item.central_conjugation_relevance),
            0 if item.adjacent_to_nsnc_core else 1,
            1 if item.peripheral else 0,
            item.dihedral_id,
        )
    )
    return filtered[0]


def _select_artifact_bundle_descriptor(
    items: list[dict[str, Any]],
    policy: SelectionPolicy,
) -> Optional[ArtifactBundleDescriptor]:
    descriptors = [ArtifactBundleDescriptor.model_validate(item) for item in items]
    filtered = descriptors
    if policy.artifact_kind is not None:
        matching_kind = [item for item in filtered if item.artifact_kind == policy.artifact_kind]
        if matching_kind:
            filtered = matching_kind
    if policy.source_round_preference is not None:
        matching_round = [item for item in filtered if item.source_round == policy.source_round_preference]
        if matching_round:
            filtered = matching_round
    if not filtered:
        return None
    filtered.sort(key=lambda item: (-int(item.source_round), item.artifact_bundle_id))
    return filtered[0]


def _describe_dihedral_constraints(
    *,
    descriptor: DihedralDescriptor,
    policy: SelectionPolicy,
) -> list[str]:
    notes = [f"Resolved dihedral target to `{descriptor.dihedral_id}` with atoms {descriptor.atom_indices}."]
    if policy.prefer_adjacent_to_nsnc_core and descriptor.adjacent_to_nsnc_core:
        notes.append("Honored constraint: selected a dihedral adjacent to the NSNC-like core.")
    if descriptor.central_conjugation_relevance == policy.min_relevance or (
        policy.min_relevance == "medium" and descriptor.central_conjugation_relevance == "high"
    ) or (policy.min_relevance == "low"):
        notes.append(
            f"Honored constraint: central conjugation relevance is `{descriptor.central_conjugation_relevance}`."
        )
    if not policy.include_peripheral and not descriptor.peripheral:
        notes.append("Honored constraint: avoided peripheral dihedral candidates.")
    if policy.preferred_bond_types and descriptor.bond_type in policy.preferred_bond_types:
        notes.append(f"Honored constraint: selected preferred bond type `{descriptor.bond_type}`.")
    return notes


def _generate_torsion_snapshot_bundle(
    *,
    smiles: str,
    prepared: PreparedStructure,
    max_total: int,
    target_angles: Sequence[float] | None,
    target_dihedral_atoms: Sequence[int] | None,
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
    if target_dihedral_atoms:
        target = tuple(int(atom) for atom in target_dihedral_atoms)
        dihedrals = [dihedral for dihedral in dihedrals if tuple(dihedral) == target]
    if not dihedrals:
        return []

    target_angles = list(target_angles) if target_angles else [-120.0, 0.0, 120.0]
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


def _read_xyz_symbols_and_coordinates(xyz_path: Path) -> tuple[list[str], list[list[float]]]:
    if not xyz_path.exists():
        return ([], [])
    lines = xyz_path.read_text(encoding="utf-8", errors="replace").splitlines()
    if len(lines) < 3:
        return ([], [])
    symbols: list[str] = []
    coordinates: list[list[float]] = []
    for line in lines[2:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        try:
            xyz = [float(parts[1]), float(parts[2]), float(parts[3])]
        except ValueError:
            return ([], [])
        symbols.append(parts[0])
        coordinates.append(xyz)
    return (symbols, coordinates)


def _read_xyz_coordinates(xyz_path: Path) -> list[list[float]]:
    _, coordinates = _read_xyz_symbols_and_coordinates(xyz_path)
    return coordinates


AmespBaselineMicroscopicTool = AmespMicroscopicTool
