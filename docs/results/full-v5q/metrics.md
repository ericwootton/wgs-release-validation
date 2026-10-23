### Benchmark results: `full-v5q`

Region `chr20:21000001-26000000` · HG002 vs GIAB v5.0q smvar (GRCh38, draft) · hap.py (vcfeval) · mean depth 36.3x

| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| gatk | SNP | all benchmark regions | 6,374 | 106 | 59 | 98.34% (98.0–98.6) | 99.06% (98.8–99.3) | 98.70% |
| gatk | SNP | not_difficult | 4,832 | 2 | 10 | 99.96% (99.8–100.0) | 99.79% (99.6–99.9) | 99.88% |
| gatk | SNP | all_difficult | 1,542 | 104 | 49 | 93.26% (91.9–94.4) | 96.67% (95.6–97.5) | 94.93% |
| gatk | SNP | lowmap_or_segdup | 938 | 82 | 36 | 91.26% (89.3–92.9) | 95.95% (94.4–97.1) | 93.54% |
| gatk | SNP | homopolymer | 226 | 5 | 2 | 97.79% (94.9–99.1) | 99.07% (96.7–99.7) | 98.43% |
| gatk | SNP | tandem_repeat | 265 | 23 | 11 | 91.32% (87.3–94.1) | 95.55% (92.2–97.5) | 93.39% |
| gatk | SNP | coding | 29 | 0 | 0 | 100.00% (88.3–100.0) | 100.00% (88.3–100.0) | 100.00% |
| gatk | INDEL | all benchmark regions | 1,242 | 115 | 42 | 90.74% (89.0–92.2) | 96.27% (95.0–97.2) | 93.42% |
| gatk | INDEL | not_difficult | 282 | 1 | 1 | 99.65% (98.0–99.9) | 99.65% (98.1–99.9) | 99.65% |
| gatk | INDEL | all_difficult | 962 | 115 | 42 | 88.05% (85.8–89.9) | 95.00% (93.3–96.3) | 91.39% |
| gatk | INDEL | lowmap_or_segdup | 110 | 23 | 7 | 79.09% (70.6–85.6) | 92.39% (85.1–96.3) | 85.23% |
| gatk | INDEL | homopolymer | 599 | 63 | 15 | 89.48% (86.8–91.7) | 97.13% (95.3–98.3) | 93.15% |
| gatk | INDEL | tandem_repeat | 317 | 45 | 27 | 85.80% (81.5–89.2) | 90.25% (86.2–93.2) | 87.97% |
| gatk | INDEL | coding | 1 | 0 | 0 | 100.00% (20.7–100.0) | 100.00% (20.7–100.0) | 100.00% |
| deepvariant | SNP | all benchmark regions | 6,374 | 90 | 13 | 98.59% (98.3–98.8) | 99.79% (99.6–99.9) | 99.19% |
| deepvariant | SNP | not_difficult | 4,832 | 0 | 0 | 100.00% (99.9–100.0) | 100.00% (99.9–100.0) | 100.00% |
| deepvariant | SNP | all_difficult | 1,542 | 90 | 13 | 94.16% (92.9–95.2) | 99.11% (98.5–99.5) | 96.57% |
| deepvariant | SNP | lowmap_or_segdup | 938 | 69 | 7 | 92.64% (90.8–94.1) | 99.20% (98.4–99.6) | 95.81% |
| deepvariant | SNP | homopolymer | 226 | 7 | 1 | 96.90% (93.7–98.5) | 99.54% (97.4–99.9) | 98.20% |
| deepvariant | SNP | tandem_repeat | 265 | 19 | 6 | 92.83% (89.1–95.4) | 97.62% (94.9–98.9) | 95.16% |
| deepvariant | SNP | coding | 29 | 0 | 0 | 100.00% (88.3–100.0) | 100.00% (88.3–100.0) | 100.00% |
| deepvariant | INDEL | all benchmark regions | 1,242 | 70 | 16 | 94.36% (92.9–95.5) | 98.57% (97.7–99.1) | 96.42% |
| deepvariant | INDEL | not_difficult | 282 | 0 | 0 | 100.00% (98.7–100.0) | 100.00% (98.7–100.0) | 100.00% |
| deepvariant | INDEL | all_difficult | 962 | 70 | 16 | 92.72% (90.9–94.2) | 98.08% (96.9–98.8) | 95.33% |
| deepvariant | INDEL | lowmap_or_segdup | 110 | 15 | 2 | 86.36% (78.7–91.6) | 97.85% (92.5–99.4) | 91.75% |
| deepvariant | INDEL | homopolymer | 599 | 26 | 8 | 95.66% (93.7–97.0) | 98.51% (97.1–99.2) | 97.06% |
| deepvariant | INDEL | tandem_repeat | 317 | 38 | 8 | 88.01% (84.0–91.1) | 96.90% (94.0–98.4) | 92.24% |
| deepvariant | INDEL | coding | 1 | 0 | 0 | 100.00% (20.7–100.0) | 100.00% (20.7–100.0) | 100.00% |

Intervals are 95% Wilson score intervals on the counts shown; small strata have wide intervals.
