import gzip
import hashlib
from pathlib import Path

import pytest

import fetch_data as fd


def test_region_parse_is_one_based_inclusive():
    region = fd.Region.parse("chr20:1,000,001-1,200,000")
    assert (region.chrom, region.start, region.end) == ("chr20", 1_000_000, 1_200_000)
    assert region.length == 200_000
    assert str(region) == "chr20:1000001-1200000"


@pytest.mark.parametrize("text", ["chr20", "chr20:100", "chr20:200-100", "chr20:0-10", ":1-2"])
def test_region_parse_rejects_bad_input(text):
    with pytest.raises(ValueError):
        fd.Region.parse(text)


def test_merge_clip_intersect_total():
    merged = fd.merge([(10, 20), (5, 12), (30, 40), (40, 45)])
    assert merged == [(5, 20), (30, 45)]
    assert fd.clip(merged, 15, 35) == [(15, 20), (30, 35)]
    assert fd.intersect(merged, [(0, 8), (18, 32), (44, 100)]) == [(5, 8), (18, 20), (30, 32), (44, 45)]
    assert fd.total_bp(merged) == 30


def test_contains_uses_half_open_intervals():
    ivs = [(10, 20), (30, 40)]
    assert fd.contains(ivs, 10)
    assert fd.contains(ivs, 19)
    assert not fd.contains(ivs, 20)
    assert not fd.contains(ivs, 9)
    assert fd.contains(ivs, 39)
    assert not fd.contains(ivs, 40)
    assert not fd.contains([], 5)


def test_read_bed_skips_headers_and_other_contigs(tmp_path: Path):
    bed = tmp_path / "x.bed.gz"
    with gzip.open(bed, "wt") as fh:
        fh.write("track name=x\n#comment\nchr1\t0\t10\nchr20\t50\t60\nchr20\t10\t20\nchr20\t15\t30\n")
    assert fd.read_bed(bed, "chr20") == [(10, 30), (50, 60)]


VCF = """##fileformat=VCFv4.2
##contig=<ID=chr19,length=58617616>
##contig=<ID=chr20,length=64444167>
##contig=<ID=chr21,length=46709983>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tHG002
chr19\t100\t.\tA\tG\t50\tPASS\t.\tGT\t0/1
chr20\t100\t.\tA\tG\t50\tPASS\t.\tGT\t0/1
chr20\t200\t.\tAT\tA\t50\tPASS\t.\tGT\t1/1
chr20\t300\t.\tC\tT,G\t50\tPASS\t.\tGT\t1/2
chr20\t400\t.\tC\tCAA,T\t50\tPASS\t.\tGT\t1/2
chr21\t100\t.\tA\tG\t50\tPASS\t.\tGT\t0/1
"""


def test_chrom_cache_keeps_one_contig_and_classifies_variants(tmp_path: Path):
    src = tmp_path / "truth.vcf.gz"
    with gzip.open(src, "wt") as fh:
        fh.write(VCF)
    cached = fd.chrom_vcf_cache(src, "chr20")
    text = cached.read_text()
    assert "ID=chr20," in text and "ID=chr19" not in text and "ID=chr21" not in text
    kinds = [(v.pos0, v.kind) for v in fd.iter_variants(cached, "chr20")]
    assert kinds == [(99, "SNP"), (199, "INDEL"), (299, "SNP"), (399, "INDEL")]

    out = tmp_path / "subset.vcf"
    assert fd.subset_vcf(cached, fd.Region.parse("chr20:150-350"), out) == 2


def test_download_verifies_checksum(tmp_path: Path):
    payload = b"hello genome\n"
    src = tmp_path / "remote.txt"
    src.write_bytes(payload)
    good = hashlib.md5(payload).hexdigest()
    dest = tmp_path / "cache" / "remote.txt"
    assert fd.download(src.as_uri(), dest, good).read_bytes() == payload
    assert dest.with_name("remote.txt.md5ok").read_text() == good
    with pytest.raises(OSError, match="checksum mismatch"):
        fd.download(src.as_uri(), tmp_path / "cache2" / "remote.txt", "0" * 32, retries=1)


def test_manifest_and_strata_are_consistent():
    manifest = fd.read_manifest()
    for row in manifest.values():
        assert row["url"].startswith("https://")
        assert len(row["md5"]) == 32
        assert row["citation"]
    for stratum in fd.read_tsv(fd.STRAT_SUBSET):
        assert stratum["manifest_id"] in manifest
        assert stratum["plain_language"]
    for profile in fd.read_tsv(fd.PROFILES):
        fd.Region.parse(profile["region"])
