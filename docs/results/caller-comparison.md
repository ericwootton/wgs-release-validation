# Caller comparison: GATK HaplotypeCaller or DeepVariant?

**Recommendation: make DeepVariant 1.10.0 the default for short-read germline WGS, and keep GATK
4.7.0.0 for customers who need GATK's GVCF and joint-genotyping path or must stay consistent with
data already processed by GATK.** On the same reads, DeepVariant was at least as accurate in every
stratum of the gated benchmark and in all but one of the draft benchmark (SNPs in homopolymers,
98.20% against 98.43% F1 on 226 variants), made a tenth as many false SNP calls, and costs about
the same to run.

Everything below is one sample (HG002, 35x NovaSeq) on 5 Mb of chr20 (`full` profile), run on the
same machine with the same inputs. That is enough to see a consistent pattern, not to quote
genome-wide accuracy.

## Accuracy against the GIAB v4.2.1 benchmark (the gated one)

From [`full/metrics.md`](full/metrics.md). F1, with missed (FN) and false (FP) calls:

| Type | Stratum | Truth variants | GATK 4.7.0.0 | DeepVariant 1.10.0 |
|---|---|---:|---:|---:|
| SNP | all benchmark regions | 6,298 | 97.92% (82 FN, 182 FP) | 99.31% (68 FN, 19 FP) |
| SNP | not_difficult | 4,767 | 99.90% (0 FN, 10 FP) | 100.00% (0 FN, 0 FP) |
| SNP | all_difficult | 1,531 | 91.94% (82 FN, 172 FP) | 97.11% (68 FN, 19 FP) |
| SNP | lowmap_or_segdup | 1,063 | 88.69% (79 FN, 172 FP) | 95.91% (67 FN, 18 FP) |
| INDEL | all benchmark regions | 816 | 97.87% (14 FN, 20 FP) | 99.44% (8 FN, 1 FP) |
| INDEL | not_difficult | 254 | 100.00% (0 FN, 0 FP) | 100.00% (0 FN, 0 FP) |
| INDEL | all_difficult | 564 | 96.89% (14 FN, 20 FP) | 99.19% (8 FN, 1 FP) |
| INDEL | lowmap_or_segdup | 82 | 85.98% (7 FN, 17 FP) | 95.57% (6 FN, 1 FP) |

![F1 by stratum for GATK and DeepVariant on the full profile](figures/f1_by_stratum.png)

Outside the difficult regions the two callers are effectively identical. The gap is in
low-mappability and segmentally duplicated sequence, and it is mostly precision: 172 of GATK's 182
false SNP calls are there. Recall is closer (82 against 68 missed SNPs);
[CS-01](../case-studies/CS-01-missed-variants-lowmap.md) looks at the sites both callers miss.

## Against the draft GIAB v5.0q benchmark

GIAB's v5.0q small-variant benchmark is a **draft**, so it is used here for comparison only, never
for the gate. It evaluates a different and larger set of variants: in this region it has 1,242
truth INDELs against v4.2.1's 816, most of the additions in homopolymers and tandem repeats. From
[`full-v5q/metrics.md`](full-v5q/metrics.md):

| Type | Stratum | Truth variants | GATK 4.7.0.0 | DeepVariant 1.10.0 |
|---|---|---:|---:|---:|
| SNP | all benchmark regions | 6,374 | 98.70% (106 FN, 59 FP) | 99.19% (90 FN, 13 FP) |
| SNP | all_difficult | 1,542 | 94.93% (104 FN, 49 FP) | 96.57% (90 FN, 13 FP) |
| SNP | lowmap_or_segdup | 938 | 93.54% (82 FN, 36 FP) | 95.81% (69 FN, 7 FP) |
| INDEL | all benchmark regions | 1,242 | 93.42% (115 FN, 42 FP) | 96.42% (70 FN, 16 FP) |
| INDEL | homopolymer | 599 | 93.15% (63 FN, 15 FP) | 97.06% (26 FN, 8 FP) |
| INDEL | tandem_repeat | 317 | 87.97% (45 FN, 27 FP) | 92.24% (38 FN, 8 FP) |
| INDEL | lowmap_or_segdup | 110 | 85.23% (23 FN, 7 FP) | 91.75% (15 FN, 2 FP) |

Two things to read from it:

- **INDEL scores drop for both callers**, because the new benchmark includes the harder repeats.
  DeepVariant's lead grows there: it misses 26 homopolymer INDELs to GATK's 63.
- **GATK's SNP score goes up, which is not a sign that it got better.** Of the 182 SNP calls that
  v4.2.1 counts as false, 137 fall outside the regions v5.0q evaluates and 45 are still false
  (traced site by site through the two hap.py output VCFs). The draft benchmark simply does not
  score most of the sequence where GATK makes false calls. Comparing callers on one benchmark is
  fair; comparing one caller's score across benchmarks is not.

## Cost and runtime

From the [cost estimate](cost-estimate.md), which scales the measured task times to a 30x whole
genome; central estimates, per genome:

| Option | GATK 4.7.0.0 | DeepVariant 1.10.0 |
|---|---:|---:|
| AWS EC2 us-east-1, spot | $3.01 | $2.99 |
| AWS EC2 us-east-1, on demand | $6.83 | $6.80 |
| GCP Batch northamerica-northeast1, spot | $3.86 | $3.84 |
| AWS HealthOmics us-east-1 | $18.47 | $18.38 |

The central estimates differ by under 1%, well inside the estimates' own ranges. Measured on the
`full` run (both callers side by side, 4 CPUs each): HaplotypeCaller 297.7 s wall and 938
CPU-seconds, DeepVariant 296.5 s and 896 CPU-seconds. Single runs on this laptop vary: in the
separate upgrade runs, each caller on its own, DeepVariant 1.10.0 took 235.5 s and GATK 4.7.0.0
288.1 s. Neither caller is clearly cheaper; re-measure before quoting a difference. The practical
differences are elsewhere:

- DeepVariant is given 8 GiB to GATK's 6 GiB. Its recorded peak was about 2 GiB on the 200 kb
  `ci` region and 6.9 to 7.9 GiB in three runs on the 5 Mb `full` region, but that peak includes
  file cache, which
  fills toward whatever limit is set ([CS-03](../case-studies/CS-03-deepvariant-memory.md)). On a
  4-vCPU machine the 8 GiB costs nothing extra, and customers who lower it to save money can hit
  the intermittent failures CS-03 describes.
- The DeepVariant image is about 7 GB and the GATK image about 9 GB, so neither is cheap to pull
  on every node; cache them in the region's registry.
- Runtimes here come from one laptop CPU; the estimate prices them on the machines in
  `config/prices.yaml`. Re-measure on the customer's actual instance family before quoting.

## When GATK is still the right choice

- The customer joint-genotypes a cohort with GATK (`-ERC GVCF`, GenomicsDBImport,
  GenotypeGVCFs), or has years of GATK-processed samples to stay consistent with. Switching callers
  mid-cohort creates a batch effect that is worse than the accuracy gain.
- A regulated or published protocol names GATK and changing it means revalidation.
- They need a tool that ships inside the GATK image (Mutect2, CNV callers) and want one image to
  maintain.

## What this comparison does not cover

- Other samples, ancestries, coverage depths, PCR-plus libraries, or exome and panel data (the
  DeepVariant WES model is separate).
- GVCF output and joint calling.
- Long reads, for which DeepVariant has its own models and GATK is not the usual choice.
