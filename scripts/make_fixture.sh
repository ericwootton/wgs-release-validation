#!/usr/bin/env bash
# Build the committed offline fixture in tests/data/fixture/ (run once; needs Docker and network).
#
# - reads: the fixture region of HG002 (35x NovaSeq), header reduced to chr20
# - reference: full-length chr20 with every base outside the region (+/- 5 kb) replaced by N, so
#   coordinates match GRCh38 while the bgzipped file stays small
# - truth, benchmark regions and strata: from `fetch_data.py prepare --profile fixture`
set -euo pipefail

repo=$(cd "$(dirname "$0")/.." && pwd)
out="$repo/tests/data/fixture"
samtools_img=${SAMTOOLS_DOCKER:-quay.io/biocontainers/samtools:1.24--h9dcdb79_1@sha256:a130447589651ed09252aa95a5e4f4132942cdb54d835d81a04a9a930d656561}
ref_url=https://storage.googleapis.com/deepvariant/case-study-testdata/GCA_000001405.15_GRCh38_no_alt_analysis_set.fa
bam_url=https://storage.googleapis.com/deepvariant/case-study-testdata/HG002.novaseq.pcr-free.35x.dedup.grch38_no_alt.bam
region=$(awk -F'\t' '$1 == "fixture" {print $2}' "$repo/config/profiles.tsv")
span=${region#*:}; start=${span%-*}; end=${span#*-}
keep_start=$((start - 5000)); keep_end=$((end + 5000))

python3 "$repo/scripts/fetch_data.py" prepare --profile fixture --out "$repo/data"
rm -rf "$out"; mkdir -p "$out"
cp -r "$repo/data/fixture/." "$out/"

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
docker run --rm -u "$(id -u):$(id -g)" -v "$work:/w" -w /w "$samtools_img" bash -c "
    set -euo pipefail
    samtools faidx '$ref_url' chr20 > chr20.fa
    samtools view -b -o raw.bam '$bam_url' '$region'
    samtools view -h raw.bam \
        | awk 'BEGIN{OFS=\"\t\"} /^@SQ/ {if (\$2 == \"SN:chr20\") print; next} /^@/ {print; next} {if (\$7 != \"=\" && \$7 != \"chr20\") {\$7 = \"*\"; \$8 = 0}; print}' \
        | samtools view -b -o reads.bam -
    samtools index reads.bam
"
python3 - "$work/chr20.fa" "$work/masked.fa" "$keep_start" "$keep_end" <<'PY'
import sys
src, dst, keep_start, keep_end = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
with open(src) as fh:
    header = fh.readline()
    seq = "".join(line.strip() for line in fh)
masked = "N" * (keep_start - 1) + seq[keep_start - 1:keep_end] + "N" * (len(seq) - keep_end)
assert len(masked) == len(seq)
with open(dst, "w") as out:
    out.write(header)
    for i in range(0, len(masked), 60):
        out.write(masked[i:i + 60] + "\n")
PY
docker run --rm -u "$(id -u):$(id -g)" -v "$work:/w" -w /w "$samtools_img" bash -c "
    bgzip -@2 -c masked.fa > chr20_masked.fa.gz && samtools faidx chr20_masked.fa.gz
"
cp "$work"/chr20_masked.fa.gz* "$work"/reads.bam "$work"/reads.bam.bai "$out/"
du -sh "$out"/*
