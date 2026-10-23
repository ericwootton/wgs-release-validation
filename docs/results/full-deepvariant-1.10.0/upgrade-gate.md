## Regression gate: ✅ PASS: no regression beyond thresholds

Baseline `docs/results/full-deepvariant-1.9.0/metrics.json` vs candidate `docs/results/full-deepvariant-1.10.0/metrics.json`.
Tool images and parameters identical: no.

| Status | Caller | Type | Stratum | Truth variants | Baseline F1 % | Candidate F1 % | Δ F1 (points) | Allowed drop (points) | Note |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| ✅ PASS | deepvariant | SNP | all | 6,298 | 99.30 | 99.31 | +0.01 | 0.20 |  |
| ✅ PASS | deepvariant | SNP | TS_contained | 6,298 | 99.30 | 99.31 | +0.01 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | all_difficult | 1,531 | 97.08 | 97.11 | +0.03 | 1.00 |  |
| ℹ️ INFO | deepvariant | SNP | coding | 29 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | deepvariant | SNP | gc_extreme | 273 | 99.82 | 99.82 | +0.00 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | homopolymer | 163 | 99.69 | 99.69 | +0.00 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | low_mappability | 578 | 93.22 | 93.22 | +0.00 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | lowmap_or_segdup | 1,063 | 95.91 | 95.91 | +0.00 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | not_difficult | 4,767 | 100.00 | 100.00 | +0.00 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | not_lowmap_or_segdup | 5,235 | 99.97 | 99.98 | +0.01 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | segdup | 690 | 98.63 | 98.63 | +0.00 | 1.00 |  |
| ✅ PASS | deepvariant | SNP | tandem_repeat | 206 | 99.28 | 99.52 | +0.24 | 1.00 |  |
| ✅ PASS | deepvariant | INDEL | all | 816 | 99.38 | 99.44 | +0.06 | 0.50 |  |
| ℹ️ INFO | deepvariant | INDEL | TS_boundary | 3 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | deepvariant | INDEL | TS_contained | 813 | 99.38 | 99.44 | +0.06 | 2.00 |  |
| ✅ PASS | deepvariant | INDEL | all_difficult | 564 | 99.10 | 99.19 | +0.09 | 2.00 |  |
| ℹ️ INFO | deepvariant | INDEL | coding | 1 | 100.00 | 100.00 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | deepvariant | INDEL | gc_extreme | 59 | 100.00 | 100.00 | +0.00 | 2.00 |  |
| ✅ PASS | deepvariant | INDEL | homopolymer | 308 | 100.00 | 100.00 | +0.00 | 2.00 |  |
| ℹ️ INFO | deepvariant | INDEL | low_mappability | 30 | 88.89 | 88.89 | +0.00 | – | fewer than 50 truth variants; not gated |
| ✅ PASS | deepvariant | INDEL | lowmap_or_segdup | 82 | 95.57 | 95.57 | +0.00 | 2.00 |  |
| ✅ PASS | deepvariant | INDEL | not_difficult | 254 | 100.00 | 100.00 | +0.00 | 2.00 |  |
| ✅ PASS | deepvariant | INDEL | not_lowmap_or_segdup | 734 | 99.80 | 99.86 | +0.07 | 2.00 |  |
| ✅ PASS | deepvariant | INDEL | segdup | 62 | 99.16 | 99.16 | +0.00 | 2.00 |  |
| ✅ PASS | deepvariant | INDEL | tandem_repeat | 201 | 99.25 | 99.50 | +0.25 | 2.00 |  |

0 failing row(s) of 25.
