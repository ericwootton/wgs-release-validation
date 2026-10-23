# wgs-release-validation

Release validation for a germline whole-genome workflow: call variants on a region of GIAB HG002,
grade them against the GIAB truth set by genome stratum, and block any tool or parameter change
that makes the results worse.

[![CI](https://github.com/ericwootton/wgs-release-validation/actions/workflows/ci.yml/badge.svg)](https://github.com/ericwootton/wgs-release-validation/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![WDL 1.0](https://img.shields.io/badge/WDL-1.0-blue)](wdl/main.wdl)

Documentation, results, case studies and runbooks: **<https://ericwootton.github.io/wgs-release-validation/>**

## Results at a glance

<!-- results:start -->
HG002 against GIAB v4.2.1, 5 Mb of chr20 (`full` profile, mean depth 36.3x). F1, with missed and
false calls in brackets; full tables with confidence intervals are in
[`docs/results/full/metrics.md`](docs/results/full/metrics.md).

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

Both callers are near perfect outside the difficult regions; the difference is in repeats and
duplicated sequence, where most of GATK's false SNP calls sit.
<!-- results:end -->

![F1 by stratum for GATK and DeepVariant on the full profile](docs/results/figures/f1_by_stratum.png)

The comparison against the draft GIAB v5.0q benchmark, the cost of each caller and a
recommendation are in [the caller comparison](docs/results/caller-comparison.md).

## Why this exists

A pipeline that gave correct results last month can give different ones after an image update or
a changed default, and nobody notices until a customer does. This repository shows how to catch
that before release: a fixed benchmark, per-stratum thresholds, a gate in CI, and a written
decision for every upgrade.

## Quickstart

Needs Linux or macOS, Docker and Python 3.10+. Disk: about 12 GB of images for the GATK path (the
GATK image alone is 9 GB; DeepVariant adds 7 GB) and under 1 GB of downloaded GIAB files.

```bash
python3 -m pip install -r requirements-dev.txt     # miniwdl, PyYAML, matplotlib, pytest, ruff, mypy
docker build -t happy-vcfeval:0.3.15-rtg3.13 docker/happy-vcfeval
make run PROFILE=fixture                           # committed test data, no GIAB downloads (minutes)
make ci                                            # 200 kb of chr20, then the regression gate
```

`make ci` downloads the GIAB files once (checked against MD5s), streams the reads it needs over
HTTPS, and exits non-zero if any gated stratum got worse than `baselines/ci.json` allows. The input
check needs the [ngs-preflight](https://github.com/ericwootton/ngs-preflight) image
(`docker build -t ngs-preflight:0.1.0 <path to ngs-preflight>`); without it, add
`EXTRA="run_preflight=false"`.

## What it does

```mermaid
flowchart LR
    ref[GRCh38 chr20] --> slice[FetchReadsSlice<br/>region of the HG002 BAM]
    reads[(HG002 35x Illumina)] --> slice
    slice --> pre{{Preflight<br/>ngs-preflight}}
    pre --> gatk[GATK HaplotypeCaller]
    pre --> dv[DeepVariant]
    gatk --> norm[normalise]
    dv --> norm
    norm --> happy[hap.py + vcfeval<br/>GIAB v4.2.1, stratified]
    happy --> sum[metrics.json<br/>recall, precision, F1, 95% CI]
    sum --> gate{{regression gate<br/>vs baselines/}}
```

Every task records wall time, CPU time and peak memory, which feed the
[cost estimate](docs/results/cost-estimate.md). [How it works](docs/workflow.md) has the details.

What else is here:

- **Upgrade reports**: [GATK 4.6.2.0 → 4.7.0.0](docs/upgrade-reports/2026-10-23-gatk-4.6.2.0-to-4.7.0.0.md),
  [DeepVariant 1.9.0 → 1.10.0](docs/upgrade-reports/2026-10-23-deepvariant-1.9.0-to-1.10.0.md).
- **An incident the gate caught**: [INC-01](docs/incidents/INC-01-mapq-default-change.md), a proposed
  MAPQ default change rejected before release.
- **Support-ticket case studies**, each ending with the reply sent to the customer:
  [CS-01](docs/case-studies/CS-01-missed-variants-lowmap.md) missed variants in low-mappability sequence,
  [CS-02](docs/case-studies/CS-02-contig-names.md) `20` versus `chr20`,
  [CS-03](docs/case-studies/CS-03-deepvariant-memory.md) DeepVariant out of memory,
  [CS-04](docs/case-studies/CS-04-partner-handoff.md) a long-read partner handoff.
- **Runbooks** for [release validation](docs/runbooks/release-validation.md),
  [failed-run triage](docs/runbooks/failed-run-triage.md) and
  [updating baselines](docs/runbooks/updating-baselines.md); a [FAQ](docs/kb/faq.md).
- **Optional modules**: long-read SV, tandem-repeat and methylation QC with a partner handoff
  folder (`wdl/optional/longread.wdl`), and customer deliverables (`wdl/optional/deliverables.wdl`,
  [what the customer receives](docs/deliverables.md)).
- **SV merging study**: [six ways to combine pbsv and Sniffles calls](docs/results/sv-merging.md),
  each benchmarked against GIAB v5.0q (`wdl/optional/sv_merge.wdl`).
- **Cloud**: [steps for AWS HealthOmics and GCP Batch](docs/results/cloud-run.md) (written, not yet run).
- **GA4GH**: the same workflow [run through a WES API](docs/ga4gh.md) on Cromwell, with results
  identical to miniwdl; a `.dockstore.yml` for Dockstore (TRS); notes on DRS inputs.
- **[Validation summary](docs/validation-summary.md)**: accuracy, repeatability and reportable range
  laid out as a lab validation summary would be (it is not a clinical validation).

### Tools

| Tool | Version | Image |
|---|---|---|
| GATK HaplotypeCaller | 4.7.0.0 | `broadinstitute/gatk:4.7.0.0@sha256:7da5cf58…` |
| DeepVariant | 1.10.0 | `google/deepvariant:1.10.0@sha256:962e5a83…` |
| hap.py with RTG vcfeval | 0.3.15 / RTG 3.13 | built from `docker/happy-vcfeval` |
| samtools / bcftools | 1.24 | biocontainers, pinned by digest |
| mosdepth | 0.3.14 | biocontainers, pinned by digest |
| ngs-preflight | 0.1.0 | built from the companion repo |

Full digests are in `wdl/main.wdl`, and every run records them in `metrics.json`.

## Data and citations

| Data | Source |
|---|---|
| Reads | HG002 NovaSeq PCR-free 35x, GRCh38 no-alt (Google DeepVariant case-study data) |
| Reference | `GCA_000001405.15_GRCh38_no_alt_analysis_set` |
| Truth | GIAB HG002 v4.2.1 (gate); GIAB v5.0q small variants (**draft**, comparison only) |
| Strata | GIAB genome stratifications v3.6 |

URLs and MD5s are in `config/data_manifest.tsv`. GIAB data are released by NIST for benchmarking.

- Zook JM et al. *Sci Data* 3, 160025 (2016). [doi:10.1038/sdata.2016.25](https://doi.org/10.1038/sdata.2016.25)
- Wagner J et al. *Cell Genomics* 2(5), 100128 (2022). [doi:10.1016/j.xgen.2022.100128](https://doi.org/10.1016/j.xgen.2022.100128)
- Dwarshuis N et al. *Nat Commun* 15, 9029 (2024). [doi:10.1038/s41467-024-53260-y](https://doi.org/10.1038/s41467-024-53260-y)
- Krusche P et al. *Nat Biotechnol* 37, 555–560 (2019). [doi:10.1038/s41587-019-0054-x](https://doi.org/10.1038/s41587-019-0054-x)

## Limitations

- One sample (HG002), one chromosome, 5 Mb at most. Accuracy on 5 Mb of chr20 is not
  genome-wide accuracy, and small strata have wide confidence intervals (shown in every table).
- Benchmarks cover the GIAB confident regions only. The hardest sequence is partly outside them,
  which is why scores against the draft v5.0q benchmark are lower.
- Short reads only in the gated workflow. The long-read module is QC for a handoff, not a gate.
- Research use only. Nothing here is validated for clinical decisions.
- The cloud run is documented but has not been executed, so the cost model is an estimate from
  local resource use and published prices.

### Gotchas found on the way

- **The read header has to be trimmed by re-encoding, not `samtools reheader`.** BAM records
  point to contigs by index, so deleting `@SQ` lines with `reheader` silently moves reads to the
  wrong chromosome. `FetchReadsSlice` re-encodes through SAM text instead.
- **Extra contigs in the BAM header are fine for GATK 4.7 and DeepVariant 1.10**, contrary to what
  is often assumed; a name mismatch (`20` versus `chr20`) is what actually breaks a run, silently
  ([CS-02](docs/case-studies/CS-02-contig-names.md)).
- **Some images cannot stream over HTTPS.** `staphb/samtools:1.24` has no CA certificates, so
  htslib fails with libcurl error 60; the biocontainers images work.
- **hap.py from bioconda cannot use vcfeval**: it is built without it and does not ship RTG
  Tools. `docker/happy-vcfeval` adds RTG Tools 3.13.
- **DeepVariant can hang instead of failing when out of memory**: an OOM-killed worker leaves the
  others waiting about five minutes before exiting 247 with no message. At the edge of the limit
  this happens in some runs and not others. The task now watches the container's OOM counter and
  fails with a message naming memory as the cause
  ([CS-03](docs/case-studies/CS-03-deepvariant-memory.md)).
- **Cromwell 92 cannot run digest-pinned images on its local backend**
  ([cromwell#7846](https://github.com/broadinstitute/cromwell/issues/7846)); Cromwell 91 runs the
  workflow unchanged ([GA4GH standards](docs/ga4gh.md)).
- **Task images should run as root.** Cromwell saves the inputs it downloads readable by its own
  user only, so the ngs-preflight image, which ran as an unprivileged user, failed under Cromwell
  and passed under miniwdl.
- **`truvari refine` can hang with its default POA aligner**: on one 40 kb region it failed to
  allocate 32 GiB and then waited at 0% CPU. The long-read module uses MAFFT and a 30-minute
  timeout instead ([CS-04](docs/case-studies/CS-04-partner-handoff.md)).

## Repository layout

```text
wdl/main.wdl, wdl/tasks/   the workflow; wdl/optional/ has the long-read and deliverables modules
scripts/                   data preparation, metrics, regression gate, plots, cost model, cloud inputs
config/                    data manifest (URLs, MD5s), profiles, gate thresholds, cloud prices
baselines/                 gated reference metrics (change only per the baseline runbook)
inputs/                    inputs JSON per profile and module
docs/                      the documentation site; docs/results/ holds committed run outputs
docker/happy-vcfeval/      hap.py with RTG vcfeval
cloud/                     example Cromwell config and image helper for a cloud run
tests/                     offline unit tests and the fixture data
CLAUDE.md                  conventions for working on this repository
```

## How this was built

The author made the design decisions (what to benchmark and how, the gate's rules and thresholds,
how each case study is told), reviewed the diffs and verified the results.
[Claude Code](https://claude.com/claude-code) did scaffolding, test generation and iteration under
that direction, and independent AI review passes were run on the diffs. Every number in the docs
comes from a generated file: a real run of the workflow on public data. See [`CLAUDE.md`](CLAUDE.md).

## Licence

MIT, see [`LICENSE`](LICENSE). GIAB data are public; see the citations above.
