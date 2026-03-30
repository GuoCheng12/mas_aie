#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from aie_mas.report_analysis import (  # noqa: E402
    analyze_report_with_llm,
    build_analysis_config,
    load_report_context,
    render_report_analysis_markdown,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze a completed AIE-MAS debug report with an OpenAI-compatible API."
    )
    parser.add_argument("report_dir", type=Path, help="Path to a completed debug report directory.")
    parser.add_argument("--base-url", dest="base_url", default=None, help="OpenAI-compatible API base URL.")
    parser.add_argument("--model", dest="model", default=None, help="Model name.")
    parser.add_argument("--api-key", dest="api_key", default=None, help="API key.")
    parser.add_argument(
        "--temperature",
        dest="temperature",
        type=float,
        default=0.0,
        help="Sampling temperature for the analysis call.",
    )
    parser.add_argument(
        "--timeout-seconds",
        dest="timeout_seconds",
        type=float,
        default=180.0,
        help="API timeout in seconds.",
    )
    parser.add_argument(
        "--output-json",
        dest="output_json",
        type=Path,
        default=None,
        help="Path to write structured analysis JSON. Defaults to <report_dir>/api_report_analysis.json.",
    )
    parser.add_argument(
        "--output-md",
        dest="output_md",
        type=Path,
        default=None,
        help="Path to write markdown analysis. Defaults to <report_dir>/api_report_analysis.md.",
    )
    parser.add_argument(
        "--print-context-only",
        dest="print_context_only",
        action="store_true",
        help="Print the extracted local analysis context JSON and exit without calling the API.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    report_dir = args.report_dir.expanduser().resolve()
    report_context = load_report_context(report_dir)

    if args.print_context_only:
        print(json.dumps(report_context.model_dump(mode="json"), ensure_ascii=False, indent=2))
        return 0

    config = build_analysis_config(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        temperature=args.temperature,
        timeout_seconds=args.timeout_seconds,
    )
    analysis = analyze_report_with_llm(report_context=report_context, config=config)
    markdown = render_report_analysis_markdown(analysis)

    output_json = args.output_json or (report_dir / "api_report_analysis.json")
    output_md = args.output_md or (report_dir / "api_report_analysis.md")
    output_json.write_text(
        json.dumps(analysis.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    output_md.write_text(markdown, encoding="utf-8")

    print(f"analysis_json: {output_json}")
    print(f"analysis_markdown: {output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
