# Runbook: validating a new pipeline or tool version

Use this whenever a container image, tool parameters, or the workflow itself changes. The goal
is a written decision (approve, approve with notes, block) backed by benchmark numbers, before
anything is delivered to customers.

## 1. Before you start

- [ ] Read the release notes for each version from the tool's current version to the proposed
      version. Record all changes which could affect variant-calling results or resource use
      (for example, models, filters, and default settings).
- [ ] To pin the new image by digest, run
      `docker pull IMAGE:TAG` and then run
      `docker image inspect --format '{{index .RepoDigests 0}}' IMAGE:TAG`.
- [ ] Confirm that the current baselines match what you expect using `git log -- baselines/`.

## 2. Run the baseline and the candidate

Both runs use the same profile, inputs and thread counts. Only the image changes.

```bash
make run PROFILE=full LABEL=gatk-old EXTRA='gatk_docker=IMAGE:OLD@sha256:...'
make run PROFILE=full LABEL=gatk-new EXTRA='gatk_docker=IMAGE:NEW@sha256:...'
```

The `full` profile covers 5 Mb of chr20 and runs both callers side by side, about 5 minutes
each. It took 7.5 minutes (447 s) on an 8-core, 15 GB laptop once the GIAB files were
downloaded. If the image is untested, first run a quick smoke test using `ci`.

## 3. Compare

```bash
python3 scripts/compare_metrics.py docs/results/gatk-old/metrics.json docs/results/gatk-new/metrics.json \
    --thresholds config/thresholds.yaml --out-md docs/results/gatk-new/gate.md
python3 scripts/plot_metrics.py --metrics old=docs/results/gatk-old/metrics.json \
    --metrics new=docs/results/gatk-new/metrics.json --out docs/results/figures --prefix gatk-upgrade-
```

Exit code 0 means every gated row passed. Exit code 1 means at least one row failed. Exit code 2
means input comparison could not be performed (different regions, unreadable files).

## 4. Look at what changed, not just the totals

- List the sites whose decisions changed between the hap.py output VCF files from the two runs using
  `python3 scripts/diff_decisions.py results/gatk-old/gatk.vcf.gz results/gatk-new/gatk.vcf.gz -n 10`
  (a Markdown table showing the old and new decision, genotypes, and strata for each site).
- Check the sequencing reads for 5-10 of these (`scripts/site_evidence.py`, or the igv-reports
  page). Typical patterns include borderline-quality variant calls which change classification,
  INDELs with different representations, and sites in segmental duplication regions.
- To check for changes in runtime and memory use, compare `docs/results/<label>/resources.tsv`.

## 5. Decide and write it up

Fill in `docs/templates/upgrade-report.md`.

| Situation | Usual decision |
|---|---|
| Gate passes, no meaningful change | Approve |
| Gate passes, but a stratum moved or runtime/memory changed noticeably | Approve with notes (say what to tell customers, what to resize) |
| Gate fails overall, or a stratum customers rely on fails | Block, unless the change is a known improvement in a different representation that the benchmark penalizes; then escalate |

## 6. Release

- [ ] Update the default image in `wdl/main.wdl` in the same commit as the report.
- [ ] If the new metrics are adopted as the reference, update the
      baseline (see [updating-baselines.md](updating-baselines.md)).
- [ ] Add a CHANGELOG entry.
