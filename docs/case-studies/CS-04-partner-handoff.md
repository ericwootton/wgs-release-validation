# CS-04: Releasing long-read results to an analysis partner

All runs, files and numbers are real: GIAB HG002 PacBio HiFi (Revio, 48x) over
`chr20:1000001-6000000`, run with `make longread` on an 8-core, 15 GB Linux laptop. The partner and
request are fictional. The handoff folder this produced is summarised in
[Long-read hand-off QC](../results/longread/QC_SUMMARY.md).

| Field | Value |
|---|---|
| Ticket ID | CS-04 |
| Date opened / closed | 2026-10-22 / 2026-10-23 |
| Type | Data release, not a fault |
| Partner | Kestrel Bay Long-Read Lab, research collaboration (fictional) |
| Request | "Before we send you our own samples, please send us HG002 SV, tandem-repeat and methylation calls for one region, in the form you would deliver them, so we can check your outputs against our pipeline." |

## 1. Summary

The partner wanted a sample of what a delivery looks like, so the job was less about producing
calls than about making sure that everything in the folder is correct, explained and usable
without a call to us. The checks below found four problems before release:

- The SV benchmark step hung for 28 minutes on its default aligner.
- Per-haplotype methylation files were produced but left out of the folder.
- The summary said it covered "50 bp and larger" SVs while the files contained 66 smaller calls.
- The summary described the methylation pattern as that of "normal cells", although HG002 DNA
  comes from a cell line.

All four were fixed and the folder was regenerated from scratch before it went out. The whole
module's tasks take 266 s in total on this region (from `qc.json`), and the run finished in under
5 minutes.

## 2. What was delivered

One folder, `handoff/`, with 19 files:

| File | What it is |
|---|---|
| `longread.pbsv.vcf.gz`, `longread.sniffles.vcf.gz` | Structural variants from pbsv 2.11.0 and Sniffles 2.8.0 |
| `longread.trgt.vcf.gz` | Tandem-repeat genotypes from TRGT 5.1.0 for the 346 catalogue loci in the region |
| `longread.trgt.SCA36_NOP56.svg`, `longread.trgt.CJD_PRNP.svg` | Read-level plots of the two disease-associated repeat loci in the region |
| `longread.cpg.combined.bed.gz`, `.hap1.bed.gz`, `.hap2.bed.gz` | CpG methylation from pb-CpG-tools 3.0.0, all reads and per haplotype |
| a `.tbi` for each of the six data files | tabix indexes |
| `MANIFEST.tsv` | Every file with its size, MD5 and a one-line description |
| `DATA_DICTIONARY.md` | Every column and VCF field used |
| `QC_SUMMARY.md` | One page, plain language, for the person receiving it |
| `VERSIONS.md` | Each step's container image (pinned by digest) and command |
| `qc.json` | The QC numbers, machine-readable |

## 3. What was checked before release

| Check | How | Result |
|---|---|---|
| The reads and our reference agree | The GIAB BAM is aligned to GRCh38-GIABv3, which masks three genes on chr7 and chr17 and adds decoys. Streamed chr20 from GIAB's GIABv3 FASTA and compared its MD5 with the chr20 used here (`samtools dict`) | Identical: `b18e6c531b0bd70e949a7fc20859cb01`, 64,444,167 bp |
| The region can say something about SVs | Counted benchmark SVs inside the region's benchmark regions | 52, above the 20 we aim for |
| The SV benchmark follows its own instructions | GIAB v5.0q is a **draft** benchmark. Its README asks for spanning-deletion (`*`) alleles to be removed and for `truvari bench` followed by `truvari refine`; flags checked against truvari 5.5.0 | Done; both the bench and the refined numbers are in `qc.json` |
| SV accuracy is plausible | Precision, recall and F1 after refinement | pbsv F1 0.938 (48 found, 4 missed, 2 false); Sniffles F1 0.906 (47 found, 5 missed, 4 false) |
| Repeat genotypes are complete | No-call rate and spanning reads across the 346 loci; `--karyotype XY` set for HG002 | 346 of 346 genotyped, median 42 spanning reads per locus |
| Methylation looks like human DNA | Coverage, the two-peaked distribution, CpG islands against the rest | 63,126 CpGs, 99.9% at 10x or more; 18.6% below 20% and 56.2% above 80%; islands 14.9% against 73.2% elsewhere |
| Every data file is usable | bgzip header checked by the script; then, by hand, a tabix query on each file over chr20:3,000,000-3,100,000 | All six files return records (4 to 1,966) |
| The manifest is right | `md5sum -c` against `MANIFEST.tsv` on the unpacked folder | All 18 files listed match |
| Nothing claims more than the data shows | Read `QC_SUMMARY.md` as the partner would | Two wording problems found (section 4) |

## 4. Problems found before release

### The SV benchmark hung on its default aligner

`truvari refine` re-aligns the regions where the calls and the benchmark disagree, so that one
event described in two ways still counts as a match. With its default aligner (POA), the Sniffles
run printed

```text
[SIMDMalloc] posix_memalign fail! Size: 34359738368, Error: 12
```

which is a failed request for 32 GiB, and then sat at 0% CPU for 28 minutes until it was stopped.
The pbsv run, with three regions to refine against Sniffles' five, finished in seconds. The task
now uses MAFFT, which ships in the same truvari image, and runs refine under a 30-minute timeout so
that any future hang becomes a failure. With MAFFT the whole Sniffles benchmark task, refine
included, takes about 130 s (128.5 s in the final run, from `qc.json`).

Refinement matters for the numbers. Before it, recall was 0.865 for pbsv and 0.846 for Sniffles;
after it, 0.923 and 0.904, with precision unchanged. A partner who runs `truvari bench` alone will
get the lower figures, so the summary gives both.

### Per-haplotype methylation was produced and then dropped

13,404 of the 14,151 reads (95%) carry an `HP` haplotype tag, and pb-CpG-tools wrote hap1 and
hap2 files next to the combined one. The workflow collected only the combined file. The handoff
now includes both haplotype files with their indexes, and the summary reports them:

- hap1: 62,589 CpGs; hap2: 62,878 CpGs; mean methylation 66.5% and 66.8%.
- Of 55,786 CpGs with 10 or more reads on both haplotypes, 4,925 (8.8%) differ by 50 percentage
  points or more.

That share is reported, not interpreted. We did check that it is not just sampling noise from
having half the reads per haplotype: it stays at 8.3% for CpGs with 25 or more reads on each
haplotype, and 4,357 of the 4,925 sites are within 1 kb of another such site, so the differences
come in regions. Whether those regions reflect imprinting, the cell line or something else was not
examined. The summary also warns that haplotype numbers are only consistent within a phase block.

### The summary said "50 bp and larger" but the files did not

pbsv's default minimum length is 20 bp (`--min-sv-length 20`), and it reported 64 events under
50 bp; Sniffles reported two deletions of 46 and 49 bp. These 66 calls are in the delivered VCFs,
but the benchmark contains only events of 50 bp and larger. Truvari compares calls from 30 bp
(`--sizefilt 30`), so a call just under 50 bp can still match a benchmark event; anything smaller
is not scored. The heading now says only "Structural variants", and a sentence below the size
table says how many calls are under 50 bp and how the benchmark treats them.

### "Expected of normal cells"

HG002 DNA comes from a lymphoblastoid cell line, whose methylation at some loci differs from blood
or tissue. The summary now says the two-peaked pattern is typical of human DNA and adds that
caveat.

## 5. What this delivery does not show

- **Accuracy for repeats and methylation.** The SV numbers come from a benchmark. The TRGT and CpG
  checks only show that the results are complete and look reasonable, since this region has no
  truth set for either.
- **Anything beyond one sample and 5 Mb.** Rates from 52 benchmark SVs have wide uncertainty.
- **Interpretation.** The two disease-associated repeat loci are given as allele lengths and motif
  counts with read-level plots. Whether a length is in a normal range is for clinical-grade review.

## 6. Cover note sent with the folder

> Hi Sam,
>
> Attached is the HG002 delivery for chr20:1,000,001-6,000,000, in exactly the form your own samples will
> arrive in. Start with `QC_SUMMARY.md` (one page), then `DATA_DICTIONARY.md` for the fields.
> `MANIFEST.tsv` has an MD5 for every file so you can check the transfer.
>
> A few things that will help when you compare with your pipeline:
>
> - The SV figures are against GIAB's v5.0q benchmark, which is still a draft, and are after
>   `truvari refine`. If you run `truvari bench` alone, expect recall about 6 points lower; both
>   sets of numbers are in `qc.json`.
> - pbsv also reports events shorter than 50 bp, so its VCF contains calls the benchmark mostly
>   does not score. Filter on `SVLEN` if you want to compare like for like.
> - Methylation is given for all reads and for each haplotype. Haplotype 1 and 2 are only
>   consistent within a phase block.
> - HG002 DNA comes from a cell line, so treat its methylation as a test sample, not a reference
>   for tissue.
>
> If anything in the folder is unclear without asking us, that is something we should fix, so
> please tell me.
>
> Best regards,
> Customer Success
