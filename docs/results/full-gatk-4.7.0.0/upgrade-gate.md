## Regression gate: ✅ PASS: no regression beyond thresholds

Baseline `docs/results/full-gatk-4.6.2.0/metrics.json` vs candidate `docs/results/full-gatk-4.7.0.0/metrics.json`.
Tool images and parameters identical: no.

| Status | Caller | Type | Stratum | Truth variants | Baseline F1 % | Candidate F1 % | Δ F1 (points) | Allowed drop (points) | Note |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| ✅ PASS | gatk | SNP | all | 6,298 | 97.92 | 97.92 | +0.00 | 0.20 |  |
| ℹ️ INFO | gatk | SNP | TS_boundary | 0 | – | – | – | – | no truth variants |
| ✅ PASS | gatk | SNP | TS_contained | 6,298 | 97.92 | 97.92 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | all_difficult | 1,531 | 91.94 | 91.94 | +0.00 | 1.00 |  |
| ℹ️ INFO | gatk | SNP | coding | 29 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | gatk | SNP | gc_extreme | 273 | 97.84 | 97.84 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | homopolymer | 163 | 99.08 | 99.08 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | low_mappability | 578 | 83.07 | 83.07 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | lowmap_or_segdup | 1,063 | 88.69 | 88.69 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | not_difficult | 4,767 | 99.90 | 99.90 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | not_lowmap_or_segdup | 5,235 | 99.88 | 99.88 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | segdup | 690 | 89.54 | 89.54 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | SNP | tandem_repeat | 206 | 98.54 | 98.54 | +0.00 | 1.00 |  |
| ✅ PASS | gatk | INDEL | all | 816 | 97.87 | 97.87 | +0.00 | 0.50 |  |
| ℹ️ INFO | gatk | INDEL | TS_boundary | 3 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | gatk | INDEL | TS_contained | 813 | 97.86 | 97.86 | +0.00 | 2.00 |  |
| ✅ PASS | gatk | INDEL | all_difficult | 564 | 96.89 | 96.89 | +0.00 | 2.00 |  |
| ℹ️ INFO | gatk | INDEL | coding | 1 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | gatk | INDEL | gc_extreme | 59 | 99.15 | 99.15 | +0.00 | 2.00 |  |
| ✅ PASS | gatk | INDEL | homopolymer | 308 | 99.17 | 99.17 | +0.00 | 2.00 |  |
| ℹ️ INFO | gatk | INDEL | low_mappability | 30 | 73.02 | 73.02 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | gatk | INDEL | lowmap_or_segdup | 82 | 85.98 | 85.98 | +0.00 | 2.00 |  |
| ✅ PASS | gatk | INDEL | not_difficult | 254 | 100.00 | 100.00 | +0.00 | 2.00 |  |
| ✅ PASS | gatk | INDEL | not_lowmap_or_segdup | 734 | 99.31 | 99.31 | +0.00 | 2.00 |  |
| ✅ PASS | gatk | INDEL | segdup | 62 | 87.59 | 87.59 | +0.00 | 2.00 |  |
| ✅ PASS | gatk | INDEL | tandem_repeat | 201 | 98.72 | 98.72 | +0.00 | 2.00 |  |

0 failing row(s) of 26.
