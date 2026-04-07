#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AMESP_BIN = (
    Path(os.environ.get("AIE_MAS_AMESP_BIN") or PROJECT_ROOT / "third_party" / "Amesp" / "Bin" / "amesp")
    .expanduser()
    .resolve()
)
DEFAULT_REPORT_ROOT = PROJECT_ROOT / "debug_reports"

CONTEXTS: dict[str, dict[str, Any]] = {
    "dft_sp": {
        "title": "DFT single-point",
        "keywords": ["b3lyp", "sto-3g"],
        "pre_ope_blocks": [],
        "post_ope_blocks": [],
    },
    "td_posthf_after_ope": {
        "title": "TD-DFT with >posthf after >ope",
        "keywords": ["b3lyp", "sto-3g", "td"],
        "pre_ope_blocks": [],
        "post_ope_blocks": [("posthf", ["nstates 2", "tout 1"])],
    },
    "td_posthf_before_ope": {
        "title": "TD-DFT with >posthf before >ope",
        "keywords": ["b3lyp", "sto-3g", "td"],
        "pre_ope_blocks": [("posthf", ["nstates 2", "tout 1"])],
        "post_ope_blocks": [],
    },
    "tda_ris_posthf_after_ope": {
        "title": "TDA-RIS with >posthf after >ope",
        "keywords": ["b3lyp", "sto-3g", "tda-ris"],
        "pre_ope_blocks": [],
        "post_ope_blocks": [("posthf", ["nstates 2", "tout 1"])],
    },
    "tda_ris_posthf_before_ope": {
        "title": "TDA-RIS with >posthf before >ope",
        "keywords": ["b3lyp", "sto-3g", "tda-ris"],
        "pre_ope_blocks": [("posthf", ["nstates 2", "tout 1"])],
        "post_ope_blocks": [],
    },
}

TARGETS: dict[str, dict[str, Any]] = {
    "control_mofile_only": {
        "title": "Control with mofile only",
        "method_lines": [],
        "ope_lines": ["mofile on"],
    },
    "control_out2_only": {
        "title": "Control with out 2 only",
        "method_lines": [],
        "ope_lines": ["out 2"],
    },
    "lmo_pm_method_mofile": {
        "title": "Localized orbital (PM in >method) with mofile",
        "method_lines": ["lmo pm"],
        "ope_lines": ["mofile on"],
    },
    "lmo_pm_method_mofile_nlmo_occ": {
        "title": "Localized orbital (PM in >method) with mofile + nlmo occ",
        "method_lines": ["lmo pm"],
        "ope_lines": ["mofile on", "nlmo occ"],
    },
    "lmo_pm_method_out2_mofile_nlmo_occ": {
        "title": "Localized orbital (PM in >method) with out 2 + mofile + nlmo occ",
        "method_lines": ["lmo pm"],
        "ope_lines": ["out 2", "mofile on", "nlmo occ"],
    },
    "lmo_boys_method_mofile_nlmo_occ": {
        "title": "Localized orbital (Boys in >method) with mofile + nlmo occ",
        "method_lines": ["lmo boys"],
        "ope_lines": ["mofile on", "nlmo occ"],
    },
    "lmo_boys_method_mofile_nlmo_all": {
        "title": "Localized orbital (Boys in >method) with mofile + nlmo all",
        "method_lines": ["lmo boys"],
        "ope_lines": ["mofile on", "nlmo all"],
    },
    "natorb_no_method_plain": {
        "title": "Natural orbital (NO in >method) without >ope",
        "method_lines": ["natorb no"],
        "ope_lines": [],
    },
    "natorb_no_method_mofile": {
        "title": "Natural orbital (NO in >method) with mofile",
        "method_lines": ["natorb no"],
        "ope_lines": ["mofile on"],
    },
    "natorb_no_method_out2_mofile": {
        "title": "Natural orbital (NO in >method) with out 2 + mofile",
        "method_lines": ["natorb no"],
        "ope_lines": ["out 2", "mofile on"],
    },
    "natorb_uno_method_mofile": {
        "title": "Natural orbital (UNO in >method) with mofile",
        "method_lines": ["natorb uno"],
        "ope_lines": ["mofile on"],
    },
    "natorb_nso_method_mofile": {
        "title": "Natural orbital (NSO in >method) with mofile",
        "method_lines": ["natorb nso"],
        "ope_lines": ["mofile on"],
    },
}

DEFAULT_CONTEXT_SELECTION = [
    "dft_sp",
    "td_posthf_after_ope",
    "td_posthf_before_ope",
    "tda_ris_posthf_after_ope",
    "tda_ris_posthf_before_ope",
]

DEFAULT_TARGET_SELECTION = [
    "control_mofile_only",
    "control_out2_only",
    "lmo_pm_method_mofile",
    "lmo_pm_method_mofile_nlmo_occ",
    "lmo_boys_method_mofile_nlmo_occ",
    "natorb_no_method_mofile",
    "natorb_uno_method_mofile",
    "natorb_nso_method_mofile",
]

WATER_GEOMETRY = [
    ("O", 0.000000, 0.000000, 0.000000),
    ("H", 0.000000, 0.757160, 0.586260),
    ("H", 0.000000, -0.757160, 0.586260),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Amesp lmo/natorb acceptance across a matrix of method families, >posthf placement, "
            "and explicit >method / >ope combinations."
        )
    )
    parser.add_argument(
        "--amesp-bin",
        default=str(DEFAULT_AMESP_BIN),
        help="Path to the Amesp executable. Defaults to AIE_MAS_AMESP_BIN or project third_party/Amesp/Bin/amesp.",
    )
    parser.add_argument(
        "--report-root",
        default=str(DEFAULT_REPORT_ROOT),
        help="Directory under which the probe report directory will be created.",
    )
    parser.add_argument(
        "--contexts",
        default="default",
        help=(
            "Comma-separated context ids to run. Use 'default' or 'all'. "
            "Supported ids: " + ", ".join(CONTEXTS)
        ),
    )
    parser.add_argument(
        "--targets",
        default="default",
        help=(
            "Comma-separated target ids to run. Use 'default' or 'all'. "
            "Supported ids: " + ", ".join(TARGETS)
        ),
    )
    parser.add_argument("--npara", type=int, default=1, help="Value written to %% npara.")
    parser.add_argument("--maxcore-mb", type=int, default=4000, help="Value written to %% maxcore.")
    parser.add_argument("--charge", type=int, default=0, help="Total charge for the minimal molecule.")
    parser.add_argument("--multiplicity", type=int, default=1, help="Spin multiplicity for the minimal molecule.")
    return parser.parse_args()


def _resolve_selection(raw: str, allowed: dict[str, Any], default_ids: list[str], label: str) -> list[str]:
    value = raw.strip().lower()
    if value == "default":
        return list(default_ids)
    if value == "all":
        return list(allowed)
    resolved: list[str] = []
    for item in raw.split(","):
        key = item.strip()
        if not key:
            continue
        if key not in allowed:
            raise SystemExit(f"Unsupported {label} '{key}'. Allowed: {', '.join(sorted(allowed))}")
        resolved.append(key)
    if not resolved:
        raise SystemExit(f"At least one {label} must be selected.")
    return resolved


def _build_report_dir(report_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_dir = report_root / f"ope_syntax_matrix_probe_{timestamp}_{uuid.uuid4().hex[:12]}"
    report_dir.mkdir(parents=True, exist_ok=False)
    return report_dir


def _build_env(amesp_bin: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("KMP_STACKSIZE", "4g")
    bin_dir = str(amesp_bin.parent)
    current_path = env.get("PATH", "")
    path_entries = [entry for entry in current_path.split(os.pathsep) if entry]
    if bin_dir not in path_entries:
        env["PATH"] = f"{bin_dir}{os.pathsep}{current_path}" if current_path else bin_dir
    return env


def _write_block(lines: list[str], name: str, entries: list[str]) -> None:
    lines.append(f">{name}")
    lines.extend([f"  {entry}" for entry in entries])
    lines.append("end")


def _write_input(
    *,
    aip_path: Path,
    context: dict[str, Any],
    target: dict[str, Any],
    charge: int,
    multiplicity: int,
    npara: int,
    maxcore_mb: int,
) -> None:
    lines: list[str] = [
        f"% npara {npara}",
        f"% maxcore {maxcore_mb}",
        "! " + " ".join(context["keywords"]),
        ">scf",
        "  maxcyc 2000",
        "  vshift 500",
        "end",
    ]
    if target["method_lines"]:
        _write_block(lines, "method", list(target["method_lines"]))
    for block_name, block_lines in context["pre_ope_blocks"]:
        _write_block(lines, block_name, list(block_lines))
    if target["ope_lines"]:
        _write_block(lines, "ope", list(target["ope_lines"]))
    for block_name, block_lines in context["post_ope_blocks"]:
        _write_block(lines, block_name, list(block_lines))
    lines.append(f">xyz {charge} {multiplicity}")
    for symbol, x, y, z in WATER_GEOMETRY:
        lines.append(f" {symbol:<2} {x: .6f} {y: .6f} {z: .6f}")
    lines.append("end")
    aip_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _stop_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if "stop :" in line.lower()]


def _run_case(
    *,
    context_id: str,
    target_id: str,
    amesp_bin: Path,
    report_dir: Path,
    charge: int,
    multiplicity: int,
    npara: int,
    maxcore_mb: int,
) -> dict[str, Any]:
    context = CONTEXTS[context_id]
    target = TARGETS[target_id]
    case_id = f"{context_id}__{target_id}"
    workdir = report_dir / "work" / case_id
    workdir.mkdir(parents=True, exist_ok=True)
    aip_path = workdir / f"{case_id}.aip"
    aop_path = workdir / f"{case_id}.aop"
    stdout_path = workdir / f"{case_id}.stdout.log"
    stderr_path = workdir / f"{case_id}.stderr.log"

    _write_input(
        aip_path=aip_path,
        context=context,
        target=target,
        charge=charge,
        multiplicity=multiplicity,
        npara=npara,
        maxcore_mb=maxcore_mb,
    )

    env = _build_env(amesp_bin)
    completed = subprocess.run(
        [str(amesp_bin), aip_path.name, aop_path.name],
        cwd=str(workdir),
        env=env,
        capture_output=True,
        text=True,
    )
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")
    aop_text = aop_path.read_text(encoding="utf-8", errors="replace") if aop_path.exists() else ""

    terminated_normally = "Normal termination of Amesp!" in aop_text
    status = "success" if completed.returncode == 0 and terminated_normally else "failed"
    return {
        "case_id": case_id,
        "context_id": context_id,
        "target_id": target_id,
        "context_title": context["title"],
        "target_title": target["title"],
        "status": status,
        "keywords": list(context["keywords"]),
        "method_lines": list(target["method_lines"]),
        "pre_ope_blocks": context["pre_ope_blocks"],
        "ope_lines": list(target["ope_lines"]),
        "post_ope_blocks": context["post_ope_blocks"],
        "aip_path": str(aip_path),
        "aop_path": str(aop_path),
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "exit_code": completed.returncode,
        "aop_exists": aop_path.exists(),
        "terminated_normally": terminated_normally,
        "stdout_stop_lines": _stop_lines(completed.stdout or ""),
        "stderr_stop_lines": _stop_lines(completed.stderr or ""),
        "stdout_tail": (completed.stdout or "").splitlines()[-10:],
        "stderr_tail": (completed.stderr or "").splitlines()[-10:],
        "aop_tail": aop_text.splitlines()[-20:],
    }


def _write_live_status(*, report_dir: Path, amesp_bin: Path, results: list[dict[str, Any]]) -> None:
    lines = [
        "# Amesp Method/OPE Syntax Matrix Probe",
        "",
        f"- report_dir: {report_dir}",
        f"- amesp_bin: {amesp_bin}",
        f"- cases_run: {len(results)}",
        "",
        "## Results",
    ]
    for item in results:
        lines.extend(
            [
                "",
                f"### {item['case_id']}",
                f"- context: {item['context_id']} ({item['context_title']})",
                f"- target: {item['target_id']} ({item['target_title']})",
                f"- status: {item['status']}",
                f"- keywords: {json.dumps(item['keywords'])}",
                f"- method_lines: {json.dumps(item['method_lines'])}",
                f"- pre_ope_blocks: {json.dumps(item['pre_ope_blocks'])}",
                f"- ope_lines: {json.dumps(item['ope_lines'])}",
                f"- post_ope_blocks: {json.dumps(item['post_ope_blocks'])}",
                f"- exit_code: {item['exit_code']}",
                f"- aop_exists: {item['aop_exists']}",
                f"- terminated_normally: {item['terminated_normally']}",
                f"- stdout_stop_lines: {json.dumps(item['stdout_stop_lines'], ensure_ascii=False)}",
                f"- stderr_stop_lines: {json.dumps(item['stderr_stop_lines'], ensure_ascii=False)}",
            ]
        )
    (report_dir / "live_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = _parse_args()
    amesp_bin = Path(args.amesp_bin).expanduser().resolve()
    if not amesp_bin.exists():
        raise SystemExit(f"Amesp binary not found: {amesp_bin}")

    context_ids = _resolve_selection(args.contexts, CONTEXTS, DEFAULT_CONTEXT_SELECTION, "context")
    target_ids = _resolve_selection(args.targets, TARGETS, DEFAULT_TARGET_SELECTION, "target")

    report_root = Path(args.report_root).expanduser().resolve()
    report_dir = _build_report_dir(report_root)
    manifest = {
        "report_dir": str(report_dir),
        "amesp_bin": str(amesp_bin),
        "contexts_requested": context_ids,
        "targets_requested": target_ids,
        "case_count": len(context_ids) * len(target_ids),
        "npara": int(args.npara),
        "maxcore_mb": int(args.maxcore_mb),
        "charge": int(args.charge),
        "multiplicity": int(args.multiplicity),
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    results: list[dict[str, Any]] = []
    for context_id in context_ids:
        for target_id in target_ids:
            result = _run_case(
                context_id=context_id,
                target_id=target_id,
                amesp_bin=amesp_bin,
                report_dir=report_dir,
                charge=int(args.charge),
                multiplicity=int(args.multiplicity),
                npara=int(args.npara),
                maxcore_mb=int(args.maxcore_mb),
            )
            results.append(result)
            (report_dir / f"{result['case_id']}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            _write_live_status(report_dir=report_dir, amesp_bin=amesp_bin, results=results)

    success_count = sum(1 for item in results if item["status"] == "success")
    failure_count = len(results) - success_count
    summary = {
        "report_dir": str(report_dir),
        "amesp_bin": str(amesp_bin),
        "suite_status": "success" if failure_count == 0 else "failed",
        "success_count": success_count,
        "failure_count": failure_count,
        "results": [
            {
                "case_id": item["case_id"],
                "context_id": item["context_id"],
                "target_id": item["target_id"],
                "status": item["status"],
                "exit_code": item["exit_code"],
                "method_lines": item["method_lines"],
                "ope_lines": item["ope_lines"],
                "terminated_normally": item["terminated_normally"],
                "stdout_stop_lines": item["stdout_stop_lines"],
                "stderr_stop_lines": item["stderr_stop_lines"],
                "result_file": str(report_dir / f"{item['case_id']}.json"),
            }
            for item in results
        ],
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_live_status(report_dir=report_dir, amesp_bin=amesp_bin, results=results)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
