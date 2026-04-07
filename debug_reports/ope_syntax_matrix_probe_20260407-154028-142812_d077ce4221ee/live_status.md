# Amesp OPE Syntax Matrix Probe

- report_dir: /datasets/workspace/mas_aie/debug_reports/ope_syntax_matrix_probe_20260407-154028-142812_d077ce4221ee
- amesp_bin: /datasets/workspace/mas_aie/third_party/Amesp/Bin/amesp
- cases_run: 35

## Results

### dft_sp__control_mofile_only
- context: dft_sp (DFT single-point)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g"]
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
- pre_ope_blocks: []
- ope_lines: ["out 2"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### dft_sp__lmo_pm_mofile
- context: dft_sp (DFT single-point)
- target: lmo_pm_mofile (Localized orbital (PM) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "lmo pm"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### dft_sp__lmo_boys_mofile
- context: dft_sp (DFT single-point)
- target: lmo_boys_mofile (Localized orbital (Boys) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "lmo boys"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### dft_sp__natorb_no_mofile
- context: dft_sp (DFT single-point)
- target: natorb_no_mofile (Natural orbital (NO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb no"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### dft_sp__natorb_uno_mofile
- context: dft_sp (DFT single-point)
- target: natorb_uno_mofile (Natural orbital (UNO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb uno"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### dft_sp__natorb_nso_mofile
- context: dft_sp (DFT single-point)
- target: natorb_nso_mofile (Natural orbital (NSO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb nso"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_after_ope__control_mofile_only
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
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
- pre_ope_blocks: []
- ope_lines: ["out 2"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_after_ope__lmo_pm_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: lmo_pm_mofile (Localized orbital (PM) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "lmo pm"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_after_ope__lmo_boys_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: lmo_boys_mofile (Localized orbital (Boys) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "lmo boys"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_after_ope__natorb_no_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: natorb_no_mofile (Natural orbital (NO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb no"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_after_ope__natorb_uno_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: natorb_uno_mofile (Natural orbital (UNO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb uno"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_after_ope__natorb_nso_mofile
- context: td_posthf_after_ope (TD-DFT with >posthf after >ope)
- target: natorb_nso_mofile (Natural orbital (NSO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb nso"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_before_ope__control_mofile_only
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "td"]
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
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["out 2"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### td_posthf_before_ope__lmo_pm_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: lmo_pm_mofile (Localized orbital (PM) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "lmo pm"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_before_ope__lmo_boys_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: lmo_boys_mofile (Localized orbital (Boys) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "lmo boys"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_before_ope__natorb_no_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: natorb_no_mofile (Natural orbital (NO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "natorb no"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_before_ope__natorb_uno_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: natorb_uno_mofile (Natural orbital (UNO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "natorb uno"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### td_posthf_before_ope__natorb_nso_mofile
- context: td_posthf_before_ope (TD-DFT with >posthf before >ope)
- target: natorb_nso_mofile (Natural orbital (NSO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "td"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "natorb nso"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__control_mofile_only
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
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
- pre_ope_blocks: []
- ope_lines: ["out 2"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__lmo_pm_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: lmo_pm_mofile (Localized orbital (PM) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "lmo pm"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__lmo_boys_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: lmo_boys_mofile (Localized orbital (Boys) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "lmo boys"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__natorb_no_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: natorb_no_mofile (Natural orbital (NO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb no"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__natorb_uno_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: natorb_uno_mofile (Natural orbital (UNO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb uno"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_after_ope__natorb_nso_mofile
- context: tda_ris_posthf_after_ope (TDA-RIS with >posthf after >ope)
- target: natorb_nso_mofile (Natural orbital (NSO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: []
- ope_lines: ["mofile on", "natorb nso"]
- post_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__control_mofile_only
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: control_mofile_only (Control with mofile only)
- status: success
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
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
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["out 2"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: True
- stdout_stop_lines: []
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__lmo_pm_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: lmo_pm_mofile (Localized orbital (PM) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "lmo pm"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__lmo_boys_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: lmo_boys_mofile (Localized orbital (Boys) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "lmo boys"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"lmo\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__natorb_no_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: natorb_no_mofile (Natural orbital (NO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "natorb no"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__natorb_uno_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: natorb_uno_mofile (Natural orbital (UNO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "natorb uno"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []

### tda_ris_posthf_before_ope__natorb_nso_mofile
- context: tda_ris_posthf_before_ope (TDA-RIS with >posthf before >ope)
- target: natorb_nso_mofile (Natural orbital (NSO) with mofile)
- status: failed
- keywords: ["b3lyp", "sto-3g", "tda-ris"]
- pre_ope_blocks: [["posthf", ["nstates 2", "tout 1"]]]
- ope_lines: ["mofile on", "natorb nso"]
- post_ope_blocks: []
- exit_code: 0
- aop_exists: True
- terminated_normally: False
- stdout_stop_lines: ["Stop : error keyword: \"natorb\" in >ope!"]
- stderr_stop_lines: []
