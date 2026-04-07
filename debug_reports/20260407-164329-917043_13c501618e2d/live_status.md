# Microscopic Capability Probe

- case_id: 13c501618e2d
- smiles: COc3ccc(/C(=C(C#N)\c1ccccc1)c2ccccc2)cc3
- user_query: Probe registry-backed microscopic capabilities directly.
- report_dir: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d
- events_recorded: 111

## Current Position
- phase: end
- round: 9
- agent: microscopic
- node: probe_run_targeted_natural_orbital_analysis
- current_hypothesis: None

## Probe Trace

- round=6 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 1.0215
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r06_baseline_bundle_char_s1.stderr.log

- round=6 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r06_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r06_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r06_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_06_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r06_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 1.0215

- round=6 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -50.658374232, "oscillator_strength": 0.3149, "spin_square": 0.0, "excitation_energy_ev": 2.9563, "dominant_transitions": [{"occupied_orbital": 58, "virtual_orbital": 59, "coefficient": 0.6756488}, {"occupied_orbital": 57, "virtual_orbital": 59, "coefficient": -0.1473557}]}, {"state_index": 2, "total_energy_hartree": -50.638894605, "oscillator_strength": 0.2941, "spin_square": 0.0, "excitation_energy_ev": 3.4864, "dominant_transitions": [{"occupied_orbital": 58, "virtual_orbital": 59, "coefficient": -0.1349126}, {"occupied_orbital": 58, "virtual_orbital": 60, "coefficient": 0.1265626}, {"occupied_orbital": 57, "virtual_orbital": 59, "coefficient": -0.6630148}]}]
  first_excitation_energy_ev: 2.9563
  first_oscillator_strength: 0.3149
  state_count: 2

- round=7 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=7 stage=s0_singlepoint_subprocess status=start
  pid: 105472
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.stderr.log

- round=7 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 1.0226
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.stderr.log

- round=7 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 1.0226

- round=7 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -50.8834862462
  dipole_debye: [7.1571, -2.2931, -3.2106, 8.1725]
  mulliken_charges: [0.326736, -0.494297, 0.528032, -0.211373, -0.023592, -0.019541, 0.055506, -0.043212, 0.610949, -0.754222, 0.070704, -0.07564, -0.021878, -0.037978, -0.015497, -0.063012, 0.046066, -0.045956, -0.009117, -0.024796, -0.021931, -0.059384, -0.027712, -0.154599, -0.010558, -0.00999, 0.003565, 0.043718, 0.032441, 0.030447, 0.030197, 0.029649, 0.03155, 0.041312, 0.039185, 0.033605, 0.029542, 0.029784, 0.030398, 0.033615, 0.047284]
  homo_lumo_gap_ev: 2.2192349
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=7 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "tda-ris"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=7 stage=s1_vertical_excitation_subprocess status=start
  pid: 105506
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.stderr.log

- round=7 stage=s1_vertical_excitation_subprocess status=running
  pid: 105506
  elapsed_seconds: 15.09
  aop_exists: true
  aop_size_bytes: 8341
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: Cycle      Energy       Delta-E    RMS-DDen   DIIS_ER  time(min)

- round=7 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 24.2752
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.stderr.log

- round=7 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_07_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r07_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 24.2752

- round=7 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.196815073, "oscillator_strength": 0.3693, "spin_square": 0.0, "excitation_energy_ev": 3.7515, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6715221}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.1590257}]}, {"state_index": 2, "total_energy_hartree": -966.166722052, "oscillator_strength": 0.4023, "spin_square": 0.0, "excitation_energy_ev": 4.5704, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": -0.1503974}, {"occupied_orbital": 82, "virtual_orbital": 84, "coefficient": 0.1149491}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": 0.1202947}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6447063}, {"occupied_orbital": 76, "virtual_orbital": 83, "coefficient": 0.1184951}]}]
  first_excitation_energy_ev: 3.7515
  first_oscillator_strength: 0.3693
  state_count: 2

- round=8 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.aop
  keywords: ["b3lyp", "sto-3g"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=8 stage=s0_singlepoint_subprocess status=start
  pid: 105752
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.stderr.log

- round=8 stage=s0_singlepoint_subprocess status=running
  pid: 105752
  elapsed_seconds: 15.0
  aop_exists: true
  aop_size_bytes: 8120
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: Initial guess generation...    Initial guess : harris

- round=8 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 27.6118
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.stderr.log

- round=8 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 27.6118

- round=8 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -966.3346803841
  dipole_debye: [4.7079, -1.9795, -1.5695, 5.3429]
  mulliken_charges: [-0.10267, -0.1836, 0.113779, -0.12159, -0.071715, -0.020555, 0.017829, -0.021915, 0.054802, -0.192195, 0.002504, -0.079307, -0.082721, -0.08367, -0.081703, -0.083589, -0.004271, -0.077003, -0.079405, -0.079787, -0.082137, -0.079188, -0.078899, -0.100365, 0.091291, 0.091608, 0.102625, 0.082591, 0.09218, 0.091021, 0.083555, 0.083766, 0.085046, 0.091842, 0.094761, 0.087554, 0.085947, 0.084859, 0.08974, 0.08967, 0.089317]
  homo_lumo_gap_ev: 3.9449045
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=8 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "td", "RICOSX"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=8 stage=s1_vertical_excitation_subprocess status=start
  pid: 106113
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.stderr.log

- round=8 stage=s1_vertical_excitation_subprocess status=running
  pid: 106113
  elapsed_seconds: 15.0
  aop_exists: true
  aop_size_bytes: 9617
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 6  -9.66344636E+02  -2.42E-03   3.13E-04   3.68E-03    0.02

- round=8 stage=s1_vertical_excitation_subprocess status=running
  pid: 106113
  elapsed_seconds: 30.03
  aop_exists: true
  aop_size_bytes: 15838
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 4     0.00084958        16         0.028

- round=8 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 33.5685
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.stderr.log

- round=8 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_08_run_targeted_localized_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r08_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 33.5685

- round=8 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.209826746, "oscillator_strength": 0.2875, "spin_square": 0.0, "excitation_energy_ev": 3.6776, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6896806}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": 0.1189106}]}, {"state_index": 2, "total_energy_hartree": -966.17940131, "oscillator_strength": 0.3353, "spin_square": 0.0, "excitation_energy_ev": 4.5055, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.1192603}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": -0.1059693}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6727501}]}]
  first_excitation_energy_ev: 3.6776
  first_oscillator_strength: 0.2875
  state_count: 2

- round=9 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.aop
  keywords: ["b3lyp", "sto-3g"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=9 stage=s0_singlepoint_subprocess status=start
  pid: 106538
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.stderr.log

- round=9 stage=s0_singlepoint_subprocess status=running
  pid: 106538
  elapsed_seconds: 15.0
  aop_exists: true
  aop_size_bytes: 8808
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 7  -9.66334609E+02  -8.21E-05   6.33E-05   1.07E-03    0.01

- round=9 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 20.5595
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.stderr.log

- round=9 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 20.5595

- round=9 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -966.3346803841
  dipole_debye: [4.7079, -1.9795, -1.5695, 5.3429]
  mulliken_charges: [-0.10267, -0.1836, 0.113779, -0.12159, -0.071715, -0.020555, 0.017829, -0.021915, 0.054802, -0.192195, 0.002504, -0.079307, -0.082721, -0.08367, -0.081703, -0.083589, -0.004271, -0.077003, -0.079405, -0.079787, -0.082137, -0.079188, -0.078899, -0.100365, 0.091291, 0.091608, 0.102625, 0.082591, 0.09218, 0.091021, 0.083555, 0.083766, 0.085046, 0.091842, 0.094761, 0.087554, 0.085947, 0.084859, 0.08974, 0.08967, 0.089317]
  homo_lumo_gap_ev: 3.9449045
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=9 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "td", "RICOSX"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=9 stage=s1_vertical_excitation_subprocess status=start
  pid: 106821
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.stderr.log

- round=9 stage=s1_vertical_excitation_subprocess status=running
  pid: 106821
  elapsed_seconds: 15.0
  aop_exists: true
  aop_size_bytes: 9617
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 6  -9.66344636E+02  -2.42E-03   3.13E-04   3.68E-03    0.02

- round=9 stage=s1_vertical_excitation_subprocess status=running
  pid: 106821
  elapsed_seconds: 30.03
  aop_exists: true
  aop_size_bytes: 15838
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 4     0.00084958        16         0.029

- round=9 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 33.5773
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.stderr.log

- round=9 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/work/round_09_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/13c501618e2d_probe_r09_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 33.5773

- round=9 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.209826725, "oscillator_strength": 0.2875, "spin_square": 0.0, "excitation_energy_ev": 3.6776, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6896806}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": 0.1189106}]}, {"state_index": 2, "total_energy_hartree": -966.179401288, "oscillator_strength": 0.3353, "spin_square": 0.0, "excitation_energy_ev": 4.5055, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.1192603}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": -0.1059693}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6727501}]}]
  first_excitation_energy_ev: 3.6776
  first_oscillator_strength: 0.2875
  state_count: 2

## Probe Results

### Round 1 | microscopic | probe_run_baseline_bundle

- capability_name: run_baseline_bundle

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_01_run_baseline_bundle.json

- result_summary: {"route": "baseline_bundle", "executed_capability": "run_baseline_bundle", "requested_capability": "run_baseline_bundle", "performed_new_calculations": true, "reused_existing_artifacts": false, "resolved_target_ids": {}, "missing_deliverables": []}

- route_summary: {"state_count": 2, "lowest_state_energy_ev": 3.6776, "first_bright_state_index": 1, "first_bright_state_energy_ev": 3.6776, "first_bright_state_oscillator_strength": 0.2875, "lowest_state_to_brightest_pattern": "lowest_state_is_bright", "oscillator_strength_summary": {"sum": 0.6228, "max": 0.3353}}

### Round 2 | microscopic | probe_extract_ct_descriptors_from_bundle

- capability_name: extract_ct_descriptors_from_bundle

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_02_extract_ct_descriptors_from_bundle.json

- result_summary: {"route": "artifact_parse_only", "executed_capability": "extract_ct_descriptors_from_bundle", "requested_capability": "extract_ct_descriptors_from_bundle", "performed_new_calculations": false, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": ["hole-electron-centroid-separation", "hole-electron-overlap", "qCT/charge transferred", "ct overlap index", "mulliken charges summary"]}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["hole-electron-centroid-separation", "hole-electron-overlap", "qCT/charge_transferred", "ct_overlap_index", "mulliken_charges_summary"], "ct_proxy_availability": "partial_observable_only", "available_ct_surrogates": ["dominant_transitions", "ground_state_dipole", "mulliken_charges", "oscillator_strengths", "state_ordering", "vertical_excitation_energies"], "missing_ct_descriptors": ["hole-electron-centroid-separation", "hole-electron-overlap", "qCT/charge_transferred", "ct_overlap_index", "mulliken_charges_summary"], "artifact_reuse_note": "Inspected an existing artifact bundle for bounded CT-descriptor surrogates without generating new Amesp inputs.", "state_window": [1, 2]}

### Round 3 | microscopic | probe_run_targeted_state_characterization

- capability_name: run_targeted_state_characterization

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_03_run_targeted_state_characterization.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_state_characterization", "requested_capability": "run_targeted_state_characterization", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": ["natural transition orbitals", "attachment detachment", "hole particle analysis", "hole electron separation", "hole electron overlap", "qct"]}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["dominant_transitions", "natural_transition_orbitals", "attachment_detachment", "hole_particle_analysis", "hole_electron_separation", "hole_electron_overlap", "qct", "state_family_overlap"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "state_characterization_availability": "proxy_only", "available_state_character_descriptors": ["dominant_transitions", "state_family_overlap"], "missing_state_character_descriptors": ["natural_transition_orbitals", "attachment_detachment", "hole_particle_analysis", "hole_electron_separation", "hole_electron_overlap", "qct"], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2], "shared_first_state_virtual_orbitals": [83], "shared_first_bright_state_virtual_orbitals": [83]}

### Round 4 | microscopic | probe_run_targeted_charge_analysis

- capability_name: run_targeted_charge_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_04_run_targeted_charge_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_charge_analysis", "requested_capability": "run_targeted_charge_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": ["Mulliken charges"]}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["hirshfeld_charges", "mulliken_charges", "ground_state_dipole"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "charge_availability": "proxy_only", "available_charge_observables": ["ground_state_dipole", "hirshfeld_charges"], "missing_charge_observables": ["mulliken_charges"], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 5 | microscopic | probe_run_targeted_density_population_analysis

- capability_name: run_targeted_density_population_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_05_run_targeted_density_population_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_density_population_analysis", "requested_capability": "run_targeted_density_population_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["density_matrix", "gross_orbital_populations", "mayer_bond_order"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "density_population_availability": "proxy_only", "available_density_population_observables": ["density_matrix", "gross_orbital_populations", "mayer_bond_order"], "missing_density_population_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 6 | microscopic | probe_run_targeted_transition_dipole_analysis

- capability_name: run_targeted_transition_dipole_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_06_run_targeted_transition_dipole_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_transition_dipole_analysis", "requested_capability": "run_targeted_transition_dipole_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["ground_to_excited_transition_dipoles", "excited_to_excited_transition_dipoles"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "transition_dipole_availability": "proxy_only", "available_transition_dipole_observables": ["excited_to_excited_transition_dipoles", "ground_to_excited_transition_dipoles"], "missing_transition_dipole_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 7 | microscopic | probe_run_ris_state_characterization

- capability_name: run_ris_state_characterization

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_07_run_ris_state_characterization.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_ris_state_characterization", "requested_capability": "run_ris_state_characterization", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["dominant_transitions", "state_family_overlap", "ground_state_dipole", "mulliken_charges", "molecular_orbital_files"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "ris_state_characterization_availability": "proxy_only", "available_ris_state_characterization_observables": ["dominant_transitions", "ground_state_dipole", "molecular_orbital_files", "mulliken_charges", "state_family_overlap"], "missing_ris_state_characterization_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 8 | microscopic | probe_run_targeted_localized_orbital_analysis

- capability_name: run_targeted_localized_orbital_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_08_run_targeted_localized_orbital_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_localized_orbital_analysis", "requested_capability": "run_targeted_localized_orbital_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["localized_orbitals_pm", "molecular_orbital_files"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "localized_orbital_availability": "proxy_only", "available_localized_orbital_observables": ["localized_orbitals_pm", "molecular_orbital_files"], "missing_localized_orbital_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 9 | microscopic | probe_run_targeted_natural_orbital_analysis

- capability_name: run_targeted_natural_orbital_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-164329-917043_13c501618e2d/probes/round_09_run_targeted_natural_orbital_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_natural_orbital_analysis", "requested_capability": "run_targeted_natural_orbital_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["natural_orbitals_no", "molecular_orbital_files"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "natural_orbital_availability": "proxy_only", "available_natural_orbital_observables": ["molecular_orbital_files", "natural_orbitals_no"], "missing_natural_orbital_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}
