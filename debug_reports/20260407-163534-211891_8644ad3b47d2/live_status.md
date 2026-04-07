# Microscopic Capability Probe

- case_id: 8644ad3b47d2
- smiles: COc3ccc(/C(=C(C#N)\c1ccccc1)c2ccccc2)cc3
- user_query: Probe registry-backed microscopic capabilities directly.
- report_dir: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2
- events_recorded: 81

## Current Position
- phase: end
- round: 6
- agent: microscopic
- node: probe_run_ris_state_characterization
- current_hypothesis: None

## Probe Trace

- round=3 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "td", "RICOSX"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=3 stage=s1_vertical_excitation_subprocess status=start
  pid: 97260
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.stderr.log

- round=3 stage=s1_vertical_excitation_subprocess status=running
  pid: 97260
  elapsed_seconds: 15.01
  aop_exists: true
  aop_size_bytes: 9617
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 6  -9.66344636E+02  -2.42E-03   3.13E-04   3.68E-03    0.02

- round=3 stage=s1_vertical_excitation_subprocess status=running
  pid: 97260
  elapsed_seconds: 30.02
  aop_exists: true
  aop_size_bytes: 15838
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 4     0.00084958        16         0.028

- round=3 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 32.5728
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.stderr.log

- round=3 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_03_run_targeted_natural_orbital_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r03_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 32.5728

- round=3 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.209826492, "oscillator_strength": 0.2875, "spin_square": 0.0, "excitation_energy_ev": 3.6776, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6896806}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": 0.1189106}]}, {"state_index": 2, "total_energy_hartree": -966.179401056, "oscillator_strength": 0.3353, "spin_square": 0.0, "excitation_energy_ev": 4.5055, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.1192603}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": -0.1059693}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6727501}]}]
  first_excitation_energy_ev: 3.6776
  first_oscillator_strength: 0.2875
  state_count: 2

- round=4 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=4 stage=s0_singlepoint_subprocess status=start
  pid: 97745
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.stderr.log

- round=4 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 1.0218
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.stderr.log

- round=4 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 1.0218

- round=4 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -50.8834862462
  dipole_debye: [7.1571, -2.2931, -3.2106, 8.1725]
  mulliken_charges: [0.326736, -0.494297, 0.528032, -0.211373, -0.023592, -0.019541, 0.055506, -0.043212, 0.610949, -0.754222, 0.070704, -0.07564, -0.021878, -0.037978, -0.015497, -0.063012, 0.046066, -0.045956, -0.009117, -0.024796, -0.021931, -0.059384, -0.027712, -0.154599, -0.010558, -0.00999, 0.003565, 0.043718, 0.032441, 0.030447, 0.030197, 0.029649, 0.03155, 0.041312, 0.039185, 0.033605, 0.029542, 0.029784, 0.030398, 0.033615, 0.047284]
  homo_lumo_gap_ev: 2.2192349
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=4 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "td", "RICOSX"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=4 stage=s1_vertical_excitation_subprocess status=start
  pid: 97774
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.stderr.log

- round=4 stage=s1_vertical_excitation_subprocess status=running
  pid: 97774
  elapsed_seconds: 15.0
  aop_exists: true
  aop_size_bytes: 9617
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 6  -9.66344636E+02  -2.42E-03   3.13E-04   3.68E-03    0.02

- round=4 stage=s1_vertical_excitation_subprocess status=running
  pid: 97774
  elapsed_seconds: 30.02
  aop_exists: true
  aop_size_bytes: 15838
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 4     0.00084958        16         0.028

- round=4 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 32.5676
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.stderr.log

- round=4 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_04_run_targeted_density_population_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r04_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 32.5676

- round=4 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.209826537, "oscillator_strength": 0.2875, "spin_square": 0.0, "excitation_energy_ev": 3.6776, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6896806}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": 0.1189106}]}, {"state_index": 2, "total_energy_hartree": -966.179401102, "oscillator_strength": 0.3353, "spin_square": 0.0, "excitation_energy_ev": 4.5055, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.1192603}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": -0.1059693}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6727501}]}]
  first_excitation_energy_ev: 3.6776
  first_oscillator_strength: 0.2875
  state_count: 2

- round=5 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=5 stage=s0_singlepoint_subprocess status=start
  pid: 98253
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.stderr.log

- round=5 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 1.0253
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.stderr.log

- round=5 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 1.0253

- round=5 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -50.8834862462
  dipole_debye: [7.1571, -2.2931, -3.2106, 8.1725]
  mulliken_charges: [0.326736, -0.494297, 0.528032, -0.211373, -0.023592, -0.019541, 0.055506, -0.043212, 0.610949, -0.754222, 0.070704, -0.07564, -0.021878, -0.037978, -0.015497, -0.063012, 0.046066, -0.045956, -0.009117, -0.024796, -0.021931, -0.059384, -0.027712, -0.154599, -0.010558, -0.00999, 0.003565, 0.043718, 0.032441, 0.030447, 0.030197, 0.029649, 0.03155, 0.041312, 0.039185, 0.033605, 0.029542, 0.029784, 0.030398, 0.033615, 0.047284]
  homo_lumo_gap_ev: 2.2192349
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=5 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.aop
  keywords: ["atb", "tda"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=5 stage=s1_vertical_excitation_subprocess status=start
  pid: 98280
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.stderr.log

- round=5 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 1.0301
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.stderr.log

- round=5 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_05_run_targeted_transition_dipole_analysis/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r05_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 1.0301

- round=5 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -50.658374232, "oscillator_strength": 0.3149, "spin_square": 0.0, "excitation_energy_ev": 2.9563, "dominant_transitions": [{"occupied_orbital": 58, "virtual_orbital": 59, "coefficient": 0.6756488}, {"occupied_orbital": 57, "virtual_orbital": 59, "coefficient": -0.1473557}]}, {"state_index": 2, "total_energy_hartree": -50.638894606, "oscillator_strength": 0.2941, "spin_square": 0.0, "excitation_energy_ev": 3.4864, "dominant_transitions": [{"occupied_orbital": 58, "virtual_orbital": 59, "coefficient": -0.1349126}, {"occupied_orbital": 58, "virtual_orbital": 60, "coefficient": 0.1265626}, {"occupied_orbital": 57, "virtual_orbital": 59, "coefficient": -0.6630148}]}]
  first_excitation_energy_ev: 2.9563
  first_oscillator_strength: 0.3149
  state_count: 2

- round=6 stage=s0_singlepoint status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.aop
  keywords: ["atb", "force"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=6 stage=s0_singlepoint_subprocess status=start
  pid: 98325
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.stderr.log

- round=6 stage=s0_singlepoint_subprocess status=end
  exit_code: 0
  elapsed_seconds: 1.0218
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.stderr.log

- round=6 stage=s0_singlepoint status=end
  step_id: s0_singlepoint
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s0sp.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 1.0218

- round=6 stage=s0_singlepoint_parse status=end
  final_energy_hartree: -50.8834862462
  dipole_debye: [7.1571, -2.2931, -3.2106, 8.1725]
  mulliken_charges: [0.326736, -0.494297, 0.528032, -0.211373, -0.023592, -0.019541, 0.055506, -0.043212, 0.610949, -0.754222, 0.070704, -0.07564, -0.021878, -0.037978, -0.015497, -0.063012, 0.046066, -0.045956, -0.009117, -0.024796, -0.021931, -0.059384, -0.027712, -0.154599, -0.010558, -0.00999, 0.003565, 0.043718, 0.032441, 0.030447, 0.030197, 0.029649, 0.03155, 0.041312, 0.039185, 0.033605, 0.029542, 0.029784, 0.030398, 0.033615, 0.047284]
  homo_lumo_gap_ev: 2.2192349
  geometry_atom_count: 41
  geometry_xyz_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/s0_singlepoint.xyz
  rmsd_from_prepared_structure_angstrom: 0.0

- round=6 stage=s1_vertical_excitation status=start
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.aop
  keywords: ["b3lyp", "sto-3g", "tda-ris"]
  npara: 20
  maxcore_mb: 12000
  use_ricosx: true

- round=6 stage=s1_vertical_excitation_subprocess status=start
  pid: 98357
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.stderr.log

- round=6 stage=s1_vertical_excitation_subprocess status=running
  pid: 98357
  elapsed_seconds: 15.0
  aop_exists: true
  aop_size_bytes: 8771
  stdout_size_bytes: 0
  stderr_size_bytes: 0
  aop_tail: 6  -9.66334341E+02  -2.42E-03   3.13E-04   3.68E-03    0.01

- round=6 stage=s1_vertical_excitation_subprocess status=end
  exit_code: 0
  elapsed_seconds: 19.0544
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.stderr.log

- round=6 stage=s1_vertical_excitation status=end
  step_id: s1_vertical_excitation
  aip_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.aip
  aop_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.aop
  mo_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.mo
  stdout_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.stdout.log
  stderr_path: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/work/round_06_run_ris_state_characterization/targeted_property_follow_up/baseline_bundle/8644ad3b47d2_probe_r06_baseline_bundle_char_s1.stderr.log
  exit_code: 0
  terminated_normally: true
  elapsed_seconds: 19.0544

- round=6 stage=s1_parse status=end
  excited_states: [{"state_index": 1, "total_energy_hartree": -966.196815073, "oscillator_strength": 0.3693, "spin_square": 0.0, "excitation_energy_ev": 3.7515, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": 0.6715221}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.1590257}]}, {"state_index": 2, "total_energy_hartree": -966.166722051, "oscillator_strength": 0.4023, "spin_square": 0.0, "excitation_energy_ev": 4.5704, "dominant_transitions": [{"occupied_orbital": 82, "virtual_orbital": 83, "coefficient": -0.1503974}, {"occupied_orbital": 82, "virtual_orbital": 84, "coefficient": 0.1149491}, {"occupied_orbital": 82, "virtual_orbital": 85, "coefficient": -0.1202947}, {"occupied_orbital": 81, "virtual_orbital": 83, "coefficient": -0.6447063}, {"occupied_orbital": 76, "virtual_orbital": 83, "coefficient": 0.1184951}]}]
  first_excitation_energy_ev: 3.7515
  first_oscillator_strength: 0.3693
  state_count: 2

## Probe Results

### Round 1 | microscopic | probe_run_baseline_bundle

- capability_name: run_baseline_bundle

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/probes/round_01_run_baseline_bundle.json

- result_summary: {"route": "baseline_bundle", "executed_capability": "run_baseline_bundle", "requested_capability": "run_baseline_bundle", "performed_new_calculations": true, "reused_existing_artifacts": false, "resolved_target_ids": {}, "missing_deliverables": []}

- route_summary: {"state_count": 2, "lowest_state_energy_ev": 3.6776, "first_bright_state_index": 1, "first_bright_state_energy_ev": 3.6776, "first_bright_state_oscillator_strength": 0.2875, "lowest_state_to_brightest_pattern": "lowest_state_is_bright", "oscillator_strength_summary": {"sum": 0.6228, "max": 0.3353}}

### Round 2 | microscopic | probe_run_targeted_localized_orbital_analysis

- capability_name: run_targeted_localized_orbital_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/probes/round_02_run_targeted_localized_orbital_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_localized_orbital_analysis", "requested_capability": "run_targeted_localized_orbital_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["localized_orbitals_pm", "molecular_orbital_files"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "localized_orbital_availability": "proxy_only", "available_localized_orbital_observables": ["localized_orbitals_pm", "molecular_orbital_files"], "missing_localized_orbital_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 3 | microscopic | probe_run_targeted_natural_orbital_analysis

- capability_name: run_targeted_natural_orbital_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/probes/round_03_run_targeted_natural_orbital_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_natural_orbital_analysis", "requested_capability": "run_targeted_natural_orbital_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["natural_orbitals_no", "molecular_orbital_files"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "natural_orbital_availability": "proxy_only", "available_natural_orbital_observables": ["molecular_orbital_files", "natural_orbitals_no"], "missing_natural_orbital_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 4 | microscopic | probe_run_targeted_density_population_analysis

- capability_name: run_targeted_density_population_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/probes/round_04_run_targeted_density_population_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_density_population_analysis", "requested_capability": "run_targeted_density_population_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["density_matrix", "gross_orbital_populations", "mayer_bond_order"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "density_population_availability": "proxy_only", "available_density_population_observables": ["density_matrix", "gross_orbital_populations", "mayer_bond_order"], "missing_density_population_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 5 | microscopic | probe_run_targeted_transition_dipole_analysis

- capability_name: run_targeted_transition_dipole_analysis

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/probes/round_05_run_targeted_transition_dipole_analysis.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_targeted_transition_dipole_analysis", "requested_capability": "run_targeted_transition_dipole_analysis", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["ground_to_excited_transition_dipoles", "excited_to_excited_transition_dipoles"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "transition_dipole_availability": "proxy_only", "available_transition_dipole_observables": ["excited_to_excited_transition_dipoles", "ground_to_excited_transition_dipoles"], "missing_transition_dipole_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}

### Round 6 | microscopic | probe_run_ris_state_characterization

- capability_name: run_ris_state_characterization

- status: success

- result_file: /datasets/workspace/mas_aie/debug_reports/20260407-163534-211891_8644ad3b47d2/probes/round_06_run_ris_state_characterization.json

- result_summary: {"route": "targeted_property_follow_up", "executed_capability": "run_ris_state_characterization", "requested_capability": "run_ris_state_characterization", "performed_new_calculations": true, "reused_existing_artifacts": true, "resolved_target_ids": {"artifact_bundle_id": "round_01_baseline_bundle"}, "missing_deliverables": []}

- route_summary: {"artifact_scope": "baseline_bundle", "artifact_source_round": 1, "source_bundle_completion_status": "complete", "descriptor_scope": ["dominant_transitions", "state_family_overlap", "ground_state_dipole", "mulliken_charges", "molecular_orbital_files"], "selected_target_members": ["baseline_bundle"], "selected_target_count": 1, "ris_state_characterization_availability": "proxy_only", "available_ris_state_characterization_observables": ["dominant_transitions", "ground_state_dipole", "molecular_orbital_files", "mulliken_charges", "state_family_overlap"], "missing_ris_state_characterization_observables": [], "artifact_reuse_note": "Reused one existing artifact bundle, selected a bounded representative subset of geometries, and ran fixed-geometry follow-up characterization on that subset.", "optimize_ground_state": false, "state_window": [1, 2]}
