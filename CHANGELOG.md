# Changelog

All notable changes are recorded here. This format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/). A change of a pinned image or of a default
parameter gets an upgrade report in `docs/upgrade-reports/` and, if accepted, new baselines.

## [0.1.0] - 2026-10-23

Initial release of the core validation workflow, regression gate, and support material.

### Added

- `wdl/main.wdl` (WDL 1.0) streams a region from the HG002 35x Illumina BAM and a
  single-contig GRCh38 reference sequence. Small variants are called using GATK
  HaplotypeCaller 4.7.0.0 and/or DeepVariant 1.10.0, and the calls are normalized. Then,
  hap.py (vcfeval engine) is used to evaluate the calls against GIAB v4.2.1 using GIAB v3.6
  stratification. All images are pinned by digest, and all tasks record actual wall time, CPU
  time, and peak memory usage.
- Profiles include `fixture` (30 kb, offline test data), `ci` (200 kb), and `full` (5
  Mb). Data are downloaded only once and verified against the MD5 values in
  `config/data_manifest.tsv`.
- `scripts/summarize_happy.py` writes recall, precision, F1, and their 95% Wilson intervals to
  `metrics.json` and `metrics.md` by caller, variant type, and stratum. It fails the run if
  the benchmark is empty.
- `scripts/compare_metrics.py` provides the regression gate, with per-stratum allowed drops
  (`config/thresholds.yaml`). Small strata are reported but are not included in the gating
  decision. An exact-match rule is applied when tool images and parameters are unchanged.
- An optional `Preflight` task uses
  [ngs-preflight](https://github.com/ericwootton/ngs-preflight)
  to check inputs before variant calling begins.
- DeepVariant's out-of-memory guard monitors the container's `oom_kill` counter, outputs a message
  identifying memory as the cause, and fails the task. DeepVariant could otherwise hang and exit
  with code 247 with no message.
- CI (the `ci` profile and the gate on every push), a weekly extended run (the `full` profile),
  and a documentation site published on GitHub Pages.
- Upgrade reports cover GATK 4.6.2.0 → 4.7.0.0 and DeepVariant 1.9.0 → 1.10.0. A comparison of
  GATK and DeepVariant includes the GIAB v5.0q draft benchmark. A cost model covers AWS and GCP
  (`scripts/estimate_cost.py`, `config/prices.yaml`).
- Support material includes four case studies, one incident report (INC-01), runbooks
  for triage, releases, and the baseline, an FAQ, and ticket templates.
- Optional modules include long-read SV benchmarking using `truvari bench` and `truvari refine`,
  and QC of tandem repeats and CpG methylation (overall and by haplotype). A folder is provided
  for hand-off to partners (`wdl/optional/longread.wdl`). Customer deliverables include
  read-support BAM slices with an allele support table, a collection VCF, and TSV extracts for
  specific targets (`wdl/optional/deliverables.wdl`).
- SV merging was examined (`wdl/optional/sv_merge.wdl`, `make sv-merge`). truvari was used to
  benchmark the individual pbsv and Sniffles results, their union, two collapsed unions, and
  their intersection.
- Instructions for cloud runs using Cromwell on AWS HealthOmics or GCP
  Batch (`docs/results/cloud-run.md`, `scripts/cloud_inputs.py`). Cloud
  runs have not yet been executed.
- A profile is run through a GA4GH WES 1.0 server using `make wes` and `scripts/wes_run.py`. The
  result is gated against the miniwdl run. `fixture` and `ci` were run on Cromwell 91 and
  produced identical metrics (`docs/ga4gh.md`). `.dockstore.yml` registers the four workflows
  with Dockstore. Since Cromwell renames `http://` inputs, stratum names are taken from the
  input filenames before localization.
- `docs/validation-summary.md`: Summarizes accuracy, repeatability, and the reportable range in
  the form of a laboratory validation summary. This also describes what would be added for
  clinical validation.

### Known issues

- The local backend in Cromwell 92 fails when digest-pinned
  images are used
  ([cromwell#7846](https://github.com/broadinstitute/cromwell/issues/7846)).
  Use Cromwell 91.
