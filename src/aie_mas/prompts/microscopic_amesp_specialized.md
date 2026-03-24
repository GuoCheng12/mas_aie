## task_completion
{task_completion_text}

## task_understanding
Interpret the Planner instruction as a bounded low-cost microscopic Amesp task for the current working hypothesis "{current_hypothesis}": {task_received}
Requested local focus: {requested_focus}
Recent round context: {recent_context_note}
Capability boundary: {capability_scope}
Structure handling note: {structure_source_note}
Unsupported local requests that will not be executed in this run: {unsupported_requests_note}
This agent may only return local electronic-structure evidence and must not make a global mechanism judgment or recommend the next system action.

## reasoning_summary
Local reasoning summary: {reasoning_summary_text}
Capability limit note: {capability_limit_note}
Failure policy: {failure_policy}

## execution_plan
Execute the real low-cost Amesp baseline workflow as follows: {plan_steps}
Expected outputs from this bounded run: {expected_outputs_text}
If Amesp fails, return the available partial artifacts and local uncertainty only.

## result_summary
{result_summary_text}

## remaining_local_uncertainty
Microscopic local uncertainty after this Amesp run: {local_uncertainty_detail}

## planner_readable_report
Task completion: {task_completion}
Task understanding: {task_understanding}
Reasoning summary: {reasoning_summary}
Execution plan: {execution_plan}
Result summary: {result_summary}
Remaining local uncertainty: {remaining_local_uncertainty}
