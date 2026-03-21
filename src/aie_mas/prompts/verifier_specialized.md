## task_understanding
Interpret the Planner instruction as an external supervision retrieval task for the current working hypothesis "{current_hypothesis}": {task_received}
This agent should only gather and summarize support/conflict evidence cards and should not decide whether the hypothesis should be kept or switched.

## execution_plan
Use {tool_name} to retrieve evidence cards for the current hypothesis, group them by support/conflict/neutral relation, and report only local verification findings.

## result_summary
The verifier retrieved {source_count} evidence card(s): support={support_count}, conflict={conflict_count}, neutral={neutral_count}.

## remaining_local_uncertainty
Verifier evidence cards summarize external supervision but do not replace Planner-level synthesis; unresolved local gap: {local_uncertainty_detail}

## planner_readable_report
Task understanding: {task_understanding}
Execution plan: {execution_plan}
Result summary: {result_summary}
Remaining local uncertainty: {remaining_local_uncertainty}
