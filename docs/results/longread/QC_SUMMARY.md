# QC summary: longread

HG002 PacBio HiFi reads over chr20:1000001-6000000 (GRCh38), 14,151 reads analysed. Research use only: these results are not for clinical decisions.

## Structural variants

Compared with the GIAB HG002 v5.0q structural-variant benchmark, which is a **draft** release. The benchmark scores events of 50 bp and larger inside its benchmark regions. Recall is the share of benchmark SVs that were found; precision is the share of calls that are in the benchmark.

| Caller | Calls (PASS) | Recall | Precision | F1 | Found | Missed | False calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| pbsv | 110 of 110 | 0.923 | 0.953 | 0.938 | 48 | 4 | 2 |
| sniffles | 48 of 48 | 0.904 | 0.909 | 0.906 | 47 | 5 | 4 |

These numbers are after truvari refinement, which re-aligns the calls in each disagreeing region so that the same event described differently is still matched, as the benchmark's README recommends. Before refinement: pbsv recall 0.865, precision 0.953; sniffles recall 0.846, precision 0.909.

PASS calls by type and size:

| Caller | DEL | DUP | INS | < 50 bp | 50-99 bp | 100-499 bp | 500-999 bp | 1-10 kb | >= 10 kb |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pbsv | 44 | 6 | 60 | 64 | 12 | 25 | 2 | 7 | 0 |
| sniffles | 16 | 0 | 32 | 2 | 11 | 26 | 2 | 7 | 0 |

Calls under 50 bp (64 from pbsv and 2 from sniffles) are in the files and in the table above, but the benchmark only contains events of 50 bp and larger. Truvari still compares calls from 30 bp, so a call just under 50 bp can match a benchmark event; smaller calls are not scored.

## Tandem repeats (TRGT)

346 of 346 catalogue loci in the region were genotyped (no-call rate 0.0%), with a median of 42 reads fully spanning each locus. Allele lengths ranged from 4 to 237 bp (median 26).

Disease-associated loci in the region:

| Locus | Position | Allele lengths (bp) | Motif counts | Spanning reads |
|---|---|---|---|---:|
| SCA36_NOP56 | chr20:2,652,732 | 37, 55 | 3_2_0,6_2_0 | 39 |
| CJD_PRNP | chr20:4,699,370 | 123, 123 | 1_4_0_0,1_4_0_0 | 41 |

These are measurements, not interpretations: whether an allele length is in a normal range depends on the locus and needs clinical-grade review.

Read-level plots of these loci (TRGT `plot`, one row per spanning read, coloured by motif): `longread.trgt.CJD_PRNP.svg`, `longread.trgt.SCA36_NOP56.svg`.

## CpG methylation (pb-CpG-tools)

63,126 CpG sites scored; median coverage 37x, 99.9% with at least 10 reads. At sites with 10 or more reads, mean methylation is 66.6%; 18.6% are below 20% and 56.2% above 80%, the two-peaked pattern typical of human DNA. HG002 DNA comes from a lymphoblastoid cell line, so methylation at some loci can differ from blood or tissue.
CpG islands are mostly unmethylated, as expected: 14.9% mean inside islands (7,123 sites) against 73.2% outside.

Scores are also given per haplotype, from the reads' HP tags (hap1: 62,589 sites, mean 66.5% at sites with 10 or more reads; hap2: 62,878 sites, mean 66.8% at sites with 10 or more reads).
Of 55,786 CpGs with 10 or more reads on both haplotypes, 4,925 (8.8%) differ by 50 percentage points or more between them.
The haplotype numbers come from the phasing behind the HP tags. Unless that phasing used parental data, hap1 in one phase block need not be the same parent as hap1 in the next.

## What was checked before release

- Every data file opens, is bgzip-compressed and has a matching .tbi index; MD5s are in MANIFEST.tsv.
- SV calls were compared with the benchmark only inside its benchmark regions.
- Tool versions and commands are in VERSIONS.md; field definitions are in DATA_DICTIONARY.md.
