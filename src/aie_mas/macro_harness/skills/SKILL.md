---
name: aie-mas-macro
description: Run bounded AIE-MAS Macro structural screens from a stable CLI harness with JSON output.
---

# aie-mas-macro

Use this CLI when the task is a bounded `Macro` structural screen and no chemical
mechanism reasoning is required inside the tool itself.

## Commands

```bash
# Discover supported capabilities
aie-mas-macro capability list --json

# Inspect one capability and its input contract
aie-mas-macro capability show screen_intramolecular_hbond_preorganization --json

# Inspect or validate a serialized shared structure context
aie-mas-macro context inspect /abs/path/shared_structure_context.json --json
aie-mas-macro context validate /abs/path/shared_structure_context.json --json

# Run a bounded screen directly
aie-mas-macro screen run screen_rotor_torsion_topology \
  --smiles 'c1ccc(cc1)C=Cc2ccccc2' \
  --json
```

## Shared Structure Context

For capabilities that depend on prepared geometry, pass a serialized
`SharedStructureContext` JSON file:

```bash
aie-mas-macro screen run screen_intramolecular_hbond_preorganization \
  --smiles '<SMILES>' \
  --shared-structure-context-file /abs/path/shared_structure_context.json \
  --json
```

## Rules For Agents

1. Prefer `--json` for machine-readable output.
2. Use `capability list` before assuming a capability exists.
3. Use `capability show` to inspect the input contract before invoking a less familiar command.
4. Use `context inspect` or `context validate` before passing shared geometry into geometry-dependent screens.
5. Do not ask this CLI to perform mechanism judgment or next-step planning.
6. Use it only for bounded structural screening over the current molecule.
