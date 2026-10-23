## Regression gate: ❌ FAIL: regression detected

Baseline `baselines/ci.json` vs candidate `docs/results/inc01/metrics.json`.
Tool images and parameters identical: no.

| Status | Caller | Type | Stratum | Truth variants | Baseline F1 % | Candidate F1 % | Δ F1 (points) | Allowed drop (points) | Note |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| ❌ FAIL | gatk | SNP | all | 360 | 95.66 | 94.58 | -1.08 | 0.20 | F1 dropped by 0.0108 (limit 0.002) |
| ❌ FAIL | gatk | SNP | TS_contained | 360 | 95.66 | 94.58 | -1.08 | 1.00 | F1 dropped by 0.0108 (limit 0.01) |
| ❌ FAIL | gatk | SNP | all_difficult | 100 | 82.56 | 77.30 | -5.26 | 1.00 | F1 dropped by 0.0526 (limit 0.01) |
| ℹ️ INFO | gatk | SNP | coding | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | SNP | gc_extreme | 11 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | SNP | homopolymer | 10 | 94.74 | 94.74 | +0.00 | – | fewer than 50 truth variants; not gated |
| ❌ FAIL | gatk | SNP | low_mappability | 82 | 77.94 | 70.87 | -7.08 | 1.00 | F1 dropped by 0.0708 (limit 0.01) |
| ❌ FAIL | gatk | SNP | lowmap_or_segdup | 82 | 77.94 | 70.87 | -7.08 | 1.00 | F1 dropped by 0.0708 (limit 0.01) |
| ✅ PASS | gatk | SNP | not_difficult | 260 | 100.00 | 100.00 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | not_lowmap_or_segdup | 278 | 100.00 | 100.00 | +0.00 | 1.00 |  |
| ℹ️ INFO | gatk | SNP | segdup | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | SNP | tandem_repeat | 0 | – | – | – | – | no truth variants |
| ✅ PASS | gatk | INDEL | all | 36 | 98.59 | 98.59 | +0.00 | 0.50 |  |
| ℹ️ INFO | gatk | INDEL | TS_contained | 36 | 98.59 | 98.59 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | all_difficult | 27 | 98.11 | 98.11 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | coding | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | INDEL | gc_extreme | 2 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | homopolymer | 13 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | low_mappability | 6 | 90.91 | 90.91 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | lowmap_or_segdup | 6 | 90.91 | 90.91 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | not_difficult | 9 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | not_lowmap_or_segdup | 30 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | segdup | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | INDEL | tandem_repeat | 9 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |

5 failing row(s) of 24.
