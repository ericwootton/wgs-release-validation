#!/usr/bin/env python3
"""Fetch the benchmark data named in config/data_manifest.tsv and cut it down to a profile region.

Standard library only, so it runs anywhere Python 3.10+ does.

    python scripts/fetch_data.py download                 # whole-genome files into data/cache/
    python scripts/fetch_data.py pick-region --chrom chr20 --window 200000
    python scripts/fetch_data.py prepare --profile ci      # data/ci/: truth, confident BED, strata
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import IO

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "config" / "data_manifest.tsv"
STRAT_SUBSET = REPO / "config" / "strat_subset.tsv"
PROFILES = REPO / "config" / "profiles.tsv"

Interval = tuple[int, int]  # 0-based, half-open


@dataclass(frozen=True)
class Region:
    chrom: str
    start: int  # 0-based
    end: int  # exclusive

    @classmethod
    def parse(cls, text: str) -> Region:
        """Parse samtools-style 'chr20:1,000,001-1,200,000' (1-based, inclusive)."""
        chrom, _, span = text.replace(",", "").partition(":")
        first, _, last = span.partition("-")
        if not chrom or not first or not last:
            raise ValueError(f"region must look like chr20:1000001-1200000, got {text!r}")
        start, end = int(first) - 1, int(last)
        if start < 0 or end <= start:
            raise ValueError(f"empty or negative region: {text!r}")
        return cls(chrom, start, end)

    def __str__(self) -> str:
        return f"{self.chrom}:{self.start + 1}-{self.end}"

    @property
    def length(self) -> int:
        return self.end - self.start


# --------------------------------------------------------------------------- manifest + download


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


def read_manifest(path: Path = MANIFEST) -> dict[str, dict[str, str]]:
    return {row["id"]: row for row in read_tsv(path)}


def md5sum(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            digest.update(block)
    return digest.hexdigest()


def cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / url.rsplit("/", 1)[-1]


def download(url: str, dest: Path, md5: str | None, retries: int = 4) -> Path:
    """Download url to dest, verifying md5. Re-uses a verified copy; retries with backoff."""
    stamp = dest.with_name(dest.name + ".md5ok")
    if dest.exists() and stamp.exists() and stamp.read_text().strip() == md5:
        return dest
    if dest.exists() and md5 and md5sum(dest) == md5:
        stamp.write_text(md5)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    for attempt in range(1, retries + 1):
        try:
            print(f"  downloading {url} (attempt {attempt})", file=sys.stderr)
            with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as out:
                shutil.copyfileobj(resp, out, 1 << 20)
            got = md5sum(tmp)
            if md5 and got != md5:
                raise OSError(f"checksum mismatch for {url}: expected {md5}, got {got}")
            tmp.replace(dest)
            if md5:
                stamp.write_text(md5)
            return dest
        except (OSError, urllib.error.URLError) as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            if attempt == retries:
                raise
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def download_all(cache_dir: Path, ids: Iterable[str] | None = None) -> dict[str, Path]:
    manifest = read_manifest()
    wanted = list(ids) if ids is not None else list(manifest)
    paths = {}
    for key in wanted:
        entry = manifest[key]
        paths[key] = download(entry["url"], cache_path(cache_dir, entry["url"]), entry["md5"] or None)
    return paths


# --------------------------------------------------------------------------- BED / VCF helpers


def open_text(path: Path) -> IO[str]:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def read_bed(path: Path, chrom: str) -> list[Interval]:
    """Intervals on one contig, sorted and merged."""
    out: list[Interval] = []
    with open_text(path) as fh:
        for line in fh:
            if not line.strip() or line.startswith(("#", "track", "browser")):
                continue
            fields = line.split("\t", 3)
            if fields[0] == chrom:
                out.append((int(fields[1]), int(fields[2])))
    return merge(out)


def merge(intervals: Iterable[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def clip(intervals: Iterable[Interval], start: int, end: int) -> list[Interval]:
    return [(max(s, start), min(e, end)) for s, e in intervals if e > start and s < end]


def intersect(a: list[Interval], b: list[Interval]) -> list[Interval]:
    """Intersection of two sorted, merged interval lists."""
    out: list[Interval] = []
    i = j = 0
    while i < len(a) and j < len(b):
        start, end = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if start < end:
            out.append((start, end))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def total_bp(intervals: Iterable[Interval]) -> int:
    return sum(e - s for s, e in intervals)


def contains(intervals: list[Interval], pos0: int) -> bool:
    """Is 0-based position inside a sorted, merged interval list? (binary search)"""
    lo, hi = 0, len(intervals)
    while lo < hi:
        mid = (lo + hi) // 2
        if intervals[mid][1] <= pos0:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(intervals) and intervals[lo][0] <= pos0


def write_bed(path: Path, chrom: str, intervals: Iterable[Interval]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for start, end in intervals:
            fh.write(f"{chrom}\t{start}\t{end}\n")


def chrom_vcf_cache(truth_gz: Path, chrom: str) -> Path:
    """Single-contig copy of the truth VCF (header keeps only that contig), built once."""
    out = truth_gz.parent / "derived" / f"{truth_gz.name.removesuffix('.vcf.gz')}.{chrom}.vcf"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    seen = False
    with gzip.open(truth_gz, "rt", encoding="utf-8") as src, tmp.open("w", encoding="utf-8", newline="\n") as dst:
        for line in src:
            if line.startswith("##contig=<"):
                if f"ID={chrom}," in line or f"ID={chrom}>" in line:
                    dst.write(line)
            elif line.startswith("#"):
                dst.write(line)
            elif line.startswith(chrom + "\t"):
                seen = True
                dst.write(line)
            elif seen:
                break  # contigs are contiguous in a sorted VCF
    tmp.replace(out)
    return out


@dataclass(frozen=True)
class Variant:
    pos0: int
    kind: str  # SNP or INDEL


def iter_variants(vcf: Path, chrom: str) -> Iterator[Variant]:
    with open_text(vcf) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            fields = line.split("\t", 6)
            if fields[0] != chrom:
                continue
            ref, alts = fields[3], fields[4].split(",")
            kind = "SNP" if len(ref) == 1 and all(len(a) == 1 for a in alts) else "INDEL"
            yield Variant(int(fields[1]) - 1, kind)


def subset_vcf(src: Path, region: Region, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open_text(src) as fh, dest.open("w", encoding="utf-8", newline="\n") as out:
        for line in fh:
            if line.startswith("#"):
                out.write(line)
                continue
            fields = line.split("\t", 2)
            if fields[0] == region.chrom and region.start <= int(fields[1]) - 1 < region.end:
                out.write(line)
                n += 1
    return n


# --------------------------------------------------------------------------- commands


def cmd_download(args: argparse.Namespace) -> int:
    paths = download_all(args.cache)
    for key, path in paths.items():
        print(f"{key}\t{path}")
    return 0


def cmd_pick_region(args: argparse.Namespace) -> int:
    paths = download_all(args.cache, ["truth_vcf", "truth_bed", "strat_alldifficult", "strat_lowmapsegdup"])
    chrom = args.chrom
    vcf = chrom_vcf_cache(paths["truth_vcf"], chrom)
    confident = read_bed(paths["truth_bed"], chrom)
    difficult = read_bed(paths["strat_alldifficult"], chrom)
    lowmap = read_bed(paths["strat_lowmapsegdup"], chrom)
    variants = list(iter_variants(vcf, chrom))
    end_of_data = confident[-1][1] if confident else 0

    rows = []
    for start in range(0, end_of_data, args.step):
        end = start + args.window
        in_window = [v for v in variants if start <= v.pos0 < end]
        conf = clip(confident, start, end)
        snps = sum(v.kind == "SNP" for v in in_window)
        indels = len(in_window) - snps
        diff_vars = sum(contains(difficult, v.pos0) for v in in_window)
        lowmap_vars = sum(contains(lowmap, v.pos0) for v in in_window)
        rows.append(
            {
                "region": str(Region(chrom, start, end)),
                "confident_frac": round(total_bp(conf) / args.window, 3),
                "snps": snps,
                "indels": indels,
                "difficult_vars": diff_vars,
                "lowmap_segdup_vars": lowmap_vars,
            }
        )
    eligible = [r for r in rows if r["confident_frac"] >= args.min_confident and r["indels"] >= args.min_indels]
    eligible.sort(key=lambda r: (r["lowmap_segdup_vars"], r["difficult_vars"], r["snps"] + r["indels"]), reverse=True)
    writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]), delimiter="\t")
    writer.writeheader()
    writer.writerows(eligible[: args.top])
    return 0


def load_profile(name: str) -> dict[str, str]:
    for row in read_tsv(PROFILES):
        if row["profile"] == name:
            return row
    raise SystemExit(f"unknown profile {name!r}; see {PROFILES}")


def cmd_prepare(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile)
    region = Region.parse(profile["region"])
    strata = read_tsv(STRAT_SUBSET)
    paths = download_all(args.cache, ["truth_vcf", "truth_bed", *(s["manifest_id"] for s in strata)])
    out = args.out / args.profile
    if out.exists():
        shutil.rmtree(out)
    (out / "strat").mkdir(parents=True)

    region_iv = [(region.start, region.end)]
    write_bed(out / "region.bed", region.chrom, region_iv)
    confident = intersect(read_bed(paths["truth_bed"], region.chrom), region_iv)
    write_bed(out / "confident.bed", region.chrom, confident)
    n_truth = subset_vcf(chrom_vcf_cache(paths["truth_vcf"], region.chrom), region, out / "truth.vcf")

    strat_rows = []
    summary: dict[str, object] = {
        "profile": args.profile,
        "region": str(region),
        "region_bp": region.length,
        "confident_bp": total_bp(confident),
        "truth_records_in_region": n_truth,
        "strata": {},
    }
    for stratum in strata:
        ivs = intersect(read_bed(paths[stratum["manifest_id"]], region.chrom), region_iv)
        write_bed(out / "strat" / f"{stratum['name']}.bed", region.chrom, ivs)
        strat_rows.append((stratum["name"], f"strat/{stratum['name']}.bed"))
        summary["strata"][stratum["name"]] = {  # type: ignore[index]
            "bp": total_bp(ivs),
            "confident_bp": total_bp(intersect(ivs, confident)),
        }
    with (out / "strat.tsv").open("w", encoding="utf-8", newline="\n") as fh:
        for name, rel in strat_rows:
            fh.write(f"{name}\t{rel}\n")
    (out / "data_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


def clip_bed_lines(src: Path, region: Region, dest: Path) -> int:
    """Copy BED records overlapping the region. Plain 3-column intervals are clipped to it;
    annotated records (more columns, e.g. a TRGT repeat catalogue) are kept only if fully inside,
    because cutting a repeat definition in half would make it wrong."""
    n = 0
    with open_text(src) as fh, dest.open("w", encoding="utf-8", newline="\n") as out:
        for line in fh:
            if line.startswith(("#", "track", "browser")):
                continue
            fields = line.rstrip("\n").split("\t")
            if fields[0].isdigit() and len(fields) > 3 and fields[1].startswith("chr"):
                fields = fields[1:]  # UCSC database tables start with a 'bin' column
            if fields[0] != region.chrom:
                continue
            start, end = int(fields[1]), int(fields[2])
            if end <= region.start or start >= region.end:
                continue
            if len(fields) == 3:
                out.write(f"{fields[0]}\t{max(start, region.start)}\t{min(end, region.end)}\n")
            elif start >= region.start and end <= region.end:
                out.write("\t".join(fields) + "\n")
            else:
                continue
            n += 1
    return n


def cmd_subset(args: argparse.Namespace) -> int:
    """Cut arbitrary manifest entries (VCFs and BEDs) to a region, e.g. for optional modules."""
    region = Region.parse(args.region if args.region else load_profile(args.profile)["region"])
    paths = download_all(args.cache, args.ids)
    args.out.mkdir(parents=True, exist_ok=True)
    for key in args.ids:
        url = read_manifest()[key]["url"]
        if ".vcf" in url:
            n = subset_vcf(chrom_vcf_cache(paths[key], region.chrom), region, args.out / f"{key}.vcf")
        else:
            n = clip_bed_lines(paths[key], region, args.out / f"{key}.bed")
        print(f"{key}\t{n} records in {region}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=REPO / "data" / "cache", help="download cache")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("download", help="download and verify every manifest entry").set_defaults(func=cmd_download)

    pick = sub.add_parser("pick-region", help="rank candidate windows by benchmark content")
    pick.add_argument("--chrom", default="chr20")
    pick.add_argument("--window", type=int, default=200_000)
    pick.add_argument("--step", type=int, default=50_000)
    pick.add_argument("--min-confident", type=float, default=0.8)
    pick.add_argument("--min-indels", type=int, default=20)
    pick.add_argument("--top", type=int, default=15)
    pick.set_defaults(func=cmd_pick_region)

    prep = sub.add_parser("prepare", help="cut truth, confident BED and strata to a profile region")
    prep.add_argument("--profile", required=True)
    prep.add_argument("--out", type=Path, default=REPO / "data")
    prep.set_defaults(func=cmd_prepare)

    subset = sub.add_parser("subset", help="cut chosen manifest VCFs/BEDs to a profile or region")
    subset.add_argument("ids", nargs="+", help="manifest ids")
    where = subset.add_mutually_exclusive_group(required=True)
    where.add_argument("--profile")
    where.add_argument("--region", help="chr:start-end, 1-based inclusive")
    subset.add_argument("--out", type=Path, required=True)
    subset.set_defaults(func=cmd_subset)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
