# What the customer receives

Validated variant calls do not necessarily provide what a customer needs to take action. Since
these 3 deliverables were repeatedly requested in support work, they are generated through a
single optional execution workflow `wdl/optional/deliverables.wdl`. This workflow uses outputs
which have passed the release gate. Each deliverable includes a README written for its recipient
and not for us.

```bash
make deliverables    # inputs in inputs/deliverables.json; needs `make run PROFILE=full` first; 19 s here
```

All content below is based on actual runs using the `full` profile. README text and tables
were included directly from the generated files in `docs/results/deliverables/` unedited.

## 1. Read-support slices: "show me the reads behind this call"

**When to send it.** Customers who have questions about variant calls or missing calls
typically want to check the results themselves before requesting confirmatory testing.
Sending a complete BAM file involves tens of GB of data, while a read-support BAM slice for
a specific locus is only a few KB. This slice can be opened immediately in IGV.

**What they get.** An indexed BAM per requested site, one BAM combining all sites, and an allele
support table counting reads supporting each allele are provided. These BAMs contain all reads
which overlap the regions obtained by adding 200 bases of padding to each specified site. The sites here come from
[CS-01](case-studies/CS-01-missed-variants-lowmap.md): a control site in unique sequence and four
sites within the clusters of missed variants in low mappability sequence, including the customer's
Sanger-confirmed variant.

???+ example "README.md as delivered"

    --8<-- "results/deliverables/read-support-slices.md"

The allele support table counted reads under 2 conditions. These included reads with a mapping
quality of at least 20 (which callers would typically trust) and all reads. Column 2 is the key
part of this table. At chr20:21890551, the 2 reads covering this position had mapping qualities
below 20 (both were 0 as shown in [CS-01](case-studies/CS-01-missed-variants-lowmap.md)).
Therefore, no caller can confidently call a variant at this position. This position was included
in the table, and the limitation was shown explicitly:

```text
--8<-- "results/deliverables/allele-support.tsv"
```

At the customer's Sanger-confirmed site (chr20:21911257), only 6 of 31 reads passed filtering.
Of these 6 reads, 5 showed the reference base. This is why a short-read variant caller missed
the variant and why confirmation using another method was appropriate.

## 2. Collection VCF: "one file for the whole family"

**When to send it.** A customer has single-sample VCF files from multiple individuals (family
trios, cohorts, and time series). They want a single table containing a column per sample for
filtering or import into other tools.

**What they get.** A bgzip-compressed and indexed multisample VCF which uses the same variant
representations across all samples and includes allele counts across all samples in the file.
Here, this refers to the GIAB benchmark VCFs for the Ashkenazi trio (HG002 and its parents
HG003 and HG004), restricted to the `full` region.

???+ example "README.md as delivered"

    --8<-- "results/deliverables/collection-vcf.md"

Among 9,784 records, 4,353 had genotypes in all 3 samples, 3,033 in 2 samples, and 2,398 in 1
sample. Here, the README explanation of missing genotypes is particularly important because GIAB
benchmarks cover slightly different genomic regions. Therefore, a missing parental genotype is
not evidence that a variant in the offspring is de novo.

## 3. Targeted extract: "just these genes, in a spreadsheet"

**When to send it.** A clinician-scientist or a collaborator without access to bioinformatics
support wants variants from a set of regions in a table which can be opened in Excel.

**What they get.** Selected VCF fields within regions specified by the BED file are summarized in
a TSV with one row per alternate allele. A data dictionary describes each column. This is the
coding sequence subset of DeepVariant variant calls from the `full` run.

```text
--8<-- "results/deliverables/extract.tsv"
```

???+ example "Data dictionary as delivered"

    --8<-- "results/deliverables/extract-dictionary.md"

## What we check before sending any of these

- The original variant calls passed the release gate established for the pipeline version which generated them.
- The README describes what the file contains, how it was created, and what was excluded.
- Nothing in the file describes a sample other than the one corresponding to its column. Input
  INFO fields are removed from the collection VCF because they would describe only the first
  sample in each merged record.
- As shown above for chr20:21890551, the output still includes all sites the customer asked
  about even when the response is "no usable reads".
