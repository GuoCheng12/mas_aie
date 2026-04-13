# AIE-MAS Macro Harness

Formal CLI harness for the bounded `Macro` screening layer in AIE-MAS.

This harness wraps the existing deterministic macro structural registry and exposes
it as a stable command-line tool instead of a one-off stdin execution shim.

## Goals

- Give agents a fixed, discoverable CLI surface for `Macro`
- Keep JSON output stable for orchestration and testing
- Reuse the existing `DeterministicMacroStructureTool` backend instead of
  reimplementing chemistry logic

## Commands

```bash
# List supported bounded macro capabilities
aie-mas-macro capability list --json

# Inspect one capability contract
aie-mas-macro capability show screen_intramolecular_hbond_preorganization --json

# Inspect a serialized shared structure context
aie-mas-macro context inspect /path/to/shared_structure_context.json --json

# Validate a serialized shared structure context
aie-mas-macro context validate /path/to/shared_structure_context.json --json

# Run a capability directly
aie-mas-macro screen run screen_neutral_aromatic_structure \
  --smiles 'c1ccccc1' \
  --json

# Reuse a prepared shared-structure context
aie-mas-macro screen run screen_intramolecular_hbond_preorganization \
  --smiles 'N#N=NCCOc4ccc(/C=N/N=c2c1ccccc1c3ccccc23)c(O)c4' \
  --shared-structure-context-file /path/to/shared_structure_context.json \
  --json
```

## Architecture

- `cli.py`: user-facing CLI surface
- `backend.py`: plan construction and backend execution
- `skills/SKILL.md`: agent-facing usage guidance

## Output

Use `--json` for agent consumption. Results include:

- executed capability
- structural screen payload
- fulfillment status
- observable tags
- harness metadata

On command failure in JSON mode, the CLI returns a unified error envelope:

```json
{
  "success": false,
  "error_code": "invalid_input",
  "message": "...",
  "command_path": "aie-mas-macro screen run",
  "details": {}
}
```
