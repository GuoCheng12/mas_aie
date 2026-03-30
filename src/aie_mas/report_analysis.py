from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from aie_mas.config import AieMasConfig
from aie_mas.llm.openai_compatible import OpenAICompatiblePlannerClient
from aie_mas.utils.prompts import PromptRepository


_MICROSCOPIC_PARAM_KEYS = (
    "capability_name",
    "structure_source",
    "artifact_bundle_id",
    "artifact_kind",
    "artifact_source_round",
    "perform_new_calculation",
    "optimize_ground_state",
    "reuse_existing_artifacts_only",
    "state_window",
    "snapshot_count",
    "angle_offsets_deg",
    "dihedral_id",
    "conformer_id",
    "conformer_ids",
    "max_conformers",
    "descriptor_scope",
    "requested_observable_scope",
    "budget_profile",
)
_USE_TOOL_PATTERN = re.compile(r"^Use ([A-Za-z_][A-Za-z0-9_]*)")


class ToolCallSummary(BaseModel):
    tool_name: str
    call_kind: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentRunSummary(BaseModel):
    agent_name: str
    status: str
    task_completion_status: str
    completion_reason_code: Optional[str] = None
    task_received: str
    task_understanding: Optional[str] = None
    execution_plan: Optional[str] = None
    result_summary: Optional[str] = None
    remaining_local_uncertainty: Optional[str] = None
    tools_used: list[ToolCallSummary] = Field(default_factory=list)


class HypothesisScore(BaseModel):
    name: str
    confidence: float
    rationale: Optional[str] = None


class RoundReportContext(BaseModel):
    round_id: int
    action_taken: str
    current_hypothesis: Optional[str] = None
    confidence: Optional[float] = None
    top3: list[HypothesisScore] = Field(default_factory=list)
    planner_task_instruction: Optional[str] = None
    planner_agent_task_instructions: dict[str, str] = Field(default_factory=dict)
    diagnosis_summary: Optional[str] = None
    evidence_summary: Optional[str] = None
    main_gap: Optional[str] = None
    decision_pair: list[str] = Field(default_factory=list)
    decision_gate_status: Optional[str] = None
    verifier_supplement_status: Optional[str] = None
    closure_justification_status: Optional[str] = None
    finalization_mode: Optional[str] = None
    agent_reports: list[AgentRunSummary] = Field(default_factory=list)


class ReportContext(BaseModel):
    report_dir: str
    case_id: str
    smiles: str
    final_hypothesis: Optional[str] = None
    final_confidence: Optional[float] = None
    final_top3: list[HypothesisScore] = Field(default_factory=list)
    final_diagnosis_summary: Optional[str] = None
    final_hypothesis_rationale: Optional[str] = None
    rounds: list[RoundReportContext] = Field(default_factory=list)


class RoundNarrative(BaseModel):
    round_id: int
    dialogue_summary: str
    issues: list[str] = Field(default_factory=list)


class ReportNarrative(BaseModel):
    overall_summary: str
    final_takeaway: str
    rounds: list[RoundNarrative] = Field(default_factory=list)
    cross_round_findings: list[str] = Field(default_factory=list)


class AnalyzedRound(BaseModel):
    round_id: int
    action_taken: str
    current_hypothesis: Optional[str] = None
    confidence: Optional[float] = None
    top3: list[HypothesisScore] = Field(default_factory=list)
    planner_task_instruction: Optional[str] = None
    planner_agent_task_instructions: dict[str, str] = Field(default_factory=dict)
    diagnosis_summary: Optional[str] = None
    evidence_summary: Optional[str] = None
    main_gap: Optional[str] = None
    decision_pair: list[str] = Field(default_factory=list)
    decision_gate_status: Optional[str] = None
    verifier_supplement_status: Optional[str] = None
    closure_justification_status: Optional[str] = None
    finalization_mode: Optional[str] = None
    agent_reports: list[AgentRunSummary] = Field(default_factory=list)
    dialogue_summary: str
    issues: list[str] = Field(default_factory=list)


class ReportAnalysis(BaseModel):
    report_dir: str
    case_id: str
    smiles: str
    final_hypothesis: Optional[str] = None
    final_confidence: Optional[float] = None
    final_top3: list[HypothesisScore] = Field(default_factory=list)
    final_diagnosis_summary: Optional[str] = None
    final_hypothesis_rationale: Optional[str] = None
    overall_summary: str
    final_takeaway: str
    rounds: list[AnalyzedRound] = Field(default_factory=list)
    cross_round_findings: list[str] = Field(default_factory=list)


def load_report_context(report_dir: Path) -> ReportContext:
    report_dir = report_dir.expanduser().resolve()
    state = _load_state_snapshot(report_dir)
    working_memory = state.get("working_memory") or []
    microscopic_tools_by_round = _extract_microscopic_tools(report_dir / "live_trace.jsonl")

    rounds: list[RoundReportContext] = []
    for entry in working_memory:
        round_id = int(entry["round_id"])
        agent_reports: list[AgentRunSummary] = []
        for report in entry.get("agent_reports") or []:
            agent_name = str(report.get("agent_name") or "")
            agent_reports.append(
                AgentRunSummary(
                    agent_name=agent_name,
                    status=str(report.get("status") or ""),
                    task_completion_status=str(report.get("task_completion_status") or ""),
                    completion_reason_code=_optional_text(report.get("completion_reason_code")),
                    task_received=str(report.get("task_received") or ""),
                    task_understanding=_optional_text(report.get("task_understanding")),
                    execution_plan=_optional_text(report.get("execution_plan")),
                    result_summary=_optional_text(report.get("result_summary")),
                    remaining_local_uncertainty=_optional_text(report.get("remaining_local_uncertainty")),
                    tools_used=_derive_tools_for_agent(
                        agent_name=agent_name,
                        report=report,
                        microscopic_tool_calls=microscopic_tools_by_round.get(round_id, []),
                    ),
                )
            )

        rounds.append(
            RoundReportContext(
                round_id=round_id,
                action_taken=str(entry.get("action_taken") or ""),
                current_hypothesis=_optional_text(entry.get("current_hypothesis")),
                confidence=_optional_float(entry.get("confidence")),
                top3=_top3_from_pool(entry.get("hypothesis_pool") or []),
                planner_task_instruction=_optional_text(entry.get("planner_task_instruction")),
                planner_agent_task_instructions={
                    str(key): str(value)
                    for key, value in (entry.get("planner_agent_task_instructions") or {}).items()
                },
                diagnosis_summary=_optional_text(entry.get("diagnosis_summary")),
                evidence_summary=_optional_text(entry.get("evidence_summary")),
                main_gap=_optional_text(entry.get("main_gap")),
                decision_pair=[str(item) for item in (entry.get("decision_pair") or [])],
                decision_gate_status=_optional_text(entry.get("decision_gate_status")),
                verifier_supplement_status=_optional_text(entry.get("verifier_supplement_status")),
                closure_justification_status=_optional_text(entry.get("closure_justification_status")),
                finalization_mode=_optional_text(entry.get("finalization_mode")),
                agent_reports=agent_reports,
            )
        )

    return ReportContext(
        report_dir=str(report_dir),
        case_id=str(state.get("case_id") or report_dir.name),
        smiles=str(state.get("smiles") or ""),
        final_hypothesis=_optional_text(state.get("current_hypothesis")),
        final_confidence=_optional_float(state.get("confidence")),
        final_top3=_top3_from_pool(state.get("hypothesis_pool") or []),
        final_diagnosis_summary=_optional_text(state.get("latest_evidence_summary"))
        or _optional_text((state.get("last_planner_decision") or {}).get("diagnosis")),
        final_hypothesis_rationale=_optional_text(state.get("latest_final_hypothesis_rationale"))
        or _optional_text((state.get("last_planner_decision") or {}).get("final_hypothesis_rationale")),
        rounds=rounds,
    )


def analyze_report_with_llm(
    *,
    report_context: ReportContext,
    config: AieMasConfig,
    client: Optional[OpenAICompatiblePlannerClient] = None,
) -> ReportAnalysis:
    prompt_repo = PromptRepository(config.prompts_dir)
    prompt_text = prompt_repo.read_text("report_analysis")
    llm_client = client or OpenAICompatiblePlannerClient(config)
    narrative = llm_client.invoke_json_schema(
        messages=[
            {"role": "system", "content": prompt_text},
            {
                "role": "user",
                "content": (
                    "Report analysis context JSON:\n"
                    f"{json.dumps(report_context.model_dump(mode='json'), ensure_ascii=False, indent=2)}"
                ),
            },
        ],
        response_model=ReportNarrative,
        schema_name="aie_mas_report_analysis",
    )

    round_narratives = {item.round_id: item for item in narrative.rounds}
    analyzed_rounds: list[AnalyzedRound] = []
    for round_context in report_context.rounds:
        narrative_round = round_narratives.get(round_context.round_id)
        analyzed_rounds.append(
            AnalyzedRound(
                round_id=round_context.round_id,
                action_taken=round_context.action_taken,
                current_hypothesis=round_context.current_hypothesis,
                confidence=round_context.confidence,
                top3=round_context.top3,
                planner_task_instruction=round_context.planner_task_instruction,
                planner_agent_task_instructions=round_context.planner_agent_task_instructions,
                diagnosis_summary=round_context.diagnosis_summary,
                evidence_summary=round_context.evidence_summary,
                main_gap=round_context.main_gap,
                decision_pair=round_context.decision_pair,
                decision_gate_status=round_context.decision_gate_status,
                verifier_supplement_status=round_context.verifier_supplement_status,
                closure_justification_status=round_context.closure_justification_status,
                finalization_mode=round_context.finalization_mode,
                agent_reports=round_context.agent_reports,
                dialogue_summary=(
                    narrative_round.dialogue_summary
                    if narrative_round is not None
                    else "该轮的 LLM 对话解读缺失。"
                ),
                issues=list(narrative_round.issues if narrative_round is not None else []),
            )
        )

    return ReportAnalysis(
        report_dir=report_context.report_dir,
        case_id=report_context.case_id,
        smiles=report_context.smiles,
        final_hypothesis=report_context.final_hypothesis,
        final_confidence=report_context.final_confidence,
        final_top3=report_context.final_top3,
        final_diagnosis_summary=report_context.final_diagnosis_summary,
        final_hypothesis_rationale=report_context.final_hypothesis_rationale,
        overall_summary=narrative.overall_summary,
        final_takeaway=narrative.final_takeaway,
        rounds=analyzed_rounds,
        cross_round_findings=narrative.cross_round_findings,
    )


def render_report_analysis_markdown(analysis: ReportAnalysis) -> str:
    lines: list[str] = []
    lines.append("# Report Analysis")
    lines.append("")
    lines.append(f"- report_dir: `{analysis.report_dir}`")
    lines.append(f"- case_id: `{analysis.case_id}`")
    lines.append(f"- smiles: `{analysis.smiles}`")
    if analysis.final_hypothesis:
        lines.append(f"- final_hypothesis: `{analysis.final_hypothesis}`")
    if analysis.final_confidence is not None:
        lines.append(f"- final_confidence: `{analysis.final_confidence:.3f}`")
    if analysis.final_top3:
        lines.append(f"- final_top3: {_format_top3_inline(analysis.final_top3)}")
    lines.append("")
    lines.append("## Overall Summary")
    lines.append("")
    lines.append(analysis.overall_summary)
    lines.append("")
    lines.append("## Round-by-Round")
    lines.append("")

    for round_analysis in analysis.rounds:
        lines.append(f"### Round {round_analysis.round_id}")
        lines.append("")
        if round_analysis.current_hypothesis:
            hypothesis_line = f"- current_hypothesis: `{round_analysis.current_hypothesis}`"
            if round_analysis.confidence is not None:
                hypothesis_line += f" (`{round_analysis.confidence:.3f}`)"
            lines.append(hypothesis_line)
        if round_analysis.top3:
            lines.append(f"- top3: {_format_top3_inline(round_analysis.top3)}")
        if round_analysis.action_taken:
            lines.append(f"- action_taken: `{round_analysis.action_taken}`")
        if round_analysis.decision_pair:
            lines.append(f"- decision_pair: `{round_analysis.decision_pair[0]}` vs `{round_analysis.decision_pair[1]}`")
        if round_analysis.planner_task_instruction:
            lines.append(f"- planner_task_instruction: {round_analysis.planner_task_instruction}")
        if round_analysis.diagnosis_summary:
            lines.append(f"- planner_after_round: {round_analysis.diagnosis_summary}")
        if round_analysis.main_gap:
            lines.append(f"- main_gap: {round_analysis.main_gap}")
        lines.append("- agent_runs:")
        for report in round_analysis.agent_reports:
            tool_text = _format_tools_inline(report.tools_used)
            lines.append(
                f"  - `{report.agent_name}` | status=`{report.status}` | completion=`{report.task_completion_status}`"
                + (
                    f" | reason=`{report.completion_reason_code}`"
                    if report.completion_reason_code
                    else ""
                )
                + (f" | tools={tool_text}" if tool_text else "")
            )
            if report.task_received:
                lines.append(f"    task_received: {report.task_received}")
            if report.result_summary:
                lines.append(f"    result_summary: {report.result_summary}")
        lines.append("- dialogue_summary:")
        lines.append(f"  {round_analysis.dialogue_summary}")
        if round_analysis.issues:
            lines.append("- issues:")
            for issue in round_analysis.issues:
                lines.append(f"  - {issue}")
        lines.append("")

    lines.append("## Final Takeaway")
    lines.append("")
    lines.append(analysis.final_takeaway)
    if analysis.final_hypothesis_rationale:
        lines.append("")
        lines.append("## Final Rationale")
        lines.append("")
        lines.append(analysis.final_hypothesis_rationale)
    if analysis.cross_round_findings:
        lines.append("")
        lines.append("## Cross-Round Findings")
        lines.append("")
        for finding in analysis.cross_round_findings:
            lines.append(f"- {finding}")

    return "\n".join(lines).strip() + "\n"


def build_analysis_config(
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout_seconds: Optional[float] = None,
) -> AieMasConfig:
    return AieMasConfig.from_env(
        planner_base_url=base_url,
        planner_model=model,
        planner_api_key=api_key,
        planner_temperature=temperature,
        planner_timeout_seconds=timeout_seconds,
    )


def _load_state_snapshot(report_dir: Path) -> dict[str, Any]:
    full_state_path = report_dir / "full_state.json"
    payload = json.loads(full_state_path.read_text(encoding="utf-8"))
    return dict(payload.get("state_snapshot") or {})


def _extract_microscopic_tools(live_trace_path: Path) -> dict[int, list[ToolCallSummary]]:
    if not live_trace_path.exists():
        return {}

    tool_calls_by_round: dict[int, list[ToolCallSummary]] = {}
    for line in live_trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        details = event.get("details") or {}
        if (
            event.get("phase") != "probe"
            or event.get("node") != "run_microscopic"
            or details.get("probe_stage") != "execution_plan"
            or details.get("probe_status") != "end"
        ):
            continue

        round_id = int(event.get("round") or 0)
        calls = []
        microscopic_tool_plan = details.get("microscopic_tool_plan") or {}
        for call in microscopic_tool_plan.get("calls") or []:
            request = call.get("request") or {}
            parameters = {
                key: value
                for key in _MICROSCOPIC_PARAM_KEYS
                if (value := request.get(key)) not in (None, "", [], {})
            }
            tool_name = str(request.get("capability_name") or call.get("call_id") or "unknown_tool")
            calls.append(
                ToolCallSummary(
                    tool_name=tool_name,
                    call_kind=_optional_text(call.get("call_kind")),
                    parameters=parameters,
                )
            )
        tool_calls_by_round[round_id] = calls
    return tool_calls_by_round


def _derive_tools_for_agent(
    *,
    agent_name: str,
    report: dict[str, Any],
    microscopic_tool_calls: list[ToolCallSummary],
) -> list[ToolCallSummary]:
    if agent_name == "microscopic" and microscopic_tool_calls:
        return microscopic_tool_calls

    execution_plan = str(report.get("execution_plan") or "")
    if not execution_plan:
        return []

    tool_names: list[str] = []
    for line in execution_plan.splitlines():
        candidate = line.strip().strip(":")
        match = _USE_TOOL_PATTERN.match(candidate)
        if match:
            tool_names.append(match.group(1))

    if agent_name == "verifier" and not tool_names:
        tool_names.append("verifier_evidence_lookup")

    unique_names = []
    for name in tool_names:
        if name not in unique_names:
            unique_names.append(name)
    return [ToolCallSummary(tool_name=name) for name in unique_names]


def _top3_from_pool(pool: list[dict[str, Any]]) -> list[HypothesisScore]:
    scores: list[HypothesisScore] = []
    for item in pool[:3]:
        scores.append(
            HypothesisScore(
                name=str(item.get("name") or ""),
                confidence=float(item.get("confidence") or 0.0),
                rationale=_optional_text(item.get("rationale")),
            )
        )
    return scores


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_top3_inline(top3: list[HypothesisScore]) -> str:
    return ", ".join(f"{item.name}={item.confidence:.3f}" for item in top3)


def _format_tools_inline(tools: list[ToolCallSummary]) -> str:
    parts: list[str] = []
    for tool in tools:
        if tool.parameters:
            parts.append(f"{tool.tool_name}({json.dumps(tool.parameters, ensure_ascii=False, sort_keys=True)})")
        else:
            parts.append(tool.tool_name)
    return ", ".join(parts)
