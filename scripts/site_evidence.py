#!/usr/bin/env python3
"""Summarise read evidence at one variant site from SAM records on stdin.

    samtools view slice.bam chr20:23712345-23712345 | site_evidence.py --pos 23712345 --ref A --alt G

Counts reads supporting the reference allele, the alternate allele or neither, split by mapping
quality (MAPQ). This is the first thing to look at when a customer asks why a known variant is
missing: low MAPQ means the aligner could not place the reads uniquely, and most callers
(including GATK HaplotypeCaller, which drops MAPQ < 20 reads by default) ignore those reads.

Handles SNPs and simple insertions and deletions (VCF-style, with the shared first base).
Duplicate, secondary, supplementary, QC-fail and unmapped reads are skipped, as callers do.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterable

SKIP_FLAGS = 0x4 | 0x100 | 0x200 | 0x400 | 0x800
CIGAR = re.compile(r"(\d+)([MIDNSHP=X])")
BANDS = (("0", 0, 0), ("1-19", 1, 19), ("20-59", 20, 59), ("60", 60, 255))


def band(mapq: int) -> str:
    return next(name for name, lo, hi in BANDS if lo <= mapq <= hi)


def allele_at(pos: int, cigar: str, seq: str, target: int, ref: str, alt: str) -> str:
    """'ref', 'alt' or 'other' for a read at 1-based reference position `target`."""
    rpos, qpos = pos, 0  # next reference / read position
    ops = [(int(n), op) for n, op in CIGAR.findall(cigar)]
    is_snp = len(ref) == len(alt) == 1
    for i, (n, op) in enumerate(ops):
        if op in "M=X":
            if rpos <= target < rpos + n:
                base = seq[qpos + target - rpos]
                if is_snp:
                    return "ref" if base == ref else "alt" if base == alt else "other"
                # Indel anchored at `target`: the event must start right after the anchor base.
                if target == rpos + n - 1 and i + 1 < len(ops):
                    nxt_n, nxt_op = ops[i + 1]
                    if len(ref) > len(alt) and nxt_op == "D" and nxt_n == len(ref) - len(alt):
                        return "alt"
                    if len(alt) > len(ref) and nxt_op == "I" and nxt_n == len(alt) - len(ref):
                        inserted = seq[qpos + n : qpos + n + nxt_n]
                        return "alt" if inserted == alt[1:] else "other"
                return "ref"
            rpos += n
            qpos += n
        elif op in "IS":
            qpos += n
        elif op in "DN":
            if rpos <= target < rpos + n:
                return "other"  # deleted base at the site, but not this deletion
            rpos += n
    return "other"


def tally(lines: Iterable[str], target: int, ref: str, alt: str) -> Counter[tuple[str, str]]:
    counts: Counter[tuple[str, str]] = Counter()
    for line in lines:
        if line.startswith("@"):
            continue
        f = line.split("\t", 11)
        flag, pos, mapq, cigar, seq = int(f[1]), int(f[3]), int(f[4]), f[5], f[9]
        if flag & SKIP_FLAGS or cigar == "*" or seq == "*":
            continue
        counts[(band(mapq), allele_at(pos, cigar, seq, target, ref, alt))] += 1
    return counts


def render(counts: Counter[tuple[str, str]], site: str) -> str:
    lines = [
        f"Read evidence at `{site}`:",
        "",
        "| MAPQ | Reference allele | Alternate allele | Other | Total |",
        "|---|---:|---:|---:|---:|",
    ]
    totals = Counter[str]()
    for name, _, _ in BANDS:
        row = [counts[(name, a)] for a in ("ref", "alt", "other")]
        for a, n in zip(("ref", "alt", "other"), row, strict=True):
            totals[a] += n
        lines.append(f"| {name} | {row[0]} | {row[1]} | {row[2]} | {sum(row)} |")
    lines.append(f"| **all** | {totals['ref']} | {totals['alt']} | {totals['other']} | {sum(totals.values())} |")
    usable_alt = sum(counts[(b, "alt")] for b in ("20-59", "60"))
    all_alt = totals["alt"]
    lines += ["", f"Alternate-allele reads with MAPQ >= 20: {usable_alt} of {all_alt}."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pos", type=int, required=True, help="1-based VCF position")
    parser.add_argument("--ref", required=True)
    parser.add_argument("--alt", required=True)
    parser.add_argument("--label", default="", help="site label for the heading (e.g. chr20:123 A>G)")
    args = parser.parse_args(argv)
    counts = tally(sys.stdin, args.pos, args.ref.upper(), args.alt.upper())
    sys.stdout.write(render(counts, args.label or f"{args.pos} {args.ref}>{args.alt}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
