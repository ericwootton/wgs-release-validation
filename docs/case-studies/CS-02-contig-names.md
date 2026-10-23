# CS-02: "The run finished, but the results table is empty"

All runs, errors and outputs are real (GIAB HG002, `ci` region `chr20:21800001-22000000`). The
customer and ticket are fictional. Reproduce with
`miniwdl run wdl/main.wdl -i inputs/cs02_contig_mismatch.json`, after writing
`data/cs02/confident.bed` with `sed 's/^chr20/20/' data/ci/confident.bed`.

| Field | Value |
|---|---|
| Ticket ID | CS-02 |
| Date opened / closed | 2026-10-22 / 2026-10-22 |
| Severity | P2 (one customer blocked) |
| Customer | Northfield Genomics Core, panel validation project (fictional) |
| Reported symptom | "The workflow says it succeeded but the benchmark table has no rows. Last month's run with the same data was fine." |

## 1. Summary

The customer's target BED named the chromosome `20`, while the reference and truth set call it
`chr20`. No region in the BED matched, so nothing was benchmarked, and the workflow still reported
success. We fixed the BED with one command, and changed the pipeline and the pre-submission checker
so that this now fails loudly before any compute is spent.

## 2. Impact

- One run produced an empty report. No numbers were wrong: there were no numbers.
- Risk to others: any customer whose BED came from a GRCh37-style source (`1`, `2`, …, `X`) would
  have hit the same thing. Follow-up action: scan recent submissions for BEDs without the `chr`
  prefix against a `chr`-style reference (`preflight check --bed ... --reference ...` on each).
- The variant calls themselves were fine: calling uses the region string, not the BED.

## 3. Timeline

| When | What |
|---|---|
| 10:05 | Reported via the support portal |
| 10:20 | First response: asked for the inputs JSON and the BED |
| 10:40 | Root cause found (step 2 below) |
| 11:15 | Corrected BED sent; customer re-ran and confirmed results |

## 4. Investigation

### Step 1: did anything fail?

No. Every task exited 0 (`miniwdl run ... ; echo $?` printed `0`). The hap.py summary shows the
problem immediately once you look at it:

```text
Type,Filter,TRUTH.TOTAL,TRUTH.TP,TRUTH.FN,QUERY.TOTAL,QUERY.FP,QUERY.UNK,...
INDEL,PASS,0,0,0,48,0,48,...
SNP,PASS,0,0,0,342,0,342,...
```

There are zero truth variants, and all 390 query calls are `UNK` (outside the benchmark regions).
The caller produced its usual number of calls, so the reads and the reference were fine; the
benchmark regions were empty.

### Step 2: compare the chromosome names

```bash
cut -f1 data/cs02/confident.bed | sort -u        # 20
cut -f1 ref.fa.fai                               # chr20
```

The BED was exported from a vendor portal that uses GRCh37-style names. The coordinates are
GRCh38, so the only problem is the name.

### Step 3: what the pre-submission checker says

[`ngs-preflight`](https://ericwootton.github.io/ngs-preflight/) (companion repo) on the same two
files. Its check [`BED003`](https://ericwootton.github.io/ngs-preflight/checks/#bed003) compares every BED contig name with the reference:

```text
✖ FAIL  Fix 1 error before submitting
[ERROR BED003] confident.bed: 1 chromosome name in the BED file cannot be found in the reference:
"20". The reference uses the "chr" prefix (for example "chr20"), so this looks like a naming
difference rather than missing data. Tools will fail or skip these regions, so the data you expect
to be analysed would be missing. Fix: Run: preflight fix-bed --add-chr confident.bed --out
confident.fixed.bed  (writes a corrected copy and leaves your original untouched).
    Technical: 18 intervals affected. Counts per name: 20=18
```

`preflight fix-bed --add-chr` produced a file byte-identical to the `chr`-named original
(md5 `c915f142809d14f9d5e1e91ca6334bb0` for both).

### Step 4: the related failure that does stop the run

A name mismatch in the BED fails silently. A *length* mismatch on a shared name (reads aligned to
another build) fails at once. Simulated by giving chr20 its GRCh37 length in the BAM header:

```text
A USER ERROR has occurred: Input files reference and reads have incompatible contigs: Found contigs
with the same name but different lengths:
  contig reference = chr20 / 64444167
  contig reads = chr20 / 63025520.
```

`ngs-preflight` reports this as [`REF001`](https://ericwootton.github.io/ngs-preflight/checks/#ref001) ("The reads file and the reference look like different
genome builds… chromosome 20 is 63,025,520 bp in the reads but 64,444,167 bp in the reference").

A dead end, recorded so it is not chased again: extra contigs in the BAM header are *not* a problem
for current callers. With a full 195-contig header against the chr20-only reference, GATK 4.7.0.0
called normally (exit 0) and DeepVariant 1.10.0 logged `Common contigs are ['chr20']` and finished.
The workflow still trims the header (`FetchReadsSlice`), and `ngs-preflight` warns about it
([`REF002`](https://ericwootton.github.io/ngs-preflight/checks/#ref002)), because other tools are stricter.

## 5. Root cause

**What failed:** the BED used `20` where the reference uses `chr20`, so the benchmark regions were
empty. **Why it was possible:** hap.py treats "no truth variants in the regions" as a valid, empty
result, and the summary step passed the empty table through. Nothing checked that the inputs used
the same naming before the run started.

## 6. Resolution

Sent the customer a corrected BED (`preflight fix-bed --add-chr`). Their re-run matched the expected
results exactly.

## 7. Prevention

- **The pipeline now fails on an empty benchmark.** `scripts/summarize_happy.py` exits non-zero when
  a caller has no truth variants inside the benchmark regions. The same inputs now stop with:
  `error: no truth variants inside the benchmark regions for gatk. Check that the BED files, truth
  VCF and reference use the same chromosome names (for example chr20, not 20).`
- **Checked before compute is spent.** The optional `Preflight` task (`run_preflight: true` in the
  `ci` and `full` inputs) runs `ngs-preflight` on the reference, the region and benchmark BEDs and
  the reads before calling starts. Errors (`BED003`, `REF001`) stop the run; warnings (`REF002`) are
  reported.
- **The regression gate also catches it** if an empty result ever reaches it: against
  `baselines/ci.json`, 19 of 24 rows fail. The large strata fail with "F1 could not be computed"
  or "stratum missing from candidate". Because the tool images and parameters match the baseline
  exactly, every smaller stratum whose true-positive count changed fails too; the remaining 5 rows
  have no truth variants in the region.
- **Product fix, not a recurring ticket:** the same check ships as a standalone tool customers can
  run on their own files before submitting, with a one-command fix for the common case.

## 8. Customer-facing reply

> Hi Sam,
>
> Thanks for sending the files. I've found the cause, and there's a quick fix.
>
> Your target BED names the chromosome "20", but the reference genome we analyse against calls it
> "chr20". It's the same chromosome; the two naming styles come from different sources. Because no
> region in the BED matched, nothing was benchmarked, so the table came back empty. Your variant
> calls were not affected.
>
> I've attached a corrected copy of the BED with the names changed and nothing else. If you re-run
> with it, you should see the full table. If you'd like to check files yourself in future, our
> free checker reports this before you submit and can write the corrected file for you:
> `preflight check --bed your.bed --reference ref.fa.fai`.
>
> I'm sorry the run reported success when it hadn't really done its job. That's on us, and we've
> changed the pipeline so that an empty result now stops with a clear message instead.
>
> Best regards,
> Customer Success
