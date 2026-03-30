from __future__ import annotations

from pathlib import Path

from aie_mas.report_analysis import build_analysis_config, load_report_context, render_report_analysis_markdown


REPORT_DIR = (
    Path(__file__).resolve().parents[1]
    / "debug_reports"
    / "20260330-221048-579614_a3c2c875fb66"
)


def test_load_report_context_extracts_rounds_and_top3() -> None:
    context = load_report_context(REPORT_DIR)

    assert context.case_id == "a3c2c875fb66"
    assert len(context.rounds) == 4
    assert context.final_top3[0].name == "neutral aromatic"
    assert context.final_top3[1].name == "unknown"
    assert context.final_top3[2].name == "TICT"


def test_load_report_context_extracts_microscopic_tools() -> None:
    context = load_report_context(REPORT_DIR)

    round_1 = context.rounds[0]
    round_2 = context.rounds[1]
    round_3 = context.rounds[2]

    round_1_micro = next(report for report in round_1.agent_reports if report.agent_name == "microscopic")
    round_2_micro = next(report for report in round_2.agent_reports if report.agent_name == "microscopic")
    round_3_micro = next(report for report in round_3.agent_reports if report.agent_name == "microscopic")

    assert [tool.tool_name for tool in round_1_micro.tools_used] == ["run_baseline_bundle"]
    assert round_2_micro.task_completion_status == "failed"
    assert [tool.tool_name for tool in round_3_micro.tools_used] == [
        "list_rotatable_dihedrals",
        "run_torsion_snapshots",
    ]


def test_render_report_analysis_markdown_includes_tools() -> None:
    context = load_report_context(REPORT_DIR)
    analysis = {
        "report_dir": context.report_dir,
        "case_id": context.case_id,
        "smiles": context.smiles,
        "final_hypothesis": context.final_hypothesis,
        "final_confidence": context.final_confidence,
        "final_top3": [item.model_dump(mode="json") for item in context.final_top3],
        "final_diagnosis_summary": context.final_diagnosis_summary,
        "final_hypothesis_rationale": context.final_hypothesis_rationale,
        "overall_summary": "overall",
        "final_takeaway": "final",
        "cross_round_findings": ["finding"],
        "rounds": [
            {
                **round_context.model_dump(mode="json"),
                "dialogue_summary": f"round {round_context.round_id}",
                "issues": [],
            }
            for round_context in context.rounds
        ],
    }

    from aie_mas.report_analysis import ReportAnalysis

    markdown = render_report_analysis_markdown(ReportAnalysis.model_validate(analysis))

    assert "run_baseline_bundle" in markdown
    assert "run_torsion_snapshots" in markdown
    assert "verifier_evidence_lookup" in markdown


def test_build_analysis_config_prefers_report_analysis_env(monkeypatch) -> None:
    monkeypatch.setenv("AIE_MAS_OPENAI_BASE_URL", "http://example.test/v1")
    monkeypatch.setenv("AIE_MAS_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AIE_MAS_OPENAI_MODEL", "gpt-5.2")
    monkeypatch.setenv("AIE_MAS_REPORT_ANALYSIS_MODEL", "gpt-4o-mini")

    config = build_analysis_config()

    assert config.planner_base_url == "http://example.test/v1"
    assert config.planner_api_key == "test-key"
    assert config.planner_model == "gpt-4o-mini"
