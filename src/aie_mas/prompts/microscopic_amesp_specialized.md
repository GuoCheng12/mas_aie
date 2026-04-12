## task_completion
{task_completion_text}

## task_understanding
Interpret the Planner instruction as a bounded low-cost microscopic Amesp task. {framing_note} Task received: {task_received}
Requested local focus: {requested_focus}
Requested Amesp route summary: {requested_route_summary}
Requested capability: {requested_capability}
Executed command/capability: {executed_capability}
Translation fulfillment mode: {translation_fulfillment_mode}
Translation binding mode: {translation_binding_mode}
Planner-requested capability: {planner_requested_capability}
Translation substituted action: {translation_substituted_action}
Translation substitution reason: {translation_substitution_reason}
Requested observable tags: {requested_observable_tags_text}
Covered observable tags: {covered_observable_tags_text}
Residual unmet observable tags: {residual_unmet_observable_tags_text}
Performed new calculations: {performed_new_calculations}
Reused existing artifacts only: {reused_existing_artifacts}
Resolved target IDs: {resolved_target_ids_text}
Honored constraints: {honored_constraints_text}
Unmet constraints: {unmet_constraints_text}
Missing deliverables: {missing_deliverables_text}
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
Execute the bounded CLI-backed Amesp route "{capability_route}" as follows: {plan_steps}
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
