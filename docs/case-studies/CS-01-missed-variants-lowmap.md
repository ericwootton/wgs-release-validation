# CS-01: "A variant we confirmed by Sanger is missing from my VCF"

All data are real (GIAB HG002, `ci` profile, `chr20:21800001-22000000`, 35x Illumina). The ticket
and customer are fictitious.

| Field | Value |
|---|---|
| Ticket ID | CS-01 |
| Date opened / closed | 2026-10-22 / 2026-10-22 |
| Severity | P3 (question about results; nothing is blocked) |
| Customer | Dr. A. Rivera, rare-disease research lab (fictional) |
| Reported symptom | "We have a heterozygous G>A at chr20:21,911,257 confirmed by Sanger, but it isn't in the VCF you sent. Is the pipeline broken?" |

## 1. Summary

This variant is present, but neither of the two variant callers we used reported it. This was
because almost none of the sequencing reads which could reveal it can be mapped to a unique
position in the genome. The workflow ran as designed. This region is a known blind spot for
short-read sequencing, and we have informed the customer about which other parts of their results
share this blind spot.

## 2. Impact

- A variant which was actually present in a sample is not present in its VCF. No false call was
  made. This site was missed and was not miscalled.
- Within the same region, 20 benchmark variants in HG002 were also missed by both variant callers.
  Therefore, other samples are also likely to be similarly affected. This is expected behaviour and
  does not indicate a regression. Per-stratum accuracy already reflects this in all reports (GATK
  SNP recall was 64.6% in low mappability regions and 100% outside difficult regions).
- Nothing needs to be withdrawn or reissued.

## 3. Timeline

| When | What |
|---|---|
| 09:10 | Reported by email |
| 09:30 | First response: acknowledged, asked for the sample ID and the Sanger primer coordinates |
| 11:00 | Root cause found (read evidence below) |
| 11:30 | Reply sent with explanation and options; customer confirmed the next afternoon |

## 4. Investigation

### Step 1: is the site inside the benchmarked territory, and in which stratum?

Since HG002 has a truth set, the same question can be answered using the output from the
benchmark evaluation. `scripts/pick_fn_examples.py` lists all missed true variants and the GIAB
strata to which each belongs:

```bash
python3 scripts/pick_fn_examples.py results/ci/gatk.vcf.gz --decision FN
```

All 30 sites missed by GATK in this region (29 SNPs, 1 indel) were within `low_mappability`. None
were outside difficult regions. These sites formed 2 clusters. The cluster at
chr20:21,890,551-21,891,589 contained 9 sites which were all homozygous in the truth set. Sites in
the cluster at chr20:21,911,257-21,914,030 were all heterozygous (21 sites). The customer's
target site was the 1st site in the 2nd cluster.

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

There were 39 reads, but only 1 carried the A allele. If this were a true heterozygote, we would
expect about half. Two-thirds of the reads had mapping quality 0. This means that the aligner
found equally good alignments at other positions and randomly selected one of them.

### Step 3: how bad is mappability around it?

MAPQ histogram for reads within ±200 bp (`samtools view -F 0xF04 slice.bam chr20:21911057-21911457`):

| MAPQ | Reads | Share |
|---|---:|---:|
| 0 | 67 | 62% |
| 1-19 | 25 | 23% |
| 20-59 | 16 | 15% |
| 60 | 0 | 0% |

Depth measured across the cluster (`samtools depth -a -Q <q>`) compared with depth in a
well-behaved stretch of the same region:

| Interval | Mean depth, all reads | Mean depth, MAPQ ≥ 20 |
|---|---:|---:|
| chr20:21,911,200–21,914,100 (customer's cluster) | 29.9x | 19.7x |
| chr20:21,890,500–21,891,700 (first cluster) | 16.9x | 6.8x |
| chr20:21,850,000–21,860,000 (unique sequence, for comparison) | 36.7x | 36.7x |

Since overall read depth appears normal, coverage QC would not flag this issue. Reads from the
haplotype carrying the variant are missing. These reads match another copy of the sequence at least
equally well and are therefore aligned to that copy instead.

A read-level view of all 30 sites, including the truth set, the benchmark decisions, and the reads,
is available in [CS-01-igv.html](CS-01-igv.html). This report is self-contained and can be opened
offline (igv-reports 1.16.0):

```bash
create_report sites.bed --fasta ref.fa --tracks truth.norm.vcf.gz gatk.vcf.gz slice.bam \
  --flanking 150 --title "CS-01: missed variants in low-mappability sequence" --output CS-01-igv.html
```

### Step 4: would another caller have found it?

The same sequencing reads were processed using DeepVariant 1.10.0
(`make run PROFILE=ci LABEL=ci-both EXTRA='callers=gatk callers=deepvariant'`):

| | GATK 4.7.0.0 | DeepVariant 1.10.0 |
|---|---:|---:|
| Missed SNPs in the region | 29 | 21 |
| Missed indels | 1 | 0 |
| Customer's site (21,911,257) | missed | missed |
| Missed by both | 21 | 21 |

DeepVariant detected 9 of the 30 sites missed by GATK. These included 7 homozygous sites in
cluster 1 where the few reads clearly showed only the alternate allele. It also detected 2
heterozygous sites in cluster 2. These 9 calls were considered borderline due to low genotype
quality (GQ 6-19) and read depth of only 2-20. Among the 21 sites missed by GATK and DeepVariant,
19 were heterozygous sites in cluster 2, including the customer's site. These had almost no reads
showing the alternate allele. The remaining 2 were homozygous sites in cluster 1 covered by only 2
reads (chr20:21,890,551: 2 reads, both MAPQ 0). No short-read variant caller can detect an allele
which the reads do not contain.

This unsuccessful approach was recorded so it is not retried. Increasing the minimum mapping
quality does not improve the situation and instead makes it worse. At MAPQ 40, an additional 8
SNPs were missed in this stratum (see [INC-01](../incidents/INC-01-mapq-default-change.md)).

## 5. Root cause

**What failed:** this variant lies in low mappability sequence. Reads from the haplotype carrying
it aligned equally well or better elsewhere and were therefore not placed at this location. **Why
it was possible:** This is a limitation of 150 bp paired-end reads and is not a defect in the
workflow. Accuracy was already reported by region type. However, the customer previously had no
simple way to check whether their target site lay in one of these regions.

## 6. Resolution

- The cause was explained using the read table above.
- A list was offered of other variants of interest to the customer in low mappability or
  segmental duplication regions (defined by the GIAB stratification BED). This helps the
  customer identify which other results require confirmation using an independent method.
- Long-read sequencing or a locus-specific assay designed to avoid the duplicated
  sequence was noted as one of the options if this region was important to their
  study.

## 7. Prevention

- Tables organized by stratum in all reports (`docs/results/<label>/metrics.md`) list recall and
  its confidence interval for each region type. Therefore, expected results can be assessed before
  customers ask.
- An entry in the customer-facing FAQ explains in plain language why duplicated and
  low-mappability regions have lower accuracy ([docs/kb/faq.md](../kb/faq.md)).
- `scripts/pick_fn_examples.py` now also lists genotype mismatches as false calls. If a variant
  has genotype 1/1 in the truth set but is called as 0/1, it is counted as missed and as a false
  call (consistent with hap.py). Before this correction, the script reported no false calls for
  regions where the metrics showed 1 false call.

## 8. Customer-facing reply

> Hi Dr. Rivera,
>
> Thank you for providing the Sanger result. Your variant at chr20:21,911,257 is real, but our
> analysis workflow did not report it. This was due to the surrounding DNA sequence and was not
> caused by a failure during the run.
>
> This region of chromosome 20 is highly similar to another part of the genome. Our short reads
> (150 bases) often can't distinguish between the 2 copies. So most reads containing your variant
> were aligned to the other copy. Your site had 39 reads, but only 1 showed the A allele. For a
> heterozygous variant, we would expect about 20. We also analyzed the same data with a second,
> independent variant caller (DeepVariant), and it also misses this site. Reanalyzing the existing
> data will not recover this variant.
>
> This affects a small, known part of the genome. The accuracy table in our report labels these
> regions "low mappability". We find about 65% of variants in these regions, compared with nearly
> 100% elsewhere. I've attached a list of your other variants of interest which fall within
> regions like this. You can see which of them would also benefit from confirmation.
>
> If this region is central to your study, long-read sequencing reads through the duplicated
> sequence and usually resolves it. I'm happy to set up a call with our scientific team to discuss
> whether that fits your project. I can't promise that another method will recover every variant
> in these regions. But I can tell you in advance which variants are at risk.
>
> Best regards,
> Customer Success
