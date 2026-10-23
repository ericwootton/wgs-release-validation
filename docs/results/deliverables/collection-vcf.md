# Collection VCF (hg002-full)

`hg002-full.collection.vcf.gz` combines 3 single-sample VCFs (HG002,HG003,HG004) into one
file with one column per sample: 9784 records. Before merging, each input was restricted
to the requested region, multi-allelic records were split and indels were left-aligned, so
a variant has one spelling across samples. The inputs' INFO fields were removed: in a merged
record they would describe only one of the samples. Per-sample FORMAT fields are kept.
INFO/AC, AN and AF are counts across the samples
in this file only, not population frequencies. F_MISSING is the fraction of samples with no
genotype. A missing genotype (`./.`) means the variant was absent from that sample's
input VCF. For call sets that list only variant sites, that usually means reference, but
not always (the site may be outside that sample's callable or benchmark regions), so it is
left missing rather than converted to `0/0`.
