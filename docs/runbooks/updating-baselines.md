# Runbook: updating a regression baseline

`baselines/<profile>.json` is the reference every CI run is gated against. Changing this file
changes what "no regression" means. Therefore, each change requires a reviewed, explained commit
and must never occur as a side effect.

## When a baseline update is legitimate

- A tool upgrade was approved in an upgrade report and its metrics become the new normal.
- The benchmark itself changed (new truth set, new stratifications, new region).
- A bug in the benchmarking has been fixed. The previous values were incorrect.

## When it is not

- CI failed, and "the numbers are close enough". Investigate this first. Refer to
  [failed-run-triage.md](failed-run-triage.md). If identical tools produce different counts, this
  is a determinism issue which requires an explanation. This does not warrant updating the
  baseline.
- In order to allow unrelated changes to pass.

## Steps

1. Run the pinned workflow from a clean state to generate new
   metrics using `make run PROFILE=ci`. Also run it using `PROFILE=full` if that
   baseline changes.
2. Show the differences from the current baseline and save the table for use in the commit
   message using
   `python3 scripts/compare_metrics.py baselines/ci.json docs/results/ci/metrics.json --out-md /tmp/diff.md`.
3. Copy: `cp docs/results/ci/metrics.json baselines/ci.json`.
4. Commit only the baseline (and the report which explains its basis). Include a commit message
   which explicitly states the following:
   - Why the baseline changes (link the upgrade report or issue).
   - The headline deltas (overall SNP and INDEL F1, any stratum that moved more than its
     threshold).
   - The run label and the tool versions it came from.
5. Please confirm that the CI checks pass against the new baseline.

## Reviewing someone else's baseline change

- Does this commit include a link to the rationale?
- Does `tool_versions` in the new baseline match the images currently specified in `wdl/main.wdl`?
- Have the region and truth set remained unchanged? If not, was changing them the intended purpose of this change?
