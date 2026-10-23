### Benchmark results: `full-deepvariant-1.9.0`

Region `chr20:21000001-26000000` · HG002 vs GIAB v4.2.1 (GRCh38) · hap.py (vcfeval) · mean depth 36.3x

| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| deepvariant | SNP | all benchmark regions | 6,298 | 68 | 20 | 98.92% (98.6–99.1) | 99.68% (99.5–99.8) | 99.30% |
| deepvariant | SNP | not_difficult | 4,767 | 0 | 0 | 100.00% (99.9–100.0) | 100.00% (99.9–100.0) | 100.00% |
| deepvariant | SNP | all_difficult | 1,531 | 68 | 20 | 95.56% (94.4–96.5) | 98.66% (97.9–99.1) | 97.08% |
| deepvariant | SNP | lowmap_or_segdup | 1,063 | 67 | 18 | 93.70% (92.1–95.0) | 98.23% (97.2–98.9) | 95.91% |
| deepvariant | SNP | homopolymer | 163 | 1 | 0 | 99.39% (96.6–99.9) | 100.00% (97.7–100.0) | 99.69% |
| deepvariant | SNP | tandem_repeat | 206 | 1 | 2 | 99.51% (97.3–99.9) | 99.04% (96.6–99.7) | 99.28% |
| deepvariant | SNP | coding | 29 | 0 | 0 | 100.00% (88.3–100.0) | 100.00% (88.3–100.0) | 100.00% |
| deepvariant | INDEL | all benchmark regions | 816 | 9 | 1 | 98.90% (97.9–99.4) | 99.87% (99.3–100.0) | 99.38% |
| deepvariant | INDEL | not_difficult | 254 | 0 | 0 | 100.00% (98.5–100.0) | 100.00% (98.5–100.0) | 100.00% |
| deepvariant | INDEL | all_difficult | 564 | 9 | 1 | 98.40% (97.0–99.2) | 99.81% (98.9–100.0) | 99.10% |
| deepvariant | INDEL | lowmap_or_segdup | 82 | 6 | 1 | 92.68% (84.9–96.6) | 98.65% (92.7–99.8) | 95.57% |
| deepvariant | INDEL | homopolymer | 308 | 0 | 0 | 100.00% (98.8–100.0) | 100.00% (98.7–100.0) | 100.00% |
| deepvariant | INDEL | tandem_repeat | 201 | 3 | 0 | 98.51% (95.7–99.5) | 100.00% (97.9–100.0) | 99.25% |
| deepvariant | INDEL | coding | 1 | 0 | 0 | 100.00% (20.7–100.0) | 100.00% (20.7–100.0) | 100.00% |

Intervals are 95% Wilson score intervals on the counts shown; small strata have wide intervals.
