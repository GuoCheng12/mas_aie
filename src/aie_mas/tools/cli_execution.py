from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

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
    supports_required_stdin_keys = "required_stdin_keys" in CliCommandDefinition.model_fields
    supports_required_payload_keys = "required_payload_keys" in CliCommandDefinition.model_fields
    supports_required_input_keys = "required_input_keys" in CliCommandDefinition.model_fields

    def _build_definition(
        *,
        command_id: CliCommandId,
        agent_name: str,
        command_program: str,
        command_args: list[str],
        perform_new_calculation: bool,
        required_stdin_keys: list[str],
    ) -> CliCommandDefinition:
        kwargs: dict[str, Any] = {
            "command_id": command_id,
            "agent_name": agent_name,
            "command_program": command_program,
            "command_args": command_args,
            "perform_new_calculation": perform_new_calculation,
        }
        # Keep compatibility with schema variants across branches.
        if supports_required_stdin_keys:
            kwargs["required_stdin_keys"] = required_stdin_keys
        elif supports_required_payload_keys:
            kwargs["required_payload_keys"] = required_stdin_keys
        elif supports_required_input_keys:
            kwargs["required_input_keys"] = required_stdin_keys
        return CliCommandDefinition(**kwargs)

    for command_id in macro_command_ids:
        catalog[command_id] = _build_definition(
            command_id=command_id,  # type: ignore[arg-type]
            agent_name="macro",
            command_program="python3",
            command_args=["-m", "aie_mas.macro_harness.cli", "execute-payload"],
            perform_new_calculation=False,
            required_stdin_keys=[
                "selected_capability",
                "requested_deliverables",
                "requested_observable_tags",
                "binding_mode",
                "smiles",
            ],
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
        catalog[command_id] = _build_definition(
            command_id=command_id,  # type: ignore[arg-type]
            agent_name="microscopic",
            command_program="python3",
            command_args=["-m", "aie_mas.cli.microscopic_exec"],
            perform_new_calculation=perform_new_calculation,
            required_stdin_keys=[],
        )
    return catalog


CLI_COMMAND_CATALOG = _build_catalog()


def _required_stdin_keys_for_definition(definition: CliCommandDefinition) -> list[str]:
    for attr_name in ("required_stdin_keys", "required_payload_keys", "required_input_keys"):
        attr_value = getattr(definition, attr_name, None)
        if isinstance(attr_value, list):
            return [str(item) for item in attr_value]

    model_dump = definition.model_dump(mode="python")
    for field_name in ("required_stdin_keys", "required_payload_keys", "required_input_keys"):
        field_value = model_dump.get(field_name)
        if isinstance(field_value, list):
            return [str(item) for item in field_value]

    # Last-resort compatibility fallback by command namespace.
    if str(definition.command_id).startswith("macro."):
        return [
            "selected_capability",
            "requested_deliverables",
            "requested_observable_tags",
            "binding_mode",
            "smiles",
        ]
    return []


def macro_command_id(capability_name: str) -> CliCommandId:
    return f"macro.{capability_name}"  # type: ignore[return-value]


def microscopic_command_id(capability_name: str) -> CliCommandId:
    return f"microscopic.{capability_name}"  # type: ignore[return-value]


def microscopic_capability_name(command_id: str) -> str | None:
    prefix = "microscopic."
    if not isinstance(command_id, str) or not command_id.startswith(prefix):
        return None
    capability_name = command_id[len(prefix) :].strip()
    return capability_name or None


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


CliRuntimeProbeCallback = Callable[[str, dict[str, Any]], None]


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
    if definition.agent_name == "microscopic":
        if "plan" not in action.stdin_payload and "microscopic_tool_request" not in action.stdin_payload:
            raise CliExecutionError(
                f"CLI action `{action.command_id}` must provide either `plan` or `microscopic_tool_request` in stdin payload.",
                command_id=action.command_id,
            )
    required_stdin_keys = _required_stdin_keys_for_definition(definition)
    missing_keys = [key for key in required_stdin_keys if key not in action.stdin_payload]
    if missing_keys:
        raise CliExecutionError(
            f"CLI action `{action.command_id}` is missing required stdin payload keys: {', '.join(missing_keys)}.",
            command_id=action.command_id,
        )
    return definition


def _resolve_cli_timeout_seconds(
    *,
    config: AieMasConfig,
    expected_agent_name: str,
) -> float | None:
    # Microscopic CLI execution can be long-running (Amesp). Run-to-completion by default.
    if expected_agent_name == "microscopic":
        return None
    timeout_value = config.macro_timeout_seconds
    if timeout_value is None:
        return None
    timeout_seconds = float(timeout_value)
    if timeout_seconds <= 0:
        return None
    return timeout_seconds


def _probe_interval_seconds(
    *,
    config: AieMasConfig,
    stdin_payload: dict[str, Any],
) -> float:
    tool_config = stdin_payload.get("tool_config")
    if isinstance(tool_config, dict):
        candidate = tool_config.get("probe_interval_seconds")
        if isinstance(candidate, (int, float)) and float(candidate) > 0:
            return float(candidate)
    return max(1.0, float(config.amesp_probe_interval_seconds))


def _tracked_runtime_file_stats(
    *,
    stdin_payload: dict[str, Any],
    max_recent_files: int = 6,
    max_scan_files: int = 2000,
) -> dict[str, Any]:
    workdir_raw = stdin_payload.get("workdir")
    if not isinstance(workdir_raw, str) or not workdir_raw.strip():
        return {}
    workdir = Path(workdir_raw)
    if not workdir.exists():
        return {"workdir": str(workdir), "workdir_exists": False}

    label = str(stdin_payload.get("label") or "").strip()
    details: dict[str, Any] = {
        "workdir": str(workdir),
        "workdir_exists": True,
    }

    if label:
        stdout_log_path = workdir / f"{label}.stdout.log"
        stderr_log_path = workdir / f"{label}.stderr.log"
        details["stdout_log_exists"] = stdout_log_path.exists()
        details["stderr_log_exists"] = stderr_log_path.exists()
        details["stdout_log_bytes"] = stdout_log_path.stat().st_size if stdout_log_path.exists() else 0
        details["stderr_log_bytes"] = stderr_log_path.stat().st_size if stderr_log_path.exists() else 0

    scanned = 0
    file_records: list[tuple[float, Path, int]] = []
    for path in workdir.rglob("*"):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
        except OSError:
            continue
        scanned += 1
        file_records.append((stat.st_mtime, path, stat.st_size))
        if scanned >= max_scan_files:
            break
    file_records.sort(key=lambda item: item[0], reverse=True)
    details["tracked_file_count"] = len(file_records)

    recent_files: list[dict[str, Any]] = []
    for _, file_path, size_bytes in file_records[:max_recent_files]:
        try:
            relative_path = str(file_path.relative_to(workdir))
        except ValueError:
            relative_path = str(file_path)
        recent_files.append(
            {
                "path": relative_path,
                "size_bytes": int(size_bytes),
            }
        )
    details["recent_files"] = recent_files
    return details


def _run_with_runtime_probe(
    *,
    command_id: str,
    command: list[str],
    config: AieMasConfig,
    stdin_payload: dict[str, Any],
    timeout_seconds: float | None,
    runtime_probe: CliRuntimeProbeCallback | None,
) -> subprocess.CompletedProcess[str]:
    input_text = json.dumps(stdin_payload, ensure_ascii=False)
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=str(config.project_root),
        env=_python_subprocess_env(config.project_root),
    )
    if process.stdin is not None:
        try:
            process.stdin.write(input_text)
            process.stdin.flush()
        except BrokenPipeError:
            pass
        finally:
            process.stdin.close()
            # Avoid communicate() trying to flush a closed handle.
            process.stdin = None

    probe_interval = _probe_interval_seconds(config=config, stdin_payload=stdin_payload)
    start_time = time.perf_counter()
    next_probe_at = start_time
    seen_file_sizes: dict[str, int] = {}

    if runtime_probe is not None:
        runtime_probe(
            "start",
            {
                "pid": process.pid,
                "timeout_seconds": timeout_seconds,
                **_tracked_runtime_file_stats(stdin_payload=stdin_payload),
            },
        )

    while True:
        return_code = process.poll()
        now = time.perf_counter()
        elapsed = now - start_time

        if return_code is not None:
            stdout_text, stderr_text = process.communicate()
            if runtime_probe is not None:
                runtime_probe(
                    "end",
                    {
                        "pid": process.pid,
                        "elapsed_seconds": round(elapsed, 2),
                        "return_code": int(return_code),
                        **_tracked_runtime_file_stats(stdin_payload=stdin_payload),
                    },
                )
            return subprocess.CompletedProcess(command, int(return_code), stdout=stdout_text, stderr=stderr_text)

        if timeout_seconds is not None and elapsed >= timeout_seconds:
            process.kill()
            stdout_text, stderr_text = process.communicate()
            raise CliExecutionError(
                f"{command!r} timed out after {timeout_seconds:.1f} seconds.",
                command_id=command_id,
                exit_code=124,
                stdout=(stdout_text or "").strip(),
                stderr=(stderr_text or "").strip(),
            )

        if runtime_probe is not None and now >= next_probe_at:
            runtime_details = _tracked_runtime_file_stats(stdin_payload=stdin_payload)
            recent_files = list(runtime_details.get("recent_files") or [])
            new_files: list[str] = []
            growing_files: list[str] = []
            for entry in recent_files:
                if not isinstance(entry, dict):
                    continue
                path_value = str(entry.get("path") or "")
                if not path_value:
                    continue
                size_value = int(entry.get("size_bytes") or 0)
                previous_size = seen_file_sizes.get(path_value)
                if previous_size is None:
                    new_files.append(path_value)
                elif size_value > previous_size:
                    growing_files.append(path_value)
                seen_file_sizes[path_value] = size_value
            runtime_probe(
                "running",
                {
                    "pid": process.pid,
                    "elapsed_seconds": round(elapsed, 2),
                    "new_file_count": len(new_files),
                    "growing_file_count": len(growing_files),
                    "new_files": new_files[:6],
                    "growing_files": growing_files[:6],
                    **runtime_details,
                },
            )
            next_probe_at = now + probe_interval
        time.sleep(0.5)


def execute_cli_action(
    *,
    config: AieMasConfig,
    action: CliActionSpec,
    expected_agent_name: str,
    stdin_enrichment: dict[str, Any] | None = None,
    runtime_probe: CliRuntimeProbeCallback | None = None,
) -> CliCommandResult:
    definition = validate_cli_action(action, expected_agent_name=expected_agent_name)
    final_stdin_payload = dict(action.stdin_payload)
    if stdin_enrichment:
        final_stdin_payload.update(stdin_enrichment)
    command = [definition.command_program, *definition.command_args]
    timeout_seconds = _resolve_cli_timeout_seconds(
        config=config,
        expected_agent_name=expected_agent_name,
    )
    if runtime_probe is None:
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(final_stdin_payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                cwd=str(config.project_root),
                env=_python_subprocess_env(config.project_root),
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise CliExecutionError(
                f"{action.command_id} timed out after {exc.timeout} seconds.",
                command_id=action.command_id,
                exit_code=124,
                stdout=(exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
                stderr=(exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            ) from exc
    else:
        completed = _run_with_runtime_probe(
            command_id=action.command_id,
            command=command,
            config=config,
            stdin_payload=final_stdin_payload,
            timeout_seconds=timeout_seconds,
            runtime_probe=runtime_probe,
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
            command_args=["-m", "aie_mas.macro_harness.cli", "execute-payload"],
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
                "microscopic_tool_request": plan.microscopic_tool_request.model_dump(mode="json"),
                "local_goal": plan.local_goal,
                "requested_deliverables": list(plan.requested_deliverables),
                "requested_route_summary": plan.requested_route_summary,
                "failure_reporting": plan.failure_reporting,
                "unsupported_requests": list(plan.unsupported_requests),
                "structure_source": plan.structure_source,
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
            stdin_enrichment={
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
                "smiles": smiles,
                "label": label,
                "workdir": str(workdir),
                "available_artifacts": available_artifacts or {},
                "round_index": round_index,
                "case_id": case_id,
                "current_hypothesis": current_hypothesis,
            },
        )
        from aie_mas.tools.amesp import AmespBaselineRunResult

        return AmespBaselineRunResult.model_validate(result.parsed_json)
