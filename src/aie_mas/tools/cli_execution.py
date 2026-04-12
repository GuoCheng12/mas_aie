from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from aie_mas.config import AieMasConfig
from aie_mas.graph.state import (
    CliActionSpec,
    CliCommandDefinition,
    CliCommandId,
    CliCommandResult,
    MacroExecutionPlan,
    MicroscopicExecutionPlan,
    SharedStructureContext,
)


def _python_subprocess_env(project_root: Path) -> dict[str, str]:
    env = os.environ.copy()
    src_path = str(project_root / "src")
    existing = env.get("PYTHONPATH", "").strip()
    env["PYTHONPATH"] = src_path if not existing else f"{src_path}{os.pathsep}{existing}"
    return env


def _build_catalog() -> dict[CliCommandId, CliCommandDefinition]:
    macro_command_ids = [
        "macro.screen_donor_acceptor_layout",
        "macro.screen_rotor_torsion_topology",
        "macro.screen_planarity_compactness",
        "macro.screen_intramolecular_hbond_preorganization",
        "macro.screen_conformer_geometry_proxy",
        "macro.screen_neutral_aromatic_structure",
    ]
    microscopic_command_ids = [
        "microscopic.list_rotatable_dihedrals",
        "microscopic.list_available_conformers",
        "microscopic.list_artifact_bundles",
        "microscopic.list_artifact_bundle_members",
        "microscopic.run_baseline_bundle",
        "microscopic.run_conformer_bundle",
        "microscopic.run_torsion_snapshots",
        "microscopic.run_targeted_charge_analysis",
        "microscopic.run_targeted_localized_orbital_analysis",
        "microscopic.run_targeted_natural_orbital_analysis",
        "microscopic.run_targeted_density_population_analysis",
        "microscopic.run_targeted_transition_dipole_analysis",
        "microscopic.run_targeted_approx_delta_dipole_analysis",
        "microscopic.run_ris_state_characterization",
        "microscopic.run_targeted_state_characterization",
        "microscopic.parse_snapshot_outputs",
        "microscopic.extract_ct_descriptors_from_bundle",
        "microscopic.extract_geometry_descriptors_from_bundle",
        "microscopic.inspect_raw_artifact_bundle",
    ]
    catalog: dict[CliCommandId, CliCommandDefinition] = {}
    for command_id in macro_command_ids:
        catalog[command_id] = CliCommandDefinition(
            command_id=command_id,  # type: ignore[arg-type]
            agent_name="macro",
            command_program="python3",
            command_args=["-m", "aie_mas.cli.macro_exec"],
            perform_new_calculation=False,
        )
    for command_id in microscopic_command_ids:
        perform_new_calculation = command_id not in {
            "microscopic.list_rotatable_dihedrals",
            "microscopic.list_available_conformers",
            "microscopic.list_artifact_bundles",
            "microscopic.list_artifact_bundle_members",
            "microscopic.parse_snapshot_outputs",
            "microscopic.extract_ct_descriptors_from_bundle",
            "microscopic.extract_geometry_descriptors_from_bundle",
            "microscopic.inspect_raw_artifact_bundle",
        }
        catalog[command_id] = CliCommandDefinition(
            command_id=command_id,  # type: ignore[arg-type]
            agent_name="microscopic",
            command_program="python3",
            command_args=["-m", "aie_mas.cli.microscopic_exec"],
            perform_new_calculation=perform_new_calculation,
        )
    return catalog


CLI_COMMAND_CATALOG = _build_catalog()


def macro_command_id(capability_name: str) -> CliCommandId:
    return f"macro.{capability_name}"  # type: ignore[return-value]


def microscopic_command_id(capability_name: str) -> CliCommandId:
    return f"microscopic.{capability_name}"  # type: ignore[return-value]


def render_cli_command_catalog(agent_name: str | None = None) -> dict[str, Any]:
    entries = {
        command_id: definition.model_dump(mode="json")
        for command_id, definition in CLI_COMMAND_CATALOG.items()
        if agent_name is None or definition.agent_name == agent_name
    }
    return entries


class CliExecutionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        command_id: str,
        exit_code: int = 1,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        super().__init__(message)
        self.command_id = command_id
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr


def _truncate(text: str, limit: int = 600) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _stdin_payload_summary(payload: dict[str, Any]) -> dict[str, Any]:
    summary = dict(payload)
    if "shared_structure_context" in summary and isinstance(summary["shared_structure_context"], dict):
        shared = dict(summary["shared_structure_context"])
        if "prepared_xyz_path" in shared:
            shared["prepared_xyz_path"] = _truncate(str(shared["prepared_xyz_path"]), 160)
        if "prepared_sdf_path" in shared:
            shared["prepared_sdf_path"] = _truncate(str(shared["prepared_sdf_path"]), 160)
        summary["shared_structure_context"] = shared
    if "available_artifacts" in summary and isinstance(summary["available_artifacts"], dict):
        summary["available_artifacts"] = {
            "keys": sorted(summary["available_artifacts"].keys()),
        }
    return summary


def validate_cli_action(
    action: CliActionSpec,
    *,
    expected_agent_name: str,
) -> CliCommandDefinition:
    definition = CLI_COMMAND_CATALOG.get(action.command_id)
    if definition is None:
        raise CliExecutionError(
            f"Unsupported CLI command id `{action.command_id}`.",
            command_id=action.command_id,
        )
    if definition.agent_name != expected_agent_name:
        raise CliExecutionError(
            f"CLI command `{action.command_id}` does not belong to agent `{expected_agent_name}`.",
            command_id=action.command_id,
        )
    if action.command_program != definition.command_program or list(action.command_args) != list(definition.command_args):
        raise CliExecutionError(
            f"CLI action `{action.command_id}` does not match the catalog command template.",
            command_id=action.command_id,
        )
    return definition


def execute_cli_action(
    *,
    config: AieMasConfig,
    action: CliActionSpec,
    expected_agent_name: str,
    stdin_enrichment: dict[str, Any] | None = None,
) -> CliCommandResult:
    definition = validate_cli_action(action, expected_agent_name=expected_agent_name)
    final_stdin_payload = dict(action.stdin_payload)
    if stdin_enrichment:
        final_stdin_payload.update(stdin_enrichment)
    completed = subprocess.run(
        [definition.command_program, *definition.command_args],
        input=json.dumps(final_stdin_payload, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=str(config.project_root),
        env=_python_subprocess_env(config.project_root),
        timeout=max(config.macro_timeout_seconds, config.microscopic_timeout_seconds),
        check=False,
    )
    stdout_text = completed.stdout.strip()
    stderr_text = completed.stderr.strip()
    if completed.returncode != 0:
        raise CliExecutionError(
            f"{action.command_id} exited with code {completed.returncode}.",
            command_id=action.command_id,
            exit_code=completed.returncode,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    if not stdout_text:
        raise CliExecutionError(
            f"{action.command_id} returned no JSON payload.",
            command_id=action.command_id,
            exit_code=completed.returncode,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    try:
        parsed = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        raise CliExecutionError(
            f"{action.command_id} returned invalid JSON.",
            command_id=action.command_id,
            exit_code=completed.returncode,
            stdout=stdout_text,
            stderr=stderr_text,
        ) from exc
    if not isinstance(parsed, dict):
        raise CliExecutionError(
            f"{action.command_id} returned a non-object JSON payload.",
            command_id=action.command_id,
            exit_code=completed.returncode,
            stdout=stdout_text,
            stderr=stderr_text,
        )
    return CliCommandResult(
        command_id=action.command_id,
        command_program=definition.command_program,
        command_args=list(definition.command_args),
        stdin_payload_summary=_stdin_payload_summary(final_stdin_payload),
        cli_exit_code=completed.returncode,
        cli_stdout_excerpt=_truncate(stdout_text),
        cli_stderr_excerpt=_truncate(stderr_text),
        parsed_json=parsed,
    )


class MacroCliExecutionTool:
    def __init__(self, config: AieMasConfig) -> None:
        self._config = config

    def execute(
        self,
        *,
        plan: MacroExecutionPlan,
        smiles: str,
        shared_structure_context: SharedStructureContext | None = None,
    ) -> dict[str, Any]:
        action = CliActionSpec(
            command_id=macro_command_id(plan.selected_capability or "screen_planarity_compactness"),
            command_program="python3",
            command_args=["-m", "aie_mas.cli.macro_exec"],
            stdin_payload={
                "selected_capability": plan.selected_capability,
                "requested_deliverables": list(plan.requested_deliverables),
                "requested_observable_tags": list(plan.requested_observable_tags),
                "binding_mode": plan.binding_mode,
                "smiles": smiles,
                "shared_structure_context": (
                    shared_structure_context.model_dump(mode="json")
                    if shared_structure_context is not None
                    else None
                ),
            },
            expected_outputs=list(plan.expected_outputs),
            perform_new_calculation=False,
            reused_existing_artifacts=shared_structure_context is not None,
            resolved_target_ids=dict(plan.resolved_target_ids),
            binding_mode=plan.binding_mode,
            requested_observable_tags=list(plan.requested_observable_tags),
        )
        result = execute_cli_action(
            config=self._config,
            action=action,
            expected_agent_name="macro",
        )
        return dict(result.parsed_json)


class MicroscopicCliExecutionTool:
    def __init__(self, config: AieMasConfig) -> None:
        self._config = config

    def execute(
        self,
        *,
        plan: MicroscopicExecutionPlan,
        smiles: str,
        label: str,
        workdir: Path,
        available_artifacts: dict[str, Any] | None = None,
        round_index: int = 1,
        case_id: str | None = None,
        current_hypothesis: str | None = None,
    ) -> Any:
        action = CliActionSpec(
            command_id=microscopic_command_id(plan.microscopic_tool_request.capability_name),  # type: ignore[arg-type]
            command_program="python3",
            command_args=["-m", "aie_mas.cli.microscopic_exec"],
            stdin_payload={
                "tool_config": {
                    "amesp_bin": str(self._config.amesp_binary_path) if self._config.amesp_binary_path else None,
                    "npara": self._config.amesp_npara,
                    "maxcore_mb": self._config.amesp_maxcore_mb,
                    "use_ricosx": self._config.amesp_use_ricosx,
                    "s1_nstates": self._config.amesp_s1_nstates,
                    "td_tout": self._config.amesp_td_tout,
                    "follow_up_max_conformers": self._config.amesp_follow_up_max_conformers,
                    "follow_up_max_torsion_snapshots_total": self._config.amesp_follow_up_max_torsion_snapshots_total,
                    "probe_interval_seconds": self._config.amesp_probe_interval_seconds,
                },
                "plan": plan.model_dump(mode="json"),
                "smiles": smiles,
                "label": label,
                "workdir": str(workdir),
                "available_artifacts": available_artifacts or {},
                "round_index": round_index,
                "case_id": case_id,
                "current_hypothesis": current_hypothesis,
            },
            expected_outputs=list(plan.expected_outputs),
            perform_new_calculation=bool(plan.microscopic_tool_request.perform_new_calculation),
            reused_existing_artifacts=bool(plan.microscopic_tool_request.reuse_existing_artifacts_only),
            binding_mode=plan.binding_mode,
            requested_observable_tags=list(plan.requested_observable_tags),
        )
        result = execute_cli_action(
            config=self._config,
            action=action,
            expected_agent_name="microscopic",
        )
        from aie_mas.tools.amesp import AmespBaselineRunResult

        return AmespBaselineRunResult.model_validate(result.parsed_json)
