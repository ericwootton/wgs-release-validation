# Preflight report: ⚠ WARN

**Ready to run, with 1 warning worth reviewing.**

0 errors, 1 warnings, 2 notes. 34 checks run, 0 skipped.

| File | Type | Errors | Warnings | Notes | Result |
|---|---|---:|---:|---:|---|
| `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/ref.fa.fai` | Reference | 0 | 0 | 0 | ✔ PASS |
| `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/region.bed` | Target regions (BED) | 0 | 1 | 1 | ⚠ WARN |
| `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/confident.bed` | Target regions (BED) | 0 | 0 | 1 | ✔ PASS |
| `samples.csv` | Sample sheet | 0 | 0 | 0 | ✔ PASS |

## `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/region.bed`

### WARN BED010: Interval sizes are plausible for a capture panel

**What this means.** 1 interval is longer than 1 Mb. Very short regions are often typing mistakes (a start and end that are almost equal), and very long ones are usually whole genes or chromosomes pasted in by mistake; neither behaves like normal capture targets.

**How to fix.** Check the listed lines. If they are intended (for example a large linkage region), you can ignore this warning; otherwise correct them.

<details><summary>Technical detail</summary>

Flags intervals shorter than 20 bp and longer than 1,000,000 bp (1 Mb). Whole-genome or large-region designs can ignore this warning.

Evidence: Long, lines: 1

</details>

### INFO BED009: Territory summary

**What this means.** 1 interval on 1 chromosome, covering 5,000,000 bp (5.00 Mb) after merging overlaps. Sizes: smallest 5,000,000 bp, median 5,000,000 bp, largest 5,000,000 bp. chrY absent; chrM absent.

**What to do.** No action needed. Check that the totals match what you expect for your design (for example, the panel or exome you ordered).

<details><summary>Technical detail</summary>

Counts intervals, total and merged base pairs, the size distribution, intervals on alt/decoy/unplaced contigs (any name that is not chr1-22, X, Y or M, with or without 'chr'), presence of chrY and chrM, and the number of header lines that were ignored.

Evidence: intervals=1, raw_bp=5000000, merged_bp=5000000, mean_size=5000000.0, style=chr

</details>

## `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/confident.bed`

### INFO BED009: Territory summary

**What this means.** 693 intervals on 1 chromosome, covering 4,740,229 bp (4.74 Mb) after merging overlaps. Sizes: smallest 50 bp, median 3,663 bp, largest 51,480 bp. chrY absent; chrM absent.

**What to do.** No action needed. Check that the totals match what you expect for your design (for example, the panel or exome you ordered).

<details><summary>Technical detail</summary>

Counts intervals, total and merged base pairs, the size distribution, intervals on alt/decoy/unplaced contigs (any name that is not chr1-22, X, Y or M, with or without 'chr'), presence of chrY and chrM, and the number of header lines that were ignored.

Evidence: intervals=693, raw_bp=4740229, merged_bp=4740229, mean_size=6840.2, style=chr

</details>

*ngs-preflight 0.1.0, generated 2026-10-23T03:24:38Z in 0.21s.*
