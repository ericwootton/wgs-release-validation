#!/usr/bin/env python3
"""Summarise hap.py extended.csv files into metrics.json and a Markdown table.

Standard library only: it runs inside a plain python image as the SummarizeMetrics WDL task.

    summarize_happy.py --extended gatk=gatk.extended.csv [--extended deepvariant=...] \
        --run-label ci --region chr20:1-2 --mosdepth coverage.mosdepth.summary.txt \
        --out-json metrics.json --out-md metrics.md
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
TYPES = ("SNP", "INDEL")
ALL = "*"
DEFAULT_TRUTH_SET = "GIAB v4.2.1 (GRCh38)"
# Strata shown in the Markdown table, in this order (all strata are kept in the JSON).
TABLE_STRATA = (ALL, "not_difficult", "all_difficult", "lowmap_or_segdup", "homopolymer", "tandem_repeat", "coding")


def wilson(successes: int, total: int, z: float = 1.959964) -> tuple[float, float] | None:
    """95% Wilson score interval for a proportion; None when there is no data."""
    if total <= 0:
        return None
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def ratio(num: int, den: int) -> float | None:
    return num / den if den else None


def f1(recall: float | None, precision: float | None) -> float | None:
    if recall is None or precision is None or recall + precision == 0:
        return None
    return 2 * recall * precision / (recall + precision)


def as_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def metrics_from_row(row: dict[str, str]) -> dict[str, Any]:
    tp_truth, fn = as_int(row["TRUTH.TP"]), as_int(row["TRUTH.FN"])
    tp_query, fp = as_int(row["QUERY.TP"]), as_int(row["QUERY.FP"])
    recall = ratio(tp_truth, tp_truth + fn)
    precision = ratio(tp_query, tp_query + fp)
    return {
        "truth_total": as_int(row["TRUTH.TOTAL"]),
        "truth_tp": tp_truth,
        "truth_fn": fn,
        "query_total": as_int(row["QUERY.TOTAL"]),
        "query_tp": tp_query,
        "query_fp": fp,
        "query_unk": as_int(row.get("QUERY.UNK", "0")),
        "fp_gt": as_int(row.get("FP.gt", "0")),
        "recall": recall,
        "precision": precision,
        "f1": f1(recall, precision),
        "recall_ci95": wilson(tp_truth, tp_truth + fn),
        "precision_ci95": wilson(tp_query, tp_query + fp),
    }


def read_extended(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """{type: {stratum: metrics}} for the PASS, all-subtypes, all-genotypes rows."""
    out: dict[str, dict[str, dict[str, Any]]] = {t: {} for t in TYPES}
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row["Type"] not in TYPES or row["Subtype"] != ALL or row["Filter"] != "PASS":
                continue
            if row.get("Genotype", ALL) != ALL:
                continue
            out[row["Type"]][row["Subset"]] = metrics_from_row(row)
    for kind in TYPES:
        if ALL not in out[kind]:
            raise ValueError(f"{path}: no PASS row for {kind} over all regions; is this a hap.py extended.csv?")
    return out


def read_mosdepth(path: Path) -> dict[str, float]:
    with path.open(encoding="utf-8") as fh:
        rows = {r["chrom"]: r for r in csv.DictReader(fh, delimiter="\t")}
    row = rows.get("total_region") or rows.get("total")
    if row is None:
        raise ValueError(f"{path}: not a mosdepth summary")
    return {"mean_depth": float(row["mean"]), "min_depth": float(row["min"]), "max_depth": float(row["max"])}


def fmt_pct(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{100 * value:.{digits}f}%"


def fmt_ci(ci: tuple[float, float] | list[float] | None) -> str:
    return "" if ci is None else f" ({100 * ci[0]:.1f}–{100 * ci[1]:.1f})"


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        f"### Benchmark results: `{summary['run_label']}`",
        "",
        f"Region `{summary['region']}` · HG002 vs {summary['truth_set']} · hap.py (vcfeval) · "
        f"mean depth {summary['coverage']['mean_depth']:.1f}x",
        "",
        "| Caller | Type | Stratum | Truth variants | Missed (FN) | False calls (FP) "
        "| Recall (95% CI) | Precision (95% CI) | F1 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for caller, by_type in summary["callers"].items():
        for kind in TYPES:
            for stratum in TABLE_STRATA:
                m = by_type[kind].get(stratum)
                if m is None or (m["truth_total"] == 0 and m["query_fp"] == 0):
                    continue
                name = "all benchmark regions" if stratum == ALL else stratum
                lines.append(
                    f"| {caller} | {kind} | {name} | {m['truth_total']:,} | {m['truth_fn']:,} | {m['query_fp']:,} "
                    f"| {fmt_pct(m['recall'])}{fmt_ci(m['recall_ci95'])} "
                    f"| {fmt_pct(m['precision'])}{fmt_ci(m['precision_ci95'])} "
                    f"| {fmt_pct(m['f1'])} |"
                )
    lines += [
        "",
        "Intervals are 95% Wilson score intervals on the counts shown; small strata have wide intervals.",
        "",
    ]
    return "\n".join(lines)


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    callers = {}
    for item in args.extended:
        label, sep, path = item.partition("=")
        if not sep:
            raise SystemExit(f"--extended expects label=path, got {item!r}")
        callers[label] = read_extended(Path(path))
    versions = {}
    for item in args.tool_version or []:
        tool, _, image = item.partition("=")
        versions[tool] = image
    return {
        "schema_version": SCHEMA_VERSION,
        "run_label": args.run_label,
        "region": args.region,
        "truth_set": args.truth_set,
        "tool_versions": versions,
        "coverage": read_mosdepth(Path(args.mosdepth)) if args.mosdepth else {"mean_depth": float("nan")},
        "callers": callers,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--extended", action="append", required=True, metavar="LABEL=PATH")
    parser.add_argument("--tool-version", action="append", metavar="TOOL=IMAGE")
    parser.add_argument("--run-label", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--truth-set", default=DEFAULT_TRUTH_SET, help="truth set name shown in the report")
    parser.add_argument("--mosdepth")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args(argv)

    summary = build_summary(args)
    Path(args.out_json).write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    Path(args.out_md).write_text(render_markdown(summary), encoding="utf-8")

    # hap.py exits 0 when no truth variant falls inside the benchmark regions, which is what a
    # chromosome-naming mismatch in a BED looks like (CS-02). An empty report must fail the run.
    empty = [
        label
        for label, by_type in summary["callers"].items()
        if all(by_type[t][ALL]["truth_total"] == 0 for t in TYPES)
    ]
    if empty:
        print(
            f"error: no truth variants inside the benchmark regions for {', '.join(empty)}. Check that the BED "
            "files, truth VCF and reference use the same chromosome names (for example chr20, not 20).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
