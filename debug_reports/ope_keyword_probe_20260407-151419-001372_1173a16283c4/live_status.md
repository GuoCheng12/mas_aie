# Amesp OPE Keyword Probe

- report_dir: /datasets/workspace/mas_aie/debug_reports/ope_keyword_probe_20260407-151419-001372_1173a16283c4
- amesp_bin: /datasets/workspace/mas_aie/third_party/Amesp/Bin/amesp
- probes_run: 9

## Results

### control_no_ope
- title: Control without >ope
- status: success
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### charge_hirshfeld
- title: Hirshfeld charge probe
- status: success
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["charge hirshfeld"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### density_out2
- title: Density/population out 2 probe
- status: success
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["out 2"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### mofile_only
- title: MO file only probe
- status: success
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["mofile on"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### localized_pm
- title: Localized orbital probe (PM)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["mofile on", "lmo pm"]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### localized_boys
- title: Localized orbital probe (Boys)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["mofile on", "lmo boys"]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### natural_no
- title: Natural orbital probe (NO)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["mofile on", "natorb no"]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### natural_uno
- title: Natural orbital probe (UNO)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["mofile on", "natorb uno"]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### natural_nso
- title: Natural orbital probe (NSO)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- ope_lines: ["mofile on", "natorb nso"]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []
