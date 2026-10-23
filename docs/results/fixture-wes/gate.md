## Regression gate: ✅ PASS: no regression beyond thresholds

Baseline `docs/results/fixture/metrics.json` vs candidate `docs/results/fixture-wes/metrics.json`.
Tool images and parameters identical: yes, so results must match exactly.

| Status | Caller | Type | Stratum | Truth variants | Baseline F1 % | Candidate F1 % | Δ F1 (points) | Allowed drop (points) | Note |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| ✅ PASS | gatk | SNP | all | 57 | 100.00 | 100.00 | +0.00 | 0.20 |  |
| ✅ PASS | gatk | SNP | TS_contained | 57 | 100.00 | 100.00 | +0.00 | 1.00 |  |
| ℹ️ INFO | gatk | SNP | all_difficult | 11 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | SNP | coding | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | SNP | gc_extreme | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | SNP | homopolymer | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | SNP | low_mappability | 11 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | SNP | lowmap_or_segdup | 11 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | SNP | not_difficult | 46 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | SNP | not_lowmap_or_segdup | 46 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | SNP | segdup | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | SNP | tandem_repeat | 0 | – | – | – | – | no truth variants |
| ✅ PASS | gatk | INDEL | all | 8 | 100.00 | 100.00 | +0.00 | 0.50 |  |
| ℹ️ INFO | gatk | INDEL | TS_contained | 8 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | all_difficult | 6 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | coding | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | INDEL | gc_extreme | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | INDEL | homopolymer | 2 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | low_mappability | 2 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | lowmap_or_segdup | 2 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | not_difficult | 2 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | not_lowmap_or_segdup | 6 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ℹ️ INFO | gatk | INDEL | segdup | 0 | – | – | – | – | no truth variants |
| ℹ️ INFO | gatk | INDEL | tandem_repeat | 2 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |

0 failing row(s) of 24.
