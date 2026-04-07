#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aie_mas.config import AieMasConfig
from aie_mas.graph.state import MicroscopicExecutionPlan, MicroscopicToolRequest, WorkflowProgressEvent
from aie_mas.tools.amesp import AMESP_ACTION_REGISTRY, AmespExecutionError
from aie_mas.tools.factory import build_toolset

DEFAULT_CAPABILITY_SEQUENCE = [
    "run_baseline_bundle",
    "extract_ct_descriptors_from_bundle",
    "run_targeted_state_characterization",
    "run_targeted_charge_analysis",
    "run_targeted_density_population_analysis",
    "run_targeted_transition_dipole_analysis",
    "run_ris_state_characterization",
    "run_targeted_localized_orbital_analysis",
    "run_targeted_natural_orbital_analysis",
]

CAPABILITY_ALIASES = {
    "baseline": "run_baseline_bundle",
    "ct_extract": "extract_ct_descriptors_from_bundle",
    "state_characterization": "run_targeted_state_characterization",
    "charge": "run_targeted_charge_analysis",
    "density_population": "run_targeted_density_population_analysis",
    "transition_dipole": "run_targeted_transition_dipole_analysis",
    "ris": "run_ris_state_characterization",
    "localized_orbital": "run_targeted_localized_orbital_analysis",
    "natural_orbital": "run_targeted_natural_orbital_analysis",
    "inspect": "inspect_raw_artifact_bundle",
}

BASELINE_DEPENDENT_CAPABILITIES = {
    "extract_ct_descriptors_from_bundle",
    "run_targeted_state_characterization",
    "run_targeted_charge_analysis",
    "run_targeted_density_population_analysis",
    "run_targeted_transition_dipole_analysis",
    "run_ris_state_characterization",
    "run_targeted_localized_orbital_analysis",
    "run_targeted_natural_orbital_analysis",
    "inspect_raw_artifact_bundle",
}


def render_progress_event(event: WorkflowProgressEvent) -> None:
    round_label = "setup" if event["round"] == 0 else str(event["round"])
    parts = [
        "progress",
        f"phase={event['phase']}",
        f"round={round_label}",
        f"agent={event['agent']}",
        f"node={event['node']}",
    ]
    if event.get("case_id"):
        parts.append(f"case_id={event['case_id']}")
    if event["phase"] == "probe":
        probe_stage = event["details"].get("probe_stage")
        probe_status = event["details"].get("probe_status")
        if probe_stage:
            parts.append(f"stage={probe_stage}")
        if probe_status:
            parts.append(f"status={probe_status}")
        if probe_status == "running":
            if event["details"].get("elapsed_seconds") is not None:
                parts.append(f"elapsed={event['details']['elapsed_seconds']}s")
            if event["details"].get("aop_size_bytes") is not None:
                parts.append(f"aop_bytes={event['details']['aop_size_bytes']}")
            if event["details"].get("pid") is not None:
                parts.append(f"pid={event['details']['pid']}")
    print(" ".join(parts), file=sys.stderr)


def compose_progress_callbacks(
    *callbacks: Optional[Callable[[WorkflowProgressEvent], None]],
) -> Optional[Callable[[WorkflowProgressEvent], None]]:
    active_callbacks = [callback for callback in callbacks if callback is not None]
    if not active_callbacks:
        return None

    def _composed(event: WorkflowProgressEvent) -> None:
        for callback in active_callbacks:
            callback(event)

    return _composed


class ProbeLiveTracer:
    def __init__(
        self,
        *,
        report_dir: Path,
        case_id: str,
        smiles: str,
        user_query: str,
    ) -> None:
        self._report_dir = report_dir
        self._case_id = case_id
        self._smiles = smiles
        self._user_query = user_query
        self._events: list[dict[str, object]] = []
        self._live_trace_path = report_dir / "live_trace.jsonl"
        self._live_status_path = report_dir / "live_status.md"
        self._write_status_file()

    def handle_event(self, event: WorkflowProgressEvent) -> None:
        serializable_event = _serializable_event(event)
        self._events.append(serializable_event)
        self._live_trace_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in self._events),
            encoding="utf-8",
        )
        self._write_status_file()

    def _write_status_file(self) -> None:
        lines = [
            "# Microscopic Capability Probe",
            "",
            f"- case_id: {self._case_id}",
            f"- smiles: {self._smiles}",
            f"- user_query: {self._user_query}",
            f"- report_dir: {self._report_dir}",
            f"- events_recorded: {len(self._events)}",
            "",
            "## Current Position",
        ]
        current_event = self._events[-1] if self._events else None
        if current_event is None:
            lines.append("- status: initialized")
        else:
            lines.extend(
                [
                    f"- phase: {current_event['phase']}",
                    f"- round: {current_event['round']}",
                    f"- agent: {current_event['agent']}",
                    f"- node: {current_event['node']}",
                    f"- current_hypothesis: {current_event.get('current_hypothesis')}",
                ]
            )

        probe_events = [event for event in self._events if event["phase"] == "probe"]
        lines.extend(["", "## Probe Trace"])
        if not probe_events:
            lines.append("")
            lines.append("No microscopic probe events have been recorded yet.")
        else:
            for event in probe_events[-40:]:
                round_label = "setup" if event["round"] == 0 else str(event["round"])
                details = event.get("details") or {}
                stage = details.get("probe_stage", "unknown")
                status = details.get("probe_status", "unknown")
                lines.extend(["", f"- round={round_label} stage={stage} status={status}"])
                for key, value in details.items():
                    if key in {"probe_stage", "probe_status"}:
                        continue
                    rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                    lines.append(f"  {key}: {rendered}")

        end_events = [event for event in self._events if event["phase"] == "end"]
        lines.extend(["", "## Probe Results"])
        if not end_events:
            lines.append("")
            lines.append("No completed probe result has been recorded yet.")
        else:
            for event in end_events:
                round_label = "setup" if event["round"] == 0 else str(event["round"])
                lines.extend(["", f"### Round {round_label} | {event['agent']} | {event['node']}"])
                details = event.get("details") or {}
                if not details:
                    lines.append("")
                    lines.append("No structured details were recorded for this probe.")
                    continue
                for key, value in details.items():
                    rendered = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                    lines.extend(["", f"- {key}: {rendered}"])

        self._live_status_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_capabilities(raw_value: str) -> list[str]:
    if raw_value.strip().lower() == "all":
        return list(DEFAULT_CAPABILITY_SEQUENCE)
    capabilities: list[str] = []
    for item in raw_value.split(","):
        key = item.strip()
        if not key:
            continue
        resolved = CAPABILITY_ALIASES.get(key, key)
        if resolved not in AMESP_ACTION_REGISTRY:
            allowed = ", ".join(sorted(set(DEFAULT_CAPABILITY_SEQUENCE + list(CAPABILITY_ALIASES.keys()))))
            raise SystemExit(f"Unsupported capability '{key}'. Allowed values: {allowed}")
        capabilities.append(resolved)
    if not capabilities:
        raise SystemExit("At least one capability must be requested.")
    return capabilities


def _parse_state_window(raw_value: str) -> list[int]:
    values: list[int] = []
    for item in raw_value.split(","):
        stripped = item.strip()
        if not stripped:
            continue
        values.append(int(stripped))
    if not values:
        raise SystemExit("state_window must include at least one integer, for example '1,2'.")
    return values


def _default_deliverables(capability_name: str) -> list[str]:
    action = AMESP_ACTION_REGISTRY.get(capability_name)
    if action and action.default_deliverables:
        return list(action.default_deliverables)
    return [f"Probe deliverables for {capability_name}"]


def _default_route_for_capability(capability_name: str) -> str:
    if capability_name == "run_baseline_bundle":
        return "baseline_bundle"
    if capability_name in {"extract_ct_descriptors_from_bundle", "inspect_raw_artifact_bundle"}:
        return "artifact_parse_only"
    return "targeted_property_follow_up"


def _build_request(
    *,
    capability_name: str,
    baseline_bundle_id: Optional[str],
    baseline_source_round: Optional[int],
    state_window: list[int],
) -> MicroscopicToolRequest:
    deliverables = _default_deliverables(capability_name)
    if capability_name == "run_baseline_bundle":
        return MicroscopicToolRequest(
            capability_name=capability_name,
            perform_new_calculation=True,
            optimize_ground_state=True,
            state_window=state_window,
            deliverables=deliverables,
            requested_route_summary=(
                "Probe the default baseline bundle route: S0 optimization plus bounded vertical excited-state "
                "manifold on the shared prepared structure."
            ),
        )

    if baseline_bundle_id is None or baseline_source_round is None:
        raise ValueError(f"Capability '{capability_name}' requires a reusable baseline bundle, but none is available.")

    if capability_name == "extract_ct_descriptors_from_bundle":
        return MicroscopicToolRequest(
            capability_name=capability_name,
            perform_new_calculation=False,
            reuse_existing_artifacts_only=True,
            artifact_bundle_id=baseline_bundle_id,
            artifact_source_round=baseline_source_round,
            artifact_scope="baseline_bundle",
            artifact_kind="baseline_bundle",
            state_window=state_window,
            descriptor_scope=[
                "hole-electron-centroid-separation",
                "hole-electron-overlap",
                "qCT/charge_transferred",
                "ct_overlap_index",
                "mulliken_charges_summary",
            ],
            deliverables=deliverables,
            requested_route_summary=(
                f"Probe parse-only CT extraction on artifact bundle '{baseline_bundle_id}' for state_window={state_window}."
            ),
        )

    if capability_name == "inspect_raw_artifact_bundle":
        return MicroscopicToolRequest(
            capability_name=capability_name,
            perform_new_calculation=False,
            reuse_existing_artifacts_only=True,
            artifact_bundle_id=baseline_bundle_id,
            artifact_source_round=baseline_source_round,
            artifact_scope="baseline_bundle",
            artifact_kind="baseline_bundle",
            state_window=state_window,
            deliverables=deliverables,
            requested_route_summary=(
                f"Probe raw-artifact inspection on artifact bundle '{baseline_bundle_id}' for baseline files."
            ),
        )

    request = MicroscopicToolRequest(
        capability_name=capability_name,
        perform_new_calculation=True,
        optimize_ground_state=False,
        artifact_bundle_id=baseline_bundle_id,
        artifact_source_round=baseline_source_round,
        artifact_scope="baseline_bundle",
        artifact_kind="baseline_bundle",
        target_count=1,
        state_window=state_window,
        deliverables=deliverables,
        requested_route_summary=(
            f"Probe capability '{capability_name}' on reusable baseline artifact bundle '{baseline_bundle_id}' "
            f"with fixed-geometry follow-up for state_window={state_window}."
        ),
    )
    if capability_name == "run_targeted_state_characterization":
        request.descriptor_scope = [
            "dominant_transitions",
            "natural_transition_orbitals",
            "attachment_detachment",
            "hole_particle_analysis",
            "hole_electron_separation",
            "hole_electron_overlap",
            "qct",
            "state_family_overlap",
        ]
    return request


def _build_plan(
    *,
    capability_name: str,
    baseline_bundle_id: Optional[str],
    baseline_source_round: Optional[int],
    state_window: list[int],
) -> MicroscopicExecutionPlan:
    request = _build_request(
        capability_name=capability_name,
        baseline_bundle_id=baseline_bundle_id,
        baseline_source_round=baseline_source_round,
        state_window=state_window,
    )
    return MicroscopicExecutionPlan(
        local_goal=f"Probe microscopic capability '{capability_name}' directly without Planner mediation.",
        requested_deliverables=list(request.deliverables),
        capability_route=_default_route_for_capability(capability_name),
        microscopic_tool_request=request,
        structure_source="prepared_from_smiles" if capability_name == "run_baseline_bundle" else "existing_prepared_structure",
        expected_outputs=list(request.deliverables),
        requested_route_summary=request.requested_route_summary,
        failure_reporting="If the probe fails, capture the Amesp error payload, raw stdout/stderr, and generated artifacts.",
    )


def _serializable_event(event: WorkflowProgressEvent) -> dict[str, Any]:
    return {
        "phase": event["phase"],
        "round": event["round"],
        "node": event["node"],
        "agent": event["agent"],
        "case_id": event.get("case_id"),
        "current_hypothesis": event.get("current_hypothesis"),
        "details": event.get("details", {}),
    }


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _probe_result_excerpt(payload: dict[str, Any]) -> dict[str, Any]:
    excerpt = {
        "capability_name": payload["capability_name"],
        "status": payload["status"],
        "result_file": payload["result_file"],
    }
    if payload.get("result_summary"):
        excerpt["result_summary"] = payload["result_summary"]
    if payload.get("route_summary") is not None:
        excerpt["route_summary"] = payload["route_summary"]
    if payload.get("error") is not None:
        error = dict(payload["error"])
        raw_results = dict(error.get("raw_results") or {})
        excerpt["error"] = {
            "code": error.get("code"),
            "message": error.get("message"),
            "stdout": raw_results.get("stdout"),
            "stderr": raw_results.get("stderr"),
        }
    return excerpt


def _append_baseline_registry_entry(
    available_artifacts: dict[str, Any],
    generated_artifacts: dict[str, Any],
) -> None:
    registry_entries = list(generated_artifacts.get("artifact_bundle_registry_entries") or [])
    if not registry_entries:
        return
    stored_entries = list(available_artifacts.get("artifact_bundle_registry_entries") or [])
    stored_entries.extend(registry_entries)
    available_artifacts["artifact_bundle_registry_entries"] = stored_entries


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe registry-backed microscopic capabilities directly, without Planner/LLM reasoning. "
            "The script will optionally generate a baseline bundle first and then run bounded follow-up probes."
        )
    )
    parser.add_argument("--smiles", required=True, help="Input SMILES to probe.")
    parser.add_argument(
        "--capabilities",
        default="all",
        help=(
            "Comma-separated capability names or aliases. "
            "Use 'all' for the default baseline-bound probe suite."
        ),
    )
    parser.add_argument(
        "--state-window",
        default="1,2",
        help="Comma-separated excited-state indices, for example '1,2' or '1,2,3'.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional explicit probe output directory. Defaults to debug_reports/<timestamp>_<case_id>.",
    )
    parser.add_argument(
        "--execution-profile",
        default="linux-prod",
        choices=["local-dev", "linux-prod"],
        help="Runtime execution profile used to build AieMasConfig.",
    )
    parser.add_argument("--amesp-npara", type=int, default=None)
    parser.add_argument("--amesp-maxcore-mb", type=int, default=None)
    parser.add_argument("--amesp-s1-nstates", type=int, default=None)
    parser.add_argument("--amesp-td-tout", type=int, default=None)
    parser.add_argument("--amesp-probe-interval-seconds", type=float, default=None)
    parser.add_argument(
        "--reuse-baseline-bundle-id",
        default=None,
        help="Reuse an existing baseline bundle ID instead of auto-running run_baseline_bundle first.",
    )
    parser.add_argument(
        "--reuse-baseline-source-round",
        type=int,
        default=None,
        help="Source round for --reuse-baseline-bundle-id. Required when reusing an existing baseline bundle.",
    )
    parser.add_argument(
        "--stop-on-failure",
        action="store_true",
        help="Stop the probe suite after the first failed capability.",
    )
    args = parser.parse_args(argv)

    capabilities = _parse_capabilities(args.capabilities)
    state_window = _parse_state_window(args.state_window)

    if args.reuse_baseline_bundle_id and args.reuse_baseline_source_round is None:
        raise SystemExit("--reuse-baseline-source-round is required when --reuse-baseline-bundle-id is provided.")

    if not args.reuse_baseline_bundle_id and any(
        capability in BASELINE_DEPENDENT_CAPABILITIES for capability in capabilities
    ):
        if "run_baseline_bundle" not in capabilities:
            capabilities = ["run_baseline_bundle", *capabilities]

    config = AieMasConfig.from_env(
        execution_profile=args.execution_profile,
        amesp_npara=args.amesp_npara,
        amesp_maxcore_mb=args.amesp_maxcore_mb,
        amesp_s1_nstates=args.amesp_s1_nstates,
        amesp_td_tout=args.amesp_td_tout,
        amesp_probe_interval_seconds=args.amesp_probe_interval_seconds,
    )
    config.ensure_runtime_dirs()

    project_root = config.project_root
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    case_id = uuid.uuid4().hex[:12]
    report_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else (project_root / "debug_reports" / f"{timestamp}_{case_id}")
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    probe_results_dir = report_dir / "probes"
    probe_results_dir.mkdir(parents=True, exist_ok=True)

    user_query = "Probe registry-backed microscopic capabilities directly."
    tracer = ProbeLiveTracer(report_dir=report_dir, case_id=case_id, smiles=args.smiles, user_query=user_query)
    combined_progress = compose_progress_callbacks(render_progress_event, tracer.handle_event)

    def _emit_probe_summary(round_index: int, capability_name: str, payload: dict[str, Any]) -> None:
        if combined_progress is None:
            return
        combined_progress(
            WorkflowProgressEvent(
                phase="end",
                round=round_index,
                node=f"probe_{capability_name}",
                agent="microscopic",
                case_id=case_id,
                current_hypothesis=None,
                details=_probe_result_excerpt(payload),
            )
        )

    toolset = build_toolset(config)
    tool = toolset.amesp_micro_tool
    available_artifacts: dict[str, Any] = {}
    baseline_bundle_id = args.reuse_baseline_bundle_id
    baseline_source_round = args.reuse_baseline_source_round
    suite_results: list[dict[str, Any]] = []
    suite_failed = False

    manifest = {
        "case_id": case_id,
        "smiles": args.smiles,
        "capabilities_requested": capabilities,
        "state_window": state_window,
        "report_dir": str(report_dir),
        "runtime_context": config.runtime_context(),
        "reuse_baseline_bundle_id": baseline_bundle_id,
        "reuse_baseline_source_round": baseline_source_round,
    }
    _write_json(report_dir / "manifest.json", manifest)

    for round_index, capability_name in enumerate(capabilities, start=1):
        if capability_name in BASELINE_DEPENDENT_CAPABILITIES and baseline_bundle_id is None:
            failure_payload = {
                "round_index": round_index,
                "capability_name": capability_name,
                "status": "failed",
                "result_file": str(probe_results_dir / f"round_{round_index:02d}_{capability_name}.json"),
                "error": {
                    "code": "precondition_missing",
                    "message": "No reusable baseline bundle is available for this baseline-dependent capability.",
                    "generated_artifacts": {},
                    "raw_results": {},
                    "structured_results": {},
                    "status": "failed",
                },
            }
            _write_json(Path(failure_payload["result_file"]), failure_payload)
            suite_results.append(failure_payload)
            _emit_probe_summary(round_index, capability_name, failure_payload)
            suite_failed = True
            if args.stop_on_failure:
                break
            continue

        plan = _build_plan(
            capability_name=capability_name,
            baseline_bundle_id=baseline_bundle_id,
            baseline_source_round=baseline_source_round,
            state_window=state_window,
        )
        probe_events: list[dict[str, Any]] = []

        def _probe_progress(event: WorkflowProgressEvent) -> None:
            probe_events.append(_serializable_event(event))
            if combined_progress is not None:
                combined_progress(event)

        result_file = probe_results_dir / f"round_{round_index:02d}_{capability_name}.json"
        payload: dict[str, Any]
        try:
            result = tool.execute(
                plan=plan,
                smiles=args.smiles,
                label=f"{case_id}_probe_r{round_index:02d}",
                workdir=report_dir / "work" / f"round_{round_index:02d}_{capability_name}",
                available_artifacts=available_artifacts,
                progress_callback=_probe_progress,
                round_index=round_index,
                case_id=case_id,
                current_hypothesis="probe",
            )
            payload = {
                "round_index": round_index,
                "capability_name": capability_name,
                "status": "success",
                "plan": plan.model_dump(mode="json"),
                "probe_events": probe_events,
                "result_summary": {
                    "route": result.route,
                    "executed_capability": result.executed_capability,
                    "requested_capability": result.requested_capability,
                    "performed_new_calculations": result.performed_new_calculations,
                    "reused_existing_artifacts": result.reused_existing_artifacts,
                    "resolved_target_ids": result.resolved_target_ids,
                    "missing_deliverables": result.missing_deliverables,
                },
                "route_summary": result.route_summary,
                "generated_artifacts": result.generated_artifacts,
                "result": result.model_dump(mode="json"),
                "result_file": str(result_file),
            }
            if capability_name == "run_baseline_bundle":
                baseline_bundle_id = str(result.generated_artifacts.get("artifact_bundle_id") or f"round_{round_index:02d}_baseline_bundle")
                baseline_source_round = round_index
                _append_baseline_registry_entry(available_artifacts, result.generated_artifacts)
            elif result.generated_artifacts.get("artifact_bundle_registry_entries"):
                _append_baseline_registry_entry(available_artifacts, result.generated_artifacts)
        except AmespExecutionError as exc:
            payload = {
                "round_index": round_index,
                "capability_name": capability_name,
                "status": "failed",
                "plan": plan.model_dump(mode="json"),
                "probe_events": probe_events,
                "error": exc.to_payload(),
                "result_file": str(result_file),
            }
            suite_failed = True
        except Exception as exc:  # pragma: no cover - crash guard for remote debugging
            payload = {
                "round_index": round_index,
                "capability_name": capability_name,
                "status": "failed",
                "plan": plan.model_dump(mode="json"),
                "probe_events": probe_events,
                "error": {
                    "code": "unexpected_exception",
                    "message": f"{type(exc).__name__}: {exc}",
                    "generated_artifacts": {},
                    "raw_results": {},
                    "structured_results": {},
                    "status": "failed",
                },
                "result_file": str(result_file),
            }
            suite_failed = True

        _write_json(result_file, payload)
        suite_results.append(payload)
        _emit_probe_summary(round_index, capability_name, payload)

        if payload["status"] != "success" and args.stop_on_failure:
            break

    summary_payload = {
        "case_id": case_id,
        "smiles": args.smiles,
        "suite_status": "failed" if suite_failed else "success",
        "baseline_bundle_id": baseline_bundle_id,
        "baseline_source_round": baseline_source_round,
        "report_dir": str(report_dir),
        "capabilities_run": [item["capability_name"] for item in suite_results],
        "probes": [
            {
                "round_index": item["round_index"],
                "capability_name": item["capability_name"],
                "status": item["status"],
                "result_file": item["result_file"],
                "route_summary": item.get("route_summary"),
                "error": (
                    {
                        "code": item["error"].get("code"),
                        "message": item["error"].get("message"),
                    }
                    if item.get("error")
                    else None
                ),
            }
            for item in suite_results
        ],
    }
    _write_json(report_dir / "summary.json", summary_payload)

    print(f"probe_report_dir={report_dir}", file=sys.stderr)
    print(f"probe_summary_file={report_dir / 'summary.json'}", file=sys.stderr)
    print(f"probe_live_trace_file={report_dir / 'live_trace.jsonl'}", file=sys.stderr)
    print(f"probe_live_status_file={report_dir / 'live_status.md'}", file=sys.stderr)
    return 1 if suite_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
