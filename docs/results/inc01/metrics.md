### Benchmark results: `inc01`

Region `chr20:21800001-22000000` · HG002 vs GIAB v4.2.1 (GRCh38) · hap.py (vcfeval) · mean depth 35.2x

| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| gatk | SNP | all benchmark regions | 360 | 37 | 0 | 89.72% (86.2–92.5) | 100.00% (98.8–100.0) | 94.58% |
| gatk | SNP | not_difficult | 260 | 0 | 0 | 100.00% (98.5–100.0) | 100.00% (98.5–100.0) | 100.00% |
| gatk | SNP | all_difficult | 100 | 37 | 0 | 63.00% (53.2–71.8) | 100.00% (94.3–100.0) | 77.30% |
| gatk | SNP | lowmap_or_segdup | 82 | 37 | 0 | 54.88% (44.1–65.2) | 100.00% (92.1–100.0) | 70.87% |
| gatk | SNP | homopolymer | 10 | 1 | 0 | 90.00% (59.6–98.2) | 100.00% (70.1–100.0) | 94.74% |
| gatk | INDEL | all benchmark regions | 36 | 1 | 0 | 97.22% (85.8–99.5) | 100.00% (90.1–100.0) | 98.59% |
| gatk | INDEL | not_difficult | 9 | 0 | 0 | 100.00% (70.1–100.0) | 100.00% (70.1–100.0) | 100.00% |
| gatk | INDEL | all_difficult | 27 | 1 | 0 | 96.30% (81.7–99.3) | 100.00% (87.1–100.0) | 98.11% |
| gatk | INDEL | lowmap_or_segdup | 6 | 1 | 0 | 83.33% (43.6–97.0) | 100.00% (56.6–100.0) | 90.91% |
| gatk | INDEL | homopolymer | 13 | 0 | 0 | 100.00% (77.2–100.0) | 100.00% (77.2–100.0) | 100.00% |
| gatk | INDEL | tandem_repeat | 9 | 0 | 0 | 100.00% (70.1–100.0) | 100.00% (70.1–100.0) | 100.00% |

Intervals are 95% Wilson score intervals on the counts shown; small strata have wide intervals.
