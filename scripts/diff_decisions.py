#!/usr/bin/env python3
"""List sites whose benchmark decision changed between two hap.py output VCFs (old vs new).

    diff_decisions.py old/gatk.vcf.gz new/gatk.vcf.gz [-n 10] [--strata a,b] > changed.md

Used for the "discordant calls" section of an upgrade report. A site is keyed by chrom, pos, ref
and alt; its state is the set of decisions on it (TP, FN, FP; a genotype mismatch is FN and FP).
Output is a Markdown summary line and table, sorted by position.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from pick_fn_examples import Site, iter_sites

Key = tuple[str, int, str, str]


@dataclass
class State:
    decisions: frozenset[str]
    variant_type: str
    truth_gt: str
    query_gt: str
    regions: str


def load(path: Path) -> dict[Key, State]:
    grouped: dict[Key, list[Site]] = {}
    for site in iter_sites(path):
        grouped.setdefault((site.chrom, site.pos, site.ref, site.alt), []).append(site)
    out = {}
    for key, sites in grouped.items():
        decisions = frozenset(s.decision for s in sites if s.decision in ("TP", "FN", "FP"))
        if decisions:
            first = sites[0]
            out[key] = State(decisions, first.variant_type, first.truth_gt, first.query_gt, first.regions)
    return out


def label(state: State | None) -> str:
    if state is None:
        return "absent"
    return "+".join(sorted(state.decisions))


def changed(old: dict[Key, State], new: dict[Key, State]) -> list[tuple[Key, State | None, State | None]]:
    rows = []
    for key in sorted(set(old) | set(new)):
        a, b = old.get(key), new.get(key)
        if label(a) != label(b):
            rows.append((key, a, b))
    return rows


def render(rows: list[tuple[Key, State | None, State | None]], limit: int, strata: list[str]) -> str:
    if not rows:
        return "No site changed decision.\n"
    transitions = Counter(f"{label(a)} → {label(b)}" for _, a, b in rows)
    lines = [
        f"{len(rows)} site(s) changed decision: "
        + ", ".join(f"{n} {t}" for t, n in sorted(transitions.items(), key=lambda kv: (-kv[1], kv[0])))
        + ".",
        "",
        "| Site | Type | Old | New | Truth GT | Old query GT | New query GT | Strata |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for key, a, b in rows[: limit or None]:
        chrom, pos, ref, alt = key
        any_state = a or b
        assert any_state is not None
        regions = [r for r in any_state.regions.split(",") if r and (not strata or r in strata)]
        lines.append(
            f"| {chrom}:{pos:,} {ref}>{alt} | {any_state.variant_type} | {label(a)} | {label(b)} | "
            f"{any_state.truth_gt} | {a.query_gt if a else '.'} | {b.query_gt if b else '.'} | "
            f"{', '.join(regions) or '–'} |"
        )
    if limit and len(rows) > limit:
        lines.append(f"\nFirst {limit} of {len(rows)} shown.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("old", type=Path, help="hap.py output VCF of the current version")
    parser.add_argument("new", type=Path, help="hap.py output VCF of the candidate version")
    parser.add_argument("-n", type=int, default=0, help="at most this many rows (0 = all)")
    parser.add_argument("--strata", default="", help="comma-separated strata to show (default: all)")
    args = parser.parse_args(argv)
    rows = changed(load(args.old), load(args.new))
    sys.stdout.write(render(rows, args.n, [s for s in args.strata.split(",") if s]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
