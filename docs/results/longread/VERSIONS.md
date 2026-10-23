# Versions and commands

| Step | Container image | Command |
|---|---|---|
| FetchReference | `quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561` | `samtools faidx GRCh38_no_alt_analysis_set.fa chr20` |
| FetchReadsSlice | `quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561` | `samtools view -b -X URL URL.bai REGION(+/-20 kb); header reduced to the analysed contig` |
| Pbsv | `quay.io/biocontainers/pbsv:2.11.0--h9ee0642_0@sha256:1a738d93598c14adee41f988bb47705b738798c398250741d074caf78628fd7c` | `pbsv discover --hifi --region REGION --tandem-repeats trf.bed in.bam in.svsig.gz; pbsv call --hifi -j N ref.fa in.svsig.gz pbsv.vcf` |
| Sniffles | `quay.io/biocontainers/sniffles:2.8.0--pyhdfd78af_1@sha256:787139b7592c244e2eb913c486491157e2f5b3a3494df3f7ea0c5876b72058b7` | `sniffles --input in.bam --vcf sniffles.vcf --reference ref.fa --tandem-repeats trf.bed --threads N` |
| Trgt | `quay.io/biocontainers/trgt:5.1.0--h9ee0642_0@sha256:5fae265afdca9864e5f2d42fbc0da744fe73d0e6a2e472dda506d7d604394b0a` | `trgt genotype --genome ref.fa --reads in.bam --repeats repeats.bed --karyotype XY --output-prefix trgt` |
| CpgScores | `quay.io/biocontainers/pb-cpg-tools:3.0.0--h9ee0642_0@sha256:c7d4f999b747e4d5c356669086b929e6eda34249d3e8752ede100cb45faaefb4` | `aligned_bam_to_cpg_scores --bam in.bam --ref ref.fa --output-prefix cpg --threads N` |
| Truvari (pbsv) | `quay.io/biocontainers/truvari:5.5.0--pyhdfd78af_0@sha256:28a193205760fad402674f6011425cee09f45085ab82d57f5ff3df4bc59c1264` | `truvari bench -b truth.vcf.gz -c query.vcf.gz -f ref.fa --includebed bench.bed --pick ac --passonly -r 2000 -C 5000; truvari refine -f ref.fa --align mafft --threads N` |
| Truvari (sniffles) | `quay.io/biocontainers/truvari:5.5.0--pyhdfd78af_0@sha256:28a193205760fad402674f6011425cee09f45085ab82d57f5ff3df4bc59c1264` | `truvari bench -b truth.vcf.gz -c query.vcf.gz -f ref.fa --includebed bench.bed --pick ac --passonly -r 2000 -C 5000; truvari refine -f ref.fa --align mafft --threads N` |
