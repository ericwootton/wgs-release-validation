# CS-02: "The run finished, but the results table is empty"

All runs, errors, and outputs are real records (GIAB HG002, `ci` region
`chr20:21800001-22000000`). The customer and ticket are fictional. Use
`sed 's/^chr20/20/' data/ci/confident.bed` to write
`data/cs02/confident.bed`. Then, reproduce the run using
`miniwdl run wdl/main.wdl -i inputs/cs02_contig_mismatch.json`.

| Field | Value |
|---|---|
| Ticket ID | CS-02 |
| Date opened / closed | 2026-10-22 / 2026-10-22 |
| Severity | P2 (one customer blocked) |
| Customer | Northfield Genomics Core, panel validation project (fictional) |
| Reported symptom | "The workflow says it succeeded but the benchmark table has no rows. Last month's run with the same data was fine." |

## 1. Summary

Chromosome names in the customer's target BED were `20` while those in the reference sequence and
truth set are `chr20`. Since no region in the BED matched, nothing was benchmarked, but the
workflow still reported success. We corrected the BED using one command and updated the pipeline
and pre-submission checker. When this problem is present, they now fail loudly before consuming any
compute resources.

## 2. Impact

- An empty report was generated during one run. It contained no incorrect values because it contained no values at all.
- Risk to others: any customer would have encountered the same issue if they used a BED derived
  from sources in GRCh37 format (`1`, `2`, …, `X`). Follow-up action: check recent submissions
  to confirm whether a reference in `chr` format was used with a BED without the `chr` prefix.
  Run `preflight check --bed ... --reference ...` for each submission.
- The variant calls themselves were fine. A region string was used for variant calling, and BED was not used.

## 3. Timeline

| When | What |
|---|---|
| 10:05 | Reported via the support portal |
| 10:20 | First response: asked for the inputs JSON and the BED |
| 10:40 | Root cause found (step 2 below) |
| 11:15 | Corrected BED sent; customer re-ran and confirmed results |

## 4. Investigation

### Step 1: did anything fail?

No. All tasks completed with exit code 0 (`miniwdl run ... ; echo $?` returned `0`). The
problem is immediately apparent once you look at the hap.py summary:

```text
Type,Filter,TRUTH.TOTAL,TRUTH.TP,TRUTH.FN,QUERY.TOTAL,QUERY.FP,QUERY.UNK,...
INDEL,PASS,0,0,0,48,0,48,...
SNP,PASS,0,0,0,342,0,342,...
```

There were 0 truth variants, and all 390 query calls were classified as `UNK` (outside benchmark
regions). The caller produced its usual number of calls, so the reads
and the reference were fine. The benchmark regions were empty.

### Step 2: compare the chromosome names

```bash
cut -f1 data/cs02/confident.bed | sort -u        # 20
cut -f1 ref.fa.fai                               # chr20
```

The BED was exported from a vendor portal which used GRCh37-style names. Since the
coordinates were in GRCh38, the issue was limited to naming.

### Step 3: what the pre-submission checker says

For the same 2 files, [`ngs-preflight`](https://ericwootton.github.io/ngs-preflight/) (companion
repo) uses its [`BED003`](https://ericwootton.github.io/ngs-preflight/checks/#bed003) check to
compare all BED contig names against the reference sequence:

```text
✖ FAIL  Fix 1 error before submitting
[ERROR BED003] confident.bed: 1 chromosome name in the BED file cannot be found in the reference:
"20". The reference uses the "chr" prefix (for example "chr20"), so this looks like a naming
difference rather than missing data. Tools will fail or skip these regions, so the data you expect
to be analysed would be missing. Fix: Run: preflight fix-bed --add-chr confident.bed --out
confident.fixed.bed  (writes a corrected copy and leaves your original untouched).
    Technical: 18 intervals affected. Counts per name: 20=18
```

`preflight fix-bed --add-chr` produced a file byte-identical to the original BED with `chr`
names (md5 `c915f142809d14f9d5e1e91ca6334bb0` for both).

### Step 4: the related failure that does stop the run

Name mismatches in the BED fail silently. A mismatch in *length* for a shared name (reads aligned
to a different reference genome version) causes immediate failure. This was simulated by setting
the length of chr20 in the BAM header to its length in GRCh37:

```text
A USER ERROR has occurred: Input files reference and reads have incompatible contigs: Found contigs
with the same name but different lengths:
  contig reference = chr20 / 64444167
  contig reads = chr20 / 63025520.
```

`ngs-preflight` reports this as [`REF001`](https://ericwootton.github.io/ngs-preflight/checks/#ref001) ("The reads file and the reference look like different
genome builds… chromosome 20 is 63,025,520 bp in the reads but 64,444,167 bp in the reference").

This negative finding is documented so the investigation is not repeated. Extra contigs in the BAM
header are *not* a problem for the current variant callers. Even when the header contained all 195
contigs and the reference contained only chr20, GATK 4.7.0.0 completed variant calling successfully
(exit code 0). DeepVariant 1.10.0 also logged `Common contigs are ['chr20']` and completed its run.
However, the workflow still trims the header (`FetchReadsSlice`), and `ngs-preflight` issues a
warning ([`REF002`](https://ericwootton.github.io/ngs-preflight/checks/#ref002)) because other
tools have stricter requirements.

## 5. Root cause

**What failed:** Since the BED used `20` where the reference sequence used `chr20`, the benchmark
regions were empty. **Why this was possible:** hap.py treated the absence of truth variants within
the regions as a valid empty result, and the summary step passed the empty table through. Before
the run began, nothing checked that the inputs used the same naming convention.

## 6. Resolution

The corrected BED (`preflight fix-bed --add-chr`) was sent to the customer. Their rerun matched the
expected results exactly.

## 7. Prevention

- **The pipeline now fails on an empty benchmark.** When a variant caller's benchmark regions
  contain no truth variants, `scripts/summarize_happy.py` exits with a non-zero exit code. For the same
  input, it currently outputs the following message and stops running.
  `error: no truth variants inside the benchmark regions for gatk. Check that the BED files, truth VCF and reference use the same chromosome names (for example chr20, not 20).`
- **Checked before compute is spent.** The optional `Preflight` task (`run_preflight: true` in the
  `ci` and `full` inputs) runs `ngs-preflight` on the reference sequence, region BED, benchmark
  BED, and sequencing reads before variant calling begins. Execution
  stops on errors (`BED003`, `REF001`), and warnings (`REF002`) are reported.
- **The regression gate also catches it.** If an empty result ever reaches it,
  19 of 24 rows fail comparison against `baselines/ci.json`. The large strata fail with "F1 could
  not be computed" or "stratum missing from candidate". Since the tool images and parameters are
  identical to the baseline, every smaller stratum whose true-positive count changed fails too.
  There are no truth variants in the regions corresponding to the remaining 5 rows.
- **Product fix, not a recurring ticket:** the same check ships as a standalone tool.
  Customers can run it on their own files before submitting, with a one-command fix for the common
  case.

## 8. Customer-facing reply

> Hi Sam,
>
> Thank you for sending the files. I've found the cause, and there's a quick fix.
>
> Your target BED names the chromosome "20", but the reference genome we analyze against calls it
> "chr20". These names refer to the same chromosome. The 2 naming styles come from different
> sources. Since no region in the BED matched, nothing was benchmarked, so the table came back
> empty. Your variant calls were not affected.
>
> I've attached a corrected copy of the BED with the names changed and nothing else. If you re-run
> with it, you should see the full table. If you'd like to check files yourself in future, our
> free checker reports this before you submit and can write the corrected file for you: `preflight
> check --bed your.bed --reference ref.fa.fai`.
>
> I'm sorry the run reported success when it hadn't really done its job. That's on us. We've
> changed the pipeline so that an empty result now stops with a clear message instead.
>
> Best regards,
> Customer Success
