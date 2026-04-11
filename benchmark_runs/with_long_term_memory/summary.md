# Benchmark Summary

- dataset_row_count: 264
- sampled_row_count: 20
- evaluated_row_count: 20
- successful_case_count: 20
- failed_case_count: 0
- top1_accuracy: 0.65
- macro_recall: 0.510417

## Per-label Metrics

| label | support | predicted_count | true_positive | recall | precision |
| --- | ---: | ---: | ---: | ---: | ---: |
| ICT | 8 | 10 | 6 | 0.75 | 0.6 |
| TICT | 1 | 2 | 0 | 0.0 | 0.0 |
| ESIPT | 3 | 2 | 2 | 0.666667 | 1.0 |
| neutral aromatic | 8 | 6 | 5 | 0.625 | 0.833333 |
| unknown | 0 | 0 | 0 | None | None |

## Case Results

| id | code | truth | predicted_top1 | status | is_correct | report_dir | live_status_path |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2039.0 | CBBHA-8 | ESIPT | ESIPT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-113408-703364_745cbc1fc7ee | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-113408-703364_745cbc1fc7ee/live_status.md |
| 1067.0 | o-TPEPy | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-121310-634321_fb084245040d | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-121310-634321_fb084245040d/live_status.md |
| 73.0 | DM-TPE-PA | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-122405-234951_6b55cfc2a445 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-122405-234951_6b55cfc2a445/live_status.md |
| 37.0 | TTB | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-125553-378789_0afc9c1a3073 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-125553-378789_0afc9c1a3073/live_status.md |
| 21.0 | ESIPT-N3 | ESIPT | ESIPT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-133508-617930_3d6e7ccba8ef | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-133508-617930_3d6e7ccba8ef/live_status.md |
| 2156.0 | DMF-BP-PXZ | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-135800-040253_85fc260c6111 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-135800-040253_85fc260c6111/live_status.md |
| 2012.0 | TNZtPPI | TICT | ICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-140500-804951_373d360a72e3 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-140500-804951_373d360a72e3/live_status.md |
| 1979.0 | TPA-2Ph-SCP | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-142026-580992_3faf16d634a6 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-142026-580992_3faf16d634a6/live_status.md |
| 291.0 | (E)-TPEDEPy | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-144920-673621_b0cf1d30449f | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-144920-673621_b0cf1d30449f/live_status.md |
| 1075.0 | (TPE)2SF | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-150151-512780_de9cf42ad098 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-150151-512780_de9cf42ad098/live_status.md |
| 1074.0 | TPE(PF)2 | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-154019-072267_800481658d21 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-154019-072267_800481658d21/live_status.md |
| 1991.0 | BTPE-C4 | ESIPT | TICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-164740-977139_d39f4f7d4c8d | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-164740-977139_d39f4f7d4c8d/live_status.md |
| 18.0 | TPE-Tetrazole-1 | neutral aromatic | ICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-165730-185098_dd73c2c5bec8 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-165730-185098_dd73c2c5bec8/live_status.md |
| 27.0 | CM-i | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-171715-784405_906fc02e1dd4 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-171715-784405_906fc02e1dd4/live_status.md |
| 357.0 | bBTAE-Pyr | ICT | neutral aromatic | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-172608-075957_0ff84a556294 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-172608-075957_0ff84a556294/live_status.md |
| 1072.0 | l-TPEB | neutral aromatic | neutral aromatic | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-173359-074732_a857e7a19392 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-173359-074732_a857e7a19392/live_status.md |
| 1.0 | TPE-IQ-2O | ICT | TICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-183101-433692_d3570f7c9153 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-183101-433692_d3570f7c9153/live_status.md |
| 289.0 | TPE-DOX | neutral aromatic | ICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-193543-685900_499543b72945 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-193543-685900_499543b72945/live_status.md |
| 19.0 | TPE-Tetrazole-2 | neutral aromatic | ICT | success | False | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-204608-578616_59170e5277c7 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-204608-578616_59170e5277c7/live_status.md |
| 316.0 | SPOC-SQ | ICT | ICT | success | True | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-205611-464831_5fd29069be83 | /mnt/afs/kuocheng/workspace/mas_aie/debug_reports/benchmark_with_memory/20260411-205611-464831_5fd29069be83/live_status.md |
