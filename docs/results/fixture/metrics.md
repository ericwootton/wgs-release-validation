### Benchmark results: `fixture`

Region `chr20:21860001-21890000` · HG002 vs GIAB v4.2.1 · hap.py (vcfeval) · mean depth 34.9x

| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| gatk | SNP | all benchmark regions | 57 | 0 | 0 | 100.00% (93.7–100.0) | 100.00% (93.7–100.0) | 100.00% |
| gatk | SNP | not_difficult | 46 | 0 | 0 | 100.00% (92.3–100.0) | 100.00% (92.3–100.0) | 100.00% |
| gatk | SNP | all_difficult | 11 | 0 | 0 | 100.00% (74.1–100.0) | 100.00% (74.1–100.0) | 100.00% |
| gatk | SNP | lowmap_or_segdup | 11 | 0 | 0 | 100.00% (74.1–100.0) | 100.00% (74.1–100.0) | 100.00% |
| gatk | INDEL | all benchmark regions | 8 | 0 | 0 | 100.00% (67.6–100.0) | 100.00% (67.6–100.0) | 100.00% |
| gatk | INDEL | not_difficult | 2 | 0 | 0 | 100.00% (34.2–100.0) | 100.00% (34.2–100.0) | 100.00% |
| gatk | INDEL | all_difficult | 6 | 0 | 0 | 100.00% (61.0–100.0) | 100.00% (61.0–100.0) | 100.00% |
| gatk | INDEL | lowmap_or_segdup | 2 | 0 | 0 | 100.00% (34.2–100.0) | 100.00% (34.2–100.0) | 100.00% |
| gatk | INDEL | homopolymer | 2 | 0 | 0 | 100.00% (34.2–100.0) | 100.00% (34.2–100.0) | 100.00% |
| gatk | INDEL | tandem_repeat | 2 | 0 | 0 | 100.00% (34.2–100.0) | 100.00% (34.2–100.0) | 100.00% |

Intervals are 95% Wilson score intervals on the counts shown; small strata have wide intervals.
