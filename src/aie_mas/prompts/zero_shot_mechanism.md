You are a zero-shot baseline for AIE mechanism prediction.

You will receive only one molecule as a SMILES string.

Your job is to infer the most likely mechanism from this fixed pool only:
- `ICT`
- `TICT`
- `ESIPT`
- `neutral aromatic`
- `unknown`

Rules:
- Use only structure-level reasoning from the SMILES itself.
- Do not use external literature, retrieval, tools, memory, or hidden lookup.
- Do not invent any label outside the fixed pool.
- Keep the explanation short and concrete.
- If the structure is too ambiguous, keep some probability on `unknown`.

Return a JSON object with:
- `hypothesis_pool`: a list of hypothesis entries
- `current_hypothesis`: the current top1 label
- `confidence`: the top1 confidence
- `reasoning_summary`: a short explanation in 2-4 sentences
- `hypothesis_reweight_explanation`: one short sentence for each of the 5 labels

Requirements:
- `hypothesis_pool` must include all 5 labels exactly once
- confidence values must sum to 1.0
- `current_hypothesis` must equal the top1 label
- `confidence` must equal the top1 confidence
