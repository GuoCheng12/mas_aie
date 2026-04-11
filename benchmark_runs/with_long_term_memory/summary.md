# Benchmark Summary

- dataset_row_count: 264
- sampled_row_count: 20
- evaluated_row_count: 20
- successful_case_count: 18
- failed_case_count: 2
- top1_accuracy: 0.5
- macro_recall: 0.364583

## Per-label Metrics

| label | support | predicted_count | true_positive | recall | precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| ICT | 8 | 6 | 5 | 0.625 | 0.833333 |
| TICT | 1 | 4 | 0 | 0.0 | 0.0 |
| ESIPT | 3 | 1 | 1 | 0.333333 | 1.0 |
| neutral aromatic | 8 | 7 | 4 | 0.5 | 0.571429 |
| unknown | 0 | 0 | 0 | None | None |

## Case Results

| id | code | truth | predicted_top1 | status | is_correct | report_dir | live_status_path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2039.0 | CBBHA-8 | ESIPT | ESIPT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-015723-858175_d52d3b9f94d1 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-015723-858175_d52d3b9f94d1/live_status.md |
| 1067.0 | o-TPEPy | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-020704-478809_8573b653ef19 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-020704-478809_8573b653ef19/live_status.md |
| 73.0 | DM-TPE-PA | ICT | TICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-022337-927911_029870441f83 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-022337-927911_029870441f83/live_status.md |
| 37.0 | TTB | ICT | TICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-023805-111272_f8423681673e | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-023805-111272_f8423681673e/live_status.md |
| 21.0 | ESIPT-N3 | ESIPT |  | failed | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-032242-958842_a7e0d9300b2c | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-032242-958842_a7e0d9300b2c/live_status.md |
| 2156.0 | DMF-BP-PXZ | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-034457-029642_c935008240f8 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-034457-029642_c935008240f8/live_status.md |
| 2012.0 | TNZtPPI | TICT | neutral aromatic | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-040843-684918_973db2944ec9 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-040843-684918_973db2944ec9/live_status.md |
| 1979.0 | TPA-2Ph-SCP | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-041733-601924_fdd8309d9eec | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-041733-601924_fdd8309d9eec/live_status.md |
| 291.0 | (E)-TPEDEPy | neutral aromatic |  | failed | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-062632-567260_3ffe5c5e4bcd | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-062632-567260_3ffe5c5e4bcd/live_status.md |
| 1075.0 | (TPE)2SF | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-063307-849355_aa4096c571d8 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-063307-849355_aa4096c571d8/live_status.md |
| 1074.0 | TPE(PF)2 | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-064540-358034_f520e4c75ba1 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-064540-358034_f520e4c75ba1/live_status.md |
| 1991.0 | BTPE-C4 | ESIPT | neutral aromatic | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-071247-854143_5fe155f2b4b8 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-071247-854143_5fe155f2b4b8/live_status.md |
| 18.0 | TPE-Tetrazole-1 | neutral aromatic | ICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-072718-396967_009deabaa79a | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-072718-396967_009deabaa79a/live_status.md |
| 27.0 | CM-i | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-075002-245658_d9b8aab812bc | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-075002-245658_d9b8aab812bc/live_status.md |
| 357.0 | bBTAE-Pyr | ICT | neutral aromatic | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-080601-016795_37d9de196218 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-080601-016795_37d9de196218/live_status.md |
| 1072.0 | l-TPEB | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-083017-721902_189310ec1707 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-083017-721902_189310ec1707/live_status.md |
| 1.0 | TPE-IQ-2O | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-090517-120049_194dd5268790 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-090517-120049_194dd5268790/live_status.md |
| 289.0 | TPE-DOX | neutral aromatic | TICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-092452-297710_7ef1b7512bf9 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-092452-297710_7ef1b7512bf9/live_status.md |
| 19.0 | TPE-Tetrazole-2 | neutral aromatic | TICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-100138-466536_69f5b37126a9 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-100138-466536_69f5b37126a9/live_status.md |
| 316.0 | SPOC-SQ | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-102440-090402_07bec7660e43 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-102440-090402_07bec7660e43/live_status.md |
