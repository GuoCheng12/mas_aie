# Microscopic Capability Probe

- case_id: 78ed5d49258c
- smiles: COc3ccc(/C(=C(C#N)\c1ccccc1)c2ccccc2)cc3
- user_query: Probe registry-backed microscopic capabilities directly.
- report_dir: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c
- events_recorded: 14

## Current Position
- phase: end
- round: 9
- agent: microscopic
- node: probe_run_targeted_natural_orbital_analysis
- current_hypothesis: None

## Probe Trace

- round=1 stage=structure_prep status=start
  workdir: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle

- round=1 stage=structure_prep status=end
  prepared_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/structure_prep/prepared_structure.xyz
  prepared_sdf_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/structure_prep/prepared_structure.sdf
  prepared_summary_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/structure_prep/structure_prep_summary.json
  atom_count: 41
  charge: 0
  multiplicity: 1
  source: smiles_to_3d

- round=1 stage=s0_optimization status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/78ed5d49258c_probe_r01_s0.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/78ed5d49258c_probe_r01_s0.aop
  keywords: ["atb", "opt", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=1 stage=s0_optimization_subprocess status=start
  pid: 6942
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/78ed5d49258c_probe_r01_s0.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/78ed5d49258c_probe_r01_s0.stderr.log

- round=1 stage=s0_optimization_subprocess status=end
  exit_code: 0
  elapsed_seconds: 0.5223
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/78ed5d49258c_probe_r01_s0.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/work/round_01_run_baseline_bundle/78ed5d49258c_probe_r01_s0.stderr.log

## Probe Results

### Round 1 | microscopic | probe_run_baseline_bundle

- capability_name: run_baseline_bundle

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_01_run_baseline_bundle.json

- error: {"code": "normal_termination_missing", "message": "Amesp step 's0_optimization' did not report normal termination.", "stdout": "  Stop : Please chechk the PATH environmental variable of Amesp !\n \n", "stderr": "/usr/bin/which: no amesp in (/datasets/condaenv/mas_aie/bin:/datasets/miniconda3/condabin:/root/.vscode-server/data/User/globalStorage/github.copilot-chat/debugCommand:/root/.vscode-server/data/User/globalStorage/github.copilot-chat/copilotCli:/root/.vscode-server/cli/servers/Stable-cfbea10c5ffb233ea9177d34726e6056e89913dc/server/bin/remote-cli:/usr/local/sbin:/usr/bin:/bin:/usr/sbin:/sbin:/nix/store/hpvsf3db2q0ij33aw31n953gdkhlmwrg-openssh-10.2p1/bin)\n"}

### Round 2 | microscopic | probe_extract_ct_descriptors_from_bundle

- capability_name: extract_ct_descriptors_from_bundle

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_02_extract_ct_descriptors_from_bundle.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}

### Round 3 | microscopic | probe_run_targeted_state_characterization

- capability_name: run_targeted_state_characterization

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_03_run_targeted_state_characterization.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}

### Round 4 | microscopic | probe_run_targeted_charge_analysis

- capability_name: run_targeted_charge_analysis

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_04_run_targeted_charge_analysis.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}

### Round 5 | microscopic | probe_run_targeted_density_population_analysis

- capability_name: run_targeted_density_population_analysis

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_05_run_targeted_density_population_analysis.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}

### Round 6 | microscopic | probe_run_targeted_transition_dipole_analysis

- capability_name: run_targeted_transition_dipole_analysis

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_06_run_targeted_transition_dipole_analysis.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}

### Round 7 | microscopic | probe_run_ris_state_characterization

- capability_name: run_ris_state_characterization

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_07_run_ris_state_characterization.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}

### Round 8 | microscopic | probe_run_targeted_localized_orbital_analysis

- capability_name: run_targeted_localized_orbital_analysis

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_08_run_targeted_localized_orbital_analysis.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}

### Round 9 | microscopic | probe_run_targeted_natural_orbital_analysis

- capability_name: run_targeted_natural_orbital_analysis

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-140220-413604_78ed5d49258c/probes/round_09_run_targeted_natural_orbital_analysis.json

- error: {"code": "precondition_missing", "message": "No reusable baseline bundle is available for this baseline-dependent capability.", "stdout": null, "stderr": null}
