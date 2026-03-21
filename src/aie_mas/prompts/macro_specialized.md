## task_understanding
Interpret the Planner instruction as a macro-level structural analysis task for the current working hypothesis "{current_hypothesis}": {task_received}
This agent should only summarize low-cost structural evidence and should not make a global mechanism judgment or recommend a system-level next action.

## execution_plan
Use {tool_name} on the input SMILES to extract aromaticity, hetero-atom, branching, conjugation, and flexibility proxies, then organize the observations as local structural evidence relevant to the received task.

## result_summary
The macro scan recorded aromatic_atom_count={aromatic_atom_count}, hetero_atom_count={hetero_atom_count}, branch_point_count={branch_point_count}, conjugation_proxy={conjugation_proxy}, and flexibility_proxy={flexibility_proxy}.

## remaining_local_uncertainty
Macro evidence alone cannot resolve excited-state relaxation behavior or external consistency; unresolved local gap: {local_uncertainty_detail}

## planner_readable_report
Task understanding: {task_understanding}
Execution plan: {execution_plan}
Result summary: {result_summary}
Remaining local uncertainty: {remaining_local_uncertainty}
