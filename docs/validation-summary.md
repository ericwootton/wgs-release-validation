# Validation summary

!!! warning "Not a clinical validation"
    This page uses the headings from a clinical laboratory validation overview (intended use,
    accuracy, precision, reportable range, and limitations). These headings are used to show what
    the evidence in this repository covers and what it does not. This is not a CAP or CLIA
    validation. Only a single reference sample, a 5 Mb region on a single chromosome, and a single
    computer were used. No confirmation using an independent method was performed, and no approval
    from a laboratory director was obtained. Nothing presented here supports clinical use.

## Intended use

This workflow uses GATK HaplotypeCaller or DeepVariant for germline SNV and small insertion and
deletion calling. Input consists of human short-read whole-genome sequencing data aligned to
GRCh38. This repository validates *changes* to the workflow. New tool versions or default
parameters are accepted only if accuracy against the GIAB benchmark is maintained
([release validation runbook](runbooks/release-validation.md)).

## Test material

| Item | Value |
|---|---|
| Sample | HG002 (GIAB), Illumina NovaSeq PCR-free, mean depth 36.3x in the test region |
| Reference | GRCh38 no-alt analysis set |
| Truth set | GIAB HG002 v4.2.1 small variants, inside its confident regions |
| Test region | `chr20:21000001-26000000` (5 Mb, the `full` profile); `chr20:21800001-22000000` (200 kb, `ci`) |
| Comparison | hap.py 0.3.15 with the RTG vcfeval engine, GIAB v3.6 stratifications |
| Tools | GATK 4.7.0.0 and DeepVariant 1.10.0, images pinned by digest (`wdl/main.wdl`) |

## Accuracy

From [the `full` run](results/full/metrics.md). Intervals are 95% Wilson score intervals.

| Caller | Type | Regions | Truth | Missed | False calls | Recall (95% CI) | Precision (95% CI) | F1 |
|---|---|---|---:|---:|---:|---:|---:|---:|
| GATK | SNP | all benchmark regions | 6,298 | 82 | 182 | 98.70% (98.4 to 98.9) | 97.15% (96.7 to 97.5) | 97.92% |
| GATK | SNP | not difficult | 4,767 | 0 | 10 | 100.00% (99.9 to 100.0) | 99.79% (99.6 to 99.9) | 99.90% |
| GATK | INDEL | all benchmark regions | 816 | 14 | 20 | 98.28% (97.1 to 99.0) | 97.46% (96.1 to 98.4) | 97.87% |
| GATK | INDEL | not difficult | 254 | 0 | 0 | 100.00% (98.5 to 100.0) | 100.00% (98.5 to 100.0) | 100.00% |
| DeepVariant | SNP | all benchmark regions | 6,298 | 68 | 19 | 98.92% (98.6 to 99.1) | 99.70% (99.5 to 99.8) | 99.31% |
| DeepVariant | SNP | not difficult | 4,767 | 0 | 0 | 100.00% (99.9 to 100.0) | 100.00% (99.9 to 100.0) | 100.00% |
| DeepVariant | INDEL | all benchmark regions | 816 | 8 | 1 | 99.02% (98.1 to 99.5) | 99.87% (99.3 to 100.0) | 99.44% |
| DeepVariant | INDEL | not difficult | 254 | 0 | 0 | 100.00% (98.5 to 100.0) | 100.00% (98.5 to 100.0) | 100.00% |

All missed variants in this region belonged to difficult strata. Performance was lowest in low
mappability and segmental duplication regions, where SNP recall was 92.57% for GATK and 93.70%
for DeepVariant. The [caller comparison](results/caller-comparison.md) has every stratum. It also
scores against the draft GIAB v5.0q benchmark, which covers more of the hard sequence.

## Precision (repeatability and reproducibility)

The same inputs and images gave the same result each time. "Same" here means identical true
positive, false negative and false call counts in every variant type and stratum row of
`metrics.json`, not only the same F1.

| What was repeated | Runs | Rows compared | Identical |
|---|---:|---:|---|
| GATK 4.7.0.0, `full` region | 2 (`full`, `full-gatk-4.7.0.0`) | 26 | yes |
| DeepVariant 1.10.0, `full` region | 2 (`full`, `full-deepvariant-1.10.0`) | 25 | yes |
| GATK 4.7.0.0, `ci` region | 2 (`ci`, `ci-both`) | 24 | yes |
| DeepVariant 1.10.0, `ci` region, with 1, 2 or 4 shards and 1, 2 or 8 GiB of memory | 15 | 24 | yes |
| GATK 4.7.0.0, `ci` region, on a second engine (Cromwell 91 through GA4GH WES) | 2 (`ci`, `ci-wes`) | 24 | yes |

Repeated DeepVariant runs came from [CS-03](case-studies/CS-03-deepvariant-memory.md). Shard
counts and memory limits were changed between runs, but neither change affected variant calls.
The second engine is described in [GA4GH standards](ga4gh.md). Based on this behaviour, the regression
gate requires identical true positive counts when images and parameters remain unchanged
(`same_tools_max_tp_change_pct: 0.0` in `config/thresholds.yaml`).

These were all run on the same computer. Since the reads came from a single public dataset,
repeat runs were not performed under conditions which varied the date, operator, sequencing run,
or instrument.

## Reportable range

- **Variant types**: SNV and INDEL variants within the v4.2.1 benchmark size range (less than
  50 bp). Structural variants are outside the scope of this workflow and are assessed
  separately by the long-read module for QC purposes only.
- **Genome**: Only GRCh38 is supported. Reads must use the same contig names as the reference
  sequence (`chr20`, not `20`). Otherwise, the run will produce empty results which the
  current workflow rejects ([CS-02](case-studies/CS-02-contig-names.md)).
- **Regions**: performance is known within the GIAB v4.2.1 confident regions in the tested area.
  Outside these regions, performance was not measured.
- **Depth**: Testing was performed at a sequencing depth of about 35x. Lower sequencing depths were not tested.

## Acceptance criteria for a change

A candidate passes the regression gate if it meets the following conditions when compared against
the committed baseline (`scripts/compare_metrics.py`, `config/thresholds.yaml`):

- Overall F1 drops by no more than 0.2 points for SNPs and 0.5 points for indels.
- For each stratum containing at least 50 truth variants, F1 declines are no more than 1 point
  for SNP and 2 points for INDEL (smaller strata are included in the report but excluded from the
  regression gate).
- If the image and parameters are unchanged, the number of true positive calls remains the same.

The 2 upgrades approved under these rules were documented in the upgrade report
([GATK 4.6.2.0 to 4.7.0.0](upgrade-reports/2026-10-23-gatk-4.6.2.0-to-4.7.0.0.md),
[DeepVariant 1.9.0 to 1.10.0](upgrade-reports/2026-10-23-deepvariant-1.9.0-to-1.10.0.md)). 1 change
involving the MAPQ default was rejected ([INC-01](incidents/INC-01-mapq-default-change.md)). This
change eliminated 1 false call but resulted in 8 additional missed true SNPs.

## What a clinical validation would add

- More samples, including other GIAB reference genomes (HG001-HG007) and samples carrying
  known pathogenic variants which have been confirmed using other methods.
- The entire genome, or at least every region reported on by the test, instead of 5 Mb.
- Repeats across days, operators, library preparations, and sequencers.
- Orthogonal confirmation (for example using Sanger sequencing) of a subset of variant calls.
- Acceptance criteria at the sample level such as minimum coverage, contamination checks, and sex checks.
- A signed document governed by the laboratory quality system and a revalidation plan.
