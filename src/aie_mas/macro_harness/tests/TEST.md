# Macro Harness Test Plan

## Test Inventory Plan

- `tests/test_macro_harness_cli.py`: 3 smoke tests planned
  Current implemented coverage now includes capability discovery, capability contract inspection,
  shared-structure context inspection/validation, JSON error envelope, and REPL default entry.

## Unit / CLI Smoke Plan

### Capability inventory

- Verify the harness can enumerate the bounded macro capability registry
- Confirm key capabilities are present:
  - `screen_neutral_aromatic_structure`
  - `screen_intramolecular_hbond_preorganization`

### Direct screen execution

- Run `screen_neutral_aromatic_structure` against a simple aromatic SMILES
- Verify:
  - command exits successfully
  - JSON is parseable
  - `selected_capability` and `executed_capability` match
  - harness metadata is present

### Capability contract inspection

- Run `capability show screen_intramolecular_hbond_preorganization`
- Verify:
  - capability metadata is returned
  - geometry dependency is explicit
  - input contract is machine-readable

### Shared structure context inspection / validation

- Load a serialized `SharedStructureContext` JSON file
- Verify:
  - key geometry and proxy fields are surfaced
  - path existence is reported
  - validation result distinguishes `errors` vs `warnings`

### JSON error envelope

- Run `screen run` with an invalid capability name
- Verify:
  - exit code is non-zero
  - JSON error envelope contains `success=false`, `error_code`, `message`, and `command_path`

### REPL default path

- Invoke the CLI with no subcommand
- Verify:
  - default mode enters REPL
  - `help` prints example commands
  - `exit` closes cleanly

## Current Scope Limits

- No full E2E packaging/install test yet
- No subprocess-installed-command coverage yet
