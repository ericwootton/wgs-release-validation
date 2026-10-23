# CS-01: "A variant we confirmed by Sanger is missing from my VCF"

All data are real (GIAB HG002, `ci` profile, `chr20:21800001-22000000`, 35x Illumina). The customer
and ticket are fictional.

| Field | Value |
|---|---|
| Ticket ID | CS-01 |
| Date opened / closed | 2026-10-22 / 2026-10-22 |
| Severity | P3 (question about results; nothing is blocked) |
| Customer | Dr. A. Rivera, rare-disease research lab (fictional) |
| Reported symptom | "We have a heterozygous G>A at chr20:21,911,257 confirmed by Sanger, but it isn't in the VCF you sent. Is the pipeline broken?" |

## 1. Summary

The variant is real but almost none of the sequencing reads that could show it can be placed
uniquely in the genome, so neither of our two callers reported it. The pipeline worked as designed;
this region is a known blind spot for short-read sequencing, and we have told the customer which
other parts of their results share it.

## 2. Impact

- One sample's VCF lacks a true variant. No results are wrong in the sense of a false call: the
  site is absent, not miscalled.
- The same region holds 20 other benchmark variants that both callers miss in HG002, so other
  samples are likely affected the same way. This is expected behaviour, not a regression: the
  per-stratum accuracy in every report already shows it (low-mappability SNP recall 64.6% for GATK,
  against 100% outside difficult regions).
- Nothing needs to be recalled or re-issued.

## 3. Timeline

| When | What |
|---|---|
| 09:10 | Reported by email |
| 09:30 | First response: acknowledged, asked for the sample ID and the Sanger primer coordinates |
| 11:00 | Root cause found (read evidence below) |
| 11:30 | Reply sent with explanation and options; customer confirmed the next afternoon |

## 4. Investigation

### Step 1: is the site inside the benchmarked territory, and in which stratum?

For HG002 there is a truth set, so the same question can be answered from the benchmark output.
`scripts/pick_fn_examples.py` lists every missed truth variant with the GIAB strata it falls in:

```bash
python3 scripts/pick_fn_examples.py results/ci/gatk.vcf.gz --decision FN
```

All 30 GATK misses in the region (29 SNPs, 1 indel) are in `low_mappability`; none are outside the
difficult regions. They fall in two clusters: chr20:21,890,551–21,891,589 (9 sites, all
homozygous in the truth set) and chr20:21,911,257–21,914,030 (21 sites, all heterozygous). The
customer's site is the first of the second cluster.

### Step 2: what do the reads say at the site?

```bash
samtools view results/ci/slice.bam chr20:21911257-21911257 \
  | python3 scripts/site_evidence.py --pos 21911257 --ref G --alt A --label "chr20:21911257 G>A"
```

| MAPQ | Reference allele | Alternate allele | Other | Total |
|---|---:|---:|---:|---:|
| 0 | 26 | 0 | 0 | 26 |
| 1-19 | 7 | 0 | 0 | 7 |
| 20-59 | 5 | 1 | 0 | 6 |
| 60 | 0 | 0 | 0 | 0 |
| **all** | 38 | 1 | 0 | 39 |

There are 39 reads, but only 1 carries the A allele. For a true heterozygote we would expect about
half. Two-thirds of the reads have mapping quality 0: the aligner found an equally good placement
elsewhere and chose one at random.

### Step 3: how bad is mappability around it?

MAPQ histogram for reads within ±200 bp (`samtools view -F 0xF04 slice.bam chr20:21911057-21911457`):

| MAPQ | Reads | Share |
|---|---:|---:|
| 0 | 67 | 62% |
| 1-19 | 25 | 23% |
| 20-59 | 16 | 15% |
| 60 | 0 | 0% |

Depth across the cluster (`samtools depth -a -Q <q>`), against a well-behaved stretch of the
same region:

| Interval | Mean depth, all reads | Mean depth, MAPQ ≥ 20 |
|---|---:|---:|
| chr20:21,911,200–21,914,100 (customer's cluster) | 29.9x | 19.7x |
| chr20:21,890,500–21,891,700 (first cluster) | 16.9x | 6.8x |
| chr20:21,850,000–21,860,000 (unique sequence, for comparison) | 36.7x | 36.7x |

The total depth looks normal, so a coverage QC would not flag this. What is missing is reads from
the haplotype that carries the variant: those reads match another copy of this sequence at least as
well and were placed there instead.

A read-level view of all 30 sites, with the truth set, the benchmark decisions and the reads, is in
[CS-01-igv.html](CS-01-igv.html) (igv-reports 1.16.0, self-contained, opens offline):

```bash
create_report sites.bed --fasta ref.fa --tracks truth.norm.vcf.gz gatk.vcf.gz slice.bam \
  --flanking 150 --title "CS-01: missed variants in low-mappability sequence" --output CS-01-igv.html
```

### Step 4: would another caller have found it?

The same reads were run through DeepVariant 1.10.0 (`make run PROFILE=ci LABEL=ci-both
EXTRA='callers=gatk callers=deepvariant'`):

| | GATK 4.7.0.0 | DeepVariant 1.10.0 |
|---|---:|---:|
| Missed SNPs in the region | 29 | 21 |
| Missed indels | 1 | 0 |
| Customer's site (21,911,257) | missed | missed |
| Missed by both | 21 | 21 |

DeepVariant recovered 9 of GATK's 30 misses: the 7 homozygous sites in the first cluster, where a
few reads clearly show only the alternate allele, plus 2 heterozygous sites in the second cluster.
All 9 calls have low genotype quality (GQ 6–19) and depth 2–20, so they are borderline. Of the 21
sites missed by both, 19 are heterozygous sites in the second cluster with almost no alternate
reads, including the customer's, and 2 are homozygous sites in the first cluster covered by only 2
reads (chr20:21,890,551: 2 reads, both MAPQ 0). No short-read caller can call an allele the reads
do not contain.

A dead end, recorded so it is not retried: raising the minimum mapping quality makes this worse,
not better (see [INC-01](../incidents/INC-01-mapq-default-change.md): MAPQ 40 lost 8 more SNPs in
this stratum).

## 5. Root cause

**What failed:** the variant lies in low-mappability sequence where reads from the variant-carrying
haplotype align equally well, or better, to another location, so they were not placed here.
**Why it was possible:** this is a limit of 150 bp paired-end reads, not a pipeline defect. The
pipeline already reports accuracy by region type, but the customer had no easy way to tell that
their site was in one of those regions.

## 6. Resolution

- Explained the cause, with the read table above.
- Offered a list of the customer's other variants of interest that fall in low-mappability or
  segmental-duplication regions (from the GIAB stratification BEDs), so they know which other
  results need orthogonal confirmation.
- Pointed to options if the region matters for their study: long-read sequencing, or a
  locus-specific assay designed to avoid the duplicated sequence.

## 7. Prevention

- The per-stratum table in every report (`docs/results/<label>/metrics.md`) shows recall by region
  type with confidence intervals, so the expectation is visible before a customer asks.
- The customer FAQ has a plain-language entry on why accuracy is lower in duplicated and
  low-mappability regions ([docs/kb/faq.md](../kb/faq.md)).
- `scripts/pick_fn_examples.py` now also lists genotype mismatches as false calls (a truth 1/1
  called 0/1 is both a miss and a false call, as hap.py counts it). Before this fix it reported no
  false calls in a region where the metrics showed one.

## 8. Customer-facing reply

> Hi Dr. Rivera,
>
> Thank you for the Sanger result. Your variant at chr20:21,911,257 is real, and our pipeline did
> not report it. The cause is the DNA around it, not a fault in the run.
>
> That stretch of chromosome 20 closely resembles another part of the genome. Our short reads
> (150 bases) often can't tell the two copies apart, so the reads carrying your variant were mostly
> placed at the other copy. At your site we have 39 reads, but only 1 shows the A allele; for a
> heterozygous variant we would expect about 20. We also ran a second, independent caller
> (DeepVariant) on the same data, and it misses the site too. Re-analysing the existing data will
> not recover it.
>
> This affects a small, known part of the genome. Our report's accuracy table lists it as "low
> mappability", where we find about 65% of variants, against nearly 100% elsewhere. I've attached
> a list of your other variants of interest that fall in regions like this, so you can see which
> ones would also benefit from confirmation.
>
> If this region is central to your study, long-read sequencing reads through the duplicated
> sequence and usually resolves it. I'm happy to set up a call with our scientific team to discuss
> whether that fits your project. I can't promise that every variant in these regions will be
> recovered by a different method, but I can tell you in advance which ones are at risk.
>
> Best regards,
> Customer Success
