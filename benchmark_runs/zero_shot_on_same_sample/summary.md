# Zero-Shot Benchmark Summary

- mode: structure_aware_single_shot
- model: gpt-5.4
- dataset_row_count: 20
- sampled_row_count: 20
- evaluated_row_count: 20
- successful_case_count: 20
- failed_case_count: 0
- top1_accuracy: 0.45
- macro_recall: 0.28125

## Per-label Metrics

| label | support | predicted_count | true_positive | recall | precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| ICT | 8 | 6 | 4 | 0.5 | 0.666667 |
| TICT | 1 | 6 | 0 | 0.0 | 0.0 |
| ESIPT | 3 | 0 | 0 | 0.0 | None |
| neutral aromatic | 8 | 8 | 5 | 0.625 | 0.625 |
| unknown | 0 | 0 | 0 | None | None |

## Case Results

| id | code | truth | predicted_top1 | confidence | status | is_correct |
| --- | --- | --- | --- | ---: | --- | --- |
| 2039.0 | CBBHA-8 | ESIPT | ICT | 0.36 | success | False |
| 1067.0 | o-TPEPy | neutral aromatic | neutral aromatic | 0.82 | success | True |
| 73.0 | DM-TPE-PA | ICT | TICT | 0.42 | success | False |
| 37.0 | TTB | ICT | TICT | 0.56 | success | False |
| 21.0 | ESIPT-N3 | ESIPT | TICT | 0.42 | success | False |
| 2156.0 | DMF-BP-PXZ | ICT | ICT | 0.56 | success | True |
| 2012.0 | TNZtPPI | TICT | neutral aromatic | 0.52 | success | False |
| 1979.0 | TPA-2Ph-SCP | ICT | ICT | 0.58 | success | True |
| 291.0 | (E)-TPEDEPy | neutral aromatic | ICT | 0.42 | success | False |
| 1075.0 | (TPE)2SF | neutral aromatic | neutral aromatic | 0.74 | success | True |
| 1074.0 | TPE(PF)2 | neutral aromatic | neutral aromatic | 0.88 | success | True |
| 1991.0 | BTPE-C4 | ESIPT | neutral aromatic | 0.58 | success | False |
| 18.0 | TPE-Tetrazole-1 | neutral aromatic | TICT | 0.46 | success | False |
| 27.0 | CM-i | ICT | ICT | 0.37 | success | True |
| 357.0 | bBTAE-Pyr | ICT | neutral aromatic | 0.62 | success | False |
| 1072.0 | l-TPEB | neutral aromatic | neutral aromatic | 0.75 | success | True |
| 1.0 | TPE-IQ-2O | ICT | ICT | 0.56 | success | True |
| 289.0 | TPE-DOX | neutral aromatic | TICT | 0.46 | success | False |
| 19.0 | TPE-Tetrazole-2 | neutral aromatic | neutral aromatic | 0.52 | success | True |
| 316.0 | SPOC-SQ | ICT | TICT | 0.42 | success | False |
