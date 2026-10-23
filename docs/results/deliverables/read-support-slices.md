# Read-supporting BAM slices (hg002-full)

One small BAM per requested variant, holding every read that overlaps the site
plus 200 bases either side, and `hg002-full.sites.bam` with all of them merged.
Open any of them in IGV with the GRCh38 reference. Reads are copied unchanged from the
analysed BAM; nothing is realigned or filtered. Counts of reads supporting each allele
are in the allele-support table delivered alongside.

In that table, `alleles_seen` and `allele_depths` list the alleles in the reads and
the reads behind each (`<*>` is any other allele), counting reads at the mapping-quality
threshold in the `depth_mapq` column name or above. `depth_any_mapq` counts reads at
any mapping quality. Both leave out duplicate, secondary and QC-failed reads, reads in
anomalous pairs, and bases below base quality 13. A site can have two rows when the
reads also show an indel there.

| Site | Ref | Alt | Region | File | Reads |
|---|---|---|---|---|---:|
| chr20:21855413 | G | A | chr20:21855213-21855613 | slices/chr20_21855413_G_A.bam | 161 |
| chr20:21890551 | T | C | chr20:21890351-21890751 | slices/chr20_21890551_T_C.bam | 78 |
| chr20:21890838 | T | TC | chr20:21890638-21891038 | slices/chr20_21890838_T_TC.bam | 54 |
| chr20:21911257 | G | A | chr20:21911057-21911457 | slices/chr20_21911257_G_A.bam | 110 |
| chr20:21911267 | T | C | chr20:21911067-21911467 | slices/chr20_21911267_T_C.bam | 112 |
