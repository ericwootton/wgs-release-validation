# INC-01: proposed MAPQ change blocked by the regression gate

Blameless write-up of a deliberately staged incident, used to show that the gate catches a bad
change before release. Every number below comes from real runs on the `ci` profile
(`chr20:21800001-22000000`, HG002 at 35x, GIAB v4.2.1).

| Field | Value |
|---|---|
| Incident ID | INC-01 |
| Date | 2026-10-22 |
| Status | Resolved |
| Severity | SEV3 (caught before release) |
| Detected by | Automated check (`scripts/compare_metrics.py`, `make gate`) |

## Summary

A change to raise HaplotypeCaller's minimum read mapping quality from the default 20 to 40 was
proposed as a new pipeline default, to cut false calls in segmental duplications. The regression
gate failed it: SNP F1 dropped 1.08 points overall and 7.08 points in low-mappability regions,
because 8 more true variants were missed in exchange for removing 1 false call. The change was not
released.

## Impact

None outside the team. No results were produced with the new setting, and nothing was delivered.
Had it shipped, every customer sample would have lost sensitivity in the parts of the genome that
are already hardest to call: in this region, recall in low-mappability sequence would fall from
64.6% to 54.9%.

## Timeline

All times 2026-10-22, local.

| Time | Event |
|---|---|
| 22:39 | Candidate run started: `make run PROFILE=ci LABEL=inc01 EXTRA='gatk_extra_args=--minimum-mapping-quality\ 40'` |
| 22:41 | Run finished; `make gate PROFILE=ci LABEL=inc01` exited non-zero with 5 failing rows. Change rejected; default left at MAPQ 20 |
| 22:43 | Gate changed to record parameters with tool versions (see Prevention); baseline regenerated |
| 22:47 | Candidate re-run against the new baseline (9 tasks, 129 s of task time): same 5 failures, now reported as a parameter change |

## What the gate showed

From `docs/results/inc01/gate.md`, the five failing rows (all SNP; the INDEL rows did not change):

| Stratum | Truth SNPs | Baseline F1 % | Candidate F1 % | Change (points) | Allowed drop |
|---|---:|---:|---:|---:|---:|
| all benchmark regions | 360 | 95.66 | 94.58 | -1.08 | 0.20 |
| TS_contained | 360 | 95.66 | 94.58 | -1.08 | 1.00 |
| all difficult regions | 100 | 82.56 | 77.30 | -5.26 | 1.00 |
| low mappability | 82 | 77.94 | 70.87 | -7.08 | 1.00 |
| low mappability or segdup | 82 | 77.94 | 70.87 | -7.08 | 1.00 |

The trade, in counts (`docs/results/ci/metrics.md` against `docs/results/inc01/metrics.md`):

| | Baseline (MAPQ 20) | Candidate (MAPQ 40) |
|---|---:|---:|
| Missed SNPs (FN) | 29 | 37 |
| False SNP calls (FP) | 1 | 0 |
| SNP recall, low-mappability (95% CI) | 64.63% (53.8–74.1) | 54.88% (44.1–65.2) |
| SNP precision, all regions | 99.70% | 100.00% |

Outside the difficult regions nothing changed: 260 of 260 SNPs found in both runs.

## Root cause

**Technical.** Reads in segmental duplications and other low-mappability sequence often have
mapping qualities between 20 and 40, because a near-identical copy exists elsewhere. Discarding
them removes most of the evidence at true variants in those regions, while barely touching false
calls, which in this region were already rare (1 of 360). The proposal was built on a real
complaint (false calls in segdups) but was not tested against a benchmark before being proposed as
a default.

**Process.** Caller parameters were not part of what the gate compared. The first gate run
reported the candidate as having "identical tool images" and labelled the true-positive change as
"non-determinism or input change", which pointed the reader at the wrong cause. The F1 limits still
failed the run correctly, but the wording would have sent a reviewer looking for a flaky container
instead of at the parameter.

## Detection

Automatic, within about two minutes of the candidate run finishing. Without the gate, the overall
SNP F1 change (95.66% to 94.58%) is small enough to miss when eyeballing a summary, and an
unstratified report would not have shown that the loss is concentrated in low-mappability regions.

## Resolution

The default stays at MAPQ 20. For the original complaint, the better answer is to report calls in
segmental duplications with their stratum, so customers can filter or review them, rather than to
discard the evidence for everyone (see [CS-01](../case-studies/CS-01-missed-variants-lowmap.md)).

## Prevention

| Action | Owner | Status |
|---|---|---|
| Record caller and normalisation arguments with the tool versions in `metrics.json` (`gatk_args`, `norm_args` in `wdl/main.wdl`), so the gate reports "Tool images and parameters identical: no" for a parameter change | Pipeline | Done |
| Pass tool versions to the summary step one per line (`write_lines`), so argument values containing spaces survive | Pipeline | Done |
| Any change to caller defaults goes through the release-validation runbook with an upgrade-style report, not straight into `main.wdl` | Team | Done ([runbook](../runbooks/release-validation.md)) |

## Lessons

- **What went well:** the stratified gate failed the change on the strata that matter, with the
  counts needed to explain why.
- **What did not:** the first version of the gate's note blamed non-determinism. A failure message
  that names the wrong cause costs time even when the verdict is right.
- **Where we got lucky:** the first attempt to stage this incident used a bad normalisation option
  (`bcftools norm --rm-dup all`, which keeps one record per position and would drop an allele at
  split multi-allelic sites). It changed nothing: this region has no multi-allelic sites, and
  `--atomize`, `-m +any`, `--do-not-normalize` and `-c s` also left all 420 records identical. A
  benchmark region can only catch the classes of error it contains. The `full` profile (5 Mb) is
  the place to exercise normalisation changes.
