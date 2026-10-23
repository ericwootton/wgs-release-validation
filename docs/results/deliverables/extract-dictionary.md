# Data dictionary for hg002-full.extract.tsv

One row per variant allele inside the requested regions (multi-allelic sites are split
into one row per ALT). Missing values are written as `.`. Per-sample columns are named
`SAMPLE:FIELD`.

| Column | Type | Description |
|---|---|---|
| CHROM | String | Chromosome |
| POS | Integer | 1-based position of the first REF base |
| REF | String | Reference allele |
| ALT | String | Alternate allele (one per row) |
| QUAL | Float | Phred-scaled variant quality from the caller |
| FILTER | String | PASS, or the filters the record failed |
| SAMPLE:GT | String | Genotype |
| SAMPLE:GQ | Integer | Conditional genotype quality |
| SAMPLE:DP | Integer | Read depth |
| SAMPLE:AD | Integer | Read depth for each allele |
| SAMPLE:VAF | Float | Variant allele fractions. |
