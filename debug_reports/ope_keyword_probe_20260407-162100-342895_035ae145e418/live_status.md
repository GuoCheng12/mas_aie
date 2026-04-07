# Amesp Method/OPE Keyword Probe

- report_dir: /datasets/workspace/mas_aie/debug_reports/ope_keyword_probe_20260407-162100-342895_035ae145e418
- amesp_bin: /datasets/workspace/mas_aie/third_party/Amesp/Bin/amesp
- probes_run: 10

## Results

### control_no_ope
- title: Control without >method or >ope
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: []
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
- method_lines: []
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
- method_lines: []
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
- method_lines: []
- ope_lines: ["mofile on"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### localized_pm_method
- title: Localized orbital probe (PM in >method)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["lmo pm"]
- ope_lines: ["mofile on"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### localized_pm_method_nlmo_occ
- title: Localized orbital probe (PM in >method + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["lmo pm"]
- ope_lines: ["mofile on", "nlmo occ"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### localized_boys_method_nlmo_occ
- title: Localized orbital probe (Boys in >method + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["lmo boys"]
- ope_lines: ["mofile on", "nlmo occ"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### natural_no_method
- title: Natural orbital probe (NO in >method)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["natorb no"]
- ope_lines: ["mofile on"]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### natural_uno_method
- title: Natural orbital probe (UNO in >method)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["natorb uno"]
- ope_lines: ["mofile on"]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### natural_nso_method
- title: Natural orbital probe (NSO in >method)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["natorb nso"]
- ope_lines: ["mofile on"]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []
