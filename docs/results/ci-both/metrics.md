### Benchmark results: `ci-both`

Region `chr20:21800001-22000000` · HG002 vs GIAB v4.2.1 · hap.py (vcfeval) · mean depth 35.2x

| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| gatk | SNP | all benchmark regions | 360 | 29 | 1 | 91.94% (88.7–94.3) | 99.70% (98.3–99.9) | 95.66% |
| gatk | SNP | not_difficult | 260 | 0 | 0 | 100.00% (98.5–100.0) | 100.00% (98.5–100.0) | 100.00% |
| gatk | SNP | all_difficult | 100 | 29 | 1 | 71.00% (61.5–79.0) | 98.61% (92.5–99.8) | 82.56% |
| gatk | SNP | lowmap_or_segdup | 82 | 29 | 1 | 64.63% (53.8–74.1) | 98.15% (90.2–99.7) | 77.94% |
| gatk | SNP | homopolymer | 10 | 1 | 0 | 90.00% (59.6–98.2) | 100.00% (70.1–100.0) | 94.74% |
| gatk | INDEL | all benchmark regions | 36 | 1 | 0 | 97.22% (85.8–99.5) | 100.00% (90.1–100.0) | 98.59% |
| gatk | INDEL | not_difficult | 9 | 0 | 0 | 100.00% (70.1–100.0) | 100.00% (70.1–100.0) | 100.00% |
| gatk | INDEL | all_difficult | 27 | 1 | 0 | 96.30% (81.7–99.3) | 100.00% (87.1–100.0) | 98.11% |
| gatk | INDEL | lowmap_or_segdup | 6 | 1 | 0 | 83.33% (43.6–97.0) | 100.00% (56.6–100.0) | 90.91% |
| gatk | INDEL | homopolymer | 13 | 0 | 0 | 100.00% (77.2–100.0) | 100.00% (77.2–100.0) | 100.00% |
| gatk | INDEL | tandem_repeat | 9 | 0 | 0 | 100.00% (70.1–100.0) | 100.00% (70.1–100.0) | 100.00% |
| deepvariant | SNP | all benchmark regions | 360 | 21 | 0 | 94.17% (91.2–96.2) | 100.00% (98.9–100.0) | 97.00% |
| deepvariant | SNP | not_difficult | 260 | 0 | 0 | 100.00% (98.5–100.0) | 100.00% (98.5–100.0) | 100.00% |
| deepvariant | SNP | all_difficult | 100 | 21 | 0 | 79.00% (70.0–85.8) | 100.00% (95.4–100.0) | 88.27% |
| deepvariant | SNP | lowmap_or_segdup | 82 | 21 | 0 | 74.39% (64.0–82.6) | 100.00% (94.1–100.0) | 85.31% |
| deepvariant | SNP | homopolymer | 10 | 1 | 0 | 90.00% (59.6–98.2) | 100.00% (70.1–100.0) | 94.74% |
| deepvariant | INDEL | all benchmark regions | 36 | 0 | 0 | 100.00% (90.4–100.0) | 100.00% (90.4–100.0) | 100.00% |
| deepvariant | INDEL | not_difficult | 9 | 0 | 0 | 100.00% (70.1–100.0) | 100.00% (70.1–100.0) | 100.00% |
| deepvariant | INDEL | all_difficult | 27 | 0 | 0 | 100.00% (87.5–100.0) | 100.00% (87.5–100.0) | 100.00% |
| deepvariant | INDEL | lowmap_or_segdup | 6 | 0 | 0 | 100.00% (61.0–100.0) | 100.00% (61.0–100.0) | 100.00% |
| deepvariant | INDEL | homopolymer | 13 | 0 | 0 | 100.00% (77.2–100.0) | 100.00% (77.2–100.0) | 100.00% |
| deepvariant | INDEL | tandem_repeat | 9 | 0 | 0 | 100.00% (70.1–100.0) | 100.00% (70.1–100.0) | 100.00% |

Intervals are 95% Wilson score intervals on the counts shown; small strata have wide intervals.
