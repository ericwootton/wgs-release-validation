### Benchmark results: `full`

Region `chr20:21000001-26000000` · HG002 vs GIAB v4.2.1 (GRCh38) · hap.py (vcfeval) · mean depth 36.3x

| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| gatk | SNP | all benchmark regions | 6,298 | 82 | 182 | 98.70% (98.4–98.9) | 97.15% (96.7–97.5) | 97.92% |
| gatk | SNP | not_difficult | 4,767 | 0 | 10 | 100.00% (99.9–100.0) | 99.79% (99.6–99.9) | 99.90% |
| gatk | SNP | all_difficult | 1,531 | 82 | 172 | 94.64% (93.4–95.7) | 89.39% (87.8–90.8) | 91.94% |
| gatk | SNP | lowmap_or_segdup | 1,063 | 79 | 172 | 92.57% (90.8–94.0) | 85.12% (83.0–87.1) | 88.69% |
| gatk | SNP | homopolymer | 163 | 1 | 2 | 99.39% (96.6–99.9) | 98.78% (95.7–99.7) | 99.08% |
| gatk | SNP | tandem_repeat | 206 | 3 | 3 | 98.54% (95.8–99.5) | 98.54% (95.8–99.5) | 98.54% |
| gatk | SNP | coding | 29 | 0 | 0 | 100.00% (88.3–100.0) | 100.00% (88.3–100.0) | 100.00% |
| gatk | INDEL | all benchmark regions | 816 | 14 | 20 | 98.28% (97.1–99.0) | 97.46% (96.1–98.4) | 97.87% |
| gatk | INDEL | not_difficult | 254 | 0 | 0 | 100.00% (98.5–100.0) | 100.00% (98.5–100.0) | 100.00% |
| gatk | INDEL | all_difficult | 564 | 14 | 20 | 97.52% (95.9–98.5) | 96.27% (94.3–97.6) | 96.89% |
| gatk | INDEL | lowmap_or_segdup | 82 | 7 | 17 | 91.46% (83.4–95.8) | 81.11% (71.8–87.9) | 85.98% |
| gatk | INDEL | homopolymer | 308 | 3 | 2 | 99.03% (97.2–99.7) | 99.31% (97.5–99.8) | 99.17% |
| gatk | INDEL | tandem_repeat | 201 | 4 | 1 | 98.01% (95.0–99.2) | 99.45% (97.0–99.9) | 98.72% |
| gatk | INDEL | coding | 1 | 0 | 0 | 100.00% (20.7–100.0) | 100.00% (20.7–100.0) | 100.00% |
| deepvariant | SNP | all benchmark regions | 6,298 | 68 | 19 | 98.92% (98.6–99.1) | 99.70% (99.5–99.8) | 99.31% |
| deepvariant | SNP | not_difficult | 4,767 | 0 | 0 | 100.00% (99.9–100.0) | 100.00% (99.9–100.0) | 100.00% |
| deepvariant | SNP | all_difficult | 1,531 | 68 | 19 | 95.56% (94.4–96.5) | 98.72% (98.0–99.2) | 97.11% |
| deepvariant | SNP | lowmap_or_segdup | 1,063 | 67 | 18 | 93.70% (92.1–95.0) | 98.23% (97.2–98.9) | 95.91% |
| deepvariant | SNP | homopolymer | 163 | 1 | 0 | 99.39% (96.6–99.9) | 100.00% (97.7–100.0) | 99.69% |
| deepvariant | SNP | tandem_repeat | 206 | 1 | 1 | 99.51% (97.3–99.9) | 99.52% (97.3–99.9) | 99.52% |
| deepvariant | SNP | coding | 29 | 0 | 0 | 100.00% (88.3–100.0) | 100.00% (88.3–100.0) | 100.00% |
| deepvariant | INDEL | all benchmark regions | 816 | 8 | 1 | 99.02% (98.1–99.5) | 99.87% (99.3–100.0) | 99.44% |
| deepvariant | INDEL | not_difficult | 254 | 0 | 0 | 100.00% (98.5–100.0) | 100.00% (98.5–100.0) | 100.00% |
| deepvariant | INDEL | all_difficult | 564 | 8 | 1 | 98.58% (97.2–99.3) | 99.81% (98.9–100.0) | 99.19% |
| deepvariant | INDEL | lowmap_or_segdup | 82 | 6 | 1 | 92.68% (84.9–96.6) | 98.65% (92.7–99.8) | 95.57% |
| deepvariant | INDEL | homopolymer | 308 | 0 | 0 | 100.00% (98.8–100.0) | 100.00% (98.7–100.0) | 100.00% |
| deepvariant | INDEL | tandem_repeat | 201 | 2 | 0 | 99.00% (96.4–99.7) | 100.00% (97.9–100.0) | 99.50% |
| deepvariant | INDEL | coding | 1 | 0 | 0 | 100.00% (20.7–100.0) | 100.00% (20.7–100.0) | 100.00% |

Intervals are 95% Wilson score intervals on the counts shown; small strata have wide intervals.
