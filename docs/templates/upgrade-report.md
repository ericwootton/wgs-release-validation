# Upgrade report: TOOL OLD → NEW

Copy to `docs/upgrade-reports/YYYY-MM-DD-tool-old-to-new.md`.

| Field | Value |
|---|---|
| Date | YYYY-MM-DD |
| Component | e.g. GATK HaplotypeCaller |
| From → to | `image:old@sha256:…` → `image:new@sha256:…` |
| Decision | **Approve** / **Approve with notes** / **Block** |

## Summary and recommendation

Two or three sentences: the decision and the one fact it rests on.

## What changed

Quoted release notes that could affect results or runtime, with links.

## Validation performed

- Profile and region, benchmark and version, stratifications.
- Exact commands (`make run PROFILE=… EXTRA=…`), run labels, and the gate command.

## Results

The `compare_metrics.py` table (baseline = old, candidate = new), and the plot.

## Discordant calls examined

5–10 sites that changed state (TP↔FN, new FP), each with a one-line explanation.

## Runtime and cost impact

From `resources.tsv`: wall time, CPU time and peak memory per task, old vs new.

## Risks and follow-ups

What this validation does not cover, and what to watch after release.
