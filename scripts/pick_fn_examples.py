#!/usr/bin/env python3
"""List missed (FN) or false (FP) calls from a hap.py output VCF, optionally within one stratum.

    pick_fn_examples.py results/full/gatk.vcf.gz --stratum lowmap_or_segdup --decision FN -n 10

hap.py writes two samples, TRUTH and QUERY, with BD (decision: TP/FP/FN/N/UNK) and BVT (variant
type) per sample, and lists the stratification regions containing each site in INFO/Regions.
Output is a TSV, one row per site, sorted by position.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import sys
from collections.abc import Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import IO


@dataclass
class Site:
    chrom: str
    pos: int
    ref: str
    alt: str
    decision: str
    variant_type: str
    truth_gt: str
    query_gt: str
    regions: str


def open_text(path: Path) -> IO[str]:
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")


def parse_info(text: str) -> dict[str, str]:
    out = {}
    for item in text.split(";"):
        key, _, value = item.partition("=")
        out[key] = value
    return out


def iter_sites(path: Path) -> Iterator[Site]:
    samples: list[str] = []
    with open_text(path) as fh:
        for line in fh:
            if line.startswith("##"):
                continue
            fields = line.rstrip("\n").split("\t")
            if line.startswith("#"):
                samples = fields[9:]
                continue
            keys = fields[8].split(":")
            per_sample = {
                name: dict(zip(keys, value.split(":"), strict=False))
                for name, value in zip(samples, fields[9:], strict=False)
            }
            truth, query = per_sample.get("TRUTH", {}), per_sample.get("QUERY", {})
            # A missed variant is decided on the TRUTH side, a false call on the QUERY side. A genotype
            # mismatch (truth 1/1, query 0/1) carries both, so each side yields its own site.
            for source in (truth, query):
                if source.get("BD", ".") in (".", ""):
                    continue
                yield Site(
                    chrom=fields[0],
                    pos=int(fields[1]),
                    ref=fields[3],
                    alt=fields[4],
                    decision=source["BD"],
                    variant_type=source.get("BVT", "."),
                    truth_gt=truth.get("GT", "."),
                    query_gt=query.get("GT", "."),
                    regions=parse_info(fields[7]).get("Regions", ""),
                )


def select(sites: Iterator[Site], decision: str, stratum: str | None, kind: str | None) -> list[Site]:
    chosen = []
    for site in sites:
        if site.decision != decision:
            continue
        if stratum and stratum not in site.regions.split(","):
            continue
        if kind and site.variant_type != kind:
            continue
        chosen.append(site)
    return sorted(chosen, key=lambda s: (s.chrom, s.pos))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("vcf", type=Path, help="hap.py output VCF (prefix.vcf.gz)")
    parser.add_argument("--decision", choices=["FN", "FP"], default="FN")
    parser.add_argument("--stratum", help="keep sites inside this stratum (name from config/strat_subset.tsv)")
    parser.add_argument("--type", dest="kind", choices=["SNP", "INDEL"], help="keep one variant type")
    parser.add_argument("-n", type=int, default=0, help="at most this many sites (0 = all)")
    args = parser.parse_args(argv)

    sites = select(iter_sites(args.vcf), args.decision, args.stratum, args.kind)
    if args.n:
        sites = sites[: args.n]
    writer = csv.DictWriter(sys.stdout, fieldnames=list(Site.__dataclass_fields__), delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for site in sites:
        writer.writerow(asdict(site))
    print(f"{len(sites)} site(s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
