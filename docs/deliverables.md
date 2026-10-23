# What the customer receives

Validated calls are not always what a customer needs to act on. These three deliverables come up
again and again in support work, so they are built by one optional workflow,
`wdl/optional/deliverables.wdl`, from outputs that already passed the release gate. Each one ships
with a README written for the person receiving it, not for us.

```bash
make deliverables    # inputs in inputs/deliverables.json; needs `make run PROFILE=full` first; 19 s here
```

Everything below comes from the real run on the `full` profile. The README text and tables are
pulled in from the generated files in `docs/results/deliverables/`, unedited.

## 1. Read-support slices: "show me the reads behind this call"

**When to send it.** A customer questions a call (or a missing call) and wants to look for
themselves, typically before ordering a confirmation assay. Sending the whole BAM is tens of
gigabytes; a slice per site is a few kilobytes and opens straight away in IGV.

**What they get.** One indexed BAM per requested site with every read overlapping it, padded by
200 bases, one merged BAM of all sites, and an allele-support table counting the reads behind each
allele. The sites here come from [CS-01](case-studies/CS-01-missed-variants-lowmap.md): a control
in unique sequence, and four sites from the clusters of missed variants in low-mappability
sequence, including the customer's Sanger-confirmed variant.

???+ example "README.md as delivered"

    --8<-- "results/deliverables/read-support-slices.md"

The allele-support table counts reads twice: those with mapping quality 20 or more (what a caller
would normally trust) and all reads. That second column is the point of the table. At
chr20:21890551 both reads that cover the site are below mapping quality 20 (both are at 0, as
[CS-01](case-studies/CS-01-missed-variants-lowmap.md) shows), so no caller can make a confident
call there, and the table says so instead of leaving the site out:

```text
--8<-- "results/deliverables/allele-support.tsv"
```

At the customer's Sanger-confirmed site (chr20:21911257) only 6 of 31 reads pass the filter, and
of those 6, 5 show the reference base: that is why a short-read caller missed it, and why
confirming it by another method was right.

## 2. Collection VCF: "one file for the whole family"

**When to send it.** A customer has single-sample VCFs from several people (a trio, a cohort, a
time series) and wants one table with a column per sample for filtering or import into another
tool.

**What they get.** A bgzipped, indexed multi-sample VCF in which every variant is spelled the same
way in every sample, with allele counts across the samples in the file. Here: the GIAB benchmark
VCFs for the Ashkenazi trio (HG002 and the parents HG003 and HG004), restricted to the `full`
region.

???+ example "README.md as delivered"

    --8<-- "results/deliverables/collection-vcf.md"

Of the 9,784 records, 4,353 have a genotype in all three samples, 3,033 in two and 2,398 in one.
The README's point about missing genotypes matters here: each GIAB benchmark covers a slightly
different part of the genome, so a missing genotype in a parent is not evidence that the child's
variant is de novo.

## 3. Targeted extract: "just these genes, in a spreadsheet"

**When to send it.** A clinician-scientist or a collaborator without bioinformatics support wants
the variants in a set of regions as a table they can open in Excel.

**What they get.** A TSV of chosen VCF fields over a BED file, one row per alternate allele, and a
data dictionary that says what each column means. Here: the DeepVariant calls from the `full` run
in coding sequence.

```text
--8<-- "results/deliverables/extract.tsv"
```

???+ example "Data dictionary as delivered"

    --8<-- "results/deliverables/extract-dictionary.md"

## What we check before sending any of these

- The source calls passed the release gate for the pipeline version that made them.
- The README says what the file contains, how it was made and what was left out.
- Nothing in the file describes a different sample from the one in its column. The collection
  VCF removes the inputs' own INFO fields for this reason: in a merged record they would describe
  only whichever sample came first.
- Sites the customer asked about are all present in the output, even when the answer is "no
  usable reads", as at chr20:21890551 above.
