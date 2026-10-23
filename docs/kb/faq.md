# Frequently asked questions

Each response starts with a brief explanation which anyone can understand. Then, it gives a detailed explanation.

## What does "confident region" mean?

**Short version:** it is the part of the genome where the reference sample's true variants are
known well enough to grade a pipeline. Outside it, nobody knows the right answer, so accuracy
there is not measured.

Genome in a Bottle (GIAB) combines multiple technologies to determine which variants are present in
samples such as HG002. Regions where the methods agree and the sequence can be resolved are included
in the benchmark BED file. GIAB v4.2.1 used here covers about 92% of the GRCh38 autosomes. Variant
calls outside these regions are not counted as correct or incorrect. This means that accuracy
metrics reflect performance only within confident regions, while some of the most difficult genomic
regions fall outside them. v5.0q is a draft benchmark built from a nearly complete HG002 genome
assembly and provides broader coverage of difficult regions. Therefore, scores can decline when it
is used for evaluation, even when the same workflow is used.

## Why is precision lower in segmental duplications?

**Short version:** these are long DNA regions which occur as nearly identical copies at different
locations. Short reads from one copy can be incorrectly aligned to another copy. In these cases,
variant callers detect differences between copies which do not represent differences between the
individual and the reference sequence.

A segmental duplication is a region at least 1 kb long which shares at least 90% sequence identity
with another part of the genome. A 150 bp read that falls inside such a region may align equally
well to two locations. In this case, the aligner reports low mapping quality (MAPQ) or selects one
of the locations. Reads aligned to the wrong copy produce false calls, reducing precision. Since
most variant callers ignore reads with low MAPQ, these reads lead to missed variants, reducing
recall. These regions are reported separately in this repository so that these effects remain
visible and are not obscured by averaging (`lowmap_or_segdup`, `segdup`). Long reads, which span
most duplications, largely avoid this problem.

## What coverage do I need?

**Short version:** In germline whole-genome sequencing, an average coverage depth of about 30x
is a common standard. When coverage depth falls below about 20x, missed heterozygous variants
rise noticeably.

Mean coverage is the average number of reads covering each base. Since coverage is uneven, the
proportion of the genome meeting a minimum threshold is useful (for example, at least 90% of bases
at 20x or above). Here, each run reports both measures. Check `coverage` in `metrics.json` and the
mosdepth threshold file. Increasing coverage is most helpful in regions which are difficult to
sequence evenly (sequences with high or low GC content). However, it does not resolve mapping
problems in duplicated regions. Analyses involving somatic variants or low-frequency variants
require much greater read depth and are outside the scope of this discussion.

## What is the difference between a VCF and a gVCF?

**Short version:** A VCF lists sites where a sample differs from the reference sequence. A gVCF
also records sites which match the reference sequence and the confidence in that match. This can
allow for a distinction between no variant and no data.

A gVCF adds reference blocks: stretches with no variant, with their depth and genotype quality.
That is what makes joint genotyping of many samples possible, and what lets you answer "was this
position actually covered?" for a single sample. VCF files are smaller and are what
most downstream tools expect. If a customer asks whether a variant was absent or simply not tested
for, VCF alone cannot answer it. This can be answered using gVCF or BAM.

## Why does my variant appear with a different representation?

**Short version:** the same DNA change can typically be represented in several ways,
particularly for insertions or deletions in repetitive sequences. Tools normalize records
before comparison to bring these representations into a single standard form.

Deleting 1 `A` from `AAAA` can be represented at any of 4 positions. Normalization
(`bcftools norm`) moves these events to the leftmost position, trims shared bases, and splits sites
containing multiple alternate alleles into separate records for each allele. In this workflow, all
variant call sets are normalized before benchmarking. Furthermore, hap.py uses the vcfeval engine
to additionally compare haplotypes, so equivalent variants are matched even when their
representations differ. If you compare our VCF against another laboratory's VCF by position alone,
normalize them first. Otherwise, variants which appear different will turn out to be the same.
