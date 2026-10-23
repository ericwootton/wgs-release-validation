# How it works

The workflow (`wdl/main.wdl`, WDL 1.0) takes one region of chromosome 20, calls variants in it with
one or both callers, and grades the calls against the Genome in a Bottle (GIAB) truth set for
HG002. It runs with miniwdl locally and in CI, and with Cromwell or AWS HealthOmics in the cloud.

```mermaid
flowchart TD
    ref[FetchReference<br/>chr20 from GRCh38 no-alt] --> slice
    reads[(HG002 35x Illumina BAM<br/>streamed over HTTPS)] --> slice[FetchReadsSlice<br/>region + 1 kb, header trimmed to chr20]
    slice --> pre{{Preflight<br/>ngs-preflight, optional}}
    pre --> gatk[HaplotypeCaller<br/>GATK]
    pre --> dv[DeepVariant]
    slice --> cov[Mosdepth<br/>coverage]
    gatk --> norm[NormalizeQuery<br/>split multi-allelics, left-align, PASS only]
    dv --> norm
    truth[(GIAB truth VCF<br/>and benchmark BED)] --> ntruth[NormalizeTruth]
    norm --> qc[VariantQC<br/>bcftools stats]
    norm --> happy[HappyBenchmark<br/>hap.py + vcfeval, GIAB stratifications]
    ntruth --> happy
    happy --> sum[SummarizeMetrics<br/>recall, precision, F1, 95% Wilson intervals]
    cov --> sum
    sum --> gate{{Regression gate<br/>compare_metrics.py vs baselines/}}
```

Each caller runs as one shard of a scatter, so the benchmark and QC steps run once per caller.
Every task writes `resources.json` (wall time, CPU time, peak memory, requested CPU and memory),
which `scripts/collect_run.py` gathers into `resources.tsv` and `scripts/estimate_cost.py` prices.

## Profiles

| Profile | Region | Used for |
|---|---|---|
| `fixture` | `chr20:21860001-21890000` (30 kb) | Unit and integration tests |
| `ci` | `chr20:21800001-22000000` (200 kb) | Every push, with the regression gate |
| `full` | `chr20:21000001-26000000` (5 Mb) | Caller comparison, upgrade reports, weekly CI |

`scripts/fetch_data.py pick-region` chose the `ci` window. It scans the benchmark VCF and the
difficult-region BEDs on chr20 for a window with enough variants and some difficult sequence.

## Data sources

| Data | Source |
|---|---|
| Reads | HG002 NovaSeq PCR-free 35x, aligned to GRCh38 no-alt (Google DeepVariant case-study data) |
| Reference | `GCA_000001405.15_GRCh38_no_alt_analysis_set` |
| Truth (default) | GIAB HG002 v4.2.1, GRCh38, benchmark VCF and `noinconsistent` BED |
| Truth (comparison only) | GIAB HG002 v5.0q small variants. A **draft** benchmark; never used as the release gate |
| Strata | GIAB genome stratifications v3.6 (GRCh38) |
| Trio (deliverables) | GIAB HG003 and HG004 v4.2.1 benchmark VCFs |

Exact URLs and MD5 checksums are in `config/data_manifest.tsv`. `fetch_data.py` verifies every
download against them.

GIAB data are released by NIST for benchmarking. Please cite:

- Zook JM et al. Extensive sequencing of seven human genomes to characterize benchmark reference
  materials. *Sci Data* 3, 160025 (2016). [doi:10.1038/sdata.2016.25](https://doi.org/10.1038/sdata.2016.25)
- Wagner J et al. Benchmarking challenging small variants with linked and long reads.
  *Cell Genomics* 2(5), 100128 (2022). [doi:10.1016/j.xgen.2022.100128](https://doi.org/10.1016/j.xgen.2022.100128)
- Dwarshuis N et al. The GIAB genomic stratifications resource for human reference genomes.
  *Nat Commun* 15, 9029 (2024). [doi:10.1038/s41467-024-53260-y](https://doi.org/10.1038/s41467-024-53260-y)
- Krusche P et al. Best practices for benchmarking germline small-variant calls in human genomes.
  *Nat Biotechnol* 37, 555–560 (2019). [doi:10.1038/s41587-019-0054-x](https://doi.org/10.1038/s41587-019-0054-x)

## Design choices worth knowing

- **The read header is trimmed to chr20.** The workflow uses a chr20-only reference. The slice is
  re-headered so other tools, and `ngs-preflight`, see matching contigs. GATK 4.7 and DeepVariant
  1.10 would accept the extra contigs ([CS-02](case-studies/CS-02-contig-names.md)), but other
  tools do not.
- **Memory limits are hard.** `config/miniwdl.cfg` enforces `runtime.memory` the way a cloud VM
  would, so a task that would be killed in the cloud is killed locally too
  ([CS-03](case-studies/CS-03-deepvariant-memory.md)).
- **Parameters count as versions.** Arguments that change calls (`gatk_extra_args`,
  `extra_norm_args`) are recorded next to the image digests in `metrics.json`. The gate can then
  tell a parameter change from non-determinism ([INC-01](incidents/INC-01-mapq-default-change.md)).
- **An empty benchmark fails the run.** hap.py accepts "no truth variants in the regions" as a valid
  result, so `SummarizeMetrics` stops the run instead ([CS-02](case-studies/CS-02-contig-names.md)).
