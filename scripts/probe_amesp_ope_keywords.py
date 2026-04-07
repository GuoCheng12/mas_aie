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


DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "case_id": "control_no_ope",
        "title": "Control without >method or >ope",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": [],
        "ope_lines": [],
    },
    {
        "case_id": "charge_hirshfeld",
        "title": "Hirshfeld charge probe",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": [],
        "ope_lines": ["charge hirshfeld"],
    },
    {
        "case_id": "density_out2",
        "title": "Density/population out 2 probe",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": [],
        "ope_lines": ["out 2"],
    },
    {
        "case_id": "mofile_only",
        "title": "MO file only probe",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": [],
        "ope_lines": ["mofile on"],
    },
    {
        "case_id": "localized_pm_method",
        "title": "Localized orbital probe (PM in >method)",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": ["lmo pm"],
        "ope_lines": ["mofile on"],
    },
    {
        "case_id": "localized_pm_method_nlmo_occ",
        "title": "Localized orbital probe (PM in >method + nlmo occ)",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": ["lmo pm"],
        "ope_lines": ["mofile on", "nlmo occ"],
    },
    {
        "case_id": "localized_boys_method_nlmo_occ",
        "title": "Localized orbital probe (Boys in >method + nlmo occ)",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": ["lmo boys"],
        "ope_lines": ["mofile on", "nlmo occ"],
    },
    {
        "case_id": "natural_no_method",
        "title": "Natural orbital probe (NO in >method)",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": ["natorb no"],
        "ope_lines": ["mofile on"],
    },
    {
        "case_id": "natural_uno_method",
        "title": "Natural orbital probe (UNO in >method)",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": ["natorb uno"],
        "ope_lines": ["mofile on"],
    },
    {
        "case_id": "natural_nso_method",
        "title": "Natural orbital probe (NSO in >method)",
        "keywords": ["b3lyp", "sto-3g"],
        "method_lines": ["natorb nso"],
        "ope_lines": ["mofile on"],
    },
]


WATER_GEOMETRY = [
    ("O", 0.000000, 0.000000, 0.000000),
    ("H", 0.000000, 0.757160, 0.586260),
    ("H", 0.000000, -0.757160, 0.586260),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Amesp keyword compatibility on a minimal fixed-geometry DFT single-point input "
            "with explicit >method / >ope placement."
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
        "--cases",
        default="all",
        help=(
            "Comma-separated case ids to run. Default 'all'. "
            "Supported ids: " + ", ".join(case["case_id"] for case in DEFAULT_CASES)
        ),
    )
    parser.add_argument("--npara", type=int, default=1, help="Value written to %% npara.")
    parser.add_argument("--maxcore-mb", type=int, default=4000, help="Value written to %% maxcore.")
    parser.add_argument("--charge", type=int, default=0, help="Total charge for the minimal molecule.")
    parser.add_argument("--multiplicity", type=int, default=1, help="Spin multiplicity for the minimal molecule.")
    return parser.parse_args()


def _resolve_cases(raw: str) -> list[dict[str, Any]]:
    if raw.strip().lower() == "all":
        return list(DEFAULT_CASES)
    allowed = {case["case_id"]: case for case in DEFAULT_CASES}
    resolved: list[dict[str, Any]] = []
    for item in raw.split(","):
        case_id = item.strip()
        if not case_id:
            continue
        if case_id not in allowed:
            raise SystemExit(f"Unsupported case_id '{case_id}'. Allowed: {', '.join(sorted(allowed))}")
        resolved.append(allowed[case_id])
    if not resolved:
        raise SystemExit("At least one keyword probe case must be selected.")
    return resolved


def _build_report_dir(report_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_dir = report_root / f"ope_keyword_probe_{timestamp}_{uuid.uuid4().hex[:12]}"
    report_dir.mkdir(parents=True, exist_ok=False)
    return report_dir


def _write_input(
    *,
    aip_path: Path,
    keywords: list[str],
    method_lines: list[str],
    ope_lines: list[str],
    charge: int,
    multiplicity: int,
    npara: int,
    maxcore_mb: int,
) -> None:
    lines: list[str] = [
        f"% npara {npara}",
        f"% maxcore {maxcore_mb}",
        "! " + " ".join(keywords),
        ">scf",
        "  maxcyc 2000",
        "  vshift 500",
        "end",
    ]
    if method_lines:
        lines.extend([">method", *[f"  {item}" for item in method_lines], "end"])
    if ope_lines:
        lines.extend([">ope", *[f"  {item}" for item in ope_lines], "end"])
    lines.append(f">xyz {charge} {multiplicity}")
    for symbol, x, y, z in WATER_GEOMETRY:
        lines.append(f" {symbol:<2} {x: .6f} {y: .6f} {z: .6f}")
    lines.append("end")
    aip_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_env(amesp_bin: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("KMP_STACKSIZE", "4g")
    bin_dir = str(amesp_bin.parent)
    current_path = env.get("PATH", "")
    path_entries = [entry for entry in current_path.split(os.pathsep) if entry]
    if bin_dir not in path_entries:
        env["PATH"] = f"{bin_dir}{os.pathsep}{current_path}" if current_path else bin_dir
    return env


def _stop_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if "stop :" in line.lower()]


def _run_case(
    *,
    case: dict[str, Any],
    amesp_bin: Path,
    report_dir: Path,
    charge: int,
    multiplicity: int,
    npara: int,
    maxcore_mb: int,
) -> dict[str, Any]:
    workdir = report_dir / "work" / case["case_id"]
    workdir.mkdir(parents=True, exist_ok=True)
    label = case["case_id"]
    aip_path = workdir / f"{label}.aip"
    aop_path = workdir / f"{label}.aop"
    stdout_path = workdir / f"{label}.stdout.log"
    stderr_path = workdir / f"{label}.stderr.log"

    _write_input(
        aip_path=aip_path,
        keywords=list(case["keywords"]),
        method_lines=list(case.get("method_lines", [])),
        ope_lines=list(case["ope_lines"]),
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
    result = {
        "case_id": case["case_id"],
        "title": case["title"],
        "status": status,
        "keywords": list(case["keywords"]),
        "method_lines": list(case.get("method_lines", [])),
        "ope_lines": list(case["ope_lines"]),
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
    return result


def _write_live_status(
    *,
    report_dir: Path,
    amesp_bin: Path,
    results: list[dict[str, Any]],
) -> None:
    lines = [
        "# Amesp Method/OPE Keyword Probe",
        "",
        f"- report_dir: {report_dir}",
        f"- amesp_bin: {amesp_bin}",
        f"- probes_run: {len(results)}",
        "",
        "## Results",
    ]
    for result in results:
        lines.extend(
            [
                "",
                f"### {result['case_id']}",
                f"- title: {result['title']}",
                f"- status: {result['status']}",
                f"- keywords: {json.dumps(result['keywords'])}",
                f"- method_lines: {json.dumps(result['method_lines'])}",
                f"- ope_lines: {json.dumps(result['ope_lines'])}",
                f"- exit_code: {result['exit_code']}",
                f"- aop_exists: {result['aop_exists']}",
                f"- terminated_normally: {result['terminated_normally']}",
                f"- stdout_stop_lines: {json.dumps(result['stdout_stop_lines'], ensure_ascii=False)}",
                f"- stderr_stop_lines: {json.dumps(result['stderr_stop_lines'], ensure_ascii=False)}",
            ]
        )
    (report_dir / "live_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = _parse_args()
    amesp_bin = Path(args.amesp_bin).expanduser().resolve()
    if not amesp_bin.exists():
        raise SystemExit(f"Amesp binary not found: {amesp_bin}")

    selected_cases = _resolve_cases(args.cases)
    report_root = Path(args.report_root).expanduser().resolve()
    report_dir = _build_report_dir(report_root)
    manifest = {
        "report_dir": str(report_dir),
        "amesp_bin": str(amesp_bin),
        "cases_requested": [case["case_id"] for case in selected_cases],
        "npara": int(args.npara),
        "maxcore_mb": int(args.maxcore_mb),
        "charge": int(args.charge),
        "multiplicity": int(args.multiplicity),
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    results: list[dict[str, Any]] = []
    for case in selected_cases:
        result = _run_case(
            case=case,
            amesp_bin=amesp_bin,
            report_dir=report_dir,
            charge=int(args.charge),
            multiplicity=int(args.multiplicity),
            npara=int(args.npara),
            maxcore_mb=int(args.maxcore_mb),
        )
        results.append(result)
        (report_dir / f"{case['case_id']}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        _write_live_status(report_dir=report_dir, amesp_bin=amesp_bin, results=results)

    suite_status = "success" if all(item["status"] == "success" for item in results) else "failed"
    summary = {
        "report_dir": str(report_dir),
        "amesp_bin": str(amesp_bin),
        "suite_status": suite_status,
        "results": [
            {
                "case_id": item["case_id"],
                "title": item["title"],
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
