# Validation summary

!!! warning "Not a clinical validation"
    This page uses the headings of a clinical laboratory's validation summary (intended use,
    accuracy, precision, reportable range, limitations) to show what this repository's evidence
    covers and what it does not. It is not a CAP or CLIA validation. It uses one reference sample,
    5 Mb of one chromosome, one computer, no orthogonal confirmation and no laboratory director's
    sign-off. Nothing here supports clinical use.

## Intended use

The workflow calls germline SNVs and small indels from short-read whole-genome sequencing of a
human sample aligned to GRCh38, with GATK HaplotypeCaller or DeepVariant. This repository
validates *changes* to the workflow: a new tool version or default parameter is accepted only if
accuracy against the GIAB benchmark holds (the [release validation runbook](runbooks/release-validation.md)).

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

Every missed variant in this region is in a difficult stratum. Low-mappability and segmental
duplication sequence is the weakest: SNP recall there is 92.57% for GATK and 93.70% for
DeepVariant. The [caller comparison](results/caller-comparison.md) has every stratum, and scores
against the draft GIAB v5.0q benchmark, which covers more of the hard sequence.

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

The DeepVariant repeats come from [CS-03](case-studies/CS-03-deepvariant-memory.md), where the
shard count and memory limit were changed between runs: neither changed a call. The second engine
is described in [GA4GH standards](ga4gh.md). The regression gate relies on this: with unchanged
images and parameters it requires the true positive counts to match exactly
(`same_tools_max_tp_change_pct: 0.0` in `config/thresholds.yaml`).

All of these ran on one computer. Repeats across days, operators, sequencing runs or instruments
were not done, because the reads are one public data set.

## Reportable range

- **Variant types**: SNVs and indels in the size range of the v4.2.1 benchmark (under 50 bp).
  Structural variants are out of range for this workflow; the long-read module scores them
  separately, as QC only.
- **Genome**: GRCh38 only. Reads must use the same contig names as the reference (`chr20`, not
  `20`), or the run produces an empty result, which the workflow now refuses
  ([CS-02](case-studies/CS-02-contig-names.md)).
- **Regions**: performance is known inside the GIAB v4.2.1 confident regions of the test region.
  Outside them it was not measured.
- **Depth**: tested at about 35x. Lower depth was not tested.

## Acceptance criteria for a change

A candidate passes the gate (`scripts/compare_metrics.py`, `config/thresholds.yaml`) when, against
the committed baseline:

- overall F1 drops by no more than 0.2 points for SNPs and 0.5 points for indels;
- F1 in each stratum with at least 50 truth variants drops by no more than 1 point for SNPs and 2
  points for indels (smaller strata are reported, not gated);
- with unchanged images and parameters, the true positive counts are identical.

The two upgrades accepted under these rules are in the upgrade reports
([GATK 4.6.2.0 to 4.7.0.0](upgrade-reports/2026-10-23-gatk-4.6.2.0-to-4.7.0.0.md),
[DeepVariant 1.9.0 to 1.10.0](upgrade-reports/2026-10-23-deepvariant-1.9.0-to-1.10.0.md)). One change
was rejected: [INC-01](incidents/INC-01-mapq-default-change.md), a MAPQ default change that missed 8
more true SNPs to remove 1 false call.

## What a clinical validation would add

- More samples: the other GIAB reference genomes (HG001 to HG007), and samples with known
  pathogenic variants confirmed by another method.
- The whole genome, or at least every region the test reports on, instead of 5 Mb.
- Repeats across days, operators, library preparations and sequencers.
- Orthogonal confirmation (for example Sanger sequencing) of a sample of calls.
- Sample-level acceptance criteria such as minimum coverage, contamination and sex checks.
- A signed document under the laboratory's quality system, and a plan for revalidation.
