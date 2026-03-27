from __future__ import annotations

import json
import re
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
    AMESP_CAPABILITY_REGISTRY,
    AmespExecutionError,
    AmespMicroscopicTool,
    render_amesp_capability_registry,
)
from aie_mas.utils.prompts import PromptRepository


MicroscopicStructureStrategy = Literal[
    "prepare_from_smiles",
    "reuse_if_available_else_prepare_from_smiles",
]


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


class MicroscopicReasoningPlanDraft(BaseModel):
    local_goal: str
    requested_deliverables: list[str] = Field(default_factory=list)
    capability_route: Optional[MicroscopicCapabilityRoute] = None
    requested_route_summary: Optional[str] = None
    microscopic_tool_request: Optional["MicroscopicToolRequestDraft"] = None
    microscopic_tool_plan: Optional["MicroscopicToolPlanDraft"] = None
    structure_strategy: MicroscopicStructureStrategy = "reuse_if_available_else_prepare_from_smiles"
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


class TaggedMicroscopicProtocolError(ValueError):
    pass


_TAGGED_REASONING_SECTION_NAMES = (
    "task_understanding",
    "reasoning_summary",
    "capability_limit_note",
    "expected_outputs",
    "failure_policy",
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


def _strip_reasoning_code_fence(raw_text: str) -> str:
    candidate = raw_text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
    return candidate


def _extract_tagged_reasoning_sections(raw_text: str) -> dict[str, str]:
    candidate = _strip_reasoning_code_fence(raw_text)
    matches = list(re.finditer(r"<([a-z_]+)>\s*(.*?)\s*</\1>", candidate, flags=re.DOTALL))
    if not matches:
        raise TaggedMicroscopicProtocolError("Tagged microscopic reasoning sections were not found.")
    sections: dict[str, str] = {}
    for match in matches:
        section_name = match.group(1)
        if section_name not in _TAGGED_REASONING_SECTION_NAMES:
            raise TaggedMicroscopicProtocolError(f"Unknown tagged reasoning section '{section_name}'.")
        if section_name in sections:
            raise TaggedMicroscopicProtocolError(f"Duplicate tagged reasoning section '{section_name}'.")
        sections[section_name] = match.group(2).strip()
    missing_sections = [name for name in _TAGGED_REASONING_SECTION_NAMES if name not in sections]
    if missing_sections:
        raise TaggedMicroscopicProtocolError(
            "Tagged microscopic reasoning response is missing required sections: "
            + ", ".join(missing_sections)
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
        if item.startswith("- "):
            item = item[2:].strip()
        elif item.startswith("* "):
            item = item[2:].strip()
        if item:
            outputs.append(item)
    return outputs


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
            payload[key] = int(value)
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


def _parse_tagged_microscopic_reasoning_response(
    raw_text: str,
    *,
    strict: bool = True,
) -> MicroscopicReasoningResponse:
    sections = _extract_tagged_reasoning_sections(raw_text)
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


class MicroscopicReasoningBackend(Protocol):
    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningResponse:
        ...


class OpenAIMicroscopicReasoningBackend:
    def __init__(
        self,
        config: AieMasConfig,
        client: Optional[OpenAICompatibleMicroscopicClient] = None,
    ) -> None:
        self._client = client or OpenAICompatibleMicroscopicClient(config)
        self.last_parse_mode = "legacy_json_fallback"
        self.last_raw_text: Optional[str] = None

    def reason(self, rendered_prompt: Any, payload: dict[str, Any]) -> MicroscopicReasoningResponse:
        _ = payload
        raw_text = self._client.invoke_text(messages=prompt_value_to_messages(rendered_prompt))
        self.last_raw_text = raw_text
        tagged_error: Exception | None = None
        try:
            response = _parse_tagged_microscopic_reasoning_response(raw_text)
        except Exception as exc:
            tagged_error = exc
        else:
            self.last_parse_mode = "tagged_protocol"
            return response

        try:
            response = _parse_tagged_microscopic_reasoning_response(raw_text, strict=False)
        except Exception:
            pass
        else:
            self.last_parse_mode = "tagged_protocol"
            return response

        try:
            payload_obj = self._client.parse_json_object_text(raw_text)
            response = MicroscopicReasoningResponse.model_validate(payload_obj)
        except Exception as exc:
            if tagged_error is None:
                raise
            raise ValueError(
                "Microscopic reasoning output was neither a valid tagged protocol nor valid legacy JSON. "
                f"Tagged error: {tagged_error}. JSON error: {exc}."
            ) from exc
        self.last_parse_mode = "legacy_json_fallback"
        return MicroscopicReasoningResponse.model_validate(response.model_dump(mode="json"))


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
        )
        rendered_prompt = self._prompts.render("microscopic_reasoning", reasoning_payload)
        reasoning = self._reasoning_backend.reason(rendered_prompt, reasoning_payload)
        reasoning_parse_mode = getattr(self._reasoning_backend, "last_parse_mode", "legacy_json_fallback")
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
            },
        )
        plan = self._normalize_execution_plan(
            task_received=task_received,
            task_spec=task_spec,
            available_artifacts=available_artifacts,
            shared_structure_context=shared_structure_context,
            reasoning=reasoning,
        )
        self._emit_probe(
            round_index=round_index,
            case_id=resolved_case_id,
            current_hypothesis=current_hypothesis,
            stage="execution_plan",
            status="end",
            details=plan.model_dump(mode="json"),
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
                reasoning=reasoning,
                plan=plan,
                shared_structure_status=shared_structure_status,
            )

        if self._amesp_tool is not None:
            return self._run_real(
                smiles=smiles,
                task_received=task_received,
                task_spec=task_spec,
                current_hypothesis=current_hypothesis,
                reasoning=reasoning,
                plan=plan,
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
        reasoning: MicroscopicReasoningResponse,
        plan: MicroscopicExecutionPlan,
        recent_rounds_context: list[dict[str, object]],
        available_artifacts: dict[str, Any],
        shared_structure_context: Optional[SharedStructureContext],
        case_id: str,
        round_index: int,
    ) -> AgentReport:
        reasoning_parse_mode = getattr(self._reasoning_backend, "last_parse_mode", "legacy_json_fallback")
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

    def _shared_structure_unavailable_report(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        current_hypothesis: str,
        reasoning: MicroscopicReasoningResponse,
        plan: MicroscopicExecutionPlan,
        shared_structure_status: SharedStructureStatus,
    ) -> AgentReport:
        reasoning_parse_mode = getattr(self._reasoning_backend, "last_parse_mode", "legacy_json_fallback")
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
                "execution_plan": plan.model_dump(mode="json"),
                "requested_capability": plan.microscopic_tool_request.capability_name,
                "executed_capability": plan.microscopic_tool_request.capability_name,
                "performed_new_calculations": False,
                "reused_existing_artifacts": False,
                "resolved_target_ids": {},
                "honored_constraints": [],
                "unmet_constraints": ["shared_structure_context was unavailable before tool execution"],
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
    ) -> dict[str, Any]:
        requested_deliverables = self._requested_deliverables(task_instruction)
        unsupported_requests = self._unsupported_requests(task_instruction, task_spec)
        return {
            "current_hypothesis": current_hypothesis,
            "task_instruction": task_instruction,
            "task_mode": task_spec.mode,
            "requested_deliverables": requested_deliverables,
            "unsupported_requests": unsupported_requests,
            "budget_profile": self._config.microscopic_budget_profile,
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

    def _normalize_execution_plan(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        available_artifacts: dict[str, Any],
        shared_structure_context: Optional[SharedStructureContext],
        reasoning: MicroscopicReasoningResponse,
    ) -> MicroscopicExecutionPlan:
        requested_deliverables = (
            list(reasoning.execution_plan.requested_deliverables)
            if reasoning.execution_plan.requested_deliverables
            else self._requested_deliverables(task_received)
        )
        tool_plan = self._build_tool_plan(
            task_received=task_received,
            task_spec=task_spec,
            requested_deliverables=requested_deliverables,
            reasoning=reasoning,
        )
        tool_request = self._compatibility_tool_request(tool_plan)
        capability_route = self._compatibility_route_for_capability(tool_request.capability_name)
        unsupported_requests = list(reasoning.execution_plan.unsupported_requests)
        structure_is_reusable = bool(shared_structure_context is not None) or self._has_reusable_structure(
            available_artifacts
        )
        structure_source = (
            "existing_prepared_structure"
            if reasoning.execution_plan.structure_strategy == "reuse_if_available_else_prepare_from_smiles"
            and structure_is_reusable
            else "prepared_from_smiles"
        )
        step_sequence = list(reasoning.execution_plan.step_sequence) or [
            "structure_prep",
            "s0_optimization",
            "s1_vertical_excitation",
        ]
        if tool_request.capability_name == "run_baseline_bundle":
            step_sequence = ["structure_prep", "s0_optimization", "s1_vertical_excitation"]
            expected_outputs = list(reasoning.expected_outputs) or [
                "S0 optimized geometry",
                "S0 final energy",
                "S0 dipole",
                "S0 Mulliken charges",
                "S0 HOMO-LUMO gap",
                "vertical excited-state manifold",
                "first bright state energy",
                "first bright state oscillator strength",
            ]
        elif tool_request.capability_name == "run_conformer_bundle":
            step_sequence = [
                "conformer_bundle_generation",
                "s0_optimization" if tool_request.optimize_ground_state else "s0_singlepoint",
                "s1_vertical_excitation",
            ]
            expected_outputs = [
                "bounded conformer bundle vertical-state records",
                "excitation spread",
                "bright-state sensitivity",
                "conformer-dependent uncertainty note",
            ]
        elif tool_request.capability_name == "run_torsion_snapshots":
            step_sequence = [
                "torsion_snapshot_generation",
                "s0_optimization" if tool_request.optimize_ground_state else "s0_singlepoint",
                "s1_vertical_excitation",
            ]
            expected_outputs = [
                "snapshot geometry labels",
                "snapshot vertical-state proxies",
                "torsion sensitivity summary",
            ]
        elif tool_request.capability_name == "parse_snapshot_outputs":
            step_sequence = ["artifact_parse"]
            expected_outputs = [
                "per-snapshot excitation energies",
                "per-snapshot oscillator strengths",
                "state-ordering records",
                "artifact reuse note",
            ]
        else:
            step_sequence = ["structure_prep"]
            expected_outputs = ["unsupported follow-up report"]
            unsupported_note = "excited-state relaxation follow-up is not yet validated in current Amesp capability"
            if unsupported_note not in unsupported_requests:
                unsupported_requests.append(unsupported_note)

        if structure_source == "existing_prepared_structure" and tool_request.perform_new_calculation:
            step_sequence = [step for step in step_sequence if step != "structure_prep"]
        steps = [self._build_step(step_type, structure_source) for step_type in step_sequence]
        return MicroscopicExecutionPlan(
            local_goal=reasoning.execution_plan.local_goal,
            requested_deliverables=requested_deliverables,
            capability_route=capability_route,
            microscopic_tool_plan=tool_plan,
            microscopic_tool_request=tool_request,
            budget_profile=self._config.microscopic_budget_profile or "balanced",
            requested_route_summary=reasoning.execution_plan.requested_route_summary
            or tool_plan.requested_route_summary
            or tool_request.requested_route_summary
            or self._requested_route_summary(capability_route, task_received),
            structure_source=structure_source,  # type: ignore[arg-type]
            supported_scope=[
                "list_rotatable_dihedrals: discovery-only rotatable dihedral enumeration with stable IDs",
                "list_available_conformers: discovery-only conformer enumeration with stable IDs",
                "list_artifact_bundles: discovery-only artifact bundle enumeration with stable IDs",
                "run_baseline_bundle: low-cost aTB S0 geometry optimization plus vertical excited-state manifold",
                "run_conformer_bundle: bounded conformer ensemble follow-up",
                "run_torsion_snapshots: bounded torsion snapshot follow-up",
                "parse_snapshot_outputs: parse existing snapshot artifacts without new calculations",
            ],
            unsupported_requests=unsupported_requests,
            steps=steps,
            expected_outputs=expected_outputs,
            failure_reporting=reasoning.failure_policy,
        )

    def _build_tool_plan(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        requested_deliverables: list[str],
        reasoning: MicroscopicReasoningResponse,
    ) -> MicroscopicToolPlan:
        draft_plan = reasoning.execution_plan.microscopic_tool_plan
        selection_policy = self._build_selection_policy(task_received=task_received, draft=draft_plan.selection_policy if draft_plan is not None else None)
        calls, normalization_notes = self._normalize_tool_calls(
            task_received=task_received,
            task_spec=task_spec,
            requested_deliverables=requested_deliverables,
            reasoning=reasoning,
        )
        return MicroscopicToolPlan(
            calls=calls,
            requested_route_summary=(
                draft_plan.requested_route_summary
                if draft_plan is not None and draft_plan.requested_route_summary
                else reasoning.execution_plan.requested_route_summary
                or self._requested_route_summary(self._compatibility_route_for_capability(self._compatibility_tool_request_from_calls(calls).capability_name), task_received)
            ),
            requested_deliverables=(
                list(draft_plan.requested_deliverables)
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

    def _compatibility_tool_request(self, tool_plan: MicroscopicToolPlan) -> MicroscopicToolRequest:
        return self._compatibility_tool_request_from_calls(tool_plan.calls)

    def _compatibility_tool_request_from_calls(
        self,
        calls: list[MicroscopicToolCall],
    ) -> MicroscopicToolRequest:
        for call in calls:
            if call.call_kind == "execution":
                return call.request
        return MicroscopicToolRequest(
            capability_name="unsupported_excited_state_relaxation",
            perform_new_calculation=False,
            reuse_existing_artifacts_only=False,
            requested_route_summary="No microscopic execution call was available.",
        )

    def _build_selection_policy(
        self,
        *,
        task_received: str,
        draft: Optional[SelectionPolicyDraft],
    ) -> SelectionPolicy:
        lower_instruction = task_received.lower()
        exclude_dihedral_ids = list(draft.exclude_dihedral_ids) if draft is not None else []
        explicit_dihedral = self._explicit_dihedral_id_from_instruction(task_received)
        if "do not use dihedral" in lower_instruction and explicit_dihedral is not None and explicit_dihedral not in exclude_dihedral_ids:
            exclude_dihedral_ids.append(explicit_dihedral)
        return SelectionPolicy(
            exclude_dihedral_ids=exclude_dihedral_ids,
            prefer_adjacent_to_nsnc_core=(
                draft.prefer_adjacent_to_nsnc_core
                if draft is not None and draft.prefer_adjacent_to_nsnc_core is not None
                else "nsnc" in lower_instruction or "core-adjacent" in lower_instruction or "core adjacent" in lower_instruction
            ),
            min_relevance=(
                draft.min_relevance
                if draft is not None and draft.min_relevance is not None
                else "high"
                if any(token in lower_instruction for token in ("maximally conjugation-relevant", "central conjugation-relevant", "truly central"))
                else "medium"
            ),
            include_peripheral=(
                draft.include_peripheral
                if draft is not None and draft.include_peripheral is not None
                else not any(token in lower_instruction for token in ("avoid peripheral", "exclude peripheral", "not peripheral"))
            ),
            preferred_bond_types=(
                list(draft.preferred_bond_types)
                if draft is not None and draft.preferred_bond_types
                else self._preferred_bond_types_from_instruction(lower_instruction)
            ),
            artifact_kind=(
                draft.artifact_kind
                if draft is not None
                else "torsion_snapshots"
                if "snapshot" in lower_instruction or "dihedral" in lower_instruction or "torsion" in lower_instruction
                else None
            ),
            source_round_preference=(
                draft.source_round_preference
                if draft is not None and draft.source_round_preference is not None
                else self._source_round_preference_from_instruction(lower_instruction)
            ),
        )

    def _normalize_tool_calls(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        requested_deliverables: list[str],
        reasoning: MicroscopicReasoningResponse,
    ) -> tuple[list[MicroscopicToolCall], list[str]]:
        draft_plan = reasoning.execution_plan.microscopic_tool_plan
        if draft_plan is not None and draft_plan.calls:
            calls = [self._normalize_tool_call(call, requested_deliverables, task_received) for call in draft_plan.calls]
        else:
            calls = self._fallback_tool_calls(
                task_received=task_received,
                task_spec=task_spec,
                requested_deliverables=requested_deliverables,
                reasoning=reasoning,
            )
        calls = self._ensure_discovery_before_execution(calls)
        return self._canonicalize_tool_call_sequence(calls)

    def _canonicalize_tool_call_sequence(
        self,
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

    def _normalize_tool_call(
        self,
        draft_call: MicroscopicToolCallDraft,
        requested_deliverables: list[str],
        task_received: str,
    ) -> MicroscopicToolCall:
        request_draft = draft_call.request or MicroscopicToolRequestDraft()
        capability_name = request_draft.capability_name or "unsupported_excited_state_relaxation"
        return MicroscopicToolCall(
            call_id=draft_call.call_id or f"{draft_call.call_kind or 'execution'}_{capability_name}",
            call_kind=draft_call.call_kind or self._default_call_kind(capability_name),
            request=self._normalize_tool_call_request(
                draft=request_draft,
                capability_name=capability_name,
                requested_deliverables=requested_deliverables,
                task_received=task_received,
            ),
        )

    def _fallback_tool_calls(
        self,
        *,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
        requested_deliverables: list[str],
        reasoning: MicroscopicReasoningResponse,
    ) -> list[MicroscopicToolCall]:
        draft = reasoning.execution_plan.microscopic_tool_request
        capability_name = (
            draft.capability_name
            if draft is not None and draft.capability_name is not None
            else self._capability_name_from_route_or_task(
                reasoning.execution_plan.capability_route,
                task_received,
                task_spec,
            )
        )
        calls: list[MicroscopicToolCall] = []
        execution_request = self._normalize_tool_call_request(
            draft=draft or MicroscopicToolRequestDraft(),
            capability_name=capability_name,
            requested_deliverables=requested_deliverables,
            task_received=task_received,
        )
        if capability_name == "run_torsion_snapshots" and not execution_request.dihedral_id:
            calls.append(
                MicroscopicToolCall(
                    call_id="discover_rotatable_dihedrals",
                    call_kind="discovery",
                    request=MicroscopicToolRequest(
                        capability_name="list_rotatable_dihedrals",
                        structure_source="round_s0_optimized_geometry",
                        min_relevance="medium",
                        include_peripheral=True,
                        requested_route_summary="Discover reusable rotatable dihedrals before torsion execution.",
                    ),
                )
            )
        if capability_name == "parse_snapshot_outputs" and not execution_request.artifact_bundle_id:
            calls.append(
                MicroscopicToolCall(
                    call_id="discover_artifact_bundles",
                    call_kind="discovery",
                    request=MicroscopicToolRequest(
                        capability_name="list_artifact_bundles",
                        artifact_kind="torsion_snapshots",
                        requested_route_summary="Discover reusable artifact bundles before parse-only execution.",
                        perform_new_calculation=False,
                        reuse_existing_artifacts_only=True,
                    ),
                )
            )
        calls.append(
            MicroscopicToolCall(
                call_id=f"execute_{capability_name}",
                call_kind="execution",
                request=execution_request,
            )
        )
        return calls

    def _ensure_discovery_before_execution(
        self,
        calls: list[MicroscopicToolCall],
    ) -> list[MicroscopicToolCall]:
        has_dihedral_discovery = any(call.request.capability_name == "list_rotatable_dihedrals" for call in calls)
        has_artifact_discovery = any(call.request.capability_name == "list_artifact_bundles" for call in calls)
        normalized: list[MicroscopicToolCall] = []
        for call in calls:
            if call.call_kind == "execution" and call.request.capability_name == "run_torsion_snapshots" and not call.request.dihedral_id and not has_dihedral_discovery:
                normalized.append(
                    MicroscopicToolCall(
                        call_id="discover_rotatable_dihedrals",
                        call_kind="discovery",
                        request=MicroscopicToolRequest(
                            capability_name="list_rotatable_dihedrals",
                            structure_source="round_s0_optimized_geometry",
                            min_relevance="medium",
                            include_peripheral=True,
                            requested_route_summary="Auto-inserted dihedral discovery before torsion execution.",
                        ),
                    )
                )
                has_dihedral_discovery = True
            if call.call_kind == "execution" and call.request.capability_name == "parse_snapshot_outputs" and not call.request.artifact_bundle_id and not has_artifact_discovery:
                normalized.append(
                    MicroscopicToolCall(
                        call_id="discover_artifact_bundles",
                        call_kind="discovery",
                        request=MicroscopicToolRequest(
                            capability_name="list_artifact_bundles",
                            artifact_kind="torsion_snapshots",
                            perform_new_calculation=False,
                            reuse_existing_artifacts_only=True,
                            requested_route_summary="Auto-inserted artifact-bundle discovery before parse-only execution.",
                        ),
                    )
                )
                has_artifact_discovery = True
            normalized.append(call)
        return normalized

    def _normalize_tool_call_request(
        self,
        *,
        draft: MicroscopicToolRequestDraft,
        capability_name: AmespCapabilityName,
        requested_deliverables: list[str],
        task_received: str,
    ) -> MicroscopicToolRequest:
        capability = AMESP_CAPABILITY_REGISTRY[capability_name]
        snapshot_count = draft.snapshot_count
        state_window = list(draft.state_window)
        if capability_name == "run_conformer_bundle" and snapshot_count is None and draft.max_conformers is None:
            snapshot_count = self._config.amesp_follow_up_max_conformers
        if capability_name == "run_torsion_snapshots" and snapshot_count is None:
            snapshot_count = 2 if draft.angle_offsets_deg else self._config.amesp_follow_up_max_torsion_snapshots_total
        if capability_name == "run_baseline_bundle" and not state_window:
            state_window = list(range(1, max(1, self._config.amesp_s1_nstates) + 1))
        if capability_name in {"run_torsion_snapshots", "run_conformer_bundle", "parse_snapshot_outputs"} and not state_window:
            state_window = list(range(1, max(1, self._config.amesp_s1_nstates) + 1))
        optimize_ground_state = (
            draft.optimize_ground_state
            if draft.optimize_ground_state is not None
            else self._default_optimize_ground_state(capability_name, task_received)
        )
        return MicroscopicToolRequest(
            capability_name=capability_name,
            structure_source=draft.structure_source,
            perform_new_calculation=(
                draft.perform_new_calculation
                if draft.perform_new_calculation is not None
                else capability.requires_new_calculation
            ),
            optimize_ground_state=optimize_ground_state,
            reuse_existing_artifacts_only=(
                draft.reuse_existing_artifacts_only
                if draft.reuse_existing_artifacts_only is not None
                else not capability.requires_new_calculation
            ),
            artifact_source_round=draft.artifact_source_round,
            artifact_scope=draft.artifact_scope,
            artifact_bundle_id=draft.artifact_bundle_id,
            artifact_kind=draft.artifact_kind,
            source_round_preference=draft.source_round_preference,
            min_relevance=draft.min_relevance,
            include_peripheral=draft.include_peripheral,
            preferred_bond_types=list(draft.preferred_bond_types),
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
            deliverables=list(draft.deliverables) if draft.deliverables else requested_deliverables,
            budget_profile=draft.budget_profile or self._config.microscopic_budget_profile,
            requested_route_summary=draft.requested_route_summary or f"Use capability '{capability_name}' for the current microscopic task.",
        )

    def _default_optimize_ground_state(
        self,
        capability_name: AmespCapabilityName,
        task_received: str,
    ) -> bool:
        if capability_name == "parse_snapshot_outputs":
            return False
        if capability_name == "run_baseline_bundle":
            return True
        if capability_name in {"run_torsion_snapshots", "run_conformer_bundle"}:
            lower_instruction = task_received.lower()
            no_reoptimization_patterns = (
                "no re-optimization",
                "no reoptimization",
                "no re-opt",
                "do not re-optimize",
                "do not reoptimize",
                "without re-optimization",
                "without reoptimization",
                "without full re-optimization",
            )
            if any(pattern in lower_instruction for pattern in no_reoptimization_patterns):
                return False
        return True

    def _default_call_kind(self, capability_name: AmespCapabilityName) -> Literal["discovery", "execution"]:
        if capability_name in {"list_rotatable_dihedrals", "list_available_conformers", "list_artifact_bundles"}:
            return "discovery"
        return "execution"

    def _preferred_bond_types_from_instruction(
        self,
        lower_instruction: str,
    ) -> list[DihedralBondType]:
        preferred: list[DihedralBondType] = []
        if "aryl–vinyl" in lower_instruction or "aryl-vinyl" in lower_instruction:
            preferred.append("aryl-vinyl")
        if "aryl–aryl" in lower_instruction or "aryl-aryl" in lower_instruction:
            preferred.append("aryl-aryl")
        if "heteroaryl" in lower_instruction or "nsnc" in lower_instruction:
            preferred.append("heteroaryl-linkage")
        return preferred

    def _source_round_preference_from_instruction(self, lower_instruction: str) -> Optional[int]:
        match = self._round_reference_pattern().search(lower_instruction)
        if not match:
            return None
        return int(match.group(1))

    def _explicit_dihedral_id_from_instruction(self, task_received: str) -> Optional[str]:
        match = re.search(r"\[(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\]", task_received)
        if not match:
            return None
        atoms = [int(match.group(index)) for index in range(1, 5)]
        return "dih_" + "_".join(str(atom) for atom in atoms)

    def _round_reference_pattern(self) -> re.Pattern[str]:
        return re.compile(r"round[_\s-]?0*(\d+)")

    def _capability_name_from_route_or_task(
        self,
        capability_route: Optional[MicroscopicCapabilityRoute],
        task_received: str,
        task_spec: MicroscopicTaskSpec,
    ) -> AmespCapabilityName:
        derived_capability_name = _capability_name_for_compatibility_route(capability_route)
        if derived_capability_name is not None:
            return derived_capability_name
        return self._resolve_capability_name(task_received, task_spec)

    def _compatibility_route_for_capability(
        self,
        capability_name: AmespCapabilityName,
    ) -> MicroscopicCapabilityRoute:
        return _compatibility_route_for_capability_name(capability_name)

    def _build_step(
        self,
        step_type: Literal[
            "structure_prep",
            "conformer_bundle_generation",
            "torsion_snapshot_generation",
            "artifact_parse",
            "s0_optimization",
            "s0_singlepoint",
            "s1_vertical_excitation",
        ],
        structure_source: str,
    ) -> MicroscopicExecutionStep:
        if step_type == "structure_prep":
            return MicroscopicExecutionStep(
                step_id="structure_prep",
                step_type="structure_prep",
                description=(
                    "Reuse a prepared 3D structure if available; otherwise generate a 3D structure from the input SMILES."
                ),
                input_source="available prepared structure artifacts or SMILES",
                expected_outputs=[
                    "prepared_structure.xyz",
                    "prepared_structure.sdf",
                    "structure_prep_summary.json",
                ],
            )
        if step_type == "conformer_bundle_generation":
            return MicroscopicExecutionStep(
                step_id="conformer_bundle_generation",
                step_type="conformer_bundle_generation",
                description=(
                    f"Generate a bounded conformer bundle and keep at most {self._config.amesp_follow_up_max_conformers} conformers "
                    "for low-cost Amesp follow-up."
                ),
                input_source="SMILES or reusable prepared structure context",
                expected_outputs=[
                    "bounded conformer bundle",
                    "per-conformer prepared geometry records",
                ],
            )
        if step_type == "torsion_snapshot_generation":
            return MicroscopicExecutionStep(
                step_id="torsion_snapshot_generation",
                step_type="torsion_snapshot_generation",
                description=(
                    f"Generate bounded torsion snapshots for at most {self._config.amesp_follow_up_max_torsion_snapshots_total} "
                    "snapshot geometries, without running a full scan or TS/IRC."
                ),
                input_source="prepared structure and detected rotatable dihedral candidates",
                expected_outputs=[
                    "snapshot geometry labels",
                    "bounded torsion snapshot structures",
                ],
            )
        if step_type == "artifact_parse":
            return MicroscopicExecutionStep(
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
        if step_type == "s0_optimization":
            return MicroscopicExecutionStep(
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
        if step_type == "s0_singlepoint":
            return MicroscopicExecutionStep(
                step_id="s0_singlepoint",
                step_type="s0_singlepoint",
                description="Run a bounded Amesp ground-state single-point evaluation on a prepared snapshot geometry.",
                input_source=structure_source,
                expected_outputs=["single-point energy", "dipole", "Mulliken charges", "HOMO-LUMO gap"],
            )
        return MicroscopicExecutionStep(
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
                f"nstates {self._config.amesp_s1_nstates}",
                f"tout {self._config.amesp_td_tout}",
            ],
            expected_outputs=["excited-state energies", "oscillator strengths"],
        )

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
        return unsupported

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

    def _resolve_capability_name(
        self,
        task_received: str,
        task_spec: MicroscopicTaskSpec,
    ) -> AmespCapabilityName:
        if task_spec.mode == "baseline_s0_s1":
            return "run_baseline_bundle"
        lower_instruction = task_received.lower()
        if (
            "parse_snapshot_outputs" in lower_instruction
            or (
                any(token in lower_instruction for token in ("reuse existing", "reuse round_", "existing artifacts", "parse-only", "do not run new calculations"))
                and any(token in lower_instruction for token in ("artifact", "output", "snapshot"))
            )
        ):
            return "parse_snapshot_outputs"
        if any(token in lower_instruction for token in ("relax", "relaxation", "excited-state geometry", "s1 optimization")):
            return "unsupported_excited_state_relaxation"
        if any(
            token in lower_instruction
            for token in ("torsion", "dihedral", "twist", "rotor", "rotation sensitivity", "rotational sensitivity")
        ):
            return "run_torsion_snapshots"
        return "run_conformer_bundle"

    def _requested_route_summary(
        self,
        capability_route: MicroscopicCapabilityRoute,
        task_received: str,
    ) -> str:
        if capability_route == "baseline_bundle":
            return "Use the default low-cost baseline bundle."
        if capability_route == "conformer_bundle_follow_up":
            return f"Interpret the request as a bounded conformer-sensitivity follow-up: {task_received}"
        if capability_route == "torsion_snapshot_follow_up":
            return f"Interpret the request as a bounded torsion-snapshot follow-up: {task_received}"
        if capability_route == "artifact_parse_only":
            return f"Interpret the request as parse-only microscopic artifact reuse without new calculations: {task_received}"
        return f"Interpret the request as excited-state relaxation follow-up: {task_received}"

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
        if code in {"subprocess_failed", "normal_termination_missing", "amesp_binary_missing"}:
            return "runtime_failed"
        return None
