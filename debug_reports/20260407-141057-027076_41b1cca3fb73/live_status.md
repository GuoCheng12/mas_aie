# Microscopic Capability Probe

- case_id: 41b1cca3fb73
- smiles: COc3ccc(/C(=C(C#N)\c1ccccc1)c2ccccc2)cc3
- user_query: Probe registry-backed microscopic capabilities directly.
- report_dir: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73
- events_recorded: 87

## Current Position
- phase: end
- round: 9
- agent: microscopic
- node: probe_run_targeted_natural_orbital_analysis
- current_hypothesis: None

## Probe Trace

- round=4 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.209826441, "oscillator_strength": 0.2875, "spin_square": 0.0, "excitation_energy_ev": 3.6776, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6896806}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": 0.1189106}]}, {"state_index": 2, "total_energy_hartree": -966.179401005, "oscillator_strength": 0.3353, "spin_square": 0.0, "excitation_energy_ev": 4.5055, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.1192603}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": -0.1059693}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6727501}]}]
  first_excitation_energy_ev: 3.6776
  first_oscillator_strength: 0.2875
  state_count: 2

- round=5 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=5 stage=s0_singlepoint_subprocess status=start
  pid: 11505
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.stderr.log

- round=5 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 0.5227
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.stderr.log

- round=5 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 0.5227

- round=5 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -50.8834862462
  dipole_debye: [7.1571, -2.2931, -3.2106, 8.1725]
  mulliken_charges: [0.326736, -0.494297, 0.528032, -0.211373, -0.023592, -0.019541, 0.055506, -0.043212, 0.610949, -0.754222, 0.070704, -0.07564, -0.021878, -0.037978, -0.015497, -0.063012, 0.046066, -0.045956, -0.009117, -0.024796, -0.021931, -0.059384, -0.027712, -0.154599, -0.010558, -0.00999, 0.003565, 0.043718, 0.032441, 0.030447, 0.030197, 0.029649, 0.03155, 0.041312, 0.039185, 0.033605, 0.029542, 0.029784, 0.030398, 0.033615, 0.047284]
  homo_lumo_gap_ev: 2.2192349
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=5 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "td", "RICOSX"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=5 stage=s1_vertical_excitation_subprocess status=start
  pid: 11537
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.stderr.log

- round=5 stage=s1_vertical_excitation_subprocess status=running
  pid: 11537
  elapsed_seconds: 15.01
  aop_exists: true
  aop_size_bytes: 9553
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 5  -9.66342215E+02  -2.41E-01   3.77E-03   1.30E-02    0.02

- round=5 stage=s1_vertical_excitation_subprocess status=running
  pid: 11537
  elapsed_seconds: 30.04
  aop_exists: true
  aop_size_bytes: 15885
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 5     0.00021575        20         0.023

- round=5 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 31.5772
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.stderr.log

- round=5 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_05_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r05_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 31.5772

- round=5 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.209826461, "oscillator_strength": 0.2875, "spin_square": 0.0, "excitation_energy_ev": 3.6776, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6896806}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": 0.1189106}]}, {"state_index": 2, "total_energy_hartree": -966.179401025, "oscillator_strength": 0.3353, "spin_square": 0.0, "excitation_energy_ev": 4.5055, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.1192603}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": -0.1059693}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6727501}]}]
  first_excitation_energy_ev: 3.6776
  first_oscillator_strength: 0.2875
  state_count: 2

- round=6 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=6 stage=s0_singlepoint_subprocess status=start
  pid: 11865
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.stderr.log

- round=6 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 0.5232
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.stderr.log

- round=6 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 0.5232

- round=6 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -50.8834862462
  dipole_debye: [7.1571, -2.2931, -3.2106, 8.1725]
  mulliken_charges: [0.326736, -0.494297, 0.528032, -0.211373, -0.023592, -0.019541, 0.055506, -0.043212, 0.610949, -0.754222, 0.070704, -0.07564, -0.021878, -0.037978, -0.015497, -0.063012, 0.046066, -0.045956, -0.009117, -0.024796, -0.021931, -0.059384, -0.027712, -0.154599, -0.010558, -0.00999, 0.003565, 0.043718, 0.032441, 0.030447, 0.030197, 0.029649, 0.03155, 0.041312, 0.039185, 0.033605, 0.029542, 0.029784, 0.030398, 0.033615, 0.047284]
  homo_lumo_gap_ev: 2.2192349
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=6 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.aop
  keywords: ["atb", "tda"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=6 stage=s1_vertical_excitation_subprocess status=start
  pid: 11902
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.stderr.log

- round=6 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 0.5256
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.stderr.log

- round=6 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r06_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 0.5256

- round=6 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -50.658374233, "oscillator_strength": 0.3149, "spin_square": 0.0, "excitation_energy_ev": 2.9563, "dominant_transitions": [{"occupied_orbital": 58, "virtual_orbital": 59, "coefficient": 0.6756488}, {"occupied_orbital": 57, "virtual_orbital": 59, "coefficient": -0.1473557}]}, {"state_index": 2, "total_energy_hartree": -50.638894606, "oscillator_strength": 0.2941, "spin_square": 0.0, "excitation_energy_ev": 3.4864, "dominant_transitions": [{"occupied_orbital": 58, "virtual_orbital": 59, "coefficient": -0.1349126}, {"occupied_orbital": 58, "virtual_orbital": 60, "coefficient": 0.1265626}, {"occupied_orbital": 57, "virtual_orbital": 59, "coefficient": -0.6630148}]}]
  first_excitation_energy_ev: 2.9563
  first_oscillator_strength: 0.3149
  state_count: 2

- round=7 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=7 stage=s0_singlepoint_subprocess status=start
  pid: 11930
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.stderr.log

- round=7 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 0.5264
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.stderr.log

- round=7 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 0.5264

- round=7 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -50.8834862462
  dipole_debye: [7.1571, -2.2931, -3.2106, 8.1725]
  mulliken_charges: [0.326736, -0.494297, 0.528032, -0.211373, -0.023592, -0.019541, 0.055506, -0.043212, 0.610949, -0.754222, 0.070704, -0.07564, -0.021878, -0.037978, -0.015497, -0.063012, 0.046066, -0.045956, -0.009117, -0.024796, -0.021931, -0.059384, -0.027712, -0.154599, -0.010558, -0.00999, 0.003565, 0.043718, 0.032441, 0.030447, 0.030197, 0.029649, 0.03155, 0.041312, 0.039185, 0.033605, 0.029542, 0.029784, 0.030398, 0.033615, 0.047284]
  homo_lumo_gap_ev: 2.2192349
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=7 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "tda-ris"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=7 stage=s1_vertical_excitation_subprocess status=start
  pid: 11961
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.stderr.log

- round=7 stage=s1_vertical_excitation_subprocess status=running
  pid: 11961
  elapsed_seconds: 15.01
  aop_exists: true
  aop_size_bytes: 9091
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 11  -9.66334680E+02  -2.32E-08   1.33E-06   4.54E-06    0.01

- round=7 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 16.5499
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.stderr.log

- round=7 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r07_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 16.5499

- round=7 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.196815074, "oscillator_strength": 0.3693, "spin_square": 0.0, "excitation_energy_ev": 3.7515, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6715221}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.1590257}]}, {"state_index": 2, "total_energy_hartree": -966.166722053, "oscillator_strength": 0.4023, "spin_square": 0.0, "excitation_energy_ev": 4.5704, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": -0.1503974}, {"occupied_orbital": 82, "virtual_orbital": 84, "coefficient": 0.1149491}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": 0.1202947}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6447063}, {"occupied_orbital": 76, "virtual_orbital": 83, "coefficient": 0.1184951}]}]
  first_excitation_energy_ev: 3.7515
  first_oscillator_strength: 0.3693
  state_count: 2

- round=8 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r08_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r08_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=8 stage=s0_singlepoint_subprocess status=start
  pid: 12126
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r08_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r08_baseline_bundle_char_s0sp.stderr.log

- round=8 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 0.5253
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r08_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r08_baseline_bundle_char_s0sp.stderr.log

- round=9 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r09_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r09_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=9 stage=s0_singlepoint_subprocess status=start
  pid: 12139
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r09_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r09_baseline_bundle_char_s0sp.stderr.log

- round=9 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 0.5253
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r09_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/41b1cca3fb73_probe_r09_baseline_bundle_char_s0sp.stderr.log

## Probe Results

### Round 1 | microscopic | probe_run_baseline_bundle

- capability_name: run_baseline_bundle

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_01_run_baseline_bundle.json

- result_summary: {"route": "baseline_bundle", "executed_capability": "run_baseline_bundle", "requested_capability": "run_baseline_bundle", "performed_new_calculations": true, "reused_existing_artifacts": false, "resolved_target_ids": {}, "missing_deliverables": []}

- route_summary: {"state_count": 2, "lowest_state_energy_ev": 3.6776, "first_bright_state_index": 1, "first_bright_state_energy_ev": 3.6776, "first_bright_state_oscillator_strength": 0.2875, "lowest_state_to_brightest_pattern": "lowest_state_is_bright", "oscillator_strength_summary": {"sum": 0.6228, "max": 0.3353}}

### Round 2 | microscopic | probe_extract_ct_descriptors_from_bundle

- capability_name: extract_ct_descriptors_from_bundle

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_02_extract_ct_descriptors_from_bundle.json

- result_summary: {"route": "artifact_parse_only", "executed_capability": "extract_ct_descriptors_from_bundle", "requested_capability": "extract_ct_descriptors_from_bundle", "performed_new_calculations": false, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": ["hole-electron-centroid-separation", "hole-electron-overlap", "qCT/charge transferred", "ct overlap index", "mulliken charges summary"]}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["hole-electron-centroid-separation", "hole-electron-overlap", "qCT/charge_transferred", "ct_overlap_index", "mulliken_charges_summary"], "ct_proxy_availability": "partial_observable_only", "available_ct_surrogates": ["dominant_transitions", "ground_state_dipole", "mulliken_charges", "oscillator_strengths", "state_ordering", "vertical_excitation_energies"], "missing_ct_descriptors": ["hole-electron-centroid-separation", "hole-electron-overlap", "qCT/charge_transferred", "ct_overlap_index", "mulliken_charges_summary"], "artifact_reuse_note": "Inspected an existing artifact bundle for bounded CT-descriptor surrogates without generating new Amesp inputs.", "state_window": [1, 2]}

### Round 3 | microscopic | probe_run_targeted_state_characterization

- capability_name: run_targeted_state_characterization

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_03_run_targeted_state_characterization.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_state_characterization", "requested_capability": "run_targeted_state_characterization", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": ["natural transition orbitals", "attachment detachment", "hole particle analysis", "hole electron separation", "hole electron overlap", "qct"]}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["dominant_transitions", "natural_transition_orbitals", "attachment_detachment", "hole_particle_analysis", "hole_electron_separation", "hole_electron_overlap", "qct", "state_family_overlap"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "state_characterization_availability": "proxy_only", "available_state_character_descriptors": ["dominant_transitions", "state_family_overlap"], "missing_state_character_descriptors": ["natural_transition_orbitals", "attachment_detachment", "hole_particle_analysis", "hole_electron_separation", "hole_electron_overlap", "qct"], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2], "shared_first_state_virtual_orbitals": [83], "shared_first_bright_state_virtual_orbitals": [83]}

### Round 4 | microscopic | probe_run_targeted_charge_analysis

- capability_name: run_targeted_charge_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_04_run_targeted_charge_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_charge_analysis", "requested_capability": "run_targeted_charge_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": ["Mulliken charges"]}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["hirshfeld_charges", "mulliken_charges", "ground_state_dipole"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "charge_availability": "proxy_only", "available_charge_observables": ["ground_state_dipole", "hirshfeld_charges"], "missing_charge_observables": ["mulliken_charges"], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 5 | microscopic | probe_run_targeted_density_population_analysis

- capability_name: run_targeted_density_population_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_05_run_targeted_density_population_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_density_population_analysis", "requested_capability": "run_targeted_density_population_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["density_matrix", "gross_orbital_populations", "mayer_bond_order"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "density_population_availability": "proxy_only", "available_density_population_observables": ["density_matrix", "gross_orbital_populations", "mayer_bond_order"], "missing_density_population_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 6 | microscopic | probe_run_targeted_transition_dipole_analysis

- capability_name: run_targeted_transition_dipole_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_06_run_targeted_transition_dipole_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_transition_dipole_analysis", "requested_capability": "run_targeted_transition_dipole_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["ground_to_excited_transition_dipoles", "excited_to_excited_transition_dipoles"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "transition_dipole_availability": "proxy_only", "available_transition_dipole_observables": ["excited_to_excited_transition_dipoles", "ground_to_excited_transition_dipoles"], "missing_transition_dipole_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 7 | microscopic | probe_run_ris_state_characterization

- capability_name: run_ris_state_characterization

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_07_run_ris_state_characterization.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_ris_state_characterization", "requested_capability": "run_ris_state_characterization", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["dominant_transitions", "state_family_overlap", "ground_state_dipole", "mulliken_charges", "molecular_orbital_files"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "ris_state_characterization_availability": "proxy_only", "available_ris_state_characterization_observables": ["dominant_transitions", "ground_state_dipole", "molecular_orbital_files", "mulliken_charges", "state_family_overlap"], "missing_ris_state_characterization_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 8 | microscopic | probe_run_targeted_localized_orbital_analysis

- capability_name: run_targeted_localized_orbital_analysis

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_08_run_targeted_localized_orbital_analysis.json

- error: {"code": "normal_termination_missing", "message": "Amesp step 's0_singlepoint' did not report normal termination.", "stdout": "  Stop : error keyword: \"lmo\" in >ope!\n \n", "stderr": ""}

### Round 9 | microscopic | probe_run_targeted_natural_orbital_analysis

- capability_name: run_targeted_natural_orbital_analysis

- status: failed

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-141057-027076_41b1cca3fb73/probes/round_09_run_targeted_natural_orbital_analysis.json

- error: {"code": "normal_termination_missing", "message": "Amesp step 's0_singlepoint' did not report normal termination.", "stdout": "  Stop : error keyword: \"natorb\" in >ope!\n \n", "stderr": ""}
