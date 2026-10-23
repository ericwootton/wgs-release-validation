#!/usr/bin/env python3
"""Plot recall, precision and F1 by stratum from one or more metrics.json files.

    plot_metrics.py --metrics full=docs/results/full/metrics.json --out docs/results/figures

Writes, per input set:
  f1_by_stratum.png             F1 per stratum, one marker per caller, SNP and INDEL side by side
  recall_precision_by_stratum.png   recall and precision with 95% Wilson intervals
and a matching .md data table for each figure (the table is the accessible version of the plot).

With several --metrics inputs, series are named "label: caller" so e.g. an upgrade run can be
drawn against its baseline. Colours follow the series in a fixed order, never its rank.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# Categorical slots in fixed order (validated light-mode palette); markers give a second
# encoding so identity never depends on colour alone.
SERIES_COLOURS = ["#2a78d6", "#eb6834", "#1baf7a"]
SERIES_MARKERS = ["o", "s", "D"]
INK, INK_2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
TYPES = ("SNP", "INDEL")
# Plot order, top to bottom; plain-language names for readers outside the field.
STRATA = [
    ("*", "All benchmark regions"),
    ("not_difficult", "Easy regions"),
    ("all_difficult", "All difficult regions"),
    ("lowmap_or_segdup", "Low mappability or seg. dup."),
    ("segdup", "Segmental duplications"),
    ("low_mappability", "Low mappability"),
    ("homopolymer", "Homopolymers"),
    ("tandem_repeat", "Tandem repeats"),
    ("gc_extreme", "Extreme GC"),
    ("coding", "Coding sequence"),
]
MIN_TRUTH = 10  # strata with fewer truth variants are left out of the plot (too noisy to draw)


def load_series(inputs: list[str]) -> list[tuple[str, dict[str, Any]]]:
    series = []
    for item in inputs:
        label, _, path = item.partition("=")
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for caller, by_type in data["callers"].items():
            name = caller if len(inputs) == 1 else f"{label}: {caller}"
            series.append((name, by_type))
    if len(series) > len(SERIES_COLOURS):
        raise SystemExit(f"at most {len(SERIES_COLOURS)} series per figure; got {len(series)}")
    return series


def strata_present(series: list[tuple[str, dict[str, Any]]], kind: str) -> list[tuple[str, str]]:
    keep = []
    for key, name in STRATA:
        if any(by_type.get(kind, {}).get(key, {}).get("truth_total", 0) >= MIN_TRUTH for _, by_type in series):
            keep.append((key, name))
    return keep


def style(ax: Any) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.tick_params(colors=INK_2, labelsize=8, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def offsets(n: int) -> list[float]:
    step = 0.22
    return [(i - (n - 1) / 2) * step for i in range(n)]


def panel(ax: Any, series: list[tuple[str, dict[str, Any]]], kind: str, metric: str, with_ci: bool) -> None:
    strata = strata_present(series, kind)
    style(ax)
    lo_x = 1.0
    for i, ((_, by_type), dy) in enumerate(zip(series, offsets(len(series)), strict=True)):
        for row, (key, _) in enumerate(strata):
            m = by_type.get(kind, {}).get(key)
            if not m or m["truth_total"] == 0:
                continue
            y = row + dy
            x = m[metric]
            lo_x = min(lo_x, x)
            if with_ci:
                lo, hi = m[f"{metric}_ci95"]
                lo_x = min(lo_x, lo)
                ax.plot([lo, hi], [y, y], color=SERIES_COLOURS[i], linewidth=2, solid_capstyle="round")
            ax.plot(
                x,
                y,
                SERIES_MARKERS[i],
                color=SERIES_COLOURS[i],
                markersize=6,
                markeredgecolor=SURFACE,
                markeredgewidth=1.5,
                clip_on=False,  # F1 = 1.0 sits on the axis edge; draw the whole marker
            )
    ax.set_yticks(range(len(strata)))
    ax.set_yticklabels([name for _, name in strata], color=INK)
    ax.invert_yaxis()
    ax.set_xlim(max(0.0, lo_x - 0.02), 1.002)
    ax.set_title(f"{kind} {'F1' if metric == 'f1' else metric}", color=INK, fontsize=10, loc="left")


def legend(fig: Any, series: list[tuple[str, dict[str, Any]]], y: float) -> None:
    """One row under the title, left-aligned, so a long title never runs into it."""
    handles = [
        Line2D([], [], linestyle="", marker=SERIES_MARKERS[i], color=SERIES_COLOURS[i], markersize=7, label=name)
        for i, (name, _) in enumerate(series)
    ]
    fig.legend(
        handles=handles,
        loc="upper left",
        bbox_to_anchor=(0.005, y),
        frameon=False,
        fontsize=9,
        ncol=len(series),
        labelcolor=INK,
    )


def table(series: list[tuple[str, dict[str, Any]]], metrics: list[str]) -> str:
    cols = ["Type", "Stratum", "Series", "Truth variants", *[m.capitalize() for m in metrics]]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * 3 + "---:|" * (len(cols) - 3)]
    for kind in TYPES:
        for key, name in strata_present(series, kind):
            for sname, by_type in series:
                m = by_type.get(kind, {}).get(key)
                if not m:
                    continue
                vals = []
                for metric in metrics:
                    v = f"{m[metric]:.4f}"
                    if f"{metric}_ci95" in m:
                        lo, hi = m[f"{metric}_ci95"]
                        v += f" ({lo:.4f}–{hi:.4f})"
                    vals.append(v)
                lines.append(f"| {kind} | {name} | {sname} | {m['truth_total']} | " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def plot_f1(series: list[tuple[str, dict[str, Any]]], out: Path, title: str) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2), facecolor=SURFACE)
    for ax, kind in zip(axes, TYPES, strict=True):
        panel(ax, series, kind, "f1", with_ci=False)
    fig.suptitle(title, x=0.01, ha="left", color=INK, fontsize=11)
    legend(fig, series, y=0.935)
    fig.tight_layout(rect=(0, 0, 1, 0.86))
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_recall_precision(series: list[tuple[str, dict[str, Any]]], out: Path, title: str) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), facecolor=SURFACE)
    for r, kind in enumerate(TYPES):
        for c, metric in enumerate(("recall", "precision")):
            panel(axes[r][c], series, kind, metric, with_ci=True)
    fig.suptitle(title + " (lines: 95% Wilson intervals)", x=0.01, ha="left", color=INK, fontsize=11)
    legend(fig, series, y=0.965)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(out, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--metrics", action="append", required=True, help="label=path/to/metrics.json (repeatable)")
    parser.add_argument("--out", type=Path, required=True, help="output directory")
    parser.add_argument("--title", default="HG002 vs GIAB v4.2.1")
    parser.add_argument("--prefix", default="", help="filename prefix, e.g. 'gatk-upgrade-'")
    args = parser.parse_args(argv)

    series = load_series(args.metrics)
    args.out.mkdir(parents=True, exist_ok=True)
    f1_png = args.out / f"{args.prefix}f1_by_stratum.png"
    rp_png = args.out / f"{args.prefix}recall_precision_by_stratum.png"
    plot_f1(series, f1_png, f"F1 by stratum: {args.title}")
    plot_recall_precision(series, rp_png, f"Recall and precision by stratum: {args.title}")
    f1_png.with_suffix(".md").write_text(table(series, ["f1"]), encoding="utf-8")
    rp_png.with_suffix(".md").write_text(table(series, ["recall", "precision"]), encoding="utf-8")
    print(f"wrote {f1_png} and {rp_png} (+ .md tables)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
