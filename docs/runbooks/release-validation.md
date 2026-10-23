# Runbook: validating a new pipeline or tool version

Use this whenever a container image, a tool parameter or the workflow itself changes. The goal is a
written decision (approve, approve with notes, block) backed by benchmark numbers, before anything
reaches a customer.

## 1. Before you start

- [ ] Read the tool's release notes for the versions between the current and proposed one. Note
      every change that could alter calls (models, filters, defaults) or resources.
- [ ] Pin the new image by digest: `docker pull IMAGE:TAG`, then
      `docker image inspect --format '{{index .RepoDigests 0}}' IMAGE:TAG`.
- [ ] Confirm the current baselines are the ones you expect: `git log -- baselines/`.

## 2. Run the baseline and the candidate

Both runs use the same profile, inputs and thread counts; only the image changes.

```bash
make run PROFILE=full LABEL=gatk-old EXTRA='gatk_docker=IMAGE:OLD@sha256:...'
make run PROFILE=full LABEL=gatk-new EXTRA='gatk_docker=IMAGE:NEW@sha256:...'
```

The `full` profile (5 Mb of chr20, both callers) took 7.5 minutes (447 s) on an 8-core, 15 GB
laptop once the GIAB files were downloaded; the two callers run side by side, about 5 minutes
each. Use `ci` for a quick smoke test first if the image is untested.

## 3. Compare

```bash
python3 scripts/compare_metrics.py docs/results/gatk-old/metrics.json docs/results/gatk-new/metrics.json \
    --thresholds config/thresholds.yaml --out-md docs/results/gatk-new/gate.md
python3 scripts/plot_metrics.py --metrics old=docs/results/gatk-old/metrics.json \
    --metrics new=docs/results/gatk-new/metrics.json --out docs/results/figures --prefix gatk-upgrade-
```

Exit code 0 means every gated row passed, 1 means at least one failed, 2 means the inputs could not
be compared (different regions, unreadable files).

## 4. Look at what changed, not just the totals

- List the sites that changed decision, from the hap.py output VCFs of both runs:
  `python3 scripts/diff_decisions.py results/gatk-old/gatk.vcf.gz results/gatk-new/gatk.vcf.gz -n 10`
  (a Markdown table: old and new decision, genotypes and strata for each site).
- For 5–10 of them, look at the reads (`scripts/site_evidence.py`, or an igv-reports page).
  Typical patterns: borderline-quality calls that flip, indels represented differently, sites in
  segmental duplications.
- Compare `docs/results/<label>/resources.tsv` for runtime and memory changes.

## 5. Decide and write it up

Fill in `docs/templates/upgrade-report.md`.

| Situation | Usual decision |
|---|---|
| Gate passes, no meaningful change | Approve |
| Gate passes, but a stratum moved or runtime/memory changed noticeably | Approve with notes (say what to tell customers, what to resize) |
| Gate fails overall, or a stratum customers rely on fails | Block, unless the change is a known improvement in a different representation that the benchmark penalises; then escalate |

## 6. Release

- [ ] Change the default image in `wdl/main.wdl` in the same commit as the report.
- [ ] If the new metrics become the reference, update the baseline (see
      [updating-baselines.md](updating-baselines.md)).
- [ ] Add a CHANGELOG entry.
