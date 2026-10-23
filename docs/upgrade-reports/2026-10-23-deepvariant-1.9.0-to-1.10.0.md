# Upgrade report: DeepVariant 1.9.0 → 1.10.0

| Field | Value |
|---|---|
| Date | 2026-10-23 |
| Component | DeepVariant (germline small variants, WGS model) |
| From → to | `google/deepvariant:1.9.0@sha256:07e95b34e40cc50074d23273d479934a27e80919ac75bd97bf39a731e3c2d6ad` → `google/deepvariant:1.10.0@sha256:962e5a83b1d76aae6990625d47102785f791603f2138aa1fa9aa4fb6a2eecbe6` |
| Decision | **Approve**, with a note to customers about two output changes |

## Summary and recommendation

Approve. In the 5 Mb `full` profile, 1.10.0 changed the benchmark classification at 1 site
involving a multiallelic insertion within a CA repeat. This corrected an incorrect classification
in 1.9.0. SNP false positives decreased from 20 to 19, and missed INDELs decreased from 9 to 8.
All strata were unchanged or slightly improved. There were 0 failing rows among 25, and the
regression gate was passed.

Two VCF changes need to be documented in the release notes because they can break customers'
filtering or parsing even though accuracy did not get worse (see [Risks](#risks-and-follow-ups)).
Records with no genotype now use the `NoCall` filter instead of the `RefCall` filter, and all
records now include the `MID` FORMAT field.

## What changed

The following entries in
[v1.10.0 release notes](https://github.com/google/deepvariant/releases/tag/v1.10.0)
(released 2026-03-05) relate to short-read WGS germline variant calling:

> Implemented a new multiallelic variant post-processing method called “product” which is enabled
> for all modes except for WES.

> `run_deepvariant` and `run_deepsomatic` now reads parameters from `model.example_info.json` files

Furthermore, the contributors section also lists efforts towards "enhancing read
sampling stability, fixing non-determinism, and creating robust read sampling approach
at high coverages".

Release notes did not mention retraining of the short-read WGS model or changes to default
flags. Other major items (continuous phasing, ONT models, RNA-seq, DeepSomatic, and
pangenome-aware reassembly) do not apply to this workflow. Since genotypes at sites with
multiple alternate alleles can change, changes related to multiallelic sites should be
validated.

## Validation performed

- For profile `full`, HG002 35x NovaSeq data were evaluated against GIAB v4.2.1 in
  `chr20:21000001-26000000` (5 Mb). This used the GIAB v3.6 stratifications listed in
  `config/strat_subset.tsv` and hap.py 0.3.15 with vcfeval.
- Both runs used the same inputs, 4 shards, 4 CPUs, and 8 GiB. The only difference was the image
  used. Since preflight does not affect variant detection, it was disabled in both runs.

```bash
make run PROFILE=full LABEL=full-deepvariant-1.9.0 EXTRA="run_preflight=false callers=deepvariant \
    deepvariant_docker=google/deepvariant:1.9.0@sha256:07e95b34e40cc50074d23273d479934a27e80919ac75bd97bf39a731e3c2d6ad"
make run PROFILE=full LABEL=full-deepvariant-1.10.0 EXTRA="run_preflight=false callers=deepvariant"
python3 scripts/compare_metrics.py docs/results/full-deepvariant-1.9.0/metrics.json \
    docs/results/full-deepvariant-1.10.0/metrics.json --thresholds config/thresholds.yaml \
    --out-md docs/results/full-deepvariant-1.10.0/upgrade-gate.md
python3 scripts/diff_decisions.py results/full-deepvariant-1.9.0/deepvariant.vcf.gz \
    results/full-deepvariant-1.10.0/deepvariant.vcf.gz -n 15
python3 scripts/plot_metrics.py --metrics 1.9.0=docs/results/full-deepvariant-1.9.0/metrics.json \
    --metrics 1.10.0=docs/results/full-deepvariant-1.10.0/metrics.json --out docs/results/figures \
    --prefix deepvariant-upgrade- --title "DeepVariant 1.9.0 vs 1.10.0, full profile"
```

## Results

Baseline = 1.9.0, candidate = 1.10.0:

--8<-- "results/full-deepvariant-1.10.0/upgrade-gate.md"

![F1 by stratum for DeepVariant 1.9.0 and 1.10.0](../results/figures/deepvariant-upgrade-f1_by_stratum.png)

Visible changes in SNPs and INDELs were limited to tandem repeat regions. The next section will
show that these changes arose at the same site. A tabular version of the same data is available
in
[`deepvariant-upgrade-f1_by_stratum.md`](../results/figures/deepvariant-upgrade-f1_by_stratum.md).
Recall and precision are shown with intervals in
[`deepvariant-upgrade-recall_precision_by_stratum.png`](../results/figures/deepvariant-upgrade-recall_precision_by_stratum.png).

## Discordant calls examined

Output from `diff_decisions.py` for 2 hap.py VCFs:

--8<-- "results/full-deepvariant-1.10.0/changed-sites.md"

These 3 rows represent the same locus recorded with different allele combinations in 2
versions. Its true genotype is heterozygous and consists of 2 insertions in a CA repeat, `+CA`
and `+CACACACACACA`. DeepVariant's own records are shown below (taken from `calls.vcf.gz`,
before normalization):

| Version | ALT | GT | QUAL | AD |
|---|---|---|---:|---|
| 1.9.0 | `ACA,GCA,GCACACACACACA` | 0/1 | 29.1 | 0,3,13,2 |
| 1.10.0 | `ACA,GCA,GCACACACACACA` | 2/3 | 98.8 | 0,3,13,2 |

Each version identified the same 3 candidate alleles, and read support for each candidate allele
was unchanged. 1.9.0 called the reference allele and `ACA` (a G>A change followed by a CA
insertion, supported by 3 reads). hap.py assessed this as a false positive SNP, a true positive
CA insertion, and a missed 12 bp insertion. 1.10.0 assigned a genotype consisting of two
insertions which matched the true genotype exactly, and confidence was much higher. This is the
intended behaviour of the new multiallelic post-processing. This explains all changes in the
counts. In every stratum which contained the site, 1 SNP false positive and 1 INDEL false
negative were eliminated. These strata included, for example, `all`, `tandem_repeat`, and
`all_difficult` for SNP, and `all`, `tandem_repeat`, `all_difficult`, `TS_contained`, and
`not_lowmap_or_segdup` for INDEL.

hap.py does not evaluate variant calls outside GIAB confident regions. Outside these regions, the
normalized VCF files differ at four more sites:

| Site | 1.9.0 | 1.10.0 | Note |
|---|---|---|---|
| chr20:21,787,363, two TA-repeat insertions | 0/1, QUAL 24.2 | 1/2, QUAL 46.6 | multiallelic, now het-alt |
| chr20:23,099,840, `GCACA` → `G`,`GCA` | **0/0 with FILTER PASS**, QUAL 24.8 | 1/2, QUAL 73.4 | multiallelic, now het-alt |
| chr20:23,099,844 A>G (inside the deletion above) | 1/1 PASS (small model) | 0/0 RefCall | GIAB v4.2.1 has 0/1 here, unscored |
| chr20:25,642,616 A>G | **0/0 with FILTER PASS** | 0/0 RefCall | label only |

These 2 **0/0 PASS** records warrant attention. In 1.9.0, these records were marked PASS
despite having homozygous reference genotypes. A customer who counted variants by
`FILTER == PASS` alone would have counted them. 1.10.0 writes none. Each version had 12,232 raw output records (before normalization). In
1.9.0, these included 8,031 PASS records with ALT genotypes, plus the aforementioned 2. In
1.10.0, there were 8,031.

## Runtime and cost impact

`DeepVariant` row in `docs/results/<label>/resources.tsv` (1 run each, executed sequentially on
the same machine):

| Version | Wall time (s) | CPU time (s) | Peak memory (bytes) |
|---|---:|---:|---:|
| 1.9.0 | 225.34 | 783.18 | 7,523,241,984 |
| 1.10.0 | 235.49 | 803.72 | 8,487,870,464 |

Results from one run of each version showed that wall time increased by 4.5% and CPU time
increased by 2.6% for 1.10.0. This was within the variation observed when repeating the same run
on this laptop (69.5 s and 100.3 s for one configuration in
[CS-03](../case-studies/CS-03-deepvariant-memory.md)). Therefore, treat this as no apparent
change and repeat the measurements on cloud hardware. Peak memory was measured using the cgroup
`memory.peak` value which also includes the page cache and grows towards the 8 GiB limit. For the
200 kb `ci` region, CS-03 measured peak memory at about 2 GiB. This does not indicate that 1.10.0
requires more memory, but it also does not establish that it does not require more memory. Cost
estimates were unchanged.

## Risks and follow-ups

- **Customer note: `NoCall` instead of `RefCall`.** In 1.9.0, 580 records with no genotype (`./.`)
  were filtered `RefCall`. In 1.10.0, they are filtered `NoCall`. These were the same 580 sites in
  each version. VCF header text still describes `NoCall` as "Site has depth=0", but these records
  have sequencing reads (for example, DP=9). This change leaves filtering which retains only PASS
  records unaffected. However, these records will pass filters which remove nonvariant records by
  excluding `RefCall`.
- **Customer note: `MID` on every record.** All records now include a FORMAT field which
  identifies the model that generated the call (`deepvariant` or `small_model`). In 1.9.0, this
  field was missing from 2,411 of 12,232 records. Parsers which read FORMAT by position instead
  of key will break. Calls generated by the small model decreased by 38 (from 9,821 to 9,783),
  and the full model handled the corresponding calls.
- **Not covered: exome.** Multiallelic changes are disabled in WES by design. Validate the WES
  model separately before communicating anything to exome analysis customers.
- **Not covered: GVCF output and joint calling.** This workflow writes VCF only.
- **Scale.** Within 5 Mb of one chromosome in one sample, one site changed within the
  confident regions. While the direction of change was favourable, one site says nothing about
  the size of the genome-wide gain.
- After release, the weekly `full` CI runs and `baselines/full.json` will reflect the new
  values. Updates to the baseline follow
  [the baseline runbook](../runbooks/updating-baselines.md).
