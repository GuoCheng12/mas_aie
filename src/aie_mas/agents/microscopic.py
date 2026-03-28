from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Protocol

from pydantic import BaseModel, Field, ValidationError, field_validator

from aie_mas.compat.langchain import prompt_value_to_messages
from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    AmespCapabilityName,
    AgentReport,
    DihedralBondType,
    MicroscopicCapabilityRoute,
    MicroscopicCompletionReasonCode,
    MicroscopicExecutionPlan,
    MicroscopicExecutionStep,
    MicroscopicToolCall,
    MicroscopicToolPlan,
    MicroscopicToolRequest,
    MicroscopicTaskSpec,
    SelectionPolicy,
    SharedStructureContext,
    SharedStructureStatus,
    WorkflowProgressEvent,
)
from aie_mas.llm.openai_compatible import OpenAICompatibleMicroscopicClient
from aie_mas.tools.amesp import (
    AMESP_ACTION_REGISTRY,
    AMESP_CAPABILITY_REGISTRY,
    AmespActionDefinition,
    AmespExecutionError,
    AmespMicroscopicTool,
    render_amesp_action_registry,
    render_amesp_capability_registry,
    render_registry_backed_microscopic_examples,
)
from aie_mas.utils.prompts import PromptRepository


MicroscopicStructureStrategy = Literal[
    "prepare_from_smiles",
    "reuse_if_available_else_prepare_from_smiles",
]
MicroscopicSemanticContractMode = Literal[
    "semantic_contract",
    "legacy_semantic_contract_fallback",
    "legacy_tagged_protocol_fallback",
    "legacy_json_fallback",
    "failed",
]
MicroscopicSemanticDiscoveryNeed = Literal["rotatable_dihedrals", "conformers", "artifact_bundles"]
MicroscopicSemanticTargetObjectKind = Literal["none", "dihedral", "conformer", "artifact_bundle"]


_PLACEHOLDER_TARGET_PATTERNS = (
    "to_be_selected",
    "discover_first",
    "after_call",
    "to_be_resolved",
    "tbd",
)


def _default_prompt_repository() -> PromptRepository:
    return PromptRepository(Path(__file__).resolve().parents[1] / "prompts")


def _compatibility_route_for_capability_name(capability_name: AmespCapabilityName) -> MicroscopicCapabilityRoute:
    if capability_name == "run_baseline_bundle":
        return "baseline_bundle"
    if capability_name == "run_conformer_bundle":
        return "conformer_bundle_follow_up"
    if capability_name == "run_torsion_snapshots":
        return "torsion_snapshot_follow_up"
    if capability_name == "parse_snapshot_outputs":
        return "artifact_parse_only"
    return "excited_state_relaxation_follow_up"


def _capability_name_for_compatibility_route(
    capability_route: Optional[MicroscopicCapabilityRoute],
) -> Optional[AmespCapabilityName]:
    if capability_route == "baseline_bundle":
        return "run_baseline_bundle"
    if capability_route == "conformer_bundle_follow_up":
        return "run_conformer_bundle"
    if capability_route == "torsion_snapshot_follow_up":
        return "run_torsion_snapshots"
    if capability_route == "artifact_parse_only":
        return "parse_snapshot_outputs"
    if capability_route == "excited_state_relaxation_follow_up":
        return "unsupported_excited_state_relaxation"
    return None


def _is_placeholder_target_value(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return False
    return any(pattern in normalized for pattern in _PLACEHOLDER_TARGET_PATTERNS)


class MicroscopicReasoningPlanDraft(BaseModel):
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    capability_route: Optional[MicroscopicCapabilityRoute] = None
    requested_route_summary: Optional[str] = None
    microscopic_tool_request: Optional["MicroscopicToolRequestDraft"] = None
    microscopic_tool_plan: Optional["MicroscopicToolPlanDraft"] = None
    structure_strategy: MicroscopicStructureStrategy = "reuse_if_available_else_prepare_from_smiles"
    planning_unmet_constraints: list[str] = Field(default_factory=list)
    step_sequence: list[
        Literal[
            "structure_prep",
            "conformer_bundle_generation",
            "torsion_snapshot_generation",
            "artifact_parse",
            "s0_optimization",
            "s0_singlepoint",
            "s1_vertical_excitation",
        ]
    ] = Field(default_factory=lambda: ["structure_prep", "s0_optimization", "s1_vertical_excitation"])
    unsupported_requests: list[str] = Field(default_factory=list)

    @field_validator("structure_strategy", mode="before")
    @classmethod
    def _normalize_structure_strategy(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return "reuse_if_available_else_prepare_from_smiles"
        aliases = {
            "prefer_shared_prepared_structure": "reuse_if_available_else_prepare_from_smiles",
            "prefer_shared_prepared_structure_context": "reuse_if_available_else_prepare_from_smiles",
            "reuse_shared_prepared_structure_if_available": "reuse_if_available_else_prepare_from_smiles",
        }
        return aliases.get(normalized, normalized)

    @field_validator("capability_route", mode="before")
    @classmethod
    def _normalize_compatibility_route(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        if normalized in {
            "run_baseline_bundle",
            "run_conformer_bundle",
            "run_torsion_snapshots",
            "parse_snapshot_outputs",
            "unsupported_excited_state_relaxation",
        }:
            return _compatibility_route_for_capability_name(normalized)  # type: ignore[arg-type]
        return normalized


class MicroscopicToolRequestDraft(BaseModel):
    capability_name: Optional[AmespCapabilityName] = None
    structure_source: Optional[Literal["shared_prepared_structure", "round_s0_optimized_geometry", "latest_available"]] = None
    perform_new_calculation: Optional[bool] = None
    optimize_ground_state: Optional[bool] = None
    reuse_existing_artifacts_only: Optional[bool] = None
    artifact_source_round: Optional[int] = None
    artifact_scope: Optional[str] = None
    artifact_bundle_id: Optional[str] = None
    artifact_kind: Optional[Literal["baseline_bundle", "torsion_snapshots", "conformer_bundle"]] = None
    source_round_preference: Optional[int] = None
    min_relevance: Optional[Literal["high", "medium", "low"]] = None
    include_peripheral: Optional[bool] = None
    preferred_bond_types: list[DihedralBondType] = Field(default_factory=list)
    dihedral_id: Optional[str] = None
    dihedral_atom_indices: list[int] = Field(default_factory=list)
    conformer_id: Optional[str] = None
    conformer_ids: list[str] = Field(default_factory=list)
    max_conformers: Optional[int] = None
    snapshot_count: Optional[int] = None
    angle_offsets_deg: list[float] = Field(default_factory=list)
    state_window: list[int] = Field(default_factory=list)
    honor_exact_target: Optional[bool] = None
    allow_fallback: Optional[bool] = None
    deliverables: list[str] = Field(default_factory=list)
    budget_profile: Optional[Literal["conservative", "balanced", "aggressive"]] = None
    requested_route_summary: Optional[str] = None

    @field_validator("structure_source", mode="before")
    @classmethod
    def _normalize_structure_source(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        aliases = {
            "shared_prepared_structure_context": "shared_prepared_structure",
            "shared_prepared_structure_if_available": "shared_prepared_structure",
            "round_s0_optimized_geometry_context": "round_s0_optimized_geometry",
            "latest_available_structure": "latest_available",
        }
        return aliases.get(normalized, normalized)

    @field_validator("dihedral_id", "conformer_id", "artifact_bundle_id", mode="before")
    @classmethod
    def _reject_placeholder_target_value(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        if _is_placeholder_target_value(normalized):
            raise ValueError(f"Placeholder target values are not allowed: {normalized!r}")
        return normalized

    @field_validator("conformer_ids", mode="before")
    @classmethod
    def _reject_placeholder_conformer_ids(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        for item in value:
            if isinstance(item, str) and _is_placeholder_target_value(item):
                raise ValueError(f"Placeholder target values are not allowed: {item!r}")
        return value


class MicroscopicSemanticConstraintsDraft(BaseModel):
    perform_new_calculation: Optional[bool] = None
    optimize_ground_state: Optional[bool] = None
    reuse_existing_artifacts_only: Optional[bool] = None
    snapshot_count: Optional[int] = None
    angle_offsets_deg: list[float] = Field(default_factory=list)
    state_window: list[int] = Field(default_factory=list)
    max_conformers: Optional[int] = None
    honor_exact_target: Optional[bool] = None
    allow_fallback: Optional[bool] = None


class MicroscopicSemanticSelectionDraft(BaseModel):
    exclude_dihedral_ids: list[str] = Field(default_factory=list)
    prefer_adjacent_to_nsnc_core: Optional[bool] = None
    min_relevance: Optional[Literal["high", "medium", "low"]] = None
    include_peripheral: Optional[bool] = None
    preferred_bond_types: list[DihedralBondType] = Field(default_factory=list)
    artifact_kind: Optional[Literal["baseline_bundle", "torsion_snapshots", "conformer_bundle"]] = None
    source_round_selector: Optional[str] = None

    @field_validator("source_round_selector", mode="before")
    @classmethod
    def _normalize_source_round_selector(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized in {"current_run", "current"}:
            return "current_run"
        if normalized in {"latest_available", "latest"}:
            return "latest_available"
        match = re.fullmatch(r"round[_\s-]?0*(\d+)", normalized)
        if match is not None:
            return f"round_{int(match.group(1)):02d}"
        raise ValueError(
            "source_round_selector must be current_run, latest_available, or round_XX."
        )


class MicroscopicSemanticTargetDraft(BaseModel):
    dihedral_id: Optional[str] = None
    conformer_id: Optional[str] = None
    conformer_ids: list[str] = Field(default_factory=list)
    artifact_bundle_id: Optional[str] = None

    @field_validator("dihedral_id", "conformer_id", "artifact_bundle_id", mode="before")
    @classmethod
    def _reject_placeholder_target_value(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return None
        if _is_placeholder_target_value(normalized):
            raise ValueError(f"Placeholder target values are not allowed: {normalized!r}")
        return normalized

    @field_validator("conformer_ids", mode="before")
    @classmethod
    def _reject_placeholder_conformer_ids(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        for item in value:
            if isinstance(item, str) and _is_placeholder_target_value(item):
                raise ValueError(f"Placeholder target values are not allowed: {item!r}")
        return value


class MicroscopicSemanticContractDraft(BaseModel):
    contract_version: Literal[1] = 1
    local_goal: str
    primary_capability: Literal[
        "run_baseline_bundle",
        "run_conformer_bundle",
        "run_torsion_snapshots",
        "parse_snapshot_outputs",
        "unsupported_excited_state_relaxation",
    ]
    needs_discovery: Optional[MicroscopicSemanticDiscoveryNeed] = None
    target_object_kind: MicroscopicSemanticTargetObjectKind = "none"
    requested_route_summary: str
    requested_deliverables: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    constraints: MicroscopicSemanticConstraintsDraft = Field(default_factory=MicroscopicSemanticConstraintsDraft)
    selection: MicroscopicSemanticSelectionDraft = Field(default_factory=MicroscopicSemanticSelectionDraft)
    target: MicroscopicSemanticTargetDraft = Field(default_factory=MicroscopicSemanticTargetDraft)


class MicroscopicActionCardDraft(BaseModel):
    contract_version: Literal[2] = 2
    local_goal: str
    execution_action: Literal[
        "run_baseline_bundle",
        "run_conformer_bundle",
        "run_torsion_snapshots",
        "parse_snapshot_outputs",
        "unsupported_excited_state_relaxation",
    ]
    discovery_actions: list[AmespCapabilityName] = Field(default_factory=list)
    requested_route_summary: str
    requested_deliverables: list[str] = Field(default_factory=list)
    unsupported_requests: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)


class SelectionPolicyDraft(BaseModel):
    exclude_dihedral_ids: list[str] = Field(default_factory=list)
    prefer_adjacent_to_nsnc_core: Optional[bool] = None
    min_relevance: Optional[Literal["high", "medium", "low"]] = None
    include_peripheral: Optional[bool] = None
    preferred_bond_types: list[DihedralBondType] = Field(default_factory=list)
    artifact_kind: Optional[Literal["baseline_bundle", "torsion_snapshots", "conformer_bundle"]] = None
    source_round_preference: Optional[int] = None


class MicroscopicToolCallDraft(BaseModel):
    call_id: Optional[str] = None
    call_kind: Optional[Literal["discovery", "execution"]] = None
    request: Optional[MicroscopicToolRequestDraft] = None


class MicroscopicToolPlanDraft(BaseModel):
    calls: list[MicroscopicToolCallDraft] = Field(default_factory=list)
    requested_route_summary: Optional[str] = None
    requested_deliverables: list[str] = Field(default_factory=list)
    selection_policy: Optional[SelectionPolicyDraft] = None
    failure_reporting: Optional[str] = None


class MicroscopicReasoningResponse(BaseModel):
    task_understanding: str
    reasoning_summary: str
    execution_plan: MicroscopicReasoningPlanDraft
    capability_limit_note: str
    expected_outputs: list[str] = Field(default_factory=list)
    failure_policy: str


MicroscopicToolPlanDraft.model_rebuild()
MicroscopicReasoningPlanDraft.model_rebuild()


@dataclass
class MicroscopicReasoningOutcome:
    reasoning_response: MicroscopicReasoningResponse
    compiled_execution_plan: MicroscopicExecutionPlan
    reasoning_parse_mode: MicroscopicSemanticContractMode
    reasoning_contract_mode: MicroscopicSemanticContractMode
    reasoning_contract_errors: list[str]


class TaggedMicroscopicProtocolError(ValueError):
    pass


class MicroscopicReasoningParseError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        raw_text: str,
        contract_mode: MicroscopicSemanticContractMode,
        contract_errors: list[str],
    ) -> None:
        super().__init__(message)
        self.raw_text = raw_text
        self.contract_mode = contract_mode
        self.contract_errors = list(contract_errors)


_TAGGED_REASONING_BASE_SECTION_NAMES = (
    "task_understanding",
    "reasoning_summary",
    "capability_limit_note",
    "expected_outputs",
    "failure_policy",
)
_TAGGED_REASONING_PROTOCOL_SECTION_NAMES = (
    "microscopic_semantic_contract",
    "microscopic_protocol",
)
_TAGGED_PROTOCOL_ROOT_KEYS = {
    "protocol_version",
    "local_goal",
    "structure_strategy",
    "requested_route_summary",
    "requested_deliverables",
    "unsupported_requests",
}
_TAGGED_PROTOCOL_SELECTION_KEYS = {
    "exclude_dihedral_ids",
    "prefer_adjacent_to_nsnc_core",
    "min_relevance",
    "include_peripheral",
    "preferred_bond_types",
    "artifact_kind",
    "source_round_preference",
}
_TAGGED_PROTOCOL_CALL_KEYS = {
    "kind",
    "capability_name",
    "structure_source",
    "perform_new_calculation",
    "optimize_ground_state",
    "reuse_existing_artifacts_only",
    "artifact_source_round",
    "artifact_scope",
    "artifact_bundle_id",
    "artifact_kind",
    "source_round_preference",
    "min_relevance",
    "include_peripheral",
    "preferred_bond_types",
    "dihedral_id",
    "dihedral_atom_indices",
    "conformer_id",
    "conformer_ids",
    "max_conformers",
    "snapshot_count",
    "angle_offsets_deg",
    "state_window",
    "honor_exact_target",
    "allow_fallback",
    "deliverables",
    "budget_profile",
    "requested_route_summary",
}
_TAGGED_CONTRACT_ROOT_KEYS = {
    "contract_version",
    "local_goal",
    "primary_capability",
    "needs_discovery",
    "target_object_kind",
    "requested_route_summary",
    "requested_deliverables",
    "unsupported_requests",
}
_TAGGED_CONTRACT_CONSTRAINT_KEYS = {
    "perform_new_calculation",
    "optimize_ground_state",
    "reuse_existing_artifacts_only",
    "snapshot_count",
    "angle_offsets_deg",
    "state_window",
    "max_conformers",
    "honor_exact_target",
    "allow_fallback",
}
_TAGGED_CONTRACT_SELECTION_KEYS = {
    "exclude_dihedral_ids",
    "prefer_adjacent_to_nsnc_core",
    "min_relevance",
    "include_peripheral",
    "preferred_bond_types",
    "artifact_kind",
    "source_round_selector",
}
_TAGGED_CONTRACT_TARGET_KEYS = {
    "dihedral_id",
    "conformer_id",
    "conformer_ids",
    "artifact_bundle_id",
}
_TAGGED_ACTION_CARD_ROOT_KEYS = {
    "contract_version",
    "local_goal",
    "execution_action",
    "discovery_actions",
    "requested_route_summary",
    "requested_deliverables",
    "unsupported_requests",
}


def _strip_reasoning_code_fence(raw_text: str) -> str:
    candidate = raw_text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return candidate


def _extract_tagged_reasoning_sections(raw_text: str) -> dict[str, str]:
    candidate = _strip_reasoning_code_fence(raw_text)
    opening_matches = list(re.finditer(r"<([a-z_]+)>", candidate))
    if not opening_matches:
        raise TaggedMicroscopicProtocolError("Tagged microscopic reasoning sections were not found.")
    sections: dict[str, str] = {}
    for index, match in enumerate(opening_matches):
        section_name = match.group(1)
        if section_name not in _TAGGED_REASONING_BASE_SECTION_NAMES and section_name not in _TAGGED_REASONING_PROTOCOL_SECTION_NAMES:
            raise TaggedMicroscopicProtocolError(f"Unknown tagged reasoning section '{section_name}'.")
        if section_name in sections:
            raise TaggedMicroscopicProtocolError(f"Duplicate tagged reasoning section '{section_name}'.")
        content_start = match.end()
        next_open_start = opening_matches[index + 1].start() if index + 1 < len(opening_matches) else len(candidate)
        explicit_close = re.search(rf"</{re.escape(section_name)}>", candidate[content_start:next_open_start], flags=re.DOTALL)
        if explicit_close is not None:
            content_end = content_start + explicit_close.start()
        else:
            content_end = next_open_start
        section_text = candidate[content_start:content_end].strip()
        section_lines = [line for line in section_text.splitlines() if line.strip() != "```"]
        sections[section_name] = "\n".join(section_lines).strip()
    missing_sections = [name for name in _TAGGED_REASONING_BASE_SECTION_NAMES if name not in sections]
    if missing_sections:
        raise TaggedMicroscopicProtocolError(
            "Tagged microscopic reasoning response is missing required sections: "
            + ", ".join(missing_sections)
        )
    protocol_sections = [name for name in _TAGGED_REASONING_PROTOCOL_SECTION_NAMES if name in sections]
    if not protocol_sections:
        raise TaggedMicroscopicProtocolError(
            "Tagged microscopic reasoning response is missing either <microscopic_semantic_contract> or <microscopic_protocol>."
        )
    if len(protocol_sections) > 1:
        raise TaggedMicroscopicProtocolError(
            "Tagged microscopic reasoning response must contain exactly one protocol section."
        )
    return sections


def _parse_pipe_list(value: str) -> list[str]:
    if not value.strip():
        return []
    return [item.strip() for item in value.split("|") if item.strip()]


def _parse_symbolic_list(value: str) -> list[str]:
    if not value.strip():
        return []
    if "|" in value:
        return [item.strip() for item in value.split("|") if item.strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int_list(value: str) -> list[int]:
    if not value.strip():
        return []
    try:
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise TaggedMicroscopicProtocolError(f"Invalid integer list '{value}'.") from exc


def _parse_float_list(value: str) -> list[float]:
    if not value.strip():
        return []
    try:
        return [float(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise TaggedMicroscopicProtocolError(f"Invalid float list '{value}'.") from exc


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise TaggedMicroscopicProtocolError(f"Invalid boolean literal '{value}'.")


def _parse_tagged_expected_outputs(section_text: str) -> list[str]:
    outputs: list[str] = []
    for line in section_text.splitlines():
        item = line.strip()
        if not item:
            continue
        if item == "```":
            continue
        if item.startswith("- "):
            item = item[2:].strip()
        elif item.startswith("* "):
            item = item[2:].strip()
        if item:
            outputs.append(item)
    return outputs


def _has_reusable_structure_from_payload(payload: Optional[dict[str, Any]]) -> bool:
    if payload is None:
        return False
    shared_structure_context = payload.get("shared_structure_context")
    if shared_structure_context:
        return True
    available_structure_context = payload.get("available_structure_context")
    if isinstance(available_structure_context, dict):
        return bool(available_structure_context.get("has_prepared_structure"))
    return False


def _derive_structure_strategy_from_payload(payload: Optional[dict[str, Any]]) -> MicroscopicStructureStrategy:
    if _has_reusable_structure_from_payload(payload):
        return "reuse_if_available_else_prepare_from_smiles"
    return "prepare_from_smiles"


def _structure_source_for_semantic_capability(
    capability_name: AmespCapabilityName,
    *,
    task_mode: str,
    has_reusable_structure: bool,
) -> Optional[Literal["shared_prepared_structure", "round_s0_optimized_geometry", "latest_available"]]:
    if capability_name == "parse_snapshot_outputs":
        return None
    if capability_name == "run_baseline_bundle":
        return "shared_prepared_structure" if has_reusable_structure else "latest_available"
    if capability_name in {"run_torsion_snapshots", "run_conformer_bundle", "list_rotatable_dihedrals", "list_available_conformers"}:
        if task_mode == "targeted_follow_up":
            return "round_s0_optimized_geometry"
        return "shared_prepared_structure" if has_reusable_structure else "latest_available"
    return "shared_prepared_structure" if has_reusable_structure else "latest_available"


def _source_round_preference_from_selector(
    selector: Optional[str],
    *,
    current_round_index: Optional[int],
) -> Optional[int]:
    if not selector or selector == "latest_available":
        return None
    if selector == "current_run":
        return current_round_index
    match = re.fullmatch(r"round_(\d{2})", selector)
    if match is None:
        raise TaggedMicroscopicProtocolError(
            f"Invalid source_round_selector '{selector}'. Expected current_run, latest_available, or round_XX."
        )
    return int(match.group(1))


def _parse_source_round_preference_value(value: str) -> Optional[int]:
    normalized = value.strip().lower()
    if not normalized:
        return None
    if normalized.isdigit():
        return int(normalized)
    if re.fullmatch(r"round[_\s-]?0*\d+", normalized):
        selector = MicroscopicSemanticSelectionDraft._normalize_source_round_selector(normalized)  # type: ignore[misc]
        return _source_round_preference_from_selector(selector, current_round_index=None)
    if normalized in {"latest", "latest_available"}:
        return None
    raise TaggedMicroscopicProtocolError(f"Invalid source round preference '{value}'.")


def _parse_tagged_semantic_contract_lines(
    contract_text: str,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    root_values: dict[str, str] = {}
    constraint_values: dict[str, str] = {}
    selection_values: dict[str, str] = {}
    target_values: dict[str, str] = {}
    seen_keys: set[str] = set()
    for raw_line in contract_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            raise TaggedMicroscopicProtocolError(f"Invalid semantic contract line '{raw_line}'. Expected key=value.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in seen_keys:
            raise TaggedMicroscopicProtocolError(f"Duplicate semantic contract key '{key}'.")
        seen_keys.add(key)
        if key.startswith("constraint."):
            field_name = key[len("constraint.") :]
            if field_name not in _TAGGED_CONTRACT_CONSTRAINT_KEYS:
                raise TaggedMicroscopicProtocolError(f"Unknown contract constraint field '{field_name}'.")
            constraint_values[field_name] = value
            continue
        if key.startswith("selection."):
            field_name = key[len("selection.") :]
            if field_name not in _TAGGED_CONTRACT_SELECTION_KEYS:
                raise TaggedMicroscopicProtocolError(f"Unknown contract selection field '{field_name}'.")
            selection_values[field_name] = value
            continue
        if key.startswith("target."):
            field_name = key[len("target.") :]
            if field_name not in _TAGGED_CONTRACT_TARGET_KEYS:
                raise TaggedMicroscopicProtocolError(f"Unknown contract target field '{field_name}'.")
            target_values[field_name] = value
            continue
        if key not in _TAGGED_CONTRACT_ROOT_KEYS:
            raise TaggedMicroscopicProtocolError(f"Unknown semantic contract key '{key}'.")
        root_values[key] = value
    return root_values, constraint_values, selection_values, target_values


def _build_semantic_contract_draft(
    root_values: dict[str, str],
    constraint_values: dict[str, str],
    selection_values: dict[str, str],
    target_values: dict[str, str],
) -> MicroscopicSemanticContractDraft:
    if root_values.get("contract_version") != "1":
        raise TaggedMicroscopicProtocolError(
            f"Unsupported microscopic semantic contract_version '{root_values.get('contract_version')}'."
        )
    required_root_keys = (
        "contract_version",
        "local_goal",
        "primary_capability",
        "target_object_kind",
        "requested_route_summary",
        "requested_deliverables",
    )
    missing_root_keys = [key for key in required_root_keys if key not in root_values]
    if missing_root_keys:
        raise TaggedMicroscopicProtocolError(
            "Semantic contract is missing required keys: " + ", ".join(missing_root_keys)
        )

    constraints_payload: dict[str, Any] = {}
    for key, value in constraint_values.items():
        if key in {"perform_new_calculation", "optimize_ground_state", "reuse_existing_artifacts_only", "honor_exact_target", "allow_fallback"}:
            constraints_payload[key] = _parse_bool(value)
        elif key in {"snapshot_count", "max_conformers"}:
            constraints_payload[key] = int(value)
        elif key == "angle_offsets_deg":
            constraints_payload[key] = _parse_float_list(value)
        elif key == "state_window":
            constraints_payload[key] = _parse_int_list(value)
        else:
            constraints_payload[key] = value

    selection_payload: dict[str, Any] = {}
    for key, value in selection_values.items():
        if key == "exclude_dihedral_ids":
            selection_payload[key] = _parse_symbolic_list(value)
        elif key in {"prefer_adjacent_to_nsnc_core", "include_peripheral"}:
            selection_payload[key] = _parse_bool(value)
        elif key == "preferred_bond_types":
            selection_payload[key] = _parse_symbolic_list(value)
        else:
            selection_payload[key] = value

    target_payload: dict[str, Any] = {}
    for key, value in target_values.items():
        if key == "conformer_ids":
            target_payload[key] = _parse_symbolic_list(value)
        else:
            target_payload[key] = value

    try:
        return MicroscopicSemanticContractDraft.model_validate(
            {
                "contract_version": int(root_values["contract_version"]),
                "local_goal": root_values["local_goal"],
                "primary_capability": root_values["primary_capability"],
                "needs_discovery": root_values.get("needs_discovery") or None,
                "target_object_kind": root_values["target_object_kind"],
                "requested_route_summary": root_values["requested_route_summary"],
                "requested_deliverables": _parse_pipe_list(root_values["requested_deliverables"]),
                "unsupported_requests": _parse_pipe_list(root_values.get("unsupported_requests", "")),
                "constraints": constraints_payload,
                "selection": selection_payload,
                "target": target_payload,
            }
        )
    except ValidationError as exc:
        raise TaggedMicroscopicProtocolError(f"Invalid microscopic semantic contract: {exc}") from exc


def _tagged_contract_version(contract_text: str) -> Optional[str]:
    for raw_line in contract_text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip() == "contract_version":
            normalized = value.strip()
            return normalized or None
    return None


def _parse_tagged_action_card_lines(contract_text: str) -> tuple[dict[str, str], dict[str, str]]:
    root_values: dict[str, str] = {}
    param_values: dict[str, str] = {}
    seen_keys: set[str] = set()
    for raw_line in contract_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            raise TaggedMicroscopicProtocolError(f"Invalid action-card line '{raw_line}'. Expected key=value.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in seen_keys:
            raise TaggedMicroscopicProtocolError(f"Duplicate action-card key '{key}'.")
        seen_keys.add(key)
        if key.startswith("param."):
            field_name = key[len("param.") :]
            if not field_name:
                raise TaggedMicroscopicProtocolError("Action-card params must use the form param.<name>=value.")
            param_values[field_name] = value
            continue
        if key not in _TAGGED_ACTION_CARD_ROOT_KEYS:
            raise TaggedMicroscopicProtocolError(f"Unknown action-card key '{key}'.")
        root_values[key] = value
    return root_values, param_values


def _parse_registry_param_value(
    param_name: str,
    raw_value: str,
    definition: Any,
) -> Any:
    param_type = getattr(definition, "param_type", None)
    if param_type == "bool":
        return _parse_bool(raw_value)
    if param_type == "int":
        try:
            return int(raw_value)
        except ValueError as exc:
            raise TaggedMicroscopicProtocolError(
                f"Invalid integer literal for param.{param_name}: {raw_value!r}."
            ) from exc
    if param_type == "float_list":
        return _parse_float_list(raw_value)
    if param_type == "int_list":
        return _parse_int_list(raw_value)
    if param_type == "text":
        return raw_value
    if param_type == "text_list":
        return _parse_symbolic_list(raw_value)
    if param_type == "bond_type_list":
        return _parse_symbolic_list(raw_value)
    if param_type == "min_relevance":
        return raw_value.strip()
    if param_type == "artifact_kind":
        return raw_value.strip()
    if param_type == "source_round_selector":
        return MicroscopicSemanticSelectionDraft._normalize_source_round_selector(raw_value)  # type: ignore[misc]
    if param_type in {"dihedral_id", "conformer_id", "artifact_bundle_id"}:
        normalized = raw_value.strip()
        if _is_placeholder_target_value(normalized):
            raise TaggedMicroscopicProtocolError(
                f"Placeholder target values are not allowed for param.{param_name}: {normalized!r}."
            )
        return normalized
    if param_type == "conformer_ids":
        values = _parse_symbolic_list(raw_value)
        placeholders = [item for item in values if _is_placeholder_target_value(item)]
        if placeholders:
            raise TaggedMicroscopicProtocolError(
                f"Placeholder target values are not allowed for param.{param_name}: {', '.join(placeholders)}."
            )
        return values
    raise TaggedMicroscopicProtocolError(
        f"Unsupported registry param type '{param_type}' for param.{param_name}."
    )


def _validate_enum_param_values(
    *,
    param_name: str,
    value: Any,
    definition: Any,
) -> None:
    enum_values = list(getattr(definition, "enum_values", []) or [])
    if not enum_values:
        return
    if isinstance(value, list):
        invalid = [item for item in value if item not in enum_values]
        if invalid:
            raise TaggedMicroscopicProtocolError(
                f"Invalid values for param.{param_name}: {invalid}. Allowed values: {enum_values}."
            )
        return
    if value not in enum_values:
        raise TaggedMicroscopicProtocolError(
            f"Invalid value for param.{param_name}: {value!r}. Allowed values: {enum_values}."
        )


def _build_action_card_draft(
    root_values: dict[str, str],
    param_values: dict[str, str],
) -> tuple[MicroscopicActionCardDraft, AmespActionDefinition]:
    if root_values.get("contract_version") != "2":
        raise TaggedMicroscopicProtocolError(
            f"Unsupported microscopic semantic contract_version '{root_values.get('contract_version')}'."
        )
    required_root_keys = (
        "contract_version",
        "local_goal",
        "execution_action",
        "requested_route_summary",
        "requested_deliverables",
    )
    missing_root_keys = [key for key in required_root_keys if key not in root_values]
    if missing_root_keys:
        raise TaggedMicroscopicProtocolError(
            "Registry-backed action card is missing required keys: " + ", ".join(missing_root_keys)
        )
    execution_action = root_values["execution_action"]
    action_definition = AMESP_ACTION_REGISTRY.get(execution_action)
    if action_definition is None:
        raise TaggedMicroscopicProtocolError(f"Unknown execution_action '{execution_action}'.")
    if action_definition.action_kind != "execution":
        raise TaggedMicroscopicProtocolError(
            f"execution_action '{execution_action}' must resolve to an execution action."
        )

    discovery_actions = _parse_pipe_list(root_values.get("discovery_actions", ""))
    if len(discovery_actions) > 1:
        raise TaggedMicroscopicProtocolError(
            "At most one discovery action may be requested in the current microscopic round."
        )
    for discovery_action in discovery_actions:
        discovery_definition = AMESP_ACTION_REGISTRY.get(discovery_action)
        if discovery_definition is None or discovery_definition.action_kind != "discovery":
            raise TaggedMicroscopicProtocolError(
                f"Invalid discovery action '{discovery_action}' for execution_action '{execution_action}'."
            )
        if discovery_action not in action_definition.allowed_discovery_actions:
            raise TaggedMicroscopicProtocolError(
                f"Discovery action '{discovery_action}' is not permitted for execution_action '{execution_action}'."
            )

    params_payload: dict[str, Any] = {}
    for param_name, raw_value in param_values.items():
        if param_name in action_definition.python_owned_params:
            raise TaggedMicroscopicProtocolError(
                f"param.{param_name} is Python-owned and must not be authored by the LLM."
            )
        if param_name not in action_definition.allowed_llm_params:
            raise TaggedMicroscopicProtocolError(
                f"param.{param_name} is not allowed for execution_action '{execution_action}'."
            )
        definition = action_definition.param_types[param_name]
        parsed_value = _parse_registry_param_value(param_name, raw_value, definition)
        _validate_enum_param_values(param_name=param_name, value=parsed_value, definition=definition)
        params_payload[param_name] = parsed_value

    missing_required = [
        param_name
        for param_name in action_definition.required_params
        if param_name not in params_payload and param_name not in action_definition.defaults
    ]
    if missing_required:
        raise TaggedMicroscopicProtocolError(
            "Registry-backed action card is missing required params: "
            + ", ".join(f"param.{name}" for name in missing_required)
        )

    try:
        action_card = MicroscopicActionCardDraft.model_validate(
            {
                "contract_version": 2,
                "local_goal": root_values["local_goal"],
                "execution_action": execution_action,
                "discovery_actions": discovery_actions,
                "requested_route_summary": root_values["requested_route_summary"],
                "requested_deliverables": _parse_pipe_list(root_values["requested_deliverables"]),
                "unsupported_requests": _parse_pipe_list(root_values.get("unsupported_requests", "")),
                "params": params_payload,
            }
        )
    except ValidationError as exc:
        raise TaggedMicroscopicProtocolError(
            f"Invalid registry-backed microscopic action card: {exc}"
        ) from exc
    return action_card, action_definition


def _semantic_contract_from_action_card(
    action_card: MicroscopicActionCardDraft,
    *,
    action_definition: AmespActionDefinition,
) -> MicroscopicSemanticContractDraft:
    params = {**action_definition.defaults, **action_card.params}
    execution_action = action_card.execution_action
    discovery_action = action_card.discovery_actions[0] if action_card.discovery_actions else None

    needs_discovery: Optional[MicroscopicSemanticDiscoveryNeed] = None
    target_object_kind: MicroscopicSemanticTargetObjectKind = "none"
    constraints_payload: dict[str, Any] = {}
    selection_payload: dict[str, Any] = {}
    target_payload: dict[str, Any] = {}

    if execution_action == "run_baseline_bundle":
        target_object_kind = "none"
        for key in ("perform_new_calculation", "optimize_ground_state", "reuse_existing_artifacts_only", "state_window"):
            if key in params:
                constraints_payload[key] = params[key]
    elif execution_action == "run_torsion_snapshots":
        target_object_kind = "dihedral"
        if discovery_action == "list_rotatable_dihedrals" or "dihedral_id" not in params:
            needs_discovery = "rotatable_dihedrals"
        if "dihedral_id" in params:
            target_payload["dihedral_id"] = params["dihedral_id"]
        for key in (
            "perform_new_calculation",
            "optimize_ground_state",
            "reuse_existing_artifacts_only",
            "snapshot_count",
            "angle_offsets_deg",
            "state_window",
            "honor_exact_target",
            "allow_fallback",
        ):
            if key in params:
                constraints_payload[key] = params[key]
        for key in (
            "exclude_dihedral_ids",
            "prefer_adjacent_to_nsnc_core",
            "min_relevance",
            "include_peripheral",
            "preferred_bond_types",
            "source_round_selector",
        ):
            if key in params:
                selection_payload[key] = params[key]
    elif execution_action == "run_conformer_bundle":
        target_object_kind = "conformer"
        if discovery_action == "list_available_conformers" or not any(
            key in params for key in ("conformer_id", "conformer_ids")
        ):
            needs_discovery = "conformers"
        if "conformer_id" in params:
            target_payload["conformer_id"] = params["conformer_id"]
        if "conformer_ids" in params:
            target_payload["conformer_ids"] = params["conformer_ids"]
        for key in (
            "perform_new_calculation",
            "optimize_ground_state",
            "reuse_existing_artifacts_only",
            "snapshot_count",
            "max_conformers",
            "state_window",
            "honor_exact_target",
            "allow_fallback",
        ):
            if key in params:
                constraints_payload[key] = params[key]
        if "source_round_selector" in params:
            selection_payload["source_round_selector"] = params["source_round_selector"]
    elif execution_action == "parse_snapshot_outputs":
        target_object_kind = "artifact_bundle"
        if discovery_action == "list_artifact_bundles" or "artifact_bundle_id" not in params:
            needs_discovery = "artifact_bundles"
        if "artifact_bundle_id" in params:
            target_payload["artifact_bundle_id"] = params["artifact_bundle_id"]
        for key in ("perform_new_calculation", "reuse_existing_artifacts_only", "state_window"):
            if key in params:
                constraints_payload[key] = params[key]
        for key in ("artifact_kind", "source_round_selector"):
            if key in params:
                selection_payload[key] = params[key]
    elif execution_action == "unsupported_excited_state_relaxation":
        target_object_kind = "none"
    else:
        raise TaggedMicroscopicProtocolError(
            f"Unsupported registry-backed execution_action '{execution_action}'."
        )

    try:
        return MicroscopicSemanticContractDraft.model_validate(
            {
                "contract_version": 1,
                "local_goal": action_card.local_goal,
                "primary_capability": execution_action,
                "needs_discovery": needs_discovery,
                "target_object_kind": target_object_kind,
                "requested_route_summary": action_card.requested_route_summary,
                "requested_deliverables": list(action_card.requested_deliverables),
                "unsupported_requests": list(action_card.unsupported_requests),
                "constraints": constraints_payload,
                "selection": selection_payload,
                "target": target_payload,
            }
        )
    except ValidationError as exc:
        raise TaggedMicroscopicProtocolError(
            f"Registry-backed action card could not be compiled into the canonical semantic contract: {exc}"
        ) from exc


def compile_action_card_to_tool_plan(
    action_card: MicroscopicActionCardDraft,
    *,
    action_definition: AmespActionDefinition,
    task_instruction: str,
    task_mode: str,
    expected_outputs: list[str],
    failure_policy: str,
    budget_profile: Literal["conservative", "balanced", "aggressive"],
    available_structure_context: Optional[dict[str, Any]] = None,
    shared_structure_context: Optional[dict[str, Any]] = None,
    current_round_index: Optional[int] = None,
) -> tuple[MicroscopicSemanticContractDraft, MicroscopicToolPlan, MicroscopicToolRequest, MicroscopicExecutionPlan]:
    contract = _semantic_contract_from_action_card(
        action_card,
        action_definition=action_definition,
    )
    tool_plan, execution_request, execution_plan = compile_semantic_contract_to_tool_plan(
        contract,
        task_instruction=task_instruction,
        task_mode=task_mode,
        expected_outputs=expected_outputs,
        failure_policy=failure_policy,
        budget_profile=budget_profile,
        available_structure_context=available_structure_context,
        shared_structure_context=shared_structure_context,
        current_round_index=current_round_index,
    )
    return contract, tool_plan, execution_request, execution_plan


def _has_explicit_contract_target(contract: MicroscopicSemanticContractDraft) -> bool:
    return any(
        (
            contract.target.dihedral_id,
            contract.target.conformer_id,
            contract.target.conformer_ids,
            contract.target.artifact_bundle_id,
        )
    )


def _required_discovery_for_contract(contract: MicroscopicSemanticContractDraft) -> Optional[MicroscopicSemanticDiscoveryNeed]:
    if _has_explicit_contract_target(contract):
        return None
    if contract.needs_discovery is not None:
        return contract.needs_discovery
    if contract.primary_capability == "run_torsion_snapshots":
        return "rotatable_dihedrals"
    if contract.primary_capability == "run_conformer_bundle":
        return "conformers"
    if contract.primary_capability == "parse_snapshot_outputs":
        return "artifact_bundles"
    return None


def _selection_policy_from_semantic_contract(
    contract: MicroscopicSemanticContractDraft,
    *,
    current_round_index: Optional[int],
) -> SelectionPolicy:
    return SelectionPolicy(
        exclude_dihedral_ids=list(contract.selection.exclude_dihedral_ids),
        prefer_adjacent_to_nsnc_core=bool(contract.selection.prefer_adjacent_to_nsnc_core or False),
        min_relevance=contract.selection.min_relevance or "medium",
        include_peripheral=True if contract.selection.include_peripheral is None else contract.selection.include_peripheral,
        preferred_bond_types=list(contract.selection.preferred_bond_types),
        artifact_kind=contract.selection.artifact_kind,
        source_round_preference=_source_round_preference_from_selector(
            contract.selection.source_round_selector,
            current_round_index=current_round_index,
        ),
    )


def _planning_unmet_constraints_for_instruction(
    *,
    task_instruction: str,
    capability_name: AmespCapabilityName,
) -> list[str]:
    lower_instruction = task_instruction.lower()
    unmet: list[str] = []
    if capability_name == "run_torsion_snapshots":
        multi_target_patterns = (
            "two dihedrals",
            "two selected dihedrals",
            "two selected rotatable dihedrals",
            "2 dihedrals",
            "multiple dihedrals",
            "two key dihedrals",
        )
        if any(pattern in lower_instruction for pattern in multi_target_patterns):
            unmet.append(
                "The Planner instruction referenced multiple torsion targets, but the current microscopic contract executes one resolved dihedral per round."
            )
    return unmet


def compile_semantic_contract_to_tool_plan(
    contract: MicroscopicSemanticContractDraft,
    *,
    task_instruction: str,
    task_mode: str,
    expected_outputs: list[str],
    failure_policy: str,
    budget_profile: Literal["conservative", "balanced", "aggressive"],
    available_structure_context: Optional[dict[str, Any]] = None,
    shared_structure_context: Optional[dict[str, Any]] = None,
    current_round_index: Optional[int] = None,
) -> tuple[MicroscopicToolPlan, MicroscopicToolRequest, MicroscopicExecutionPlan]:
    payload = {
        "available_structure_context": available_structure_context or {},
        "shared_structure_context": shared_structure_context,
    }
    has_reusable_structure = _has_reusable_structure_from_payload(payload)
    structure_strategy = _derive_structure_strategy_from_payload(payload)
    selection_policy = _selection_policy_from_semantic_contract(
        contract,
        current_round_index=current_round_index,
    )
    effective_capability = contract.primary_capability
    planning_unmet_constraints = _planning_unmet_constraints_for_instruction(
        task_instruction=task_instruction,
        capability_name=contract.primary_capability,
    )
    if task_mode == "baseline_s0_s1" and effective_capability != "run_baseline_bundle":
        planning_unmet_constraints.append(
            f"Baseline microscopic rounds must execute `run_baseline_bundle`; the semantic contract requested `{effective_capability}` and was contracted to the fixed baseline route."
        )
        effective_capability = "run_baseline_bundle"
    discovery_need = _required_discovery_for_contract(contract) if effective_capability == contract.primary_capability else None
    calls: list[MicroscopicToolCall] = []

    if discovery_need == "rotatable_dihedrals":
        calls.append(
            MicroscopicToolCall(
                call_id="discover_rotatable_dihedrals",
                call_kind="discovery",
                request=MicroscopicToolRequest(
                    capability_name="list_rotatable_dihedrals",
                    structure_source=_structure_source_for_semantic_capability(
                        "list_rotatable_dihedrals",
                        task_mode=task_mode,
                        has_reusable_structure=has_reusable_structure,
                    ),
                    min_relevance=selection_policy.min_relevance,
                    include_peripheral=selection_policy.include_peripheral,
                    preferred_bond_types=list(selection_policy.preferred_bond_types),
                    requested_route_summary="Discover stable rotatable dihedral targets before bounded torsion execution.",
                ),
            )
        )
    elif discovery_need == "conformers":
        calls.append(
            MicroscopicToolCall(
                call_id="discover_conformers",
                call_kind="discovery",
                request=MicroscopicToolRequest(
                    capability_name="list_available_conformers",
                    structure_source=_structure_source_for_semantic_capability(
                        "list_available_conformers",
                        task_mode=task_mode,
                        has_reusable_structure=has_reusable_structure,
                    ),
                    requested_route_summary="Discover stable conformer targets before bounded conformer execution.",
                ),
            )
        )
    elif discovery_need == "artifact_bundles":
        calls.append(
            MicroscopicToolCall(
                call_id="discover_artifact_bundles",
                call_kind="discovery",
                request=MicroscopicToolRequest(
                    capability_name="list_artifact_bundles",
                    artifact_kind=selection_policy.artifact_kind,
                    source_round_preference=selection_policy.source_round_preference,
                    perform_new_calculation=False,
                    reuse_existing_artifacts_only=True,
                    requested_route_summary="Discover canonical artifact bundles before parse-only microscopic execution.",
                ),
            )
        )

    capability_definition = AMESP_CAPABILITY_REGISTRY[effective_capability]
    execution_request = MicroscopicToolRequest(
        capability_name=effective_capability,
        structure_source=_structure_source_for_semantic_capability(
            effective_capability,
            task_mode=task_mode,
            has_reusable_structure=has_reusable_structure,
        ),
        perform_new_calculation=(
            contract.constraints.perform_new_calculation
            if contract.constraints.perform_new_calculation is not None
            else capability_definition.requires_new_calculation
        ),
        optimize_ground_state=(
            contract.constraints.optimize_ground_state
            if contract.constraints.optimize_ground_state is not None
            else effective_capability != "parse_snapshot_outputs"
        ),
        reuse_existing_artifacts_only=(
            contract.constraints.reuse_existing_artifacts_only
            if contract.constraints.reuse_existing_artifacts_only is not None
            else not capability_definition.requires_new_calculation
        ),
        artifact_bundle_id=contract.target.artifact_bundle_id if effective_capability == "parse_snapshot_outputs" else None,
        artifact_kind=selection_policy.artifact_kind if effective_capability == "parse_snapshot_outputs" else None,
        artifact_source_round=selection_policy.source_round_preference if effective_capability == "parse_snapshot_outputs" else None,
        source_round_preference=selection_policy.source_round_preference if effective_capability in {"parse_snapshot_outputs", "list_artifact_bundles"} else selection_policy.source_round_preference,
        min_relevance=selection_policy.min_relevance,
        include_peripheral=selection_policy.include_peripheral,
        preferred_bond_types=list(selection_policy.preferred_bond_types),
        dihedral_id=contract.target.dihedral_id if effective_capability == "run_torsion_snapshots" else None,
        conformer_id=contract.target.conformer_id if effective_capability == "run_conformer_bundle" else None,
        conformer_ids=list(contract.target.conformer_ids) if effective_capability == "run_conformer_bundle" else [],
        max_conformers=contract.constraints.max_conformers,
        snapshot_count=contract.constraints.snapshot_count if effective_capability in {"run_torsion_snapshots", "run_conformer_bundle"} else None,
        angle_offsets_deg=list(contract.constraints.angle_offsets_deg) if effective_capability == "run_torsion_snapshots" else [],
        state_window=list(contract.constraints.state_window),
        honor_exact_target=contract.constraints.honor_exact_target if contract.constraints.honor_exact_target is not None else True,
        allow_fallback=contract.constraints.allow_fallback if contract.constraints.allow_fallback is not None else False,
        deliverables=list(contract.requested_deliverables),
        budget_profile=budget_profile,
        requested_route_summary=contract.requested_route_summary,
    )
    calls.append(
        MicroscopicToolCall(
            call_id=f"execute_{effective_capability}",
            call_kind="execution",
            request=execution_request,
        )
    )
    tool_plan = MicroscopicToolPlan(
        calls=calls,
        requested_route_summary=contract.requested_route_summary,
        requested_deliverables=list(contract.requested_deliverables),
        selection_policy=selection_policy,
        normalization_notes=[],
        failure_reporting=failure_policy,
    )
    execution_plan = MicroscopicExecutionPlan(
        local_goal=contract.local_goal,
        requested_deliverables=list(contract.requested_deliverables),
        capability_route=_compatibility_route_for_capability_name(effective_capability),
        microscopic_tool_plan=tool_plan,
        microscopic_tool_request=execution_request,
        budget_profile=budget_profile,
        requested_route_summary=contract.requested_route_summary,
        structure_source=(
            "existing_prepared_structure"
            if structure_strategy == "reuse_if_available_else_prepare_from_smiles" and has_reusable_structure
            else "prepared_from_smiles"
        ),
        unsupported_requests=list(contract.unsupported_requests),
        planning_unmet_constraints=planning_unmet_constraints,
        expected_outputs=list(expected_outputs),
        failure_reporting=failure_policy,
    )
    return tool_plan, execution_request, execution_plan


def _selection_policy_from_reasoning_draft(draft: Optional[SelectionPolicyDraft]) -> SelectionPolicy:
    if draft is None:
        return SelectionPolicy()
    return SelectionPolicy(
        exclude_dihedral_ids=list(draft.exclude_dihedral_ids),
        prefer_adjacent_to_nsnc_core=bool(draft.prefer_adjacent_to_nsnc_core or False),
        min_relevance=draft.min_relevance or "medium",
        include_peripheral=True if draft.include_peripheral is None else draft.include_peripheral,
        preferred_bond_types=list(draft.preferred_bond_types),
        artifact_kind=draft.artifact_kind,
        source_round_preference=draft.source_round_preference,
    )


def _default_requested_deliverables_for_capability(capability_name: AmespCapabilityName) -> list[str]:
    if capability_name == "run_baseline_bundle":
        return [
            "low-cost aTB S0 geometry optimization",
            "vertical excited-state manifold characterization",
        ]
    if capability_name == "run_conformer_bundle":
        return ["conformer-sensitivity summary"]
    if capability_name == "run_torsion_snapshots":
        return ["torsion-sensitivity summary", "vertical excited-state manifold characterization"]
    if capability_name == "parse_snapshot_outputs":
        return [
            "per-snapshot excitation energies",
            "per-snapshot oscillator strengths",
            "state-ordering records",
        ]
    return ["unsupported follow-up report"]


def _default_expected_outputs_for_capability(capability_name: AmespCapabilityName) -> list[str]:
    if capability_name == "run_baseline_bundle":
        return [
            "S0 optimized geometry",
            "S0 final energy",
            "S0 dipole",
            "S0 Mulliken charges",
            "S0 HOMO-LUMO gap",
            "vertical excited-state manifold",
            "first bright state energy",
            "first bright state oscillator strength",
        ]
    if capability_name == "run_conformer_bundle":
        return [
            "bounded conformer bundle vertical-state records",
            "excitation spread",
            "bright-state sensitivity",
            "conformer-dependent uncertainty note",
        ]
    if capability_name == "run_torsion_snapshots":
        return [
            "snapshot geometry labels",
            "snapshot vertical-state proxies",
            "torsion sensitivity summary",
        ]
    if capability_name == "parse_snapshot_outputs":
        return [
            "per-snapshot excitation energies",
            "per-snapshot oscillator strengths",
            "state-ordering records",
            "artifact reuse note",
        ]
    return ["unsupported follow-up report"]


def _default_requested_route_summary_for_capability(capability_name: AmespCapabilityName) -> str:
    if capability_name == "run_baseline_bundle":
        return "Use the default low-cost baseline bundle."
    if capability_name == "run_conformer_bundle":
        return "Use the bounded conformer-bundle follow-up route."
    if capability_name == "run_torsion_snapshots":
        return "Use the bounded torsion-snapshot follow-up route."
    if capability_name == "parse_snapshot_outputs":
        return "Reuse an existing artifact bundle and parse snapshot outputs without new calculations."
    return "Use the unsupported excited-state-relaxation placeholder route."


def _default_call_kind_for_capability(
    capability_name: AmespCapabilityName,
) -> Literal["discovery", "execution"]:
    if capability_name in {"list_rotatable_dihedrals", "list_available_conformers", "list_artifact_bundles"}:
        return "discovery"
    return "execution"


def _default_optimize_ground_state_for_capability(capability_name: AmespCapabilityName) -> bool:
    return capability_name != "parse_snapshot_outputs"


def _normalize_tool_request_from_draft(
    *,
    draft: MicroscopicToolRequestDraft,
    capability_name: AmespCapabilityName,
    requested_deliverables: list[str],
    budget_profile: Literal["conservative", "balanced", "aggressive"],
    config: AieMasConfig,
    task_mode: str,
    has_reusable_structure: bool,
    selection_policy: SelectionPolicy,
) -> MicroscopicToolRequest:
    capability = AMESP_CAPABILITY_REGISTRY[capability_name]
    snapshot_count = draft.snapshot_count
    state_window = list(draft.state_window)
    if capability_name == "run_conformer_bundle" and snapshot_count is None and draft.max_conformers is None:
        snapshot_count = config.amesp_follow_up_max_conformers
    if capability_name == "run_torsion_snapshots" and snapshot_count is None:
        snapshot_count = 2 if draft.angle_offsets_deg else config.amesp_follow_up_max_torsion_snapshots_total
    if capability_name in {"run_baseline_bundle", "run_conformer_bundle", "run_torsion_snapshots", "parse_snapshot_outputs"} and not state_window:
        state_window = list(range(1, max(1, config.amesp_s1_nstates) + 1))
    source_round_preference = (
        draft.source_round_preference
        if draft.source_round_preference is not None
        else selection_policy.source_round_preference
    )
    min_relevance = draft.min_relevance if draft.min_relevance is not None else selection_policy.min_relevance
    include_peripheral = (
        draft.include_peripheral
        if draft.include_peripheral is not None
        else selection_policy.include_peripheral
    )
    preferred_bond_types = (
        list(draft.preferred_bond_types)
        if draft.preferred_bond_types
        else list(selection_policy.preferred_bond_types)
    )
    return MicroscopicToolRequest(
        capability_name=capability_name,
        structure_source=(
            draft.structure_source
            or _structure_source_for_semantic_capability(
                capability_name,
                task_mode=task_mode,
                has_reusable_structure=has_reusable_structure,
            )
        ),
        perform_new_calculation=(
            draft.perform_new_calculation
            if draft.perform_new_calculation is not None
            else capability.requires_new_calculation
        ),
        optimize_ground_state=(
            draft.optimize_ground_state
            if draft.optimize_ground_state is not None
            else _default_optimize_ground_state_for_capability(capability_name)
        ),
        reuse_existing_artifacts_only=(
            draft.reuse_existing_artifacts_only
            if draft.reuse_existing_artifacts_only is not None
            else not capability.requires_new_calculation
        ),
        artifact_source_round=draft.artifact_source_round,
        artifact_scope=draft.artifact_scope,
        artifact_bundle_id=draft.artifact_bundle_id,
        artifact_kind=draft.artifact_kind or selection_policy.artifact_kind,
        source_round_preference=source_round_preference,
        min_relevance=min_relevance,
        include_peripheral=include_peripheral,
        preferred_bond_types=preferred_bond_types,
        dihedral_id=draft.dihedral_id,
        dihedral_atom_indices=list(draft.dihedral_atom_indices),
        conformer_id=draft.conformer_id,
        conformer_ids=list(draft.conformer_ids),
        max_conformers=draft.max_conformers,
        snapshot_count=snapshot_count,
        angle_offsets_deg=list(draft.angle_offsets_deg),
        state_window=state_window,
        honor_exact_target=draft.honor_exact_target if draft.honor_exact_target is not None else True,
        allow_fallback=draft.allow_fallback if draft.allow_fallback is not None else False,
        deliverables=list(draft.deliverables) if draft.deliverables else list(requested_deliverables),
        budget_profile=draft.budget_profile or budget_profile,
        requested_route_summary=draft.requested_route_summary or _default_requested_route_summary_for_capability(capability_name),
    )


def _normalize_tool_call_from_draft(
    *,
    draft_call: MicroscopicToolCallDraft,
    requested_deliverables: list[str],
    budget_profile: Literal["conservative", "balanced", "aggressive"],
    config: AieMasConfig,
    task_mode: str,
    has_reusable_structure: bool,
    selection_policy: SelectionPolicy,
) -> MicroscopicToolCall:
    request_draft = draft_call.request or MicroscopicToolRequestDraft()
    capability_name = request_draft.capability_name or "unsupported_excited_state_relaxation"
    call_kind = draft_call.call_kind or _default_call_kind_for_capability(capability_name)
    return MicroscopicToolCall(
        call_id=draft_call.call_id or f"{call_kind}_{capability_name}",
        call_kind=call_kind,
        request=_normalize_tool_request_from_draft(
            draft=request_draft,
            capability_name=capability_name,
            requested_deliverables=requested_deliverables,
            budget_profile=budget_profile,
            config=config,
            task_mode=task_mode,
            has_reusable_structure=has_reusable_structure,
            selection_policy=selection_policy,
        ),
    )


def _insert_required_discovery_calls(
    *,
    calls: list[MicroscopicToolCall],
    selection_policy: SelectionPolicy,
    task_mode: str,
    has_reusable_structure: bool,
) -> list[MicroscopicToolCall]:
    has_dihedral_discovery = any(call.request.capability_name == "list_rotatable_dihedrals" for call in calls)
    has_conformer_discovery = any(call.request.capability_name == "list_available_conformers" for call in calls)
    has_artifact_discovery = any(call.request.capability_name == "list_artifact_bundles" for call in calls)
    normalized: list[MicroscopicToolCall] = []
    for call in calls:
        if (
            call.call_kind == "execution"
            and call.request.capability_name == "run_torsion_snapshots"
            and not call.request.dihedral_id
            and not has_dihedral_discovery
        ):
            normalized.append(
                MicroscopicToolCall(
                    call_id="discover_rotatable_dihedrals",
                    call_kind="discovery",
                    request=MicroscopicToolRequest(
                        capability_name="list_rotatable_dihedrals",
                        structure_source=_structure_source_for_semantic_capability(
                            "list_rotatable_dihedrals",
                            task_mode=task_mode,
                            has_reusable_structure=has_reusable_structure,
                        ),
                        min_relevance=selection_policy.min_relevance,
                        include_peripheral=selection_policy.include_peripheral,
                        preferred_bond_types=list(selection_policy.preferred_bond_types),
                        requested_route_summary="Discover stable rotatable dihedral targets before bounded torsion execution.",
                    ),
                )
            )
            has_dihedral_discovery = True
        if (
            call.call_kind == "execution"
            and call.request.capability_name == "run_conformer_bundle"
            and not call.request.conformer_id
            and not call.request.conformer_ids
            and not has_conformer_discovery
        ):
            normalized.append(
                MicroscopicToolCall(
                    call_id="discover_conformers",
                    call_kind="discovery",
                    request=MicroscopicToolRequest(
                        capability_name="list_available_conformers",
                        structure_source=_structure_source_for_semantic_capability(
                            "list_available_conformers",
                            task_mode=task_mode,
                            has_reusable_structure=has_reusable_structure,
                        ),
                        requested_route_summary="Discover stable conformer targets before bounded conformer execution.",
                    ),
                )
            )
            has_conformer_discovery = True
        if (
            call.call_kind == "execution"
            and call.request.capability_name == "parse_snapshot_outputs"
            and not call.request.artifact_bundle_id
            and not has_artifact_discovery
        ):
            normalized.append(
                MicroscopicToolCall(
                    call_id="discover_artifact_bundles",
                    call_kind="discovery",
                    request=MicroscopicToolRequest(
                        capability_name="list_artifact_bundles",
                        artifact_kind=call.request.artifact_kind or selection_policy.artifact_kind,
                        source_round_preference=call.request.source_round_preference or selection_policy.source_round_preference,
                        perform_new_calculation=False,
                        reuse_existing_artifacts_only=True,
                        requested_route_summary="Discover canonical artifact bundles before parse-only microscopic execution.",
                    ),
                )
            )
            has_artifact_discovery = True
        normalized.append(call)
    return normalized


def _canonicalize_compiled_tool_call_sequence(
    calls: list[MicroscopicToolCall],
) -> tuple[list[MicroscopicToolCall], list[str]]:
    normalized: list[MicroscopicToolCall] = []
    normalization_notes: list[str] = []
    execution_seen = False
    execution_call_id: Optional[str] = None
    for call in calls:
        if execution_seen:
            normalization_notes.append(
                f"Dropped trailing {call.call_kind} call `{call.call_id}` after execution `{execution_call_id}`."
            )
            continue
        normalized.append(call)
        if call.call_kind == "execution":
            execution_seen = True
            execution_call_id = call.call_id
    return normalized, normalization_notes


def _fallback_capability_name_for_plan_draft(
    reasoning: MicroscopicReasoningResponse,
    *,
    task_mode: str,
) -> AmespCapabilityName:
    draft_request = reasoning.execution_plan.microscopic_tool_request
    if draft_request is not None and draft_request.capability_name is not None:
        return draft_request.capability_name
    routed_capability = _capability_name_for_compatibility_route(reasoning.execution_plan.capability_route)
    if routed_capability is not None:
        return routed_capability
    if task_mode == "baseline_s0_s1":
        return "run_baseline_bundle"
    return "unsupported_excited_state_relaxation"


def _build_fallback_tool_calls_from_reasoning(
    *,
    reasoning: MicroscopicReasoningResponse,
    requested_deliverables: list[str],
    budget_profile: Literal["conservative", "balanced", "aggressive"],
    config: AieMasConfig,
    task_mode: str,
    has_reusable_structure: bool,
    selection_policy: SelectionPolicy,
) -> list[MicroscopicToolCall]:
    draft_request = reasoning.execution_plan.microscopic_tool_request or MicroscopicToolRequestDraft()
    capability_name = _fallback_capability_name_for_plan_draft(reasoning, task_mode=task_mode)
    execution_request = _normalize_tool_request_from_draft(
        draft=draft_request,
        capability_name=capability_name,
        requested_deliverables=requested_deliverables,
        budget_profile=budget_profile,
        config=config,
        task_mode=task_mode,
        has_reusable_structure=has_reusable_structure,
        selection_policy=selection_policy,
    )
    return [
        MicroscopicToolCall(
            call_id=f"execute_{capability_name}",
            call_kind="execution",
            request=execution_request,
        )
    ]


def _build_execution_steps(
    *,
    config: AieMasConfig,
    capability_name: AmespCapabilityName,
    structure_source: str,
    optimize_ground_state: bool,
    perform_new_calculation: bool,
) -> list[MicroscopicExecutionStep]:
    if capability_name == "run_baseline_bundle":
        step_types: list[str] = ["structure_prep", "s0_optimization", "s1_vertical_excitation"]
    elif capability_name == "run_conformer_bundle":
        step_types = [
            "conformer_bundle_generation",
            "s0_optimization" if optimize_ground_state else "s0_singlepoint",
            "s1_vertical_excitation",
        ]
    elif capability_name == "run_torsion_snapshots":
        step_types = [
            "torsion_snapshot_generation",
            "s0_optimization" if optimize_ground_state else "s0_singlepoint",
            "s1_vertical_excitation",
        ]
    elif capability_name == "parse_snapshot_outputs":
        step_types = ["artifact_parse"]
    else:
        step_types = ["structure_prep"]
    if structure_source == "existing_prepared_structure" and perform_new_calculation:
        step_types = [step for step in step_types if step != "structure_prep"]
    steps: list[MicroscopicExecutionStep] = []
    for step_type in step_types:
        if step_type == "structure_prep":
            steps.append(
                MicroscopicExecutionStep(
                    step_id="structure_prep",
                    step_type="structure_prep",
                    description="Reuse a prepared 3D structure if available; otherwise generate a 3D structure from the input SMILES.",
                    input_source="available prepared structure artifacts or SMILES",
                    expected_outputs=["prepared_structure.xyz", "prepared_structure.sdf", "structure_prep_summary.json"],
                )
            )
        elif step_type == "conformer_bundle_generation":
            steps.append(
                MicroscopicExecutionStep(
                    step_id="conformer_bundle_generation",
                    step_type="conformer_bundle_generation",
                    description=(
                        f"Generate a bounded conformer bundle and keep at most {config.amesp_follow_up_max_conformers} conformers "
                        "for low-cost Amesp follow-up."
                    ),
                    input_source="SMILES or reusable prepared structure context",
                    expected_outputs=["bounded conformer bundle", "per-conformer prepared geometry records"],
                )
            )
        elif step_type == "torsion_snapshot_generation":
            steps.append(
                MicroscopicExecutionStep(
                    step_id="torsion_snapshot_generation",
                    step_type="torsion_snapshot_generation",
                    description=(
                        f"Generate bounded torsion snapshots for at most {config.amesp_follow_up_max_torsion_snapshots_total} "
                        "snapshot geometries, without running a full scan or TS/IRC."
                    ),
                    input_source="prepared structure and detected rotatable dihedral candidates",
                    expected_outputs=["snapshot geometry labels", "bounded torsion snapshot structures"],
                )
            )
        elif step_type == "artifact_parse":
            steps.append(
                MicroscopicExecutionStep(
                    step_id="artifact_parse",
                    step_type="artifact_parse",
                    description="Parse existing microscopic snapshot artifacts without generating new Amesp inputs or rerunning S0/S1 calculations.",
                    input_source="available microscopic artifact bundle",
                    expected_outputs=[
                        "per-snapshot excitation energies",
                        "per-snapshot oscillator strengths",
                        "state-ordering summaries",
                    ],
                )
            )
        elif step_type == "s0_optimization":
            steps.append(
                MicroscopicExecutionStep(
                    step_id="s0_optimization",
                    step_type="s0_optimization",
                    description="Run a real low-cost Amesp aTB S0 geometry optimization on the prepared 3D structure.",
                    input_source=structure_source,
                    keywords=["atb", "opt", "force", "maxcyc 2000", "gediis off", "maxstep 0.3", "vshift 500"],
                    expected_outputs=[
                        "low-cost final S0 energy",
                        "low-cost final geometry",
                        "dipole",
                        "Mulliken charges",
                        "HOMO-LUMO gap",
                    ],
                )
            )
        elif step_type == "s0_singlepoint":
            steps.append(
                MicroscopicExecutionStep(
                    step_id="s0_singlepoint",
                    step_type="s0_singlepoint",
                    description="Run a bounded Amesp ground-state single-point evaluation on a prepared snapshot geometry.",
                    input_source=structure_source,
                    expected_outputs=["single-point energy", "dipole", "Mulliken charges", "HOMO-LUMO gap"],
                )
            )
        else:
            steps.append(
                MicroscopicExecutionStep(
                    step_id="s1_vertical_excitation",
                    step_type="s1_vertical_excitation",
                    description=(
                        "Run a bounded real Amesp vertical excitation calculation at the best available low-cost geometry "
                        "to characterize the low-lying excited-state manifold without escalating to heavy excited-state optimization."
                    ),
                    input_source="S0 optimized geometry",
                    keywords=[
                        "b3lyp",
                        "sto-3g",
                        "td",
                        f"nstates {config.amesp_s1_nstates}",
                        f"tout {config.amesp_td_tout}",
                    ],
                    expected_outputs=["excited-state energies", "oscillator strengths"],
                )
            )
    return steps


def _supported_scope_descriptions(config: AieMasConfig) -> list[str]:
    return [
        "list_rotatable_dihedrals: discovery-only rotatable dihedral enumeration with stable IDs",
        "list_available_conformers: discovery-only conformer enumeration with stable IDs",
        "list_artifact_bundles: discovery-only artifact bundle enumeration with stable IDs",
        "run_baseline_bundle: low-cost aTB S0 geometry optimization plus vertical excited-state manifold",
        "run_conformer_bundle: bounded conformer ensemble follow-up",
        "run_torsion_snapshots: bounded torsion snapshot follow-up",
        "parse_snapshot_outputs: parse existing snapshot artifacts without new calculations",
        f"runtime budget_profile default: {config.microscopic_budget_profile or 'balanced'}",
    ]


def compile_reasoning_response_to_execution_plan(
    reasoning: MicroscopicReasoningResponse,
    *,
    payload: Optional[dict[str, Any]],
    config: AieMasConfig,
) -> MicroscopicExecutionPlan:
    task_instruction = str((payload or {}).get("task_instruction") or "")
    task_mode = str((payload or {}).get("task_mode") or "targeted_follow_up")
    budget_profile = (payload or {}).get("budget_profile") or config.microscopic_budget_profile or "balanced"
    has_reusable_structure = _has_reusable_structure_from_payload(payload)
    structure_strategy = _derive_structure_strategy_from_payload(payload)
    requested_deliverables = (
        list(reasoning.execution_plan.requested_deliverables)
        or (
            list(reasoning.execution_plan.microscopic_tool_plan.requested_deliverables)
            if reasoning.execution_plan.microscopic_tool_plan is not None
            else []
        )
        or (
            list(reasoning.execution_plan.microscopic_tool_request.deliverables)
            if reasoning.execution_plan.microscopic_tool_request is not None
            else []
        )
        or list(reasoning.expected_outputs)
    )
    selection_policy = _selection_policy_from_reasoning_draft(
        reasoning.execution_plan.microscopic_tool_plan.selection_policy
        if reasoning.execution_plan.microscopic_tool_plan is not None
        else None
    )
    draft_plan = reasoning.execution_plan.microscopic_tool_plan
    if draft_plan is not None and draft_plan.calls:
        calls = [
            _normalize_tool_call_from_draft(
                draft_call=call,
                requested_deliverables=requested_deliverables,
                budget_profile=budget_profile,
                config=config,
                task_mode=task_mode,
                has_reusable_structure=has_reusable_structure,
                selection_policy=selection_policy,
            )
            for call in draft_plan.calls
        ]
    else:
        calls = _build_fallback_tool_calls_from_reasoning(
            reasoning=reasoning,
            requested_deliverables=requested_deliverables,
            budget_profile=budget_profile,
            config=config,
            task_mode=task_mode,
            has_reusable_structure=has_reusable_structure,
            selection_policy=selection_policy,
        )
    calls = _insert_required_discovery_calls(
        calls=calls,
        selection_policy=selection_policy,
        task_mode=task_mode,
        has_reusable_structure=has_reusable_structure,
    )
    calls, normalization_notes = _canonicalize_compiled_tool_call_sequence(calls)
    execution_call = next((call for call in calls if call.call_kind == "execution"), None)
    if execution_call is None:
        raise TaggedMicroscopicProtocolError("Compiled microscopic plan did not contain an execution call.")
    execution_request = execution_call.request
    capability_name = execution_request.capability_name
    planning_unmet_constraints = list(reasoning.execution_plan.planning_unmet_constraints)
    if task_mode == "baseline_s0_s1" and capability_name != "run_baseline_bundle":
        planning_unmet_constraints.append(
            f"Baseline microscopic rounds must execute `run_baseline_bundle`; the reasoning response requested `{capability_name}` and was contracted to the fixed baseline route."
        )
        baseline_request = _normalize_tool_request_from_draft(
            draft=MicroscopicToolRequestDraft(
                capability_name="run_baseline_bundle",
                perform_new_calculation=True,
                optimize_ground_state=True,
                deliverables=list(requested_deliverables) if requested_deliverables else [],
                requested_route_summary=_default_requested_route_summary_for_capability("run_baseline_bundle"),
            ),
            capability_name="run_baseline_bundle",
            requested_deliverables=requested_deliverables or _default_requested_deliverables_for_capability("run_baseline_bundle"),
            budget_profile=budget_profile,
            config=config,
            task_mode=task_mode,
            has_reusable_structure=has_reusable_structure,
            selection_policy=SelectionPolicy(),
        )
        calls = [
            MicroscopicToolCall(
                call_id="execute_run_baseline_bundle",
                call_kind="execution",
                request=baseline_request,
            )
        ]
        normalization_notes.append("Contracted the compiled microscopic plan to the fixed baseline route for a baseline round.")
        selection_policy = SelectionPolicy()
        execution_request = baseline_request
        capability_name = "run_baseline_bundle"
    requested_deliverables = requested_deliverables or _default_requested_deliverables_for_capability(capability_name)
    unsupported_requests = list(reasoning.execution_plan.unsupported_requests)
    planning_unmet_constraints = planning_unmet_constraints + _planning_unmet_constraints_for_instruction(
        task_instruction=task_instruction,
        capability_name=capability_name,
    )
    structure_source = (
        "existing_prepared_structure"
        if structure_strategy == "reuse_if_available_else_prepare_from_smiles" and has_reusable_structure
        else "prepared_from_smiles"
    )
    tool_plan = MicroscopicToolPlan(
        calls=calls,
        requested_route_summary=(
            draft_plan.requested_route_summary
            if draft_plan is not None and draft_plan.requested_route_summary
            else reasoning.execution_plan.requested_route_summary
            or execution_request.requested_route_summary
            or _default_requested_route_summary_for_capability(capability_name)
        ),
        requested_deliverables=list(
            draft_plan.requested_deliverables
            if draft_plan is not None and draft_plan.requested_deliverables
            else requested_deliverables
        ),
        selection_policy=selection_policy,
        normalization_notes=normalization_notes,
        failure_reporting=(
            draft_plan.failure_reporting
            if draft_plan is not None and draft_plan.failure_reporting
            else reasoning.failure_policy
        ),
    )
    return MicroscopicExecutionPlan(
        local_goal=reasoning.execution_plan.local_goal,
        requested_deliverables=list(requested_deliverables),
        capability_route=_compatibility_route_for_capability_name(capability_name),
        microscopic_tool_plan=tool_plan,
        microscopic_tool_request=execution_request,
        budget_profile=budget_profile,
        requested_route_summary=tool_plan.requested_route_summary,
        structure_source=structure_source,  # type: ignore[arg-type]
        supported_scope=_supported_scope_descriptions(config),
        unsupported_requests=unsupported_requests,
        planning_unmet_constraints=planning_unmet_constraints,
        steps=_build_execution_steps(
            config=config,
            capability_name=capability_name,
            structure_source=structure_source,
            optimize_ground_state=execution_request.optimize_ground_state,
            perform_new_calculation=execution_request.perform_new_calculation,
        ),
        expected_outputs=list(reasoning.expected_outputs) or _default_expected_outputs_for_capability(capability_name),
        failure_reporting=reasoning.failure_policy,
    )


def _parse_tagged_protocol_lines(protocol_text: str) -> tuple[dict[str, str], dict[str, str], dict[int, dict[str, str]]]:
    root_values: dict[str, str] = {}
    selection_values: dict[str, str] = {}
    call_values: dict[int, dict[str, str]] = {}
    seen_keys: set[str] = set()
    for raw_line in protocol_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "=" not in line:
            raise TaggedMicroscopicProtocolError(f"Invalid protocol line '{raw_line}'. Expected key=value.")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key in seen_keys:
            raise TaggedMicroscopicProtocolError(f"Duplicate protocol key '{key}'.")
        seen_keys.add(key)
        if key.startswith("call."):
            match = re.fullmatch(r"call\.(\d+)\.([A-Za-z0-9_]+)", key)
            if match is None:
                raise TaggedMicroscopicProtocolError(f"Invalid call key '{key}'.")
            call_index = int(match.group(1))
            field_name = match.group(2)
            if field_name not in _TAGGED_PROTOCOL_CALL_KEYS:
                raise TaggedMicroscopicProtocolError(f"Unknown call field '{field_name}'.")
            call_values.setdefault(call_index, {})
            call_values[call_index][field_name] = value
            continue
        if key.startswith("selection."):
            field_name = key[len("selection.") :]
            if field_name not in _TAGGED_PROTOCOL_SELECTION_KEYS:
                raise TaggedMicroscopicProtocolError(f"Unknown selection field '{field_name}'.")
            selection_values[field_name] = value
            continue
        if key not in _TAGGED_PROTOCOL_ROOT_KEYS:
            raise TaggedMicroscopicProtocolError(f"Unknown protocol key '{key}'.")
        root_values[key] = value
    return root_values, selection_values, call_values


def _build_tagged_selection_policy(selection_values: dict[str, str]) -> Optional[SelectionPolicyDraft]:
    if not selection_values:
        return None
    payload: dict[str, Any] = {}
    for key, value in selection_values.items():
        if key == "exclude_dihedral_ids":
            payload[key] = _parse_symbolic_list(value)
        elif key in {"prefer_adjacent_to_nsnc_core", "include_peripheral"}:
            payload[key] = _parse_bool(value)
        elif key == "source_round_preference":
            payload[key] = _parse_source_round_preference_value(value)
        elif key == "preferred_bond_types":
            payload[key] = _parse_symbolic_list(value)
        else:
            payload[key] = value
    try:
        return SelectionPolicyDraft.model_validate(payload)
    except ValidationError as exc:
        raise TaggedMicroscopicProtocolError(f"Invalid selection policy in microscopic protocol: {exc}") from exc


def _build_tagged_tool_calls(
    call_values: dict[int, dict[str, str]],
    *,
    strict: bool = True,
) -> list[MicroscopicToolCallDraft]:
    if not call_values:
        raise TaggedMicroscopicProtocolError("The microscopic protocol did not define any tool calls.")
    sorted_indices = sorted(call_values)
    expected_indices = list(range(1, len(sorted_indices) + 1))
    if sorted_indices != expected_indices:
        raise TaggedMicroscopicProtocolError(
            f"Tool call indices must be contiguous and start at 1. Received: {sorted_indices!r}."
        )
    calls: list[MicroscopicToolCallDraft] = []
    execution_seen = False
    execution_count = 0
    for index in sorted_indices:
        fields = call_values[index]
        call_kind = fields.get("kind")
        capability_name = fields.get("capability_name")
        if call_kind is None or capability_name is None:
            raise TaggedMicroscopicProtocolError(
                f"Call {index} must define both 'kind' and 'capability_name'."
            )
        if strict and execution_seen and call_kind == "discovery":
            raise TaggedMicroscopicProtocolError(
                "Discovery calls must appear before the execution call."
            )
        if call_kind == "execution":
            execution_seen = True
            execution_count += 1
        request_payload: dict[str, Any] = {"capability_name": capability_name}
        for key, value in fields.items():
            if key in {"kind", "capability_name"}:
                continue
            if key in {
                "perform_new_calculation",
                "optimize_ground_state",
                "reuse_existing_artifacts_only",
                "honor_exact_target",
                "allow_fallback",
                "include_peripheral",
            }:
                request_payload[key] = _parse_bool(value)
            elif key in {
                "artifact_source_round",
                "source_round_preference",
                "max_conformers",
                "snapshot_count",
            }:
                if key == "source_round_preference":
                    request_payload[key] = _parse_source_round_preference_value(value)
                else:
                    request_payload[key] = int(value)
            elif key in {"angle_offsets_deg"}:
                request_payload[key] = _parse_float_list(value)
            elif key in {"state_window", "dihedral_atom_indices"}:
                request_payload[key] = _parse_int_list(value)
            elif key in {"deliverables"}:
                request_payload[key] = _parse_pipe_list(value)
            elif key in {"conformer_ids", "preferred_bond_types"}:
                request_payload[key] = _parse_symbolic_list(value)
            else:
                request_payload[key] = value
        try:
            request_draft = MicroscopicToolRequestDraft.model_validate(request_payload)
            call_draft = MicroscopicToolCallDraft.model_validate(
                {
                    "call_id": f"{call_kind}_{capability_name}_{index}",
                    "call_kind": call_kind,
                    "request": request_draft.model_dump(mode="json"),
                }
            )
        except ValidationError as exc:
            raise TaggedMicroscopicProtocolError(
                f"Invalid microscopic protocol call {index}: {exc}"
            ) from exc
        calls.append(call_draft)
    if strict and execution_count != 1:
        raise TaggedMicroscopicProtocolError(
            f"Exactly one execution call is required. Received {execution_count}."
        )
    if execution_count == 0:
        raise TaggedMicroscopicProtocolError("At least one execution call is required.")
    return calls


def _parse_tagged_semantic_contract_response_with_plan(
    raw_text: str,
    *,
    payload: Optional[dict[str, Any]] = None,
) -> tuple[MicroscopicReasoningResponse, MicroscopicExecutionPlan]:
    sections = _extract_tagged_reasoning_sections(raw_text)
    if "microscopic_semantic_contract" not in sections:
        raise TaggedMicroscopicProtocolError("Tagged response did not contain <microscopic_semantic_contract>.")
    contract_text = sections["microscopic_semantic_contract"]
    contract_version = _tagged_contract_version(contract_text)
    expected_outputs = _parse_tagged_expected_outputs(sections["expected_outputs"])
    task_instruction = str((payload or {}).get("task_instruction") or "")
    task_mode = str((payload or {}).get("task_mode") or "targeted_follow_up")
    budget_profile = (payload or {}).get("budget_profile") or "balanced"

    if contract_version == "2":
        root_values, param_values = _parse_tagged_action_card_lines(contract_text)
        action_card, action_definition = _build_action_card_draft(root_values, param_values)
        contract, tool_plan, execution_request, execution_plan = compile_action_card_to_tool_plan(
            action_card,
            action_definition=action_definition,
            task_instruction=task_instruction,
            task_mode=task_mode,
            expected_outputs=expected_outputs,
            failure_policy=sections["failure_policy"],
            budget_profile=budget_profile,
            available_structure_context=(payload or {}).get("available_structure_context"),
            shared_structure_context=(payload or {}).get("shared_structure_context"),
            current_round_index=(payload or {}).get("current_round_index"),
        )
    else:
        root_values, constraint_values, selection_values, target_values = _parse_tagged_semantic_contract_lines(
            contract_text
        )
        contract = _build_semantic_contract_draft(
            root_values,
            constraint_values,
            selection_values,
            target_values,
        )
        tool_plan, execution_request, execution_plan = compile_semantic_contract_to_tool_plan(
            contract,
            task_instruction=task_instruction,
            task_mode=task_mode,
            expected_outputs=expected_outputs,
            failure_policy=sections["failure_policy"],
            budget_profile=budget_profile,
            available_structure_context=(payload or {}).get("available_structure_context"),
            shared_structure_context=(payload or {}).get("shared_structure_context"),
            current_round_index=(payload or {}).get("current_round_index"),
        )
    try:
        response = MicroscopicReasoningResponse(
            task_understanding=sections["task_understanding"],
            reasoning_summary=sections["reasoning_summary"],
            execution_plan=MicroscopicReasoningPlanDraft(
                local_goal=contract.local_goal,
                requested_deliverables=list(contract.requested_deliverables),
                capability_route=execution_plan.capability_route,
                requested_route_summary=contract.requested_route_summary,
                microscopic_tool_plan=MicroscopicToolPlanDraft(
                    calls=[
                        MicroscopicToolCallDraft.model_validate(call.model_dump(mode="json"))
                        for call in tool_plan.calls
                    ],
                    requested_route_summary=tool_plan.requested_route_summary,
                    requested_deliverables=list(tool_plan.requested_deliverables),
                    selection_policy=SelectionPolicyDraft.model_validate(
                        tool_plan.selection_policy.model_dump(mode="json")
                    ),
                    failure_reporting=sections["failure_policy"],
                ),
                microscopic_tool_request=MicroscopicToolRequestDraft.model_validate(
                    execution_request.model_dump(mode="json")
                ),
                structure_strategy=_derive_structure_strategy_from_payload(payload),
                planning_unmet_constraints=list(execution_plan.planning_unmet_constraints),
                step_sequence=[],
                unsupported_requests=list(contract.unsupported_requests),
            ),
            capability_limit_note=sections["capability_limit_note"],
            expected_outputs=expected_outputs,
            failure_policy=sections["failure_policy"],
        )
        return response, execution_plan
    except ValidationError as exc:
        raise TaggedMicroscopicProtocolError(
            f"Invalid semantic-contract microscopic reasoning response: {exc}"
        ) from exc


def _parse_tagged_semantic_contract_response(
    raw_text: str,
    *,
    payload: Optional[dict[str, Any]] = None,
) -> MicroscopicReasoningResponse:
    response, _ = _parse_tagged_semantic_contract_response_with_plan(raw_text, payload=payload)
    return response


def _parse_legacy_tagged_microscopic_reasoning_response(
    raw_text: str,
    *,
    strict: bool = True,
) -> MicroscopicReasoningResponse:
    sections = _extract_tagged_reasoning_sections(raw_text)
    if "microscopic_protocol" not in sections:
        raise TaggedMicroscopicProtocolError("Tagged response did not contain <microscopic_protocol>.")
    root_values, selection_values, call_values = _parse_tagged_protocol_lines(sections["microscopic_protocol"])
    protocol_version = root_values.get("protocol_version")
    if protocol_version != "1":
        raise TaggedMicroscopicProtocolError(
            f"Unsupported microscopic protocol_version '{protocol_version}'."
        )
    if "local_goal" not in root_values:
        raise TaggedMicroscopicProtocolError("The microscopic protocol is missing 'local_goal'.")
    if "structure_strategy" not in root_values:
        raise TaggedMicroscopicProtocolError("The microscopic protocol is missing 'structure_strategy'.")
    if "requested_route_summary" not in root_values:
        raise TaggedMicroscopicProtocolError(
            "The microscopic protocol is missing 'requested_route_summary'."
        )
    if "requested_deliverables" not in root_values:
        raise TaggedMicroscopicProtocolError(
            "The microscopic protocol is missing 'requested_deliverables'."
        )
    calls = _build_tagged_tool_calls(call_values, strict=strict)
    selection_policy = _build_tagged_selection_policy(selection_values)
    execution_call = next(call for call in calls if call.call_kind == "execution")
    execution_capability = execution_call.request.capability_name
    capability_route = _compatibility_route_for_capability_name(execution_capability)
    try:
        return MicroscopicReasoningResponse(
            task_understanding=sections["task_understanding"],
            reasoning_summary=sections["reasoning_summary"],
            execution_plan=MicroscopicReasoningPlanDraft(
                local_goal=root_values["local_goal"],
                requested_deliverables=_parse_pipe_list(root_values["requested_deliverables"]),
                capability_route=capability_route,
                requested_route_summary=root_values["requested_route_summary"],
                microscopic_tool_plan=MicroscopicToolPlanDraft(
                    calls=calls,
                    requested_route_summary=root_values["requested_route_summary"],
                    requested_deliverables=_parse_pipe_list(root_values["requested_deliverables"]),
                    selection_policy=selection_policy,
                    failure_reporting=sections["failure_policy"],
                ),
                structure_strategy=root_values["structure_strategy"],  # type: ignore[arg-type]
                step_sequence=[],
                unsupported_requests=_parse_pipe_list(root_values.get("unsupported_requests", "")),
            ),
            capability_limit_note=sections["capability_limit_note"],
            expected_outputs=_parse_tagged_expected_outputs(sections["expected_outputs"]),
            failure_policy=sections["failure_policy"],
        )
    except ValidationError as exc:
        raise TaggedMicroscopicProtocolError(
            f"Invalid tagged microscopic reasoning response: {exc}"
        ) from exc


def _parse_tagged_microscopic_reasoning_response(
    raw_text: str,
    *,
    payload: Optional[dict[str, Any]] = None,
    strict: bool = True,
) -> MicroscopicReasoningResponse:
    sections = _extract_tagged_reasoning_sections(raw_text)
    if "microscopic_semantic_contract" in sections:
        return _parse_tagged_semantic_contract_response(raw_text, payload=payload)
    return _parse_legacy_tagged_microscopic_reasoning_response(raw_text, strict=strict)


class MicroscopicReasoningBackend(Protocol):
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningOutcome:
        ...


class OpenAIMicroscopicReasoningBackend:
    def __init__(
        self,
        config: AieMasConfig,
        client: Optional[OpenAICompatibleMicroscopicClient] = None,
    ) -> None:
        self._config = config
        self._client = client or OpenAICompatibleMicroscopicClient(config)

    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningOutcome:
        raw_text = self._client.invoke_text(messages=prompt_value_to_messages(rendered_prompt))
        contract_errors: list[str] = []
        try:
            response, compiled_plan = _parse_tagged_semantic_contract_response_with_plan(raw_text, payload=payload)
        except Exception as exc:
            contract_errors.append(f"semantic_contract: {exc}")
        else:
            sections = _extract_tagged_reasoning_sections(raw_text)
            contract_version = _tagged_contract_version(sections.get("microscopic_semantic_contract", ""))
            contract_mode: MicroscopicSemanticContractMode = (
                "semantic_contract" if contract_version == "2" else "legacy_semantic_contract_fallback"
            )
            return MicroscopicReasoningOutcome(
                reasoning_response=response,
                compiled_execution_plan=compiled_plan,
                reasoning_parse_mode=contract_mode,
                reasoning_contract_mode=contract_mode,
                reasoning_contract_errors=[],
            )

        try:
            response = _parse_legacy_tagged_microscopic_reasoning_response(raw_text)
            compiled_plan = compile_reasoning_response_to_execution_plan(
                response,
                payload=payload,
                config=self._config,
            )
        except Exception as exc:
            contract_errors.append(f"legacy_tagged_protocol: {exc}")
            try:
                response = _parse_legacy_tagged_microscopic_reasoning_response(raw_text, strict=False)
                compiled_plan = compile_reasoning_response_to_execution_plan(
                    response,
                    payload=payload,
                    config=self._config,
                )
            except Exception as recovery_exc:
                contract_errors.append(f"legacy_tagged_protocol_recovery: {recovery_exc}")
            else:
                return MicroscopicReasoningOutcome(
                    reasoning_response=response,
                    compiled_execution_plan=compiled_plan,
                    reasoning_parse_mode="legacy_tagged_protocol_fallback",
                    reasoning_contract_mode="legacy_tagged_protocol_fallback",
                    reasoning_contract_errors=list(contract_errors),
                )
        else:
            return MicroscopicReasoningOutcome(
                reasoning_response=response,
                compiled_execution_plan=compiled_plan,
                reasoning_parse_mode="legacy_tagged_protocol_fallback",
                reasoning_contract_mode="legacy_tagged_protocol_fallback",
                reasoning_contract_errors=list(contract_errors),
            )

        try:
            payload_obj = self._client.parse_json_object_text(raw_text)
            response = MicroscopicReasoningResponse.model_validate(payload_obj)
            compiled_plan = compile_reasoning_response_to_execution_plan(
                response,
                payload=payload,
                config=self._config,
            )
        except Exception as exc:
            contract_errors.append(f"legacy_json: {exc}")
            raise MicroscopicReasoningParseError(
                "Microscopic reasoning output was neither a valid semantic contract, valid legacy tagged protocol, nor valid legacy JSON.",
                raw_text=raw_text,
                contract_mode="failed",
                contract_errors=contract_errors,
            ) from exc
        return MicroscopicReasoningOutcome(
            reasoning_response=MicroscopicReasoningResponse.model_validate(response.model_dump(mode="json")),
            compiled_execution_plan=compiled_plan,
            reasoning_parse_mode="legacy_json_fallback",
            reasoning_contract_mode="legacy_json_fallback",
            reasoning_contract_errors=list(contract_errors),
        )


class MicroscopicAgent:
    def __init__(
        self,
        amesp_tool: Optional[AmespMicroscopicTool] = None,
        *,
        prompts: Optional[PromptRepository] = None,
        tools_work_dir: Optional[Path] = None,
        config: Optional[AieMasConfig] = None,
        llm_client: Optional[OpenAICompatibleMicroscopicClient] = None,
        progress_callback: Optional[Callable[[WorkflowProgressEvent], None]] = None,
    ) -> None:
        self._amesp_tool = amesp_tool
        self._prompts = prompts or _default_prompt_repository()
        self._tools_work_dir = tools_work_dir
        self._config = config or AieMasConfig()
        self._reasoning_backend = self._build_reasoning_backend(self._config, llm_client)
        self._progress_callback = progress_callback

    def run(
        self,
        smiles: str,
        task_received: str,
        task_spec: Optional[MicroscopicTaskSpec] = None,
        current_hypothesis: str = "unknown",
        *,
        recent_rounds_context: Optional[list[dict[str, object]]] = None,
        available_artifacts: Optional[dict[str, Any]] = None,
        shared_structure_context: Optional[SharedStructureContext] = None,
        shared_structure_status: SharedStructureStatus = "missing",
        allow_internal_structure_fallback: bool = True,
        case_id: Optional[str] = None,
        round_index: int = 1,
    ) -> AgentReport:
        task_spec = task_spec or MicroscopicTaskSpec(
            mode="baseline_s0_s1",
            task_label="initial-baseline",
            objective="Run fixed first-stage S0/S1 optimization.",
        )
        recent_rounds_context = recent_rounds_context or []
        available_artifacts = available_artifacts or {}
        resolved_case_id = case_id or "ad_hoc_case"

        self._emit_probe(
            round_index=round_index,
            case_id=resolved_case_id,
            current_hypothesis=current_hypothesis,
            stage="reasoning",
            status="start",
            details={
                "task_instruction": task_received,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
            },
        )

        reasoning_payload = self._build_reasoning_payload(
            current_hypothesis=current_hypothesis,
            task_instruction=task_received,
            task_spec=task_spec,
            recent_rounds_context=recent_rounds_context,
            available_artifacts=available_artifacts,
            shared_structure_context=shared_structure_context,
            round_index=round_index,
        )
        rendered_prompt = self._prompts.render("microscopic_reasoning", reasoning_payload)
        try:
            outcome = self._reasoning_backend.reason(rendered_prompt, reasoning_payload)
        except MicroscopicReasoningParseError as exc:
            self._emit_probe(
                round_index=round_index,
                case_id=resolved_case_id,
                current_hypothesis=current_hypothesis,
                stage="reasoning",
                status="end",
                details={
                    "reasoning_backend": self._config.microscopic_backend,
                    "reasoning_parse_mode": "failed",
                    "reasoning_contract_mode": exc.contract_mode,
                    "reasoning_contract_errors": list(exc.contract_errors),
                },
            )
            return self._reasoning_parse_failure_report(
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                parse_error=exc,
            )
        reasoning = outcome.reasoning_response
        plan = outcome.compiled_execution_plan
        reasoning_parse_mode = outcome.reasoning_parse_mode
        reasoning_contract_mode = outcome.reasoning_contract_mode
        reasoning_contract_errors = list(outcome.reasoning_contract_errors)
        self._emit_probe(
            round_index=round_index,
            case_id=resolved_case_id,
            current_hypothesis=current_hypothesis,
            stage="reasoning",
            status="end",
            details={
                "reasoning_backend": self._config.microscopic_backend,
                "task_understanding": reasoning.task_understanding,
                "reasoning_summary": reasoning.reasoning_summary,
                "capability_limit_note": reasoning.capability_limit_note,
                "expected_outputs": reasoning.expected_outputs,
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
            },
        )
        self._emit_probe(
            round_index=round_index,
            case_id=resolved_case_id,
            current_hypothesis=current_hypothesis,
            stage="execution_plan",
            status="end",
            details=plan.model_dump(mode="json"),
        )
        registry_blocked_requests = self._registry_blocked_requests(task_received)
        if registry_blocked_requests:
            return self._registry_blocked_request_report(
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                outcome=outcome,
                registry_blocked_requests=registry_blocked_requests,
            )

        if (
            self._amesp_tool is not None
            and not allow_internal_structure_fallback
            and shared_structure_context is None
            and not self._has_reusable_structure(available_artifacts)
        ):
            return self._shared_structure_unavailable_report(
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                outcome=outcome,
                shared_structure_status=shared_structure_status,
            )

        if self._amesp_tool is not None:
            return self._run_real(
                smiles=smiles,
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                outcome=outcome,
                recent_rounds_context=recent_rounds_context,
                available_artifacts=available_artifacts,
                shared_structure_context=shared_structure_context,
                case_id=resolved_case_id,
                round_index=round_index,
            )
        raise RuntimeError(
            "MicroscopicAgent requires an Amesp baseline tool; no alternate execution path is available."
        )

    def _run_real(
        self,
        *,
        smiles: str,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        outcome: MicroscopicReasoningOutcome,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
        shared_structure_context: Optional[SharedStructureContext],
        case_id: str,
        round_index: int,
    ) -> AgentReport:
        reasoning = outcome.reasoning_response
        plan = outcome.compiled_execution_plan
        reasoning_parse_mode = outcome.reasoning_parse_mode
        reasoning_contract_mode = outcome.reasoning_contract_mode
        reasoning_contract_errors = list(outcome.reasoning_contract_errors)
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(plan.requested_deliverables),
            "capability_route": plan.capability_route,
            "requested_capability": plan.microscopic_tool_request.capability_name,
            "executed_capability": plan.microscopic_tool_request.capability_name,
            "performed_new_calculations": str(plan.microscopic_tool_request.perform_new_calculation).lower(),
            "reused_existing_artifacts": str(plan.microscopic_tool_request.reuse_existing_artifacts_only).lower(),
            "resolved_target_ids_text": "No target IDs have been resolved yet.",
            "honored_constraints_text": "No honored constraints have been recorded yet.",
            "unmet_constraints_text": "No unmet constraints have been recorded yet.",
            "missing_deliverables_text": "No missing deliverables have been identified yet.",
            "requested_route_summary": plan.requested_route_summary,
            "task_completion_text": "Task completion is pending Amesp microscopic execution.",
            "recent_context_note": self._recent_context_note(recent_rounds_context),
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": self._structure_source_note(
                plan.structure_source,
                available_artifacts,
                shared_structure_context=shared_structure_context,
            ),
            "unsupported_requests_note": self._unsupported_requests_note(plan.unsupported_requests),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "failure_policy": reasoning.failure_policy,
            "plan_steps": self._plan_steps_text(plan),
            "expected_outputs_text": ", ".join(plan.expected_outputs),
            "result_summary_text": "Amesp microscopic execution has not run yet.",
            "local_uncertainty_detail": self._remaining_uncertainty_text(
                plan.unsupported_requests,
                task_spec.mode,
                plan.capability_route,
            ),
        }
        draft = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)

        label = f"{case_id}_round_{round_index:02d}_micro"
        workdir = self._resolve_workdir(case_id=case_id, round_index=round_index)
        tool_calls = [
            "microscopic_reasoning(task_instruction_to_execution_plan)",
            (
                f"{self._amesp_tool.name}.execute("
                f"plan_version='{plan.plan_version}', capability='{plan.microscopic_tool_request.capability_name}', label='{label}')"
            ),
        ]
        if plan.structure_source == "existing_prepared_structure":
            tool_calls.insert(1, "shared_structure_context(reuse_prepared_3d_structure)")
        else:
            tool_calls.insert(1, "structure_preparation(smiles_to_3d or reusable prepared structure)")

        try:
            run_result = self._amesp_tool.execute(
                plan=plan,
                smiles=smiles,
                label=label,
                workdir=workdir,
                available_artifacts=available_artifacts,
                progress_callback=self._progress_callback,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis=current_hypothesis,
            )
            structured_results = {
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "reasoning": reasoning.model_dump(mode="json"),
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
                "registry_action_name": plan.microscopic_tool_request.capability_name,
                "registry_validation_errors": [],
                "execution_plan": plan.model_dump(mode="json"),
                "attempted_route": getattr(run_result, "route", plan.capability_route),
                "requested_capability": plan.microscopic_tool_request.capability_name,
                "executed_capability": getattr(run_result, "executed_capability", plan.microscopic_tool_request.capability_name),
                "performed_new_calculations": getattr(run_result, "performed_new_calculations", True),
                "reused_existing_artifacts": getattr(run_result, "reused_existing_artifacts", False),
                "resolved_target_ids": dict(getattr(run_result, "resolved_target_ids", {})),
                "honored_constraints": list(getattr(run_result, "honored_constraints", [])),
                "unmet_constraints": list(getattr(run_result, "unmet_constraints", [])),
                "missing_deliverables": list(getattr(run_result, "missing_deliverables", [])),
                "structure_source": plan.structure_source,
                "supported_scope": plan.supported_scope,
                "unsupported_requests": plan.unsupported_requests,
                "structure": run_result.structure.model_dump(mode="json"),
                "s0": run_result.s0.model_dump(mode="json") if run_result.s0 is not None else None,
                "s1": run_result.s1.model_dump(mode="json") if run_result.s1 is not None else None,
                "parsed_snapshot_records": list(getattr(run_result, "parsed_snapshot_records", [])),
                "route_records": list(getattr(run_result, "route_records", [])),
                "route_summary": dict(getattr(run_result, "route_summary", {})),
                "vertical_state_manifold": self._vertical_state_manifold(run_result.s1) if run_result.s1 is not None else {},
                "s0_energy": run_result.s0.final_energy_hartree if run_result.s0 is not None else None,
                "s1_energy": (
                    run_result.s1.excited_states[0].total_energy_hartree
                    if run_result.s1 is not None and run_result.s1.excited_states
                    else None
                ),
                "rigidity_proxy": None,
                "geometry_change_proxy": getattr(
                    run_result.s0,
                    "rmsd_from_prepared_structure_angstrom",
                    None,
                ),
                "oscillator_strength_proxy": getattr(run_result.s1, "first_oscillator_strength", None),
                "relaxation_gap": getattr(run_result.s1, "first_excitation_energy_ev", None),
            }
            raw_results = {
                "reasoning_output": reasoning.model_dump(mode="json"),
                "execution_plan": plan.model_dump(mode="json"),
                "amesp_raw_step_results": run_result.raw_step_results,
            }
            generated_artifacts = dict(run_result.generated_artifacts)
            generated_artifacts["source_round"] = round_index
            result_summary_text = self._successful_result_summary(structured_results)
            status = "success"
        except AmespExecutionError as exc:
            structured_results = {
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "reasoning": reasoning.model_dump(mode="json"),
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
                "registry_action_name": plan.microscopic_tool_request.capability_name,
                "registry_validation_errors": [],
                "execution_plan": plan.model_dump(mode="json"),
                "attempted_route": plan.capability_route,
                "requested_capability": plan.microscopic_tool_request.capability_name,
                "executed_capability": (
                    exc.structured_results.get("executed_capability")
                    if isinstance(exc.structured_results, dict)
                    else None
                )
                or plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": (
                    exc.structured_results.get("performed_new_calculations")
                    if isinstance(exc.structured_results, dict)
                    else plan.microscopic_tool_request.perform_new_calculation
                ),
                "reused_existing_artifacts": (
                    exc.structured_results.get("reused_existing_artifacts")
                    if isinstance(exc.structured_results, dict)
                    else plan.microscopic_tool_request.reuse_existing_artifacts_only
                ),
                "resolved_target_ids": (
                    dict(exc.structured_results.get("resolved_target_ids") or {})
                    if isinstance(exc.structured_results, dict)
                    else {}
                ),
                "honored_constraints": (
                    list(exc.structured_results.get("honored_constraints") or [])
                    if isinstance(exc.structured_results, dict)
                    else []
                ),
                "unmet_constraints": (
                    list(exc.structured_results.get("unmet_constraints") or [])
                    if isinstance(exc.structured_results, dict)
                    else []
                ),
                "missing_deliverables": [],
                "structure_source": plan.structure_source,
                "supported_scope": plan.supported_scope,
                "unsupported_requests": plan.unsupported_requests,
                "error": exc.to_payload(),
                **exc.structured_results,
            }
            raw_results = {
                "reasoning_output": reasoning.model_dump(mode="json"),
                "execution_plan": plan.model_dump(mode="json"),
                "amesp_error": exc.to_payload(),
                **exc.raw_results,
            }
            generated_artifacts = dict(exc.generated_artifacts)
            generated_artifacts["source_round"] = round_index
            result_summary_text = self._failed_result_summary(exc)
            status = exc.status

        structured_results["unmet_constraints"] = list(structured_results.get("unmet_constraints") or []) + list(
            plan.planning_unmet_constraints
        )

        task_completion_status, completion_reason_code, task_completion_text = self._task_completion_for_result(
            run_status=status,
            unsupported_requests=plan.unsupported_requests,
            task_mode=task_spec.mode,
            capability_route=plan.capability_route,
            requested_capability=plan.microscopic_tool_request.capability_name,
            executed_capability=structured_results.get("executed_capability"),
            performed_new_calculations=bool(structured_results.get("performed_new_calculations")),
            reused_existing_artifacts=bool(structured_results.get("reused_existing_artifacts")),
            resolved_target_ids=dict(structured_results.get("resolved_target_ids") or {}),
            honored_constraints=list(structured_results.get("honored_constraints") or []),
            unmet_constraints=list(structured_results.get("unmet_constraints") or []),
            missing_deliverables=list(structured_results.get("missing_deliverables") or []),
            error_message=result_summary_text if status in {"partial", "failed"} else None,
            error_payload=structured_results.get("error"),
        )
        structured_results["task_completion_status"] = task_completion_status
        structured_results["completion_reason_code"] = completion_reason_code
        structured_results["task_completion"] = task_completion_text
        registry_handshake_reason = self._registry_handshake_reason(
            completion_reason_code=completion_reason_code,
            missing_deliverables=list(structured_results.get("missing_deliverables") or []),
            route_summary=(
                structured_results.get("route_summary")
                if isinstance(structured_results.get("route_summary"), dict)
                else None
            ),
            registry_validation_errors=list(structured_results.get("registry_validation_errors") or []),
        )
        structured_results["registry_infeasible_for_verifier_handshake"] = registry_handshake_reason is not None
        structured_results["registry_infeasible_reason"] = registry_handshake_reason

        rendered = self._prompts.render_sections(
            "microscopic_amesp_specialized",
            {
                **render_payload,
                "task_completion_text": task_completion_text,
                "executed_capability": structured_results.get("executed_capability") or plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": str(bool(structured_results.get("performed_new_calculations"))).lower(),
                "reused_existing_artifacts": str(bool(structured_results.get("reused_existing_artifacts"))).lower(),
                "resolved_target_ids_text": self._resolved_target_ids_text(
                    dict(structured_results.get("resolved_target_ids") or {})
                ),
                "honored_constraints_text": self._constraint_text(
                    list(structured_results.get("honored_constraints") or []),
                    default_text="No honored constraints were recorded.",
                ),
                "unmet_constraints_text": self._constraint_text(
                    list(structured_results.get("unmet_constraints") or []),
                    default_text="No unmet constraints were recorded.",
                ),
                "missing_deliverables_text": self._missing_deliverables_text(
                    list(structured_results.get("missing_deliverables") or [])
                ),
                "result_summary_text": result_summary_text,
            },
        )

        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status=task_completion_status,  # type: ignore[arg-type]
            completion_reason_code=completion_reason_code,  # type: ignore[arg-type]
            task_completion=rendered["task_completion"],
            task_understanding=draft["task_understanding"],
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=tool_calls,
            raw_results=raw_results,
            structured_results=structured_results,
            generated_artifacts=generated_artifacts,
            status=status,  # type: ignore[arg-type]
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _reasoning_parse_failure_report(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        parse_error: MicroscopicReasoningParseError,
    ) -> AgentReport:
        contract_errors = list(parse_error.contract_errors)
        completion_reason_code = self._registry_completion_code_for_parse_error(contract_errors)
        contract_error_text = "; ".join(contract_errors) if contract_errors else "No parser diagnostics were recorded."
        task_completion_text = (
            "Task could not be completed because the local microscopic semantic contract could not be parsed into a valid bounded execution plan."
        )
        result_summary_text = (
            "Microscopic reasoning stopped before tool runtime because the semantic-contract translation was invalid. "
            f"Diagnostics: {contract_error_text}"
        )
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(self._requested_deliverables(task_received)),
            "capability_route": "baseline_bundle",
            "requested_capability": "unknown",
            "executed_capability": "unknown",
            "performed_new_calculations": "false",
            "reused_existing_artifacts": "false",
            "resolved_target_ids_text": "No target IDs were resolved because reasoning stopped before tool runtime.",
            "honored_constraints_text": "No honored constraints were recorded because reasoning stopped before tool runtime.",
            "unmet_constraints_text": contract_error_text,
            "missing_deliverables_text": "No deliverables were produced because tool execution never started.",
            "requested_route_summary": "Microscopic reasoning could not be compiled into a bounded execution route.",
            "task_completion_text": task_completion_text,
            "recent_context_note": "No microscopic tool runtime was attempted because semantic-contract parsing failed.",
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": "Tool execution did not start because the semantic contract could not be compiled.",
            "unsupported_requests_note": self._unsupported_requests_note(self._unsupported_requests(task_received, task_spec)),
            "reasoning_summary_text": "Microscopic semantic-contract parsing failed before a valid local execution plan could be compiled.",
            "capability_limit_note": "Current microscopic execution requires a valid semantic contract or a valid migration fallback representation.",
            "failure_policy": "Return a local failed report and preserve parser diagnostics for Planner review.",
            "plan_steps": "No execution steps were compiled because semantic-contract parsing failed.",
            "expected_outputs_text": "No outputs were produced because tool execution never started.",
            "result_summary_text": result_summary_text,
            "local_uncertainty_detail": (
                "the Planner did not receive new microscopic evidence because local contract parsing failed before any Amesp execution could begin"
            ),
        }
        rendered = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)
        structured_results = {
            "backend": "amesp",
            "reasoning_backend": self._config.microscopic_backend,
            "task_mode": task_spec.mode,
            "task_label": task_spec.task_label,
            "task_objective": task_spec.objective,
            "task_completion_status": "failed",
            "completion_reason_code": completion_reason_code,
            "task_completion": rendered["task_completion"],
            "reasoning": {
                "task_understanding": "Microscopic reasoning could not be parsed into a valid semantic contract.",
                "reasoning_summary": "No valid bounded execution route was compiled.",
                "failure_policy": "Return parser diagnostics only.",
            },
            "reasoning_parse_mode": "failed",
            "reasoning_contract_mode": parse_error.contract_mode,
            "reasoning_contract_errors": contract_errors,
            "registry_action_name": None,
            "registry_validation_errors": list(contract_errors),
            "registry_infeasible_for_verifier_handshake": completion_reason_code == "action_not_supported_by_registry",
            "registry_infeasible_reason": (
                "action_not_supported_by_registry"
                if completion_reason_code == "action_not_supported_by_registry"
                else None
            ),
            "requested_capability": None,
            "executed_capability": None,
            "performed_new_calculations": False,
            "reused_existing_artifacts": False,
            "resolved_target_ids": {},
            "honored_constraints": [],
            "unmet_constraints": list(contract_errors),
            "missing_deliverables": self._requested_deliverables(task_received),
            "error": {
                "code": completion_reason_code,
                "message": str(parse_error),
            },
            "supported_scope": [],
            "unsupported_requests": self._unsupported_requests(task_received, task_spec),
        }
        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status="failed",
            completion_reason_code=completion_reason_code,
            task_completion=rendered["task_completion"],
            task_understanding="Microscopic semantic-contract parsing failed before local execution planning.",
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=["microscopic_reasoning(task_instruction_to_semantic_contract)"],
            raw_results={
                "reasoning_raw_text": parse_error.raw_text,
                "reasoning_contract_errors": contract_errors,
            },
            structured_results=structured_results,
            generated_artifacts={},
            status="failed",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _shared_structure_unavailable_report(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        outcome: MicroscopicReasoningOutcome,
        shared_structure_status: SharedStructureStatus,
    ) -> AgentReport:
        reasoning = outcome.reasoning_response
        plan = outcome.compiled_execution_plan
        reasoning_parse_mode = outcome.reasoning_parse_mode
        reasoning_contract_mode = outcome.reasoning_contract_mode
        reasoning_contract_errors = list(outcome.reasoning_contract_errors)
        task_completion_text = (
            "Task could not be completed. The requested microscopic instruction depended on a prepared structure, "
            "but shared structure context was unavailable and private structure preparation was not allowed in this path."
        )
        result_summary_text = (
            "Microscopic execution returned status=partial because shared structure context was not available and "
            "the normal graph path does not allow private structure preparation."
        )
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(plan.requested_deliverables),
            "capability_route": plan.capability_route,
            "requested_capability": plan.microscopic_tool_request.capability_name,
            "executed_capability": plan.microscopic_tool_request.capability_name,
            "performed_new_calculations": "false",
            "reused_existing_artifacts": "false",
            "resolved_target_ids_text": "No target IDs were resolved because execution stopped before tool runtime.",
            "honored_constraints_text": "No honored constraints were recorded because execution stopped before tool runtime.",
            "unmet_constraints_text": "Shared-structure preconditions were not met before tool execution.",
            "missing_deliverables_text": "No deliverables were produced because execution stopped before tool runtime.",
            "requested_route_summary": plan.requested_route_summary,
            "task_completion_text": task_completion_text,
            "recent_context_note": "No additional microscopic runtime step was executed.",
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": (
                f"Shared structure status is '{shared_structure_status}', so the normal microscopic path stopped before tool execution."
            ),
            "unsupported_requests_note": self._unsupported_requests_note(plan.unsupported_requests),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "failure_policy": reasoning.failure_policy,
            "plan_steps": self._plan_steps_text(plan),
            "expected_outputs_text": ", ".join(plan.expected_outputs),
            "result_summary_text": result_summary_text,
            "local_uncertainty_detail": (
                "shared prepared structure context is unavailable in the normal graph path, so no bounded microscopic runtime "
                "result could be collected without violating the shared-structure-first policy."
            ),
        }
        rendered = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)
        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status="failed",
            completion_reason_code="precondition_missing",
            task_completion=rendered["task_completion"],
            task_understanding=reasoning.task_understanding,
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=["microscopic_reasoning(task_instruction_to_execution_plan)"],
            raw_results={
                "reasoning_output": reasoning.model_dump(mode="json"),
                "shared_structure_status": shared_structure_status,
            },
            structured_results={
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "task_completion_status": "failed",
                "completion_reason_code": "precondition_missing",
                "task_completion": rendered["task_completion"],
                "reasoning": reasoning.model_dump(mode="json"),
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
                "registry_action_name": plan.microscopic_tool_request.capability_name,
                "registry_validation_errors": [],
                "registry_infeasible_for_verifier_handshake": False,
                "registry_infeasible_reason": None,
                "execution_plan": plan.model_dump(mode="json"),
                "requested_capability": plan.microscopic_tool_request.capability_name,
                "executed_capability": plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": False,
                "reused_existing_artifacts": False,
                "resolved_target_ids": {},
                "honored_constraints": [],
                "unmet_constraints": ["shared_structure_context was unavailable before tool execution"] + list(
                    plan.planning_unmet_constraints
                ),
                "missing_deliverables": list(plan.requested_deliverables),
                "error": {
                    "code": "shared_structure_unavailable",
                    "message": result_summary_text,
                    "shared_structure_status": shared_structure_status,
                },
                "supported_scope": plan.supported_scope,
                "unsupported_requests": plan.unsupported_requests,
            },
            generated_artifacts={},
            status="partial",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _registry_blocked_request_report(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        outcome: MicroscopicReasoningOutcome,
        registry_blocked_requests: list[str],
    ) -> AgentReport:
        reasoning = outcome.reasoning_response
        plan = outcome.compiled_execution_plan
        reasoning_parse_mode = outcome.reasoning_parse_mode
        reasoning_contract_mode = outcome.reasoning_contract_mode
        reasoning_contract_errors = list(outcome.reasoning_contract_errors)
        blocked_note = "; ".join(registry_blocked_requests)
        unsupported_requests = list(dict.fromkeys(list(plan.unsupported_requests) + list(registry_blocked_requests)))
        registry_validation_errors = [
            "Planner requested unsupported registry-blocked microscopic task(s): "
            + blocked_note
            + "."
        ]
        task_completion_text = (
            "Task could not be completed. The Planner requested a microscopic action that is not represented in the "
            f"current Amesp action registry: {blocked_note}."
        )
        result_summary_text = (
            "Microscopic execution did not start because the Planner explicitly requested a registry-unsupported local task. "
            f"Blocked request(s): {blocked_note}. "
            f"The closest compiled registry action `{plan.microscopic_tool_request.capability_name}` was intentionally not executed."
        )
        render_payload = {
            "task_received": task_received,
            "current_hypothesis": current_hypothesis,
            "requested_focus": ", ".join(plan.requested_deliverables),
            "capability_route": plan.capability_route,
            "requested_capability": "registry-blocked request",
            "executed_capability": "not_executed",
            "performed_new_calculations": "false",
            "reused_existing_artifacts": "false",
            "resolved_target_ids_text": "No target IDs were resolved because execution did not start.",
            "honored_constraints_text": "No honored constraints were recorded because execution did not start.",
            "unmet_constraints_text": (
                "Execution was blocked before tool runtime because the Planner explicitly requested a microscopic action "
                "that is not represented in the current Amesp action registry: "
                + blocked_note
                + "."
            ),
            "missing_deliverables_text": (
                "; ".join(plan.requested_deliverables)
                if plan.requested_deliverables
                else "No deliverables were requested."
            ),
            "requested_route_summary": plan.requested_route_summary,
            "task_completion_text": task_completion_text,
            "recent_context_note": "No additional microscopic runtime step was executed.",
            "capability_scope": self._capability_scope_text(),
            "structure_source_note": (
                "Execution was intentionally blocked before tool runtime because no registry-backed microscopic action "
                "matched the Planner request exactly."
            ),
            "unsupported_requests_note": self._unsupported_requests_note(unsupported_requests),
            "reasoning_summary_text": reasoning.reasoning_summary,
            "capability_limit_note": reasoning.capability_limit_note,
            "failure_policy": reasoning.failure_policy,
            "plan_steps": (
                "No execution steps were run because the Planner explicitly requested registry-unsupported microscopic "
                f"task(s): {blocked_note}."
            ),
            "expected_outputs_text": "No outputs were produced because tool execution did not start.",
            "result_summary_text": result_summary_text,
            "local_uncertainty_detail": (
                "the current Amesp registry does not expose the requested microscopic action, so no new local evidence "
                "was collected in this round"
            ),
        }
        rendered = self._prompts.render_sections("microscopic_amesp_specialized", render_payload)
        return AgentReport(
            agent_name="microscopic",
            task_received=task_received,
            task_completion_status="failed",
            completion_reason_code="action_not_supported_by_registry",
            task_completion=rendered["task_completion"],
            task_understanding=reasoning.task_understanding,
            reasoning_summary=rendered["reasoning_summary"],
            execution_plan=rendered["execution_plan"],
            result_summary=rendered["result_summary"],
            remaining_local_uncertainty=rendered["remaining_local_uncertainty"],
            tool_calls=["microscopic_reasoning(task_instruction_to_execution_plan)"],
            raw_results={
                "reasoning_output": reasoning.model_dump(mode="json"),
                "execution_plan_not_executed": plan.model_dump(mode="json"),
                "registry_blocked_requests": list(registry_blocked_requests),
            },
            structured_results={
                "backend": "amesp",
                "reasoning_backend": self._config.microscopic_backend,
                "task_mode": task_spec.mode,
                "task_label": task_spec.task_label,
                "task_objective": task_spec.objective,
                "task_completion_status": "failed",
                "completion_reason_code": "action_not_supported_by_registry",
                "task_completion": rendered["task_completion"],
                "reasoning": reasoning.model_dump(mode="json"),
                "reasoning_parse_mode": reasoning_parse_mode,
                "reasoning_contract_mode": reasoning_contract_mode,
                "reasoning_contract_errors": reasoning_contract_errors,
                "registry_action_name": None,
                "registry_validation_errors": registry_validation_errors,
                "registry_infeasible_for_verifier_handshake": True,
                "registry_infeasible_reason": "action_not_supported_by_registry",
                "execution_plan": plan.model_dump(mode="json"),
                "requested_capability": None,
                "executed_capability": None,
                "performed_new_calculations": False,
                "reused_existing_artifacts": False,
                "resolved_target_ids": {},
                "honored_constraints": [],
                "unmet_constraints": registry_validation_errors + list(plan.planning_unmet_constraints),
                "missing_deliverables": list(plan.requested_deliverables),
                "error": {
                    "code": "action_not_supported_by_registry",
                    "message": result_summary_text,
                },
                "supported_scope": plan.supported_scope,
                "unsupported_requests": unsupported_requests,
            },
            generated_artifacts={},
            status="failed",
            planner_readable_report=rendered["planner_readable_report"],
        )

    def _emit_probe(
        self,
        *,
        round_index: int,
        case_id: Optional[str],
        current_hypothesis: Optional[str],
        stage: str,
        status: str,
        details: dict[str, Any],
    ) -> None:
        if self._progress_callback is None:
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
        self._progress_callback(event)

    def _build_reasoning_backend(
        self,
        config: AieMasConfig,
        llm_client: Optional[OpenAICompatibleMicroscopicClient],
    ) -> MicroscopicReasoningBackend:
        return OpenAIMicroscopicReasoningBackend(config, client=llm_client)

    def _build_reasoning_payload(
        self,
        *,
        current_hypothesis: str,
        task_instruction: str,
        task_spec: MicroscopicTaskSpec,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
        shared_structure_context: Optional[SharedStructureContext],
        round_index: int,
    ) -> dict[str, Any]:
        requested_deliverables = self._requested_deliverables(task_instruction)
        unsupported_requests = self._unsupported_requests(task_instruction, task_spec)
        registry_examples = render_registry_backed_microscopic_examples()
        return {
            "current_hypothesis": current_hypothesis,
            "task_instruction": task_instruction,
            "task_mode": task_spec.mode,
            "current_round_index": round_index,
            "requested_deliverables": requested_deliverables,
            "unsupported_requests": unsupported_requests,
            "budget_profile": self._config.microscopic_budget_profile,
            "action_registry": render_amesp_action_registry(),
            "baseline_action_card_example": registry_examples["baseline"],
            "torsion_action_card_example": registry_examples["torsion"],
            "capability_registry": render_amesp_capability_registry(),
            "recent_rounds_context": recent_rounds_context,
            "available_structure_context": self._available_structure_context(
                available_artifacts,
                shared_structure_context=shared_structure_context,
            ),
            "shared_structure_context": (
                shared_structure_context.model_dump(mode="json")
                if shared_structure_context is not None
                else None
            ),
            "runtime_context": self._runtime_context_summary(),
        }

    def _available_structure_context(
        self,
        available_artifacts: dict[str, Any],
        *,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> dict[str, Any]:
        context = {
            "has_prepared_structure": False,
            "prepared_xyz_path": None,
            "prepared_summary_path": None,
            "prepared_atom_count": None,
            "prepared_charge": None,
            "prepared_multiplicity": None,
            "source": "missing",
        }
        if shared_structure_context is not None:
            context["has_prepared_structure"] = True
            context["prepared_xyz_path"] = shared_structure_context.prepared_xyz_path
            context["prepared_summary_path"] = shared_structure_context.summary_path
            context["prepared_atom_count"] = shared_structure_context.atom_count
            context["prepared_charge"] = shared_structure_context.charge
            context["prepared_multiplicity"] = shared_structure_context.multiplicity
            context["source"] = "shared_structure_context"
            return context
        summary_path = available_artifacts.get("prepared_summary_path")
        xyz_path = available_artifacts.get("prepared_xyz_path")
        if not summary_path or not xyz_path:
            return context
        summary_path_obj = Path(str(summary_path))
        xyz_path_obj = Path(str(xyz_path))
        if not summary_path_obj.exists() or not xyz_path_obj.exists():
            return context
        context["has_prepared_structure"] = True
        context["prepared_xyz_path"] = str(xyz_path_obj)
        context["prepared_summary_path"] = str(summary_path_obj)
        try:
            summary_payload = json.loads(summary_path_obj.read_text(encoding="utf-8"))
        except Exception:
            return context
        context["prepared_atom_count"] = summary_payload.get("atom_count")
        context["prepared_charge"] = summary_payload.get("charge")
        context["prepared_multiplicity"] = summary_payload.get("multiplicity")
        context["source"] = "available_artifacts"
        return context

    def _runtime_context_summary(self) -> dict[str, Any]:
        return {
            "microscopic_backend": self._config.microscopic_backend,
            "amesp_binary_path": str(self._config.amesp_binary_path) if self._config.amesp_binary_path else None,
            "supports_real_amesp": self._amesp_tool is not None,
            "baseline_policy": (
                "baseline-first must stay low-cost; do not default to heavy exhaustive DFT geometry optimization for large systems"
            ),
            "supported_scope": [
                "baseline_bundle: low-cost aTB S0 optimization plus vertical excited-state manifold",
                (
                    "conformer_bundle_follow_up: bounded conformer sensitivity route "
                    f"(max {self._config.amesp_follow_up_max_conformers} conformers)"
                ),
                (
                    "torsion_snapshot_follow_up: bounded torsion sensitivity route "
                    f"(max {self._config.amesp_follow_up_max_torsion_snapshots_total} snapshots)"
                ),
            ],
            "unsupported_scope": [
                "heavy full-DFT geometry optimization as a default first-round baseline",
                "excited-state relaxation follow-up before route validation",
                "scan",
                "TS",
                "IRC",
                "solvent",
                "SOC",
                "NAC",
                "AIMD",
            ],
            "shared_structure_policy": (
                "prefer shared prepared structure context; only compatibility paths may fall back to private structure preparation"
            ),
            "budget_profile": self._config.microscopic_budget_profile,
            "vertical_state_count_default": self._config.amesp_s1_nstates,
        }

    def _resolve_workdir(self, *, case_id: str, round_index: int) -> Path:
        base_dir = self._tools_work_dir or (Path.cwd() / "var" / "runtime" / "tools")
        return base_dir / "microscopic" / case_id / f"round_{round_index:02d}"

    def _requested_deliverables(self, task_received: str) -> list[str]:
        lower_instruction = task_received.lower()
        deliverables: list[str] = []
        torsion_like = any(
            token in lower_instruction
            for token in ("torsion", "dihedral", "twist", "rotor", "rotation sensitivity", "rotational sensitivity")
        )
        if any(token in lower_instruction for token in ("s0", "ground-state", "ground state", "opt")):
            deliverables.append("low-cost aTB S0 geometry optimization")
        if any(token in lower_instruction for token in ("s1", "excited", "oscillator", "vertical")):
            deliverables.append("vertical excited-state manifold characterization")
        if "dipole" in lower_instruction:
            deliverables.append("dipole summary")
        if "charge" in lower_instruction:
            deliverables.append("Mulliken charge summary")
        if any(token in lower_instruction for token in ("conformer", "conformational")):
            deliverables.append("conformer-sensitivity summary")
        if torsion_like:
            deliverables.append("torsion-sensitivity summary")
        if not deliverables:
            deliverables.extend(
                [
                    "low-cost aTB S0 geometry optimization",
                    "vertical excited-state manifold characterization",
                ]
            )
        return deliverables

    def _unsupported_requests(
        self,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
    ) -> list[str]:
        del task_spec
        lower_instruction = task_received.lower()
        unsupported: list[str] = []
        if "scan" in lower_instruction and any(
            token in lower_instruction for token in ("torsion", "dihedral", "rotation", "rotor")
        ):
            unsupported.append("torsion scan")
        keyword_mapping = {
            "heavy full-DFT geometry optimization": (
                re.compile(r"\bfull[\s-]?dft\b"),
                re.compile(r"\bexhaustive geometry optimization\b"),
            ),
            "transition-state optimization": (
                re.compile(r"\btransition[\s-]?state\b"),
                re.compile(r"\bts optimization\b"),
                re.compile(r"\btransition[\s-]?state optimization\b"),
            ),
            "IRC": (re.compile(r"\birc\b"),),
            "solvent model": (
                re.compile(r"\bsolvent model\b"),
                re.compile(r"\bcpcm\b"),
                re.compile(r"\bcosmo\b"),
            ),
            "SOC/NAC analysis": (
                re.compile(r"\bsoc\b"),
                re.compile(r"\bnac\b"),
            ),
            "AIMD": (
                re.compile(r"\baimd\b"),
                re.compile(r"\bab initio molecular dynamics\b"),
            ),
            "bond-order analysis": (
                re.compile(r"\bbond order\b"),
                re.compile(r"\bmayer\b"),
            ),
        }
        for label, patterns in keyword_mapping.items():
            if any(pattern.search(lower_instruction) for pattern in patterns):
                unsupported.append(label)
        unsupported.extend(self._registry_blocked_requests(task_received))
        return list(dict.fromkeys(unsupported))

    def _registry_blocked_requests(
        self,
        task_received: str,
    ) -> list[str]:
        lower_instruction = task_received.lower()
        registry_blocked: list[str] = []
        bypass_parse_patterns = (
            re.compile(r"\bdo not call parse_snapshot_outputs\b"),
            re.compile(r"\bdo not use parse_snapshot_outputs\b"),
            re.compile(r"\bwithout (?:calling|using) parse_snapshot_outputs\b"),
            re.compile(r"\binstead of parse_snapshot_outputs\b"),
        )
        direct_raw_patterns = (
            re.compile(r"\bdirect(?:ly)?\s+(?:inspect|read|check|review|parse)\b.*\b(raw|aop|mo|stdout|output files?)\b"),
            re.compile(r"\binspect\b.*\braw (?:artifact|artifacts|file|files|output|outputs)\b"),
            re.compile(r"\braw artifact inspection\b"),
            re.compile(r"\braw baseline output files?\b"),
        )
        if any(pattern.search(lower_instruction) for pattern in bypass_parse_patterns + direct_raw_patterns):
            registry_blocked.append("raw artifact inspection")
        return registry_blocked

    def _has_reusable_structure(self, available_artifacts: dict[str, Any]) -> bool:
        summary_path = available_artifacts.get("prepared_summary_path")
        xyz_path = available_artifacts.get("prepared_xyz_path")
        return bool(summary_path and xyz_path and Path(str(summary_path)).exists() and Path(str(xyz_path)).exists())

    def _recent_context_note(self, recent_rounds_context: list[dict[str, object]]) -> str:
        if not recent_rounds_context:
            return "No prior microscopic round context is available."
        latest = recent_rounds_context[-1]
        return (
            f"Recent round {latest.get('round_id')} used action '{latest.get('action_taken')}' "
            f"and left the gap '{latest.get('main_gap')}'."
        )

    def _capability_scope_text(self) -> str:
        return (
            "Current microscopic capability is Amesp low-cost multi-route execution with protocolized capabilities: "
            "run_baseline_bundle, run_conformer_bundle, run_torsion_snapshots, and parse_snapshot_outputs. "
            "unsupported_excited_state_relaxation is a fail-fast unsupported capability and does not execute."
        )

    def _structure_source_note(
        self,
        structure_source: str,
        available_artifacts: dict[str, Any],
        *,
        shared_structure_context: Optional[SharedStructureContext],
    ) -> str:
        if structure_source == "existing_prepared_structure" and shared_structure_context is not None:
            return (
                "Reuse the shared prepared 3D structure context that is already available for this case at "
                f"{shared_structure_context.prepared_xyz_path}."
            )
        if structure_source == "existing_prepared_structure":
            return "Reuse the previously prepared 3D structure artifacts that are already available for this case."
        if available_artifacts.get("prepared_xyz_path"):
            return (
                "A previous prepared structure was referenced but is not reusable from disk, so a fresh 3D structure "
                "will be generated from the input SMILES before the bounded Amesp route is executed."
            )
        return "Prepare a fresh 3D structure from the input SMILES before running the bounded Amesp route."

    def _unsupported_requests_note(self, unsupported_requests: list[str]) -> str:
        if not unsupported_requests:
            return "No unsupported local request was detected."
        return "; ".join(unsupported_requests)

    def _registry_completion_code_for_parse_error(
        self,
        contract_errors: list[str],
    ) -> MicroscopicCompletionReasonCode:
        registry_markers = (
            "unknown execution_action",
            "not allowed for execution_action",
            "python-owned and must not be authored",
            "invalid discovery action",
            "placeholder target values are not allowed for param.",
            "registry-backed action card",
        )
        joined = " ".join(contract_errors).lower()
        if any(marker in joined for marker in registry_markers):
            return "action_not_supported_by_registry"
        return "protocol_parse_failed"

    def _registry_handshake_reason(
        self,
        *,
        completion_reason_code: Optional[MicroscopicCompletionReasonCode],
        missing_deliverables: list[str],
        route_summary: Optional[dict[str, Any]],
        registry_validation_errors: list[str],
    ) -> Optional[str]:
        if completion_reason_code == "action_not_supported_by_registry":
            return "action_not_supported_by_registry"
        if completion_reason_code == "capability_unsupported":
            return "microscopic_capability_unsupported"
        if registry_validation_errors:
            return "registry_validation_failed"
        missing_lower = [item.lower() for item in missing_deliverables]
        if any("ct/localization proxy" in item or "dominant transition" in item for item in missing_lower):
            return "required_registry_observables_unavailable"
        if isinstance(route_summary, dict) and route_summary.get("ct_proxy_availability") == "not_available":
            return "required_registry_observables_unavailable"
        return None

    def _remaining_uncertainty_text(
        self,
        unsupported_requests: list[str],
        task_mode: str,
        capability_route: MicroscopicCapabilityRoute,
    ) -> str:
        limitation_bits = [
            f"this bounded Amesp route '{capability_route}' does not adjudicate the global mechanism",
            "it does not execute full-DFT or heavy excited-state optimization",
        ]
        if capability_route == "artifact_parse_only":
            limitation_bits.append("it only parses existing artifacts and cannot create new microscopic evidence")
        if unsupported_requests:
            limitation_bits.append(
                "it also leaves unsupported local requests unresolved: " + "; ".join(unsupported_requests)
            )
        if task_mode == "targeted_follow_up":
            limitation_bits.append(
                "targeted follow-up remains bounded by current Amesp route availability and resource limits"
            )
        return ". ".join(limitation_bits) + "."

    def _plan_steps_text(self, plan: MicroscopicExecutionPlan) -> str:
        return " ".join(f"[{step.step_id}] {step.description}" for step in plan.steps)

    def _successful_result_summary(self, structured_results: dict[str, Any]) -> str:
        route = structured_results.get("attempted_route") or "baseline_bundle"
        executed_capability = structured_results.get("executed_capability") or "run_baseline_bundle"
        route_summary = structured_results.get("route_summary") or {}
        if executed_capability == "parse_snapshot_outputs":
            parsed_records = structured_results.get("parsed_snapshot_records") or structured_results.get("route_records") or []
            return (
                f"Amesp capability '{executed_capability}' reused existing microscopic artifacts and returned "
                f"{len(parsed_records)} parsed snapshot records without new calculations. "
                f"Route summary={route_summary}."
            )
        s0 = structured_results["s0"]
        s1 = structured_results["s1"]
        manifold = structured_results.get("vertical_state_manifold") or {}
        return (
            f"Amesp route '{route}' finished with final_energy_hartree={s0['final_energy_hartree']}, "
            f"homo_lumo_gap_ev={s0['homo_lumo_gap_ev']}, "
            f"rmsd_from_prepared_structure_angstrom={s0['rmsd_from_prepared_structure_angstrom']}, "
            f"and {len(s0['mulliken_charges'])} Mulliken charges. "
            f"Bounded S1 vertical excitation returned first_excitation_energy_ev={s1['first_excitation_energy_ev']} "
            f"and first_oscillator_strength={s1['first_oscillator_strength']} across {s1['state_count']} states. "
            f"First bright state energy={manifold.get('first_bright_state_energy_ev')} "
            f"with pattern={manifold.get('lowest_state_to_brightest_pattern')}. "
            f"Route summary={route_summary}."
        )

    def _failed_result_summary(self, exc: AmespExecutionError) -> str:
        return f"Amesp microscopic execution returned status={exc.status} with {exc.code}: {exc.message}"

    def _task_completion_for_result(
        self,
        *,
        run_status: str,
        unsupported_requests: list[str],
        task_mode: str,
        capability_route: MicroscopicCapabilityRoute,
        requested_capability: str,
        executed_capability: Optional[str],
        performed_new_calculations: bool,
        reused_existing_artifacts: bool,
        resolved_target_ids: dict[str, Any],
        honored_constraints: list[str],
        unmet_constraints: list[str],
        missing_deliverables: list[str],
        error_message: Optional[str],
        error_payload: Optional[dict[str, Any]],
    ) -> tuple[str, Optional[MicroscopicCompletionReasonCode], str]:
        executed_capability = executed_capability or requested_capability
        action_clause = (
            f"I executed `{executed_capability}`, performed {'new calculations' if performed_new_calculations else 'no new calculations'}, "
            f"and {'reused existing artifacts' if reused_existing_artifacts else 'did not rely on existing artifacts only'}."
        )
        target_clause = (
            f" Resolved targets: {self._resolved_target_ids_text(resolved_target_ids)}."
            if resolved_target_ids
            else ""
        )
        honored_clause = (
            " Honored constraints: " + "; ".join(honored_constraints) + "."
            if honored_constraints
            else ""
        )
        unmet_clause = (
            " Unmet constraints: " + "; ".join(unmet_constraints) + "."
            if unmet_constraints
            else ""
        )
        if run_status == "failed":
            reason_code = self._map_error_to_completion_reason(error_payload)
            return (
                "failed",
                reason_code,
                (
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The task failed while using Amesp route '{capability_route}': "
                    f"{error_message or 'no error details were provided.'}"
                ),
            )
        if run_status == "partial":
            reason_code = self._map_error_to_completion_reason(error_payload) or "partial_observable_only"
            return (
                "partial",
                reason_code,
                (
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The task was only partially completed because Amesp route '{capability_route}' was incomplete: "
                    f"{error_message or 'no partial-execution details were provided.'}"
                ),
            )
        if requested_capability != executed_capability or missing_deliverables or unmet_constraints:
            missing_note = (
                " Missing deliverables: " + "; ".join(missing_deliverables) + "."
                if missing_deliverables
                else ""
            )
            unsupported_note = (
                " Unsupported background requests were also noted: " + "; ".join(unsupported_requests) + "."
                if unsupported_requests
                else ""
            )
            return (
                "contracted",
                "partial_observable_only",
                (
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The task completed in a contracted form via Amesp route '{capability_route}'.{missing_note}"
                    f"{unsupported_note}"
                ),
            )
        if unsupported_requests:
            unsupported = "; ".join(unsupported_requests)
            if capability_route == "excited_state_relaxation_follow_up":
                return (
                    "contracted",
                    "capability_unsupported",
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    "The requested excited-state relaxation follow-up is not yet validated "
                    f"within current Amesp capability, so route '{capability_route}' could not be executed. "
                    f"Unsupported parts were: {unsupported}.",
                )
            if task_mode == "targeted_follow_up":
                return (
                    "contracted",
                    "partial_observable_only",
                    f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The requested targeted microscopic follow-up could not be executed exactly as asked, so Amesp route "
                    f"'{capability_route}' returned the closest bounded substitute instead. "
                    f"Unsupported parts were: {unsupported}.",
                )
            return (
                "contracted",
                "partial_observable_only",
                f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                    f"The agent returned bounded Amesp route '{capability_route}' evidence, but it could not execute unsupported "
                    f"parts of the Planner instruction: {unsupported}.",
                )
        return (
            "completed",
            None,
            (
                f"The Planner requested `{requested_capability}`. {action_clause}{target_clause}{honored_clause}{unmet_clause} "
                "All requested deliverables were produced within current microscopic capability."
                + (
                    " Unsupported background requests were noted but did not block the executed capability: "
                    + "; ".join(unsupported_requests)
                    + "."
                    if unsupported_requests
                    else ""
                )
            ),
        )

    def _missing_deliverables_text(self, missing_deliverables: list[str]) -> str:
        if not missing_deliverables:
            return "No requested deliverables were missing."
        return "; ".join(missing_deliverables)

    def _resolved_target_ids_text(self, resolved_target_ids: dict[str, Any]) -> str:
        if not resolved_target_ids:
            return "No resolved target IDs were recorded."
        parts: list[str] = []
        for key in sorted(resolved_target_ids):
            parts.append(f"{key}={resolved_target_ids[key]}")
        return "; ".join(parts)

    def _constraint_text(self, constraints: list[str], *, default_text: str) -> str:
        if not constraints:
            return default_text
        return "; ".join(constraints)

    def _vertical_state_manifold(self, s1_result: Any) -> dict[str, Any]:
        excited_states = list(getattr(s1_result, "excited_states", []))
        bright_states = [state for state in excited_states if getattr(state, "oscillator_strength", 0.0) > 0.05]
        first_bright = bright_states[0] if bright_states else None
        return {
            "state_count": getattr(s1_result, "state_count", len(excited_states)),
            "first_bright_state_energy_ev": (
                getattr(first_bright, "excitation_energy_ev", None) if first_bright is not None else None
            ),
            "first_bright_state_oscillator_strength": (
                getattr(first_bright, "oscillator_strength", None) if first_bright is not None else None
            ),
            "lowest_state_to_brightest_pattern": (
                "lowest_state_is_bright"
                if first_bright is not None and getattr(first_bright, "state_index", None) == 1
                else "lowest_state_is_dark_then_bright"
                if first_bright is not None
                else "no_bright_state_detected"
            ),
            "oscillator_strength_summary": {
                "sum": round(sum(getattr(state, "oscillator_strength", 0.0) for state in excited_states), 6),
                "max": max((getattr(state, "oscillator_strength", 0.0) for state in excited_states), default=None),
            },
        }

    def _map_error_to_completion_reason(
        self,
        error_payload: Optional[dict[str, Any]],
    ) -> Optional[MicroscopicCompletionReasonCode]:
        if not error_payload:
            return None
        code = error_payload.get("code")
        if code in {"capability_unsupported"}:
            return "capability_unsupported"
        if code in {"precondition_missing", "structure_unavailable", "shared_structure_unavailable"}:
            return "precondition_missing"
        if code in {"resource_budget_exceeded"}:
            return "resource_budget_exceeded"
        if code in {"parse_failed"}:
            return "parse_failed"
        if code in {"action_not_supported_by_registry"}:
            return "action_not_supported_by_registry"
        if code in {"protocol_parse_failed"}:
            return "protocol_parse_failed"
        if code in {"subprocess_failed", "normal_termination_missing", "amesp_binary_missing"}:
            return "runtime_failed"
        return None
