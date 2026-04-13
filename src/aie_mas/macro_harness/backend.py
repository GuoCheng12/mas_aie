from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, cast

from pydantic import ValidationError

from aie_mas.graph.state import (
    MacroCapabilityName,
    MacroExecutionPlan,
    MacroExecutionStep,
    MacroToolPlan,
    MacroToolRequest,
    MacroTranslationBindingMode,
    SharedStructureContext,
)
from aie_mas.tools.macro import MACRO_CAPABILITY_REGISTRY, DeterministicMacroStructureTool


def list_macro_capabilities() -> list[dict[str, Any]]:
    return [
        {
            "capability_name": name,
            "purpose": definition.purpose,
            "structure_target": definition.structure_target,
            "supported_deliverables": list(definition.supported_deliverables),
            "evidence_goal_tags": list(definition.evidence_goal_tags),
            "exact_observable_tags": list(definition.exact_observable_tags),
            "unsupported_requests_note": definition.unsupported_requests_note,
        }
        for name, definition in MACRO_CAPABILITY_REGISTRY.items()
    ]


def normalize_macro_capability_name(capability_name: str) -> MacroCapabilityName:
    normalized = capability_name.strip()
    if normalized not in MACRO_CAPABILITY_REGISTRY:
        supported = ", ".join(sorted(MACRO_CAPABILITY_REGISTRY.keys()))
        raise ValueError(
            f"Unsupported macro capability `{capability_name}`. Supported capabilities: {supported}."
        )
    return cast(MacroCapabilityName, normalized)


def describe_macro_capability(capability_name: str) -> dict[str, Any]:
    normalized = normalize_macro_capability_name(capability_name)
    definition = MACRO_CAPABILITY_REGISTRY[normalized]
    requires_shared_structure_context = definition.structure_target == "shared_prepared_structure"
    return {
        "capability_name": normalized,
        "purpose": definition.purpose,
        "structure_target": definition.structure_target,
        "requires_shared_structure_context": requires_shared_structure_context,
        "supported_deliverables": list(definition.supported_deliverables),
        "evidence_goal_tags": list(definition.evidence_goal_tags),
        "exact_observable_tags": list(definition.exact_observable_tags),
        "unsupported_requests_note": definition.unsupported_requests_note,
        "input_contract": {
            "smiles": {"required": True, "type": "string"},
            "binding_mode": {
                "required": False,
                "allowed_values": ["hard", "preferred", "none"],
            },
            "shared_structure_context_file": {
                "required": requires_shared_structure_context,
                "accepted_format": "Serialized SharedStructureContext JSON file",
            },
            "requested_deliverables": {
                "required": False,
                "type": "repeatable_string_option",
            },
            "observable_tags": {
                "required": False,
                "type": "repeatable_string_option",
            },
        },
    }


def load_shared_structure_context_file(path: Path | None) -> SharedStructureContext | None:
    if path is None:
        return None
    if not path.exists():
        raise FileNotFoundError(f"Shared structure context file does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return SharedStructureContext.model_validate(payload)


def inspect_shared_structure_context(
    shared_structure_context: SharedStructureContext,
) -> dict[str, Any]:
    validation = validate_shared_structure_context(shared_structure_context)
    return {
        "input_smiles": shared_structure_context.input_smiles,
        "canonical_smiles": shared_structure_context.canonical_smiles,
        "charge": shared_structure_context.charge,
        "multiplicity": shared_structure_context.multiplicity,
        "atom_count": shared_structure_context.atom_count,
        "conformer_count": shared_structure_context.conformer_count,
        "selected_conformer_id": shared_structure_context.selected_conformer_id,
        "geometry_paths": {
            "prepared_xyz_path": shared_structure_context.prepared_xyz_path,
            "prepared_sdf_path": shared_structure_context.prepared_sdf_path,
            "summary_path": shared_structure_context.summary_path,
        },
        "path_status": validation["path_status"],
        "structure_metrics": {
            "rotatable_bond_count": shared_structure_context.rotatable_bond_count,
            "aromatic_ring_count": shared_structure_context.aromatic_ring_count,
            "ring_system_count": shared_structure_context.ring_system_count,
            "hetero_atom_count": shared_structure_context.hetero_atom_count,
            "branch_point_count": shared_structure_context.branch_point_count,
            "torsion_candidate_count": shared_structure_context.torsion_candidate_count,
        },
        "proxy_metrics": {
            "donor_acceptor_partition_proxy": shared_structure_context.donor_acceptor_partition_proxy,
            "planarity_proxy": shared_structure_context.planarity_proxy,
            "compactness_proxy": shared_structure_context.compactness_proxy,
            "principal_span_proxy": shared_structure_context.principal_span_proxy,
            "conformer_dispersion_proxy": shared_structure_context.conformer_dispersion_proxy,
        },
        "validation": validation,
    }


def validate_shared_structure_context(
    shared_structure_context: SharedStructureContext,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not shared_structure_context.input_smiles.strip():
        errors.append("input_smiles is empty.")
    if not shared_structure_context.canonical_smiles.strip():
        errors.append("canonical_smiles is empty.")
    if shared_structure_context.atom_count <= 0:
        errors.append("atom_count must be positive.")
    if shared_structure_context.conformer_count <= 0:
        errors.append("conformer_count must be positive.")
    if shared_structure_context.selected_conformer_id < 0:
        errors.append("selected_conformer_id must be non-negative.")

    path_status: dict[str, dict[str, Any]] = {}
    for label, raw_path in {
        "prepared_xyz_path": shared_structure_context.prepared_xyz_path,
        "prepared_sdf_path": shared_structure_context.prepared_sdf_path,
        "summary_path": shared_structure_context.summary_path,
    }.items():
        resolved = Path(raw_path)
        exists = resolved.exists()
        path_status[label] = {
            "path": str(resolved),
            "exists": exists,
        }
        if not exists:
            warnings.append(f"{label} does not exist on disk: {resolved}")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "path_status": path_status,
    }


def inspect_shared_structure_context_file(path: Path) -> dict[str, Any]:
    shared_structure_context = load_shared_structure_context_file(path)
    assert shared_structure_context is not None
    return {
        "context_file": str(path),
        "context_type": "SharedStructureContext",
        "inspection": inspect_shared_structure_context(shared_structure_context),
    }


def validate_shared_structure_context_file(path: Path) -> dict[str, Any]:
    shared_structure_context = load_shared_structure_context_file(path)
    assert shared_structure_context is not None
    validation = validate_shared_structure_context(shared_structure_context)
    return {
        "context_file": str(path),
        "context_type": "SharedStructureContext",
        **validation,
    }


def build_macro_execution_plan(
    *,
    capability_name: MacroCapabilityName,
    smiles: str,
    shared_structure_context: SharedStructureContext | None,
    requested_deliverables: list[str] | None = None,
    requested_observable_tags: list[str] | None = None,
    binding_mode: Optional[MacroTranslationBindingMode] = None,
    local_goal: str | None = None,
) -> MacroExecutionPlan:
    definition = MACRO_CAPABILITY_REGISTRY[capability_name]
    structure_source = (
        "shared_prepared_structure"
        if shared_structure_context is not None
        else "smiles_only_fallback"
    )
    deliverables = list(requested_deliverables or definition.supported_deliverables)
    observable_tags = list(requested_observable_tags or definition.evidence_goal_tags)
    return MacroExecutionPlan(
        local_goal=local_goal
        or f"Execute bounded macro screen `{capability_name}` for the provided molecule.",
        requested_deliverables=deliverables,
        structure_source=structure_source,
        selected_capability=capability_name,
        binding_mode=binding_mode,
        requested_observable_tags=observable_tags,
        resolved_target_ids={"structure_source": structure_source},
        focus_areas=[],
        supported_scope=list(MACRO_CAPABILITY_REGISTRY.keys()),
        unsupported_requests=[],
        steps=[
            MacroExecutionStep(
                step_id="load_structure_context",
                step_type="shared_context_load",
                description="Load reusable prepared-structure context when available.",
                input_source="shared_structure_context"
                if shared_structure_context is not None
                else "smiles_only",
                expected_outputs=["structure_source"],
            ),
            MacroExecutionStep(
                step_id="execute_selected_capability",
                step_type="geometry_proxy_analysis",
                description=f"Execute `{capability_name}` using the bounded macro registry.",
                input_source=structure_source,
                expected_outputs=deliverables,
            ),
        ],
        expected_outputs=deliverables,
        failure_reporting="Return a local failed report if macro CLI execution cannot complete.",
        macro_tool_request=MacroToolRequest(
            capability_name=capability_name,
            structure_target=definition.structure_target,
            reuse_shared_structure_only=definition.structure_target == "shared_prepared_structure",
            requested_observable_scope=observable_tags,
            requested_route_summary=definition.purpose,
            honor_exact_target=False,
            allow_fallback=True,
        ),
        macro_tool_plan=MacroToolPlan(
            calls=[
                {
                    "action_kind": "execution",
                    "capability_name": capability_name,
                    "structure_source": structure_source,
                }
            ],
            requested_route_summary=definition.purpose,
            requested_deliverables=deliverables,
        ),
    )


def execute_macro_screen(
    *,
    capability_name: str,
    smiles: str,
    shared_structure_context: SharedStructureContext | None = None,
    requested_deliverables: list[str] | None = None,
    requested_observable_tags: list[str] | None = None,
    binding_mode: Optional[MacroTranslationBindingMode] = None,
    local_goal: str | None = None,
) -> dict[str, Any]:
    normalized_capability = normalize_macro_capability_name(capability_name)
    if not smiles.strip():
        raise ValueError("smiles is required for macro screening.")
    plan = build_macro_execution_plan(
        capability_name=normalized_capability,
        smiles=smiles,
        shared_structure_context=shared_structure_context,
        requested_deliverables=requested_deliverables,
        requested_observable_tags=requested_observable_tags,
        binding_mode=binding_mode,
        local_goal=local_goal,
    )
    result = DeterministicMacroStructureTool().execute_local(
        plan=plan,
        smiles=smiles,
        shared_structure_context=shared_structure_context,
    )
    return {
        **result,
        "cli_harness": {
            "harness_name": "aie-mas-macro",
            "capability_name": normalized_capability,
            "structure_source": plan.structure_source,
            "binding_mode": binding_mode,
        },
    }


def execute_macro_payload(payload: dict[str, Any]) -> dict[str, Any]:
    capability_name = str(payload.get("selected_capability") or payload.get("capability_name") or "")
    if not capability_name:
        raise ValueError("selected_capability is required for macro CLI execution.")
    smiles = str(payload.get("smiles") or "")
    shared_structure_context = (
        SharedStructureContext.model_validate(payload["shared_structure_context"])
        if payload.get("shared_structure_context") is not None
        else None
    )
    binding_mode = payload.get("binding_mode")
    normalized_binding_mode = (
        cast(MacroTranslationBindingMode, binding_mode) if binding_mode in {"hard", "preferred", "none"} else None
    )
    return execute_macro_screen(
        capability_name=capability_name,
        smiles=smiles,
        shared_structure_context=shared_structure_context,
        requested_deliverables=list(payload.get("requested_deliverables") or []),
        requested_observable_tags=list(payload.get("requested_observable_tags") or []),
        binding_mode=normalized_binding_mode,
        local_goal=str(payload.get("local_goal") or "").strip() or None,
    )


__all__ = [
    "describe_macro_capability",
    "execute_macro_payload",
    "execute_macro_screen",
    "inspect_shared_structure_context_file",
    "list_macro_capabilities",
    "load_shared_structure_context_file",
    "normalize_macro_capability_name",
    "validate_shared_structure_context_file",
    "ValidationError",
]
