### Benchmark results: `cs03-guard-s1-m1-r3`

Region `chr20:21800001-22000000` · HG002 vs GIAB v4.2.1 (GRCh38) · hap.py (vcfeval) · mean depth 35.2x

| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
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
