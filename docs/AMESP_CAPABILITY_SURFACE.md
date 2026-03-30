# Amesp Capability Surface for AIE-MAS

## Purpose

This document aligns two different layers:

1. The **official Amesp capability surface** described in the Amesp Program Manual, Version 2.1(dev), release date 2025-10-23.
2. The **currently exposed AIE-MAS Amesp action surface** implemented in `AMESP_ACTION_REGISTRY`.

The goal is to make one boundary explicit:

- what Amesp appears to support in principle;
- what AIE-MAS currently exposes to `Microscopic`;
- which gaps are currently architectural limitations rather than chemistry limitations.

This is a capability inventory. It does **not** change the current graph or remove the existing low-cost baseline route.

## Current AIE-MAS Position

The current `Microscopic` worker is intentionally bounded to a small low-cost Amesp surface:

- `run_baseline_bundle`
- `run_conformer_bundle`
- `run_torsion_snapshots`
- `parse_snapshot_outputs`

This boundary is correct for the current workflow because:

- first-round `S0/S1 baseline` must remain available;
- real runs are resource-limited and cannot assume heavy excited-state DFT workflows;
- `Microscopic` should operate as a bounded tool worker, not as an open-ended quantum-chemistry agent.

## Source of Truth

Current code sources:

- `src/aie_mas/tools/amesp.py`
- `src/aie_mas/agents/microscopic/compiler.py`

Manual source used for this inventory:

- Amesp Program Manual, Version 2.1(dev), release date 2025-10-23

## Part I. Official Amesp Capability Surface

The manual shows that Amesp is broader than the currently exposed AIE-MAS worker surface.

### 1. Core Electronic-Structure Methods

According to the manual, Amesp supports:

- HF / DFT families
- MP2 / MP3 / MP4
- CID / CISD / QCISD / CCD / CCSD / CCSD(T)
- CASCI / CASSCF / Full CI
- aTB
- UFF / Amber

Interpretation for AIE-MAS:

- Amesp is not intrinsically limited to the current low-cost aTB-centered routes.
- AIE-MAS currently chooses to expose only a bounded subset.

### 2. Excited-State Methods

Manual sections `5.2 Electronically excited states` and related keywords indicate support for:

- CIS
- TDHF
- TDDFT
- TDA
- TDDFT-ris / TDA-ris
- SOC
- NAC
- `TDA-aTB`

Interpretation for AIE-MAS:

- Amesp has a richer excited-state layer than the current AIE-MAS worker surface.
- The current worker surface does not expose general TDDFT/TDA route selection.
- The current worker surface also does not expose SOC/NAC or explicit excited-state couplings.

### 3. Geometry Optimization

The manual states support for geometry optimization using:

- HF / DFT
- MP2-related methods
- CIS / TDHF / TDDFT / TDA
- CASSCF
- aTB
- `TDA-aTB`
- CPCM / GBSA / gCP
- UFF / Amber

Interpretation for AIE-MAS:

- Amesp in principle supports much more than the current bounded `S0` low-cost optimization.
- The current AIE-MAS route `run_baseline_bundle` uses only the low-cost ground-state part of this space.
- Excited-state relaxation is currently not exposed as a supported worker action.

### 4. Harmonic Frequencies

The manual lists:

- analytic frequencies for HF / DFT / aTB / force-field methods
- numerical hessian for additional methods with analytic gradients

Interpretation for AIE-MAS:

- frequency analysis is currently not exposed to `Microscopic`.
- this is a missing interface, not a manual-level absence.

### 5. Wavefunction Analysis and Properties

The manual explicitly lists:

- Mulliken charges
- Lowdin charges
- Hirshfeld charges
- CM5 charges
- natural orbitals
- Mayer bond order
- Pipek-Mezey and Foster-Boys orbital localization
- wavefunction stability analysis
- molecular electrostatic potential
- electric field
- atomic polarizabilities
- dipole moment
- quadrupole moment

Interpretation for AIE-MAS:

- Amesp clearly supports more property analysis than AIE-MAS currently consumes.
- AIE-MAS currently uses only a very small part of this space, mainly:
  - Mulliken charges
  - vertical excitation energies
  - oscillator strengths
  - limited state-ordering summaries

### 6. Scan and Dynamics-Related Capabilities

The manual explicitly documents:

- rigid / relaxed PES scan
- IRC
- AIMD

Interpretation for AIE-MAS:

- the current `run_torsion_snapshots` route is only a bounded snapshot approximation, not a general scan interface.
- relaxed scan is not currently exposed.
- IRC and AIMD are not currently exposed.

### 7. aTB-Specific Clues Relevant to Future CT Work

The manual also exposes some aTB / excited-state-specific knobs:

- `nstates`
- `root`
- `tdspin`
- `tdmode`
- `charge`
- `mofile`
- `out`
- `etdamax`
- `excdip` for `TDA-aTB`

Interpretation for AIE-MAS:

- there may be raw Amesp outputs that contain more information than the current parse layer uses.
- however, the manual does **not** by itself guarantee that the exact CT descriptors needed by AIE-MAS are already available as stable high-level outputs.

## Part II. Current AIE-MAS Amesp Action Surface

The current worker-visible source of truth is `AMESP_ACTION_REGISTRY`.

### Discovery Actions

#### `list_rotatable_dihedrals`

- Kind: `discovery`
- Purpose: discover stable dihedral IDs before bounded torsion execution
- LLM-facing params:
  - `min_relevance`
  - `include_peripheral`
  - `preferred_bond_types`

What it is for:

- selecting one registry-compliant torsion target
- not running a scan by itself

#### `list_available_conformers`

- Kind: `discovery`
- Purpose: discover stable conformer IDs before conformer execution
- LLM-facing params:
  - `source_round_selector`

#### `list_artifact_bundles`

- Kind: `discovery`
- Purpose: discover reusable artifact bundles before parse-only execution
- LLM-facing params:
  - `artifact_kind`
  - `source_round_selector`

### Execution Actions

#### `run_baseline_bundle`

- Kind: `execution`
- Purpose: low-cost baseline `S0` optimization plus vertical excited-state manifold
- LLM-facing params:
  - `perform_new_calculation`
  - `optimize_ground_state`
  - `reuse_existing_artifacts_only`
  - `state_window`
- Default deliverables:
  - `low-cost aTB S0 geometry optimization`
  - `vertical excited-state manifold characterization`

What it currently gives well:

- bounded first-round `S0/S1` baseline
- bright/dark pattern at the Franck-Condon geometry
- standard artifact bundle registration

Why it must stay:

- the first-round baseline route is part of the current workflow contract
- current resource constraints do not allow heavy excited-state DFT as the default route

#### `run_conformer_bundle`

- Kind: `execution`
- Purpose: bounded conformer follow-up
- LLM-facing params:
  - `perform_new_calculation`
  - `optimize_ground_state`
  - `reuse_existing_artifacts_only`
  - `snapshot_count`
  - `max_conformers`
  - `state_window`
  - `honor_exact_target`
  - `allow_fallback`
  - `conformer_id`
  - `conformer_ids`
  - `source_round_selector`
- Discovery dependency:
  - `list_available_conformers`
- Default deliverables:
  - `bounded conformer vertical-state records`
  - `conformer-sensitivity summary`

What it currently gives well:

- bounded conformer sensitivity of `S1` energy / brightness
- internal evidence against high geometry sensitivity

#### `run_torsion_snapshots`

- Kind: `execution`
- Purpose: bounded torsion snapshots and vertical excitations from a prepared structure
- LLM-facing params:
  - `perform_new_calculation`
  - `optimize_ground_state`
  - `reuse_existing_artifacts_only`
  - `snapshot_count`
  - `angle_offsets_deg`
  - `state_window`
  - `honor_exact_target`
  - `allow_fallback`
  - `dihedral_id`
  - `exclude_dihedral_ids`
  - `prefer_adjacent_to_nsnc_core`
  - `min_relevance`
  - `include_peripheral`
  - `preferred_bond_types`
  - `source_round_selector`
- Discovery dependency:
  - `list_rotatable_dihedrals`
- Default deliverables:
  - `snapshot vertical-state records`
  - `torsion sensitivity summary`

What it currently gives well:

- bounded internal discrimination for `ICT vs TICT`
- direct evidence about dark-state emergence / state reordering under twist

What it is not:

- not a general relaxed PES scan
- not an excited-state torsion relaxation workflow

#### `parse_snapshot_outputs`

- Kind: `execution`
- Purpose: parse existing snapshot artifacts without launching new calculations
- LLM-facing params:
  - `perform_new_calculation`
  - `reuse_existing_artifacts_only`
  - `artifact_kind`
  - `artifact_bundle_id`
  - `source_round_selector`
  - `state_window`
- Discovery dependency:
  - `list_artifact_bundles`
- Default deliverables:
  - `per-snapshot excitation energies`
  - `per-snapshot oscillator strengths`
  - `state-ordering summaries`
- Current explicit unsupported note:
  - dominant-transition and CT/localization proxy extraction may be unavailable

What it currently gives well:

- reuse of existing baseline / torsion / conformer artifacts
- standardized parse-only summaries

What it does **not** currently guarantee:

- explicit CT descriptors
- raw-file inspection semantics
- arbitrary per-round multi-bundle parsing in a single action

#### `unsupported_excited_state_relaxation`

- Kind: `execution`
- Purpose: fail-fast unsupported result
- Meaning:
  - current low-cost excited-state relaxation is intentionally not exposed as a supported worker route

## Part III. High-Value Capability Gaps

These are the most important gaps revealed by the comparison between the manual and the current registry.

### Capability-Unavailability Matrix

This table distinguishes four different meanings of "Microscopic cannot do it now":

| Requested capability / task | Current worker status | Main reason category | Why it is unavailable **now** | What would be needed to make it available |
| --- | --- | --- | --- | --- |
| `run_baseline_bundle` low-cost `S0/S1` baseline | Supported | N/A | This is already the current first-round microscopic route. | Keep as-is. |
| `run_conformer_bundle` bounded conformer sensitivity | Supported | N/A | This is already exposed as a registry-backed bounded follow-up. | Keep as-is. |
| `run_torsion_snapshots` bounded torsion sensitivity | Supported | N/A | This is already exposed as a registry-backed bounded follow-up. | Keep as-is. |
| `parse_snapshot_outputs` standard parse-only reuse | Supported with limits | Result not standardized beyond current summaries | Current implementation guarantees excitation energies, oscillator strengths, and state-ordering summaries, but not richer CT-style observables. | Add stable parse rules and new standardized outputs. |
| Explicit CT-descriptor extraction | Unsupported | Not yet exposed + result not standardized | The current worker surface has no dedicated action for CT descriptors, and `parse_snapshot_outputs` currently reports CT/localization-related fields as unavailable. | A new registry action plus validated raw-file parsing and standardized CT outputs. |
| Direct raw artifact inspection (`.aop`, `.mo`, stdout) | Unsupported | Not yet exposed | No `raw_artifact_inspection` action exists in the registry, so worker execution cannot bind this request safely. | Add a new registry action with explicit input/output contract and safe parsing rules. |
| Rich property-analysis actions (`Lowdin`, `Hirshfeld`, `CM5`, orbital localization, quadrupole, polarizability) | Unsupported | Not yet exposed | The manual-level Amesp surface is broader than the current AIE-MAS worker surface; these properties are not wrapped as worker actions. | Add dedicated registry-backed analysis actions and standardized property outputs. |
| Relaxed torsion scan / relaxed PES scan | Unsupported | Deliberate workflow contraction + likely higher cost | Current worker route is only bounded snapshot torsion follow-up, not a general relaxed scan interface. | Add a new bounded scan action and define acceptable cost/runtime limits. |
| Excited-state relaxation follow-up | Explicitly fail-fast unsupported | Intentionally disabled / not validated | The system intentionally blocks this route with `unsupported_excited_state_relaxation` because low-cost excited-state relaxation has not been validated as a stable worker capability. | Validation work plus a dedicated supported registry action. |
| Heavy full-DFT geometry optimization as default microscopic follow-up | Unsupported in current workflow | Resource / budget policy | The current project contract is bounded, low-cost microscopic evidence collection, and the target systems are too large for this to be a default worker route. | A separate high-cost execution profile and explicit Planner policy change. |
| `IRC` / `TS` / `AIMD` / broad exploratory dynamics workflows | Unsupported | Resource / budget policy + not yet exposed | These are manual-level Amesp families, but they are outside the current low-cost bounded worker contract. | Separate higher-cost worker actions, strong validation, and a changed project policy. |

### Gap 1. Explicit CT-descriptor extraction

What Planner wants in difficult `ICT vs neutral aromatic` cases:

- explicit charge-transfer character evidence
- examples:
  - hole/electron separation proxy
  - state-resolved charge redistribution
  - dominant transition composition
  - excited-state dipole-change proxy

What the current registry gives:

- no explicit action for CT descriptor extraction
- `parse_snapshot_outputs` explicitly returns CT/localization-related fields as unavailable in the current implementation

Interpretation:

- this is currently an **AIE-MAS integration gap**
- it is not yet justified to say the Amesp manual proves the feature is impossible
- but it is justified to say the current worker surface does not support it

### Gap 2. Raw artifact inspection

Planner sometimes needs:

- direct inspection of `.aop`, `.mo`, or detailed stdout-derived quantities

Current state:

- no `raw_artifact_inspection` action exists
- this should remain unsupported unless explicitly added as a new worker capability

### Gap 3. Relaxed torsion / relaxed excited-state follow-up

Manual surface:

- Amesp supports scan / optimization families beyond the current snapshot approximation

Current worker surface:

- only bounded `run_torsion_snapshots`
- excited-state relaxation remains fail-fast unsupported

Interpretation:

- this is a deliberate workflow contraction, not necessarily a manual-level impossibility

### Gap 4. Rich property-analysis actions

Manual surface includes:

- Lowdin / Hirshfeld / CM5
- natural orbitals
- orbital localization
- dipole / quadrupole / polarizability

Current worker surface:

- no dedicated worker action exposes these properties as standardized outputs

Interpretation:

- a future registry extension could expose a subset of these, if they are useful and stable enough for AIE-MAS reasoning

## Part IV. Recommended Immediate Working Model

Before adding new Amesp actions, use this interpretation rule:

- If a task can be represented exactly by an existing registry action, `Microscopic` may execute it.
- If a task depends on a manual-level Amesp feature that is **not yet exposed** in `AMESP_ACTION_REGISTRY`, `Microscopic` must return `action_not_supported_by_registry`.
- Do not silently downgrade unsupported requests into nearby actions.

This keeps the current architecture consistent with the project rule that only `Planner` reasons and all worker agents return bounded tool results.

## Part V. Recommended Next Inventory Step

The next practical step should be a second document:

- `Amesp Capability Surface v2: Candidate Registry Extensions`

That follow-up should answer, action by action:

1. Which manual-supported features are worth exposing to AIE-MAS?
2. Which of those are still compatible with current cost constraints?
3. Which raw files and parse rules would be required?
4. Which outputs can be standardized strongly enough for Planner consumption?

The highest-priority candidate actions are:

### Candidate Action 1. `extract_ct_descriptors_from_bundle`

- Candidate kind: `execution`
- Intended purpose:
  - extract explicit CT-character evidence from an existing registered artifact bundle
  - support difficult `ICT vs neutral aromatic` closure cases without forcing a new heavy calculation route
- Expected input pattern:
  - `artifact_kind`
  - `artifact_bundle_id`
  - `source_round_selector`
  - `state_window`
  - optional bounded `descriptor_scope`
- Expected standardized outputs:
  - `ct_proxy_availability`
  - `dominant_transitions`
  - `ct_localization_proxy`
  - `state_resolved_charge_redistribution`
  - `excited_state_dipole_proxy`
- Likely raw-file dependencies:
  - `.aop`
  - `.mo`
  - stdout / out files
- Why this is first:
  - it is the clearest current blocker in `ICT vs neutral aromatic` closure
  - it reuses existing artifacts, so it is more compatible with current cost constraints than adding a new heavy excited-state route

### Candidate Action 2. `inspect_raw_artifact_bundle`

- Candidate kind: `execution`
- Intended purpose:
  - allow bounded direct inspection of registered Amesp raw outputs when the needed observable is not covered by current standardized parse actions
- Expected input pattern:
  - `artifact_kind`
  - `artifact_bundle_id`
  - `source_round_selector`
  - `requested_observable_scope`
- Expected standardized outputs:
  - `inspection_status`
  - `available_raw_files`
  - `extractable_observables`
  - `missing_observables`
  - `inspection_notes`
- Likely raw-file dependencies:
  - `.aop`
  - `.mo`
  - stdout / out files
  - geometry / summary side products when available
- Why this is second:
  - it gives a controlled interface for low-level raw-file inspection instead of forcing Planner or Microscopic to request ad hoc "read the raw files"
  - it can act as a capability bridge before richer standardized descriptor actions are fully implemented

Recommended ordering:

1. Add `extract_ct_descriptors_from_bundle` first if the immediate bottleneck is `ICT vs neutral aromatic`.
2. Add `inspect_raw_artifact_bundle` next if Amesp raw outputs contain useful signals that cannot yet be normalized into a narrower descriptor action.
