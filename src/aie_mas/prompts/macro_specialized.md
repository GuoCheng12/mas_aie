## task_completion
{task_completion_text}

## task_understanding
Interpret the Planner instruction as a bounded macro-level structural analysis task. {framing_note} Task received: {task_received}
{shared_context_note}
This agent should only summarize low-cost structural evidence and should not make a global mechanism judgment or recommend a system-level next action.

## reasoning_summary
{reasoning_summary_text}
Capability limit note: {capability_limit_note}

## execution_plan
Use {tool_name} to execute the bounded macro workflow with focus areas: {focus_areas_text}. Planned local steps: {plan_steps}

## result_summary
{result_summary_text}
Key proxies: aromatic_atom_count={aromatic_atom_count}, hetero_atom_count={hetero_atom_count}, branch_point_count={branch_point_count}, conjugation_proxy={conjugation_proxy}, flexibility_proxy={flexibility_proxy}, rotatable_bond_count={rotatable_bond_count}, aromatic_ring_count={aromatic_ring_count}, ring_system_count={ring_system_count}, donor_acceptor_partition_proxy={donor_acceptor_partition_proxy}, planarity_proxy={planarity_proxy}, compactness_proxy={compactness_proxy}, conformer_dispersion_proxy={conformer_dispersion_proxy}.

## remaining_local_uncertainty
Macro evidence alone cannot resolve excited-state relaxation behavior or external consistency; unresolved local gap: {local_uncertainty_detail}

## planner_readable_report
Task completion: {task_completion}
Task understanding: {task_understanding}
Reasoning summary: {reasoning_summary}
Execution plan: {execution_plan}
Result summary: {result_summary}
Remaining local uncertainty: {remaining_local_uncertainty}
