# Upgrade report: TOOL OLD → NEW

Copy to `docs/upgrade-reports/YYYY-MM-DD-tool-old-to-new.md`.

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Component | e.g. GATK HaplotypeCaller |
| From → to | `image:old@sha256:…` → `image:new@sha256:…` |
| Decision | **Approve** / **Approve with notes** / **Block** |

## Summary and recommendation

State the decision and 1 fact supporting it in 2 or 3 sentences.

## What changed

Quoted release notes that could affect results or runtime, with links.

## Validation performed

- Profile and region, benchmark and version, stratifications.
- Exact commands (`make run PROFILE=… EXTRA=…`), run labels, and regression gate commands.

## Results

The table from `compare_metrics.py` (baseline = old, candidate = new), along with the plot.

## Discordant calls examined

5-10 sites whose status changed (TP↔FN, new FP). Include a one-line explanation for each site.

## Runtime and cost impact

From `resources.tsv`: wall time, CPU time, and peak memory per task, old vs new.

## Risks and follow-ups

Items not covered by this validation and points to note after release.
