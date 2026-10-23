# Preflight report: ✔ PASS

**Ready to run.**

0 errors, 0 warnings, 2 notes. 34 checks run, 0 skipped.

| File | Type | Errors | Warnings | Notes | Result |
|---|---|---:|---:|---:|---|
| `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/ref.fa.fai` | Reference | 0 | 0 | 0 | ✔ PASS |
| `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/region.bed` | Target regions (BED) | 0 | 0 | 1 | ✔ PASS |
| `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/confident.bed` | Target regions (BED) | 0 | 0 | 1 | ✔ PASS |
| `samples.csv` | Sample sheet | 0 | 0 | 0 | ✔ PASS |

## `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/region.bed`

### INFO BED009: Territory summary

**What this means.** 1 interval on 1 chromosome, covering 200,000 bp (0.20 Mb) after merging overlaps. Sizes: smallest 200,000 bp, median 200,000 bp, largest 200,000 bp. chrY absent; chrM absent.

**What to do.** No action needed. Check that the totals match what you expect for your design (for example, the panel or exome you ordered).

<details><summary>Technical detail</summary>

Counts intervals, total and merged base pairs, the size distribution, intervals on alt/decoy/unplaced contigs (any name that is not chr1-22, X, Y or M, with or without 'chr'), presence of chrY and chrM, and the number of header lines that were ignored.

Evidence: intervals=1, raw_bp=200000, merged_bp=200000, mean_size=200000.0, style=chr

</details>

## `/mnt/miniwdl_task_container/work/_miniwdl_inputs/0/confident.bed`

### INFO BED009: Territory summary

**What this means.** 18 intervals on 1 chromosome, covering 197,548 bp (0.20 Mb) after merging overlaps. Sizes: smallest 597 bp, median 9,031 bp, largest 35,225 bp. chrY absent; chrM absent.

**What to do.** No action needed. Check that the totals match what you expect for your design (for example, the panel or exome you ordered).

<details><summary>Technical detail</summary>

Counts intervals, total and merged base pairs, the size distribution, intervals on alt/decoy/unplaced contigs (any name that is not chr1-22, X, Y or M, with or without 'chr'), presence of chrY and chrM, and the number of header lines that were ignored.

Evidence: intervals=18, raw_bp=197548, merged_bp=197548, mean_size=10974.9, style=chr

</details>

*ngs-preflight 0.1.0, generated 2026-10-23T13:42:18Z in 0.14s.*
