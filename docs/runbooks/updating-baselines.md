# Runbook: updating a regression baseline

`baselines/<profile>.json` is the reference every CI run is gated against. Changing it changes what
"no regression" means, so it is a reviewed, explained commit, never a side effect.

## When a baseline update is legitimate

- A tool upgrade was approved in an upgrade report and its metrics become the new normal.
- The benchmark itself changed (new truth set, new stratifications, new region).
- A bug in the benchmarking was fixed and the old numbers were wrong.

## When it is not

- CI failed and "the numbers are close enough". Investigate first: see
  [failed-run-triage.md](failed-run-triage.md). If identical tools gave different counts, that is a
  determinism problem to explain, not a baseline to refresh.
- To make an unrelated change pass.

## Steps

1. Produce the new metrics from a clean run of the pinned workflow:
   `make run PROFILE=ci` (and `PROFILE=full` if that baseline also changes).
2. Show the difference against the current baseline, and keep the table for the commit message:
   `python3 scripts/compare_metrics.py baselines/ci.json docs/results/ci/metrics.json --out-md /tmp/diff.md`
3. Copy: `cp docs/results/ci/metrics.json baselines/ci.json`.
4. Commit only the baseline (and the report that justifies it), with a message that states:
   - why the baseline changes (link the upgrade report or issue);
   - the headline deltas (overall SNP and INDEL F1, any stratum that moved more than its threshold);
   - the run label and tool versions it came from.
5. Confirm CI passes against the new baseline.

## Reviewing someone else's baseline change

- Does the commit link a reason?
- Do `tool_versions` in the new baseline match the images now in `wdl/main.wdl`?
- Did the region and truth set stay the same? If not, is that the point of the change?
