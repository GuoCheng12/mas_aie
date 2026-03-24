## task_understanding
Interpret the Planner instruction as an external supervision retrieval task for the current working hypothesis "{current_hypothesis}": {task_received}
This agent should only retrieve and summarize relevant raw evidence cards and should not decide whether the hypothesis should be kept, switched, supported, or conflicted.

## execution_plan
Use {tool_name} to retrieve raw evidence cards for the current hypothesis, summarize the retrieved topics, and report only local verification findings.

## result_summary
The verifier retrieved {source_count} evidence card(s) covering these topics: {topic_summary}.

## remaining_local_uncertainty
Verifier evidence cards summarize external supervision but do not replace Planner-level synthesis; unresolved local gap: {local_uncertainty_detail}

## planner_readable_report
Task understanding: {task_understanding}
Execution plan: {execution_plan}
Result summary: {result_summary}
Remaining local uncertainty: {remaining_local_uncertainty}
