# Amesp Method/OPE Syntax Matrix Probe

- report_dir: /datasets/workspace/mas_aie/debug_reports/ope_syntax_matrix_probe_20260407-162107-670709_cd37cb2a2bdf
- amesp_bin: /datasets/workspace/mas_aie/third_party/Amesp/Bin/amesp
- cases_run: 40

## Results

### dft_sp__control_mofile_only
- context: dft_sp (DFT single-point)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: []
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__control_out2_only
- context: dft_sp (DFT single-point)
- target: control_out2_only (Control with out 2 only)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: []
- pre_ope_blocks: []
- ope_lines: ["out 2"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__lmo_pm_method_mofile
- context: dft_sp (DFT single-point)
- target: lmo_pm_method_mofile (Localized orbital (PM in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__lmo_pm_method_mofile_nlmo_occ
- context: dft_sp (DFT single-point)
- target: lmo_pm_method_mofile_nlmo_occ (Localized orbital (PM in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__lmo_boys_method_mofile_nlmo_occ
- context: dft_sp (DFT single-point)
- target: lmo_boys_method_mofile_nlmo_occ (Localized orbital (Boys in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["lmo boys"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__natorb_no_method_mofile
- context: dft_sp (DFT single-point)
- target: natorb_no_method_mofile (Natural orbital (NO in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["natorb no"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__natorb_uno_method_mofile
- context: dft_sp (DFT single-point)
- target: natorb_uno_method_mofile (Natural orbital (UNO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["natorb uno"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__natorb_nso_method_mofile
- context: dft_sp (DFT single-point)
- target: natorb_nso_method_mofile (Natural orbital (NSO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- method_lines: ["natorb nso"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__control_mofile_only
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: []
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__control_out2_only
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: control_out2_only (Control with out 2 only)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: []
- pre_ope_blocks: []
- ope_lines: ["out 2"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__lmo_pm_method_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: lmo_pm_method_mofile (Localized orbital (PM in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__lmo_pm_method_mofile_nlmo_occ
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: lmo_pm_method_mofile_nlmo_occ (Localized orbital (PM in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__lmo_boys_method_mofile_nlmo_occ
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: lmo_boys_method_mofile_nlmo_occ (Localized orbital (Boys in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["lmo boys"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__natorb_no_method_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: natorb_no_method_mofile (Natural orbital (NO in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["natorb no"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__natorb_uno_method_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: natorb_uno_method_mofile (Natural orbital (UNO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["natorb uno"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__natorb_nso_method_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: natorb_nso_method_mofile (Natural orbital (NSO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["natorb nso"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__control_mofile_only
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: []
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__control_out2_only
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: control_out2_only (Control with out 2 only)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: []
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["out 2"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__lmo_pm_method_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: lmo_pm_method_mofile (Localized orbital (PM in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__lmo_pm_method_mofile_nlmo_occ
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: lmo_pm_method_mofile_nlmo_occ (Localized orbital (PM in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__lmo_boys_method_mofile_nlmo_occ
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: lmo_boys_method_mofile_nlmo_occ (Localized orbital (Boys in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["lmo boys"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__natorb_no_method_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: natorb_no_method_mofile (Natural orbital (NO in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["natorb no"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__natorb_uno_method_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: natorb_uno_method_mofile (Natural orbital (UNO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["natorb uno"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__natorb_nso_method_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: natorb_nso_method_mofile (Natural orbital (NSO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- method_lines: ["natorb nso"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__control_mofile_only
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: []
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__control_out2_only
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: control_out2_only (Control with out 2 only)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: []
- pre_ope_blocks: []
- ope_lines: ["out 2"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__lmo_pm_method_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: lmo_pm_method_mofile (Localized orbital (PM in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__lmo_pm_method_mofile_nlmo_occ
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: lmo_pm_method_mofile_nlmo_occ (Localized orbital (PM in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__lmo_boys_method_mofile_nlmo_occ
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: lmo_boys_method_mofile_nlmo_occ (Localized orbital (Boys in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["lmo boys"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__natorb_no_method_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: natorb_no_method_mofile (Natural orbital (NO in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["natorb no"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__natorb_uno_method_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: natorb_uno_method_mofile (Natural orbital (UNO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["natorb uno"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__natorb_nso_method_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: natorb_nso_method_mofile (Natural orbital (NSO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["natorb nso"]
- pre_ope_blocks: []
- ope_lines: ["mofile on"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__control_mofile_only
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: []
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__control_out2_only
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: control_out2_only (Control with out 2 only)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: []
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["out 2"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__lmo_pm_method_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: lmo_pm_method_mofile (Localized orbital (PM in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__lmo_pm_method_mofile_nlmo_occ
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: lmo_pm_method_mofile_nlmo_occ (Localized orbital (PM in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["lmo pm"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__lmo_boys_method_mofile_nlmo_occ
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: lmo_boys_method_mofile_nlmo_occ (Localized orbital (Boys in >method) with mofile + nlmo occ)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["lmo boys"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "nlmo occ"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__natorb_no_method_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: natorb_no_method_mofile (Natural orbital (NO in >method) with mofile)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["natorb no"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__natorb_uno_method_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: natorb_uno_method_mofile (Natural orbital (UNO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["natorb uno"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__natorb_nso_method_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: natorb_nso_method_mofile (Natural orbital (NSO in >method) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- method_lines: ["natorb nso"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: []
- stderr_stop_lines: []
