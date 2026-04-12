from __future__ import annotations

import json
import sys

from aie_mas.graph.state import MacroExecutionPlan, SharedStructureContext
from aie_mas.tools.macro import DeterministicMacroStructureTool


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    selected_capability = str(payload.get("selected_capability") or "")
    requested_deliverables = list(payload.get("requested_deliverables") or [])
    requested_observable_tags = list(payload.get("requested_observable_tags") or [])
    binding_mode = payload.get("binding_mode")
    smiles = str(payload["smiles"])
    shared_structure_context = (
        SharedStructureContext.model_validate(payload["shared_structure_context"])
        if payload.get("shared_structure_context") is not None
        else None
    )
    plan = MacroExecutionPlan(
        local_goal=f"Execute bounded macro CLI action `{selected_capability}`.",
        requested_deliverables=requested_deliverables,
        structure_source="shared_prepared_structure" if shared_structure_context is not None else "smiles_only_fallback",
        selected_capability=selected_capability or None,
        binding_mode=binding_mode,
        requested_observable_tags=requested_observable_tags,
        resolved_target_ids={"structure_source": "shared_prepared_structure" if shared_structure_context is not None else "smiles_only_fallback"},
        expected_outputs=requested_deliverables,
        failure_reporting="Return a local failed report if macro CLI execution cannot complete.",
    )
    result = DeterministicMacroStructureTool().execute_local(
        plan=plan,
        smiles=smiles,
        shared_structure_context=shared_structure_context,
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
