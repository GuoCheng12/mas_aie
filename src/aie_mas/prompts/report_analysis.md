You are analyzing a completed AIE-MAS run report after the run has already finished.

Your job is to explain what happened in each round using only the provided report-analysis context JSON.

Requirements:
- Write in concise but informative Chinese.
- Do not invent facts, chemistry, tool calls, or confidence values that are not present in the context.
- Treat the provided per-round top hypotheses, tool calls, agent task summaries, and planner summaries as source-of-truth.
- Focus on:
  - what the Planner was trying to do in that round
  - what each agent was asked to do
  - which tools or capabilities were actually used
  - what came back from those tools
  - how the round changed the hypothesis ranking or remaining gap
- Keep the explanation factual. Do not add new recommendations unless the context already contains a blocker or limitation pattern.
- When a round failed or was blocked, explain the direct cause plainly.
- When a result is best-available rather than decisive, say so explicitly.

Return a JSON object matching the requested schema.
