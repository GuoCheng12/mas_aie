from __future__ import annotations

import json
import sys
from pathlib import Path

from aie_mas.graph.state import (
    MicroscopicExecutionPlan,
    MicroscopicToolCall,
    MicroscopicToolPlan,
    MicroscopicToolRequest,
)
from aie_mas.agents.microscopic.compiler import _compatibility_route_for_capability_name
from aie_mas.tools.amesp import AmespMicroscopicTool


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    tool_config = dict(payload.get("tool_config") or {})
    amesp_bin = tool_config.get("amesp_bin")
    tool = AmespMicroscopicTool(
        amesp_bin=Path(amesp_bin) if amesp_bin else None,
        npara=tool_config.get("npara") or 1,
        maxcore_mb=tool_config.get("maxcore_mb") or 1000,
        use_ricosx=bool(tool_config.get("use_ricosx", False)),
        s1_nstates=tool_config.get("s1_nstates") or 1,
        td_tout=tool_config.get("td_tout") or 1,
        follow_up_max_conformers=tool_config.get("follow_up_max_conformers") or 3,
        follow_up_max_torsion_snapshots_total=tool_config.get("follow_up_max_torsion_snapshots_total") or 6,
        probe_interval_seconds=tool_config.get("probe_interval_seconds") or 15.0,
    )
    if payload.get("plan") is not None:
        plan = MicroscopicExecutionPlan.model_validate(payload["plan"])
    else:
        request = MicroscopicToolRequest.model_validate(
            payload["microscopic_tool_request"]
        )
        plan = MicroscopicExecutionPlan(
            local_goal=str(payload.get("local_goal") or f"Execute `{request.capability_name}`."),
            requested_deliverables=list(payload.get("requested_deliverables") or request.deliverables),
            capability_route=_compatibility_route_for_capability_name(request.capability_name),
            microscopic_tool_plan=MicroscopicToolPlan(
                calls=[
                    MicroscopicToolCall(
                        call_id=f"execute_{request.capability_name}",
                        call_kind="execution",
                        request=request,
                    )
                ],
                requested_route_summary=str(payload.get("requested_route_summary") or request.requested_route_summary),
                requested_deliverables=list(payload.get("requested_deliverables") or request.deliverables),
                failure_reporting=str(payload.get("failure_reporting") or "Return a local failed report if CLI execution cannot complete."),
            ),
            microscopic_tool_request=request,
            budget_profile=request.budget_profile,
            requested_route_summary=str(payload.get("requested_route_summary") or request.requested_route_summary),
            structure_source=str(payload.get("structure_source") or "existing_prepared_structure"),
            supported_scope=[],
            unsupported_requests=list(payload.get("unsupported_requests") or []),
            fulfillment_mode=payload.get("fulfillment_mode"),
            binding_mode=payload.get("binding_mode"),
            planner_requested_capability=payload.get("planner_requested_capability"),
            translation_substituted_action=bool(payload.get("translation_substituted_action", False)),
            translation_substitution_reason=payload.get("translation_substitution_reason"),
            requested_observable_tags=list(payload.get("requested_observable_tags") or []),
            expected_outputs=list(payload.get("expected_outputs") or []),
            failure_reporting=str(payload.get("failure_reporting") or "Return a local failed report if CLI execution cannot complete."),
        )
    result = tool.execute(
        plan=plan,
        smiles=str(payload["smiles"]),
        label=str(payload["label"]),
        workdir=Path(payload["workdir"]),
        available_artifacts=dict(payload.get("available_artifacts") or {}),
        round_index=int(payload.get("round_index") or 1),
        case_id=payload.get("case_id"),
        current_hypothesis=payload.get("current_hypothesis"),
    )
    sys.stdout.write(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))


if __name__ == "__main__":
    main()
