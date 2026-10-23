# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/). A change of a pinned image or of a default parameter
gets an upgrade report in `docs/upgrade-reports/` and, if accepted, new baselines.

## [0.1.0] - 2026-10-23

First release: the core validation workflow, the regression gate and the support material.

### Added

- `wdl/main.wdl` (WDL 1.0): streams a region of the HG002 35x Illumina BAM and a single-contig
  GRCh38 reference, calls small variants with GATK HaplotypeCaller 4.7.0.0 and/or DeepVariant
  1.10.0, normalises the calls, and benchmarks them with hap.py (vcfeval engine) against GIAB
  v4.2.1 with GIAB v3.6 stratifications. Every image is pinned by digest; every task records
  wall time, CPU time and peak memory.
- Profiles `fixture` (30 kb, offline test data), `ci` (200 kb) and `full` (5 Mb); data is
  downloaded once and checked against MD5s in `config/data_manifest.tsv`.
- `scripts/summarize_happy.py`: recall, precision and F1 per caller, type and stratum with 95%
  Wilson intervals, in `metrics.json` and `metrics.md`. Fails the run on an empty benchmark.
- `scripts/compare_metrics.py`: the regression gate, with per-stratum allowed drops
  (`config/thresholds.yaml`), small strata reported but not gated, and an exact-match rule when
  tool images and parameters are unchanged.
- Optional `Preflight` task that checks inputs with
  [ngs-preflight](https://github.com/ericwootton/ngs-preflight) before any calling starts.
- An out-of-memory guard for DeepVariant: it watches the container's `oom_kill` counter and
  fails the task with a message naming memory as the cause, where DeepVariant could otherwise hang
  and exit 247 with no message.
- CI (`ci` profile and the gate on every push), a weekly extended run (`full` profile), and a
  documentation site published to GitHub Pages.
- Upgrade reports for GATK 4.6.2.0 → 4.7.0.0 and DeepVariant 1.9.0 → 1.10.0, a GATK versus
  DeepVariant comparison including the draft GIAB v5.0q benchmark, and a cost model for AWS and
  GCP (`scripts/estimate_cost.py`, `config/prices.yaml`).
- Support material: four case studies, one incident report (INC-01), triage, release and
  baseline runbooks, a FAQ and ticket templates.
- Optional modules: long-read SV (benchmarked with `truvari bench` and `truvari refine`),
  tandem-repeat and CpG methylation QC (combined and per haplotype) with a partner handoff folder
  (`wdl/optional/longread.wdl`), and customer deliverables: read-support BAM slices with an
  allele-support table, a collection VCF and targeted TSV extracts (`wdl/optional/deliverables.wdl`).
- An SV merging study (`wdl/optional/sv_merge.wdl`, `make sv-merge`): pbsv and Sniffles alone,
  their union, two collapsed unions and their intersection, each benchmarked with truvari.
- Steps for a cloud run on AWS HealthOmics or GCP Batch through Cromwell
  (`docs/results/cloud-run.md`, `scripts/cloud_inputs.py`), not yet executed.
- `make wes` and `scripts/wes_run.py`: run a profile through a GA4GH WES 1.0 server and gate the
  result against the miniwdl run. `fixture` and `ci` ran on Cromwell 91 with identical metrics
  (`docs/ga4gh.md`). `.dockstore.yml` registers the four workflows with Dockstore. Stratum names
  are taken from the input file names before localisation, because Cromwell renames `http://`
  inputs.
- `docs/validation-summary.md`: accuracy, repeatability and reportable range in the layout of a
  laboratory validation summary, with what a clinical validation would add.

### Known issues

- Cromwell 92's local backend fails on digest-pinned images
  ([cromwell#7846](https://github.com/broadinstitute/cromwell/issues/7846)); use Cromwell 91.
