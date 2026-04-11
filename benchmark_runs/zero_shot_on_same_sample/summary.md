# Zero-Shot Benchmark Summary

- mode: zero_shot
- model: gpt-5.2
- dataset_row_count: 20
- sampled_row_count: 20
- evaluated_row_count: 20
- successful_case_count: 20
- failed_case_count: 0
- top1_accuracy: 0.7
- macro_recall: 0.489583

## Per-label Metrics

| label | support | predicted_count | true_positive | recall | precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| ICT | 8 | 8 | 6 | 0.75 | 0.75 |
| TICT | 1 | 2 | 0 | 0.0 | 0.0 |
| ESIPT | 3 | 1 | 1 | 0.333333 | 1.0 |
| neutral aromatic | 8 | 9 | 7 | 0.875 | 0.777778 |
| unknown | 0 | 0 | 0 | None | None |

## Case Results

| id | code | truth | predicted_top1 | confidence | status | is_correct |
| --- | --- | --- | --- | ---: | --- | --- |
| 2039.0 | CBBHA-8 | ESIPT | ESIPT | 0.5 | success | True |
| 1067.0 | o-TPEPy | neutral aromatic | neutral aromatic | 0.78 | success | True |
| 73.0 | DM-TPE-PA | ICT | ICT | 0.55 | success | True |
| 37.0 | TTB | ICT | TICT | 0.62 | success | False |
| 21.0 | ESIPT-N3 | ESIPT | TICT | 0.46 | success | False |
| 2156.0 | DMF-BP-PXZ | ICT | ICT | 0.52 | success | True |
| 2012.0 | TNZtPPI | TICT | ICT | 0.38 | success | False |
| 1979.0 | TPA-2Ph-SCP | ICT | ICT | 0.62 | success | True |
| 291.0 | (E)-TPEDEPy | neutral aromatic | ICT | 0.42 | success | False |
| 1075.0 | (TPE)2SF | neutral aromatic | neutral aromatic | 0.8 | success | True |
| 1074.0 | TPE(PF)2 | neutral aromatic | neutral aromatic | 0.82 | success | True |
| 1991.0 | BTPE-C4 | ESIPT | neutral aromatic | 0.58 | success | False |
| 18.0 | TPE-Tetrazole-1 | neutral aromatic | neutral aromatic | 0.48 | success | True |
| 27.0 | CM-i | ICT | ICT | 0.6 | success | True |
| 357.0 | bBTAE-Pyr | ICT | neutral aromatic | 0.6 | success | False |
| 1072.0 | l-TPEB | neutral aromatic | neutral aromatic | 0.72 | success | True |
| 1.0 | TPE-IQ-2O | ICT | ICT | 0.62 | success | True |
| 289.0 | TPE-DOX | neutral aromatic | neutral aromatic | 0.4 | success | True |
| 19.0 | TPE-Tetrazole-2 | neutral aromatic | neutral aromatic | 0.55 | success | True |
| 316.0 | SPOC-SQ | ICT | ICT | 0.55 | success | True |
