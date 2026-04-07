#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
DEFAULT_HELP_CASES: list[tuple[str, list[str]]] = [
    ("no_args", []),
    ("dash_h", ["-h"]),
    ("double_dash_help", ["--help"]),
    ("dash_v", ["-v"]),
    ("double_dash_version", ["--version"]),
    ("dash_question", ["-?"]),
]
DEFAULT_KEYWORDS = [
    "lmo",
    "nlmo",
    "natorb",
    "hirshfeld",
    "lowdin",
    "cm5",
    "mofile",
    "boys",
    "pipek",
    "mayer",
    "gross orbital populations",
    "density matrix",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Amesp binary metadata/help/version output and scan the binary/examples for keyword-family hints."
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
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="Timeout for each help/version subprocess invocation.",
    )
    parser.add_argument(
        "--keywords",
        default=",".join(DEFAULT_KEYWORDS),
        help="Comma-separated keywords to search in binary strings and bundled examples.",
    )
    parser.add_argument(
        "--skip-strings",
        action="store_true",
        help="Skip scanning the binary with the `strings` utility.",
    )
    parser.add_argument(
        "--skip-examples",
        action="store_true",
        help="Skip scanning third_party/Amesp/Example for keyword mentions.",
    )
    return parser.parse_args()


def _parse_keywords(raw: str) -> list[str]:
    keywords = [item.strip() for item in raw.split(",") if item.strip()]
    if not keywords:
        raise SystemExit("At least one keyword must be provided.")
    return keywords


def _build_report_dir(report_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    report_dir = report_root / f"amesp_binary_probe_{timestamp}_{uuid.uuid4().hex[:12]}"
    report_dir.mkdir(parents=True, exist_ok=False)
    return report_dir


def _sha256_of_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tail_lines(text: str, count: int = 20) -> list[str]:
    return text.splitlines()[-count:]


def _run_command(
    *,
    label: str,
    cmd: list[str],
    cwd: Path,
    timeout_seconds: float,
    env: dict[str, str],
) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        return {
            "label": label,
            "cmd": cmd,
            "status": "completed",
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "stdout_tail": _tail_lines(completed.stdout or ""),
            "stderr_tail": _tail_lines(completed.stderr or ""),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "label": label,
            "cmd": cmd,
            "status": "timeout",
            "exit_code": None,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "stdout_tail": _tail_lines(exc.stdout or ""),
            "stderr_tail": _tail_lines(exc.stderr or ""),
        }
    except Exception as exc:  # pragma: no cover - diagnostic fallback
        return {
            "label": label,
            "cmd": cmd,
            "status": "failed",
            "exit_code": None,
            "stdout": "",
            "stderr": repr(exc),
            "stdout_tail": [],
            "stderr_tail": [repr(exc)],
        }


def _scan_binary_strings(*, amesp_bin: Path, keywords: list[str], timeout_seconds: float) -> dict[str, Any]:
    strings_bin = shutil.which("strings")
    if strings_bin is None:
        return {
            "status": "skipped",
            "reason": "`strings` is not available on PATH.",
            "matches": {},
        }
    try:
        completed = subprocess.run(
            [strings_bin, str(amesp_bin)],
            capture_output=True,
            text=True,
            timeout=max(timeout_seconds, 30.0),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "reason": "Timed out while running `strings` on the Amesp binary.",
            "matches": {},
            "stdout_tail": _tail_lines(exc.stdout or ""),
            "stderr_tail": _tail_lines(exc.stderr or ""),
        }
    if completed.returncode != 0:
        return {
            "status": "failed",
            "reason": "`strings` returned a non-zero exit code.",
            "matches": {},
            "stdout_tail": _tail_lines(completed.stdout or ""),
            "stderr_tail": _tail_lines(completed.stderr or ""),
        }
    lines = completed.stdout.splitlines()
    matches: dict[str, list[str]] = {}
    for keyword in keywords:
        lowered = keyword.lower()
        hits = [line for line in lines if lowered in line.lower()]
        matches[keyword] = hits[:20]
    return {
        "status": "completed",
        "strings_binary": strings_bin,
        "matches": matches,
    }


def _scan_example_tree(*, example_root: Path, keywords: list[str]) -> dict[str, Any]:
    if not example_root.exists():
        return {
            "status": "skipped",
            "reason": f"Example directory not found: {example_root}",
            "matches": {},
        }
    candidate_files = sorted(example_root.rglob("*.aip")) + sorted(example_root.rglob("*.aop"))
    matches: dict[str, list[str]] = {keyword: [] for keyword in keywords}
    for path in candidate_files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        lowered_text = text.lower()
        for keyword in keywords:
            if keyword.lower() in lowered_text and len(matches[keyword]) < 20:
                matches[keyword].append(str(path))
    return {
        "status": "completed",
        "example_root": str(example_root),
        "file_count_scanned": len(candidate_files),
        "matches": matches,
    }


def main() -> None:
    args = _parse_args()
    keywords = _parse_keywords(args.keywords)
    amesp_bin = Path(args.amesp_bin).expanduser().resolve()
    if not amesp_bin.exists():
        raise SystemExit(f"Amesp binary not found: {amesp_bin}")

    report_root = Path(args.report_root).expanduser().resolve()
    report_dir = _build_report_dir(report_root)

    env = os.environ.copy()
    current_path = env.get("PATH", "")
    bin_dir = str(amesp_bin.parent)
    path_entries = [entry for entry in current_path.split(os.pathsep) if entry]
    if bin_dir not in path_entries:
        env["PATH"] = f"{bin_dir}{os.pathsep}{current_path}" if current_path else bin_dir

    binary_metadata = {
        "amesp_bin": str(amesp_bin),
        "exists": amesp_bin.exists(),
        "is_executable": os.access(amesp_bin, os.X_OK),
        "size_bytes": amesp_bin.stat().st_size,
        "sha256": _sha256_of_file(amesp_bin),
        "path_head": env["PATH"].split(os.pathsep)[:5],
    }

    file_probe = _run_command(
        label="file",
        cmd=["file", str(amesp_bin)],
        cwd=report_dir,
        timeout_seconds=float(args.timeout_seconds),
        env=env,
    )
    help_results = [
        _run_command(
            label=label,
            cmd=[str(amesp_bin), *argv],
            cwd=report_dir,
            timeout_seconds=float(args.timeout_seconds),
            env=env,
        )
        for label, argv in DEFAULT_HELP_CASES
    ]
    strings_result = (
        {
            "status": "skipped",
            "reason": "User requested --skip-strings.",
            "matches": {},
        }
        if args.skip_strings
        else _scan_binary_strings(amesp_bin=amesp_bin, keywords=keywords, timeout_seconds=float(args.timeout_seconds))
    )
    example_result = (
        {
            "status": "skipped",
            "reason": "User requested --skip-examples.",
            "matches": {},
        }
        if args.skip_examples
        else _scan_example_tree(example_root=PROJECT_ROOT / "third_party" / "Amesp" / "Example", keywords=keywords)
    )

    manifest = {
        "report_dir": str(report_dir),
        "amesp_bin": str(amesp_bin),
        "timeout_seconds": float(args.timeout_seconds),
        "keywords": keywords,
        "skip_strings": bool(args.skip_strings),
        "skip_examples": bool(args.skip_examples),
    }
    (report_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "binary_metadata.json").write_text(
        json.dumps(binary_metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (report_dir / "file_probe.json").write_text(json.dumps(file_probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "help_results.json").write_text(json.dumps(help_results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "strings_scan.json").write_text(json.dumps(strings_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (report_dir / "example_scan.json").write_text(json.dumps(example_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "report_dir": str(report_dir),
        "amesp_bin": str(amesp_bin),
        "binary_metadata": {
            "size_bytes": binary_metadata["size_bytes"],
            "sha256": binary_metadata["sha256"],
            "is_executable": binary_metadata["is_executable"],
        },
        "file_probe_status": file_probe["status"],
        "help_results": [
            {
                "label": item["label"],
                "status": item["status"],
                "exit_code": item["exit_code"],
                "stdout_tail": item["stdout_tail"],
                "stderr_tail": item["stderr_tail"],
            }
            for item in help_results
        ],
        "strings_matches": strings_result.get("matches", {}),
        "example_matches": example_result.get("matches", {}),
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Amesp Binary Capability Probe",
        "",
        f"- report_dir: {report_dir}",
        f"- amesp_bin: {amesp_bin}",
        f"- sha256: {binary_metadata['sha256']}",
        f"- size_bytes: {binary_metadata['size_bytes']}",
        "",
        "## Help/Version Results",
    ]
    for item in help_results:
        lines.extend(
            [
                "",
                f"### {item['label']}",
                f"- status: {item['status']}",
                f"- exit_code: {item['exit_code']}",
                f"- stdout_tail: {json.dumps(item['stdout_tail'], ensure_ascii=False)}",
                f"- stderr_tail: {json.dumps(item['stderr_tail'], ensure_ascii=False)}",
            ]
        )
    lines.extend(["", "## Strings Matches"])
    for keyword, hits in strings_result.get("matches", {}).items():
        lines.append(f"- {keyword}: {len(hits)} hit(s)")
    lines.extend(["", "## Example Matches"])
    for keyword, hits in example_result.get("matches", {}).items():
        lines.append(f"- {keyword}: {len(hits)} file hit(s)")
    (report_dir / "live_status.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
