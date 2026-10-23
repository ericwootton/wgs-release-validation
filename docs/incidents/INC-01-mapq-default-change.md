# INC-01: proposed MAPQ change blocked by the regression gate

This record summarizes a deliberately staged incident and uses a blameless approach. It shows
that the regression gate catches a bad change before release.
All values below came from actual runs using the `ci` profile (`chr20:21800001-22000000`,
HG002, 35x coverage, GIAB v4.2.1).

| Field | Value |
|---|---|
| Incident ID | INC-01 |
| Date | 2026-10-22 |
| Status | Resolved |
| Severity | SEV3 (caught before release) |
| Detected by | Automated check (`scripts/compare_metrics.py`, `make gate`) |

## Summary

To reduce false calls in segmental duplication, increasing the minimum read mapping quality for
HaplotypeCaller from the default of 20 to 40 was proposed. This change was intended to become the
new workflow default. The regression gate failed it. SNP F1 dropped 1.08 points overall and 7.08
points in low mappability regions, because 8 more true variants were missed in exchange for
removing 1 false call. This change was not released.

## Impact

There were none at all outside the team. No results were generated under the new settings, and
nothing was delivered. If it had been released, sensitivity would have declined for all customer
samples in the parts of the genome where variants were already hardest to detect. This means that
recall in low mappability sequences within this region would have declined from 64.6% to 54.9%.

## Timeline

Unless otherwise stated, all times are given in local time on 2026-10-22.

| Time | Event |
|---|---|
| 22:39 | Candidate run started: `make run PROFILE=ci LABEL=inc01 EXTRA='gatk_extra_args=--minimum-mapping-quality\ 40'` |
| 22:41 | Run finished; `make gate PROFILE=ci LABEL=inc01` exited non-zero with 5 failing rows. Change rejected; default left at MAPQ 20 |
| 22:43 | Gate changed to record parameters with tool versions (see Prevention); baseline regenerated |
| 22:47 | Candidate re-run against the new baseline: same 5 failures, now reported as a parameter change |
| 23:44 | Baseline run repeated; `baselines/ci.json` is from this run |
| 00:32 (10-23) | Candidate run repeated against it (9 tasks, 64 s of task time). Same 5 failures; the files in `docs/results/inc01/` are from this run |

## What the gate showed

The five failing rows in `docs/results/inc01/gate.md` were all SNP. INDEL rows did not change:

| Stratum | Truth SNPs | Baseline F1 % | Candidate F1 % | Change (points) | Allowed drop |
|---|---:|---:|---:|---:|---:|
| all benchmark regions | 360 | 95.66 | 94.58 | -1.08 | 0.20 |
| TS_contained | 360 | 95.66 | 94.58 | -1.08 | 1.00 |
| all difficult regions | 100 | 82.56 | 77.30 | -5.26 | 1.00 |
| low mappability | 82 | 77.94 | 70.87 | -7.08 | 1.00 |
| low mappability or segdup | 82 | 77.94 | 70.87 | -7.08 | 1.00 |

Quantitative assessment of trade-offs (comparison of `docs/results/ci/metrics.md` and `docs/results/inc01/metrics.md`):

| | Baseline (MAPQ 20) | Candidate (MAPQ 40) |
|---|---:|---:|
| Missed SNPs (FN) | 29 | 37 |
| False SNP calls (FP) | 1 | 0 |
| SNP recall, low-mappability (95% CI) | 64.63% (53.8–74.1) | 54.88% (44.1–65.2) |
| SNP precision, all regions | 99.70% | 100.00% |

Nothing changed outside the difficult regions, and all 260 of 260 SNPs were detected in both runs.

## Root cause

**Technical.** Reads from segmental duplication and other low mappability sequences often have mapping
qualities between 20 and 40 because nearly identical copies occur elsewhere. Discarding these
reads removes most of the evidence at true variants in these regions. It barely touches false
calls, which were already rare in this region (1 of 332 scored calls). This proposal was built
on a real complaint (false calls in segmental duplication). It had not been tested against a
benchmark before being proposed as the default setting.

**Process.** Variant caller parameters were not included in the scope of the regression gate
comparison. During the first run, the candidate was reported to use the same tool image. Changes in
true positive calls were attributed to nondeterminism or input changes, directing readers towards
the wrong cause. Despite this, the F1 threshold still failed the run correctly. However, this
wording would have led reviewers to investigate containers with unstable behaviour instead of
checking the parameters.

## Detection

Automatic, within about 2 minutes of the candidate run finishing. Without a
regression gate, the small decline in overall SNP F1 (from 95.66% to 94.58%) may be overlooked
during visual inspection of the summary. Furthermore, an unstratified report would not have shown
that this decline was concentrated in low mappability regions.

## Resolution

The default remains MAPQ 20. For the original complaint, reporting variant calls in segmental
duplication alongside their stratum is more appropriate than discarding evidence for every
customer. This means customers can filter or review these results (see
[CS-01](../case-studies/CS-01-missed-variants-lowmap.md)).

## Prevention

| Action | Owner | Status |
|---|---|---|
| Record caller and normalization arguments with the tool versions in `metrics.json` (`gatk_args`, `norm_args` in `wdl/main.wdl`), so the gate reports "Tool images and parameters identical: no" for a parameter change | Pipeline | Done |
| Pass tool versions to the summary step one per line (`write_lines`), so argument values containing spaces survive | Pipeline | Done |
| Any change to caller defaults goes through the release-validation runbook with an upgrade-style report, not straight into `main.wdl` | Team | Done ([runbook](../runbooks/release-validation.md)) |

## Lessons

- **What went well:** the stratification gate found that the change failed in important strata
  and provided the counts needed to explain why.
- **What did not:** the initial explanation for the regression gate identified nondeterminism as
  the cause. A failure message that names the wrong cause costs time even when the verdict is
  right.
- **Where we got lucky:** an inappropriate normalization option was used during the first attempt
  to stage this incident. This option (`bcftools norm --rm-dup all`) retains one record per
  position and would drop an allele at split multi-allelic sites. However, nothing changed. No
  multiallelic sites were present in this region. All 420 records in the hap.py output VCF
  remained unchanged even when `--atomize`, `-m +any`, `--do-not-normalize`, and `-c s` were used.
  Benchmark regions can only detect the types of errors they contain. The place to test
  normalization changes is the `full` profile (5 Mb).
