#!/usr/bin/env python3
"""Regression gate: compare a candidate metrics.json against a committed baseline.

    compare_metrics.py baselines/ci_gatk-4.7.0.0.json results/ci/metrics.json \
        --thresholds config/thresholds.yaml [--summary-file "$GITHUB_STEP_SUMMARY"]

Exit status 0 = pass, 1 = regression found, 2 = the inputs cannot be compared.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ALL = "*"
TYPES = ("SNP", "INDEL")


@dataclass
class Row:
    caller: str
    kind: str
    stratum: str
    truth: int
    base_f1: float | None
    cand_f1: float | None
    base_tp: int
    cand_tp: int
    limit: float | None
    status: str  # PASS, FAIL, INFO
    note: str = ""

    @property
    def delta(self) -> float | None:
        if self.base_f1 is None or self.cand_f1 is None:
            return None
        return self.cand_f1 - self.base_f1


def load(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported metrics schema_version {data.get('schema_version')!r}")
    return data


def same_tools(baseline: dict[str, Any], candidate: dict[str, Any]) -> bool:
    return bool(baseline.get("tool_versions")) and baseline.get("tool_versions") == candidate.get("tool_versions")


def compare(baseline: dict[str, Any], candidate: dict[str, Any], thresholds: dict[str, Any]) -> list[Row]:
    if baseline.get("region") != candidate.get("region"):
        raise ValueError(f"regions differ: baseline {baseline.get('region')}, candidate {candidate.get('region')}")
    rows: list[Row] = []
    deterministic = same_tools(baseline, candidate)
    tp_limit = float(thresholds.get("same_tools_max_tp_change_pct", 0.0))
    min_truth = int(thresholds["strata"].get("min_truth_variants", 0))

    for caller, base_types in baseline["callers"].items():
        cand_types = candidate["callers"].get(caller)
        if cand_types is None:
            rows.append(Row(caller, "-", "-", 0, None, None, 0, 0, None, "FAIL", "caller missing from candidate"))
            continue
        for kind in TYPES:
            for stratum, base in sorted(base_types[kind].items(), key=lambda kv: (kv[0] != ALL, kv[0])):
                cand = cand_types[kind].get(stratum)
                overall = stratum == ALL
                section = thresholds["overall"] if overall else thresholds["strata"]
                limit = float(section["max_f1_drop"][kind])
                if cand is None:
                    rows.append(
                        Row(
                            caller,
                            kind,
                            stratum,
                            base["truth_total"],
                            base["f1"],
                            None,
                            base["truth_tp"],
                            0,
                            limit,
                            "FAIL",
                            "stratum missing from candidate",
                        )
                    )
                    continue
                row = Row(
                    caller,
                    kind,
                    stratum,
                    base["truth_total"],
                    base["f1"],
                    cand["f1"],
                    base["truth_tp"],
                    cand["truth_tp"],
                    limit,
                    "PASS",
                )
                if base["truth_total"] == 0:
                    row.status, row.limit, row.note = "INFO", None, "no truth variants"
                elif not overall and base["truth_total"] < min_truth:
                    row.status, row.limit, row.note = "INFO", None, f"fewer than {min_truth} truth variants; not gated"
                elif row.delta is None:
                    row.status, row.note = "FAIL", "F1 could not be computed"
                elif row.delta < -limit - 1e-12:
                    row.status, row.note = "FAIL", f"F1 dropped by {-row.delta:.4f} (limit {limit})"
                if deterministic and base["truth_tp"]:
                    change = 100 * abs(cand["truth_tp"] - base["truth_tp"]) / base["truth_tp"]
                    if change > tp_limit + 1e-12:
                        row.status = "FAIL"
                        row.note = (row.note + "; " if row.note else "") + (
                            f"TP changed by {change:.2f}% with identical tool images and parameters "
                            "(non-determinism or input change)"
                        )
                rows.append(row)
    return rows


def fmt(value: float | None, scale: float = 100, digits: int = 2, signed: bool = False) -> str:
    if value is None:
        return "–"
    return f"{value * scale:+.{digits}f}" if signed else f"{value * scale:.{digits}f}"


def render(rows: list[Row], baseline_path: Path, candidate_path: Path, deterministic: bool) -> str:
    failed = [r for r in rows if r.status == "FAIL"]
    verdict = "❌ FAIL: regression detected" if failed else "✅ PASS: no regression beyond thresholds"
    lines = [
        f"## Regression gate: {verdict}",
        "",
        f"Baseline `{baseline_path.as_posix()}` vs candidate `{candidate_path.as_posix()}`.",
        "Tool images and parameters identical: " + ("yes, so results must match exactly." if deterministic else "no."),
        "",
        "| Status | Caller | Type | Stratum | Truth variants | Baseline F1 % | Candidate F1 % | Δ F1 (points) "
        "| Allowed drop (points) | Note |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    symbol = {"PASS": "✅ PASS", "FAIL": "❌ FAIL", "INFO": "ℹ️ INFO"}
    for r in rows:
        lines.append(
            f"| {symbol[r.status]} | {r.caller} | {r.kind} | {'all' if r.stratum == ALL else r.stratum} "
            f"| {r.truth:,} | {fmt(r.base_f1)} | {fmt(r.cand_f1)} | {fmt(r.delta, signed=True)} "
            f"| {fmt(r.limit)} | {r.note} |"
        )
    lines += ["", f"{len(failed)} failing row(s) of {len(rows)}.", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument(
        "--thresholds", type=Path, default=Path(__file__).resolve().parent.parent / "config" / "thresholds.yaml"
    )
    parser.add_argument("--out-md", type=Path, help="write the Markdown report here")
    parser.add_argument("--summary-file", type=Path, help="append the report (e.g. $GITHUB_STEP_SUMMARY)")
    args = parser.parse_args(argv)

    try:
        baseline, candidate = load(args.baseline), load(args.candidate)
        thresholds = yaml.safe_load(args.thresholds.read_text(encoding="utf-8"))
        rows = compare(baseline, candidate, thresholds)
    except (OSError, ValueError, KeyError) as exc:
        print(f"cannot compare: {exc}", file=sys.stderr)
        return 2

    report = render(rows, args.baseline, args.candidate, same_tools(baseline, candidate))
    print(report)
    if args.out_md:
        args.out_md.write_text(report, encoding="utf-8")
    if args.summary_file:
        with args.summary_file.open("a", encoding="utf-8") as fh:
            fh.write(report + "\n")
    return 1 if any(r.status == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
