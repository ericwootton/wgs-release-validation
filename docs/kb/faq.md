# Frequently asked questions

Each answer starts with a short version for anyone, then gives the detail.

## What does "confident region" mean?

**Short version:** it is the part of the genome where the reference sample's true variants are known
well enough to grade a pipeline. Outside it, nobody knows the right answer, so accuracy there is not
measured.

The Genome in a Bottle (GIAB) consortium combines many technologies to decide, for samples such as
HG002, which variants are really present. Where the methods agree and the sequence can be resolved,
the region goes into the benchmark BED file (here, GIAB v4.2.1 covers about 92% of the GRCh38
autosomes). Calls outside it are not counted as right or wrong. That means accuracy figures describe
the confident regions only; the hardest parts of the genome are partly outside them. The draft v5.0q
benchmark, built from a near-complete HG002 assembly, covers more of the difficult regions, which is
why the same pipeline can score lower against it.

## Why is precision lower in segmental duplications?

**Short version:** these are long stretches of DNA that appear in near-identical copies in different
places. Short reads from one copy can be placed on the wrong copy, so the caller sees differences
that are really between copies, not between the person and the reference.

Segmental duplications are at least 1 kb long and at least 90% identical to another part of the
genome. A 150 bp read that falls inside one may match two places equally well; the aligner then
reports a low mapping quality (MAPQ) or picks a location. Reads placed on the wrong copy create
false positive calls (lower precision), and reads with low MAPQ are ignored by most callers, which
causes missed variants (lower recall). This repository reports these regions separately
(`lowmap_or_segdup`, `segdup`) so the effect is visible, not averaged away. Long reads, which span
most duplications, largely avoid the problem.

## What coverage do I need?

**Short version:** for germline whole-genome sequencing, about 30x mean coverage is the common
standard; below about 20x, missed heterozygous variants rise noticeably.

Mean coverage is the average number of reads over each base. Because coverage is uneven, the useful
number is the share of the genome above a minimum (for example, at least 90% of bases at 20x or
more). Each run here reports both: see `coverage` in `metrics.json` and the mosdepth thresholds
file. Higher coverage helps most in regions that are hard to sequence evenly (GC-rich or GC-poor
sequence) and does not fix mapping problems in duplicated regions. Somatic and low-frequency
variant work needs far higher depth and is out of scope here.

## What is the difference between a VCF and a gVCF?

**Short version:** a VCF lists the places where a sample differs from the reference. A gVCF also
records the places where it matches, and how confident that is, so "no variant" can be told apart
from "no data".

A gVCF adds reference blocks: stretches with no variant, with their depth and genotype quality.
That is what makes joint genotyping of many samples possible, and what lets you answer "was this
position actually covered?" for a single sample. VCFs are smaller and are what most downstream tools
expect. If a customer asks whether a variant is absent or just not looked at, a VCF alone cannot
answer it; the gVCF or the BAM can.

## Why does my variant appear with a different representation?

**Short version:** the same change in DNA can often be written in more than one way, especially
insertions and deletions in repetitive sequence. Tools agree on one standard spelling by
"normalising" the record before comparing.

Deleting one `A` from `AAAA` can be written at any of the four positions. Normalisation
(`bcftools norm`) shifts such events to the leftmost position, trims shared bases, and splits sites
with several alternate alleles into one record each. This workflow normalises every call set before
benchmarking, and the benchmarking tool (hap.py with the vcfeval engine) additionally compares
haplotypes, so equivalent but differently written variants still match. If you compare our VCF with
another lab's by position alone, normalise both first, or apparently "different" variants will turn
out to be the same.
