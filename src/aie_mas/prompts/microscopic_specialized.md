## task_understanding
Interpret the Planner instruction as a microscopic evidence task for the current working hypothesis "{current_hypothesis}": {task_received}
This agent should only characterize local electronic-structure proxies for the requested micro task and should not produce a global mechanism decision.

## execution_plan
Run {baseline_tools} for the requested microscopic task mode "{task_mode}" to obtain S0/S1 proxy results. {targeted_plan}

## result_summary
The microscopic run ({task_mode}) recorded s0_energy={s0_energy}, s1_energy={s1_energy}, rigidity_proxy={rigidity_proxy}, geometry_change_proxy={geometry_change_proxy}, oscillator_strength_proxy={oscillator_strength_proxy}, and relaxation_gap={relaxation_gap}. {targeted_summary}

## remaining_local_uncertainty
Microscopic proxy results alone cannot establish the final mechanism or verifier-aligned conclusion; unresolved local gap: {local_uncertainty_detail}

## planner_readable_report
Task understanding: {task_understanding}
Execution plan: {execution_plan}
Result summary: {result_summary}
Remaining local uncertainty: {remaining_local_uncertainty}
