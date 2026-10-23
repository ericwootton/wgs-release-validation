#!/usr/bin/env python3
"""Estimate what one 30x whole genome would cost per caller, cloud and pricing model.

    estimate_cost.py --results docs/results --prices config/prices.yaml --out docs/results/cost-estimate.md

Method (also printed in the report):
1. Read each run's per-task measurements (docs/results/<label>/resources.tsv, written by every
   WDL task) and the region it covered (metrics.json).
2. Keep the tasks a production run would have: the caller, coverage QC and the VCF clean-up and
   QC steps. Region fetching, benchmarking and reporting exist only for validation.
3. Scale each task's wall time to a whole genome: read-driven tasks by genome size / region size
   and by target depth / observed depth; VCF-only tasks by genome size / region size.
4. Put each task on the cheapest listed machine that meets its requested CPU and memory, and
   price the hours on demand and on spot.
5. Report a range. Low and high come from the spread of per-megabase rates across profiles (the
   200 kb CI region and the 5 Mb full region), with 25% added to the high end for localisation,
   retries and the genome being harder on average than these regions.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

GENOME_BP = 2_900_000_000  # GRCh38 primary assembly excluding N gaps, approximately
TARGET_DEPTH = 30.0
CALLER_TASKS = {"gatk": "HaplotypeCaller", "deepvariant": "DeepVariant"}
READ_DRIVEN = {"HaplotypeCaller", "DeepVariant", "Mosdepth"}
HIGH_OVERHEAD = 1.25
# Published reference point for the sanity check: DeepVariant 1.10.0 on HG003 35x WGS,
# n2-standard-96, 1 h 8 min 58 s mean (https://github.com/google/deepvariant/blob/r1.10/docs/metrics.md).
PUBLISHED_DV_VCPU_HOURS = 96 * (1 + 8 / 60 + 58 / 3600)


@dataclass(frozen=True)
class Machine:
    cloud: str
    region: str
    name: str
    vcpu: int
    mem_gib: float
    on_demand: float
    spot: float | None


@dataclass
class TaskEstimate:
    task: str
    cpu: int
    mem_gb: float
    wall_hours: float  # whole-genome estimate on the requested size
    cpu_hours: float


def region_bp(region: str) -> int:
    span = region.split(":", 1)[1].replace(",", "")
    start, end = span.split("-")
    return int(end) - int(start) + 1


def load_machines(prices: dict[str, Any]) -> list[Machine]:
    machines = []
    for cloud in ("aws_ec2", "aws_healthomics", "gcp_compute"):
        for region, rows in prices[cloud]["regions"].items():
            for row in rows:
                machines.append(
                    Machine(
                        cloud,
                        region,
                        row["name"],
                        int(row["vcpu"]),
                        float(row["mem_gib"]),
                        float(row["on_demand"]),
                        float(row["spot"]) if "spot" in row else None,
                    )
                )
    return machines


def cheapest(machines: list[Machine], cloud: str, region: str, cpu: int, mem_gb: float, spot: bool) -> Machine:
    fits = [m for m in machines if m.cloud == cloud and m.region == region and m.vcpu >= cpu and m.mem_gib >= mem_gb]
    if spot:
        fits = [m for m in fits if m.spot is not None]
    if not fits:
        raise ValueError(f"no {cloud} {region} machine with >= {cpu} vCPU and {mem_gb} GiB")
    return min(fits, key=lambda m: m.spot if spot and m.spot is not None else m.on_demand)


def read_run(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    metrics = json.loads((run_dir / "metrics.json").read_text(encoding="utf-8"))
    with (run_dir / "resources.tsv").open(newline="", encoding="utf-8") as fh:
        resources = list(csv.DictReader(fh, delimiter="\t"))
    return metrics, resources


def production_tasks(resources: list[dict[str, str]], caller: str) -> list[dict[str, str]]:
    keep = []
    for row in resources:
        task, label = row["task"], row.get("label", "")
        if (
            task == CALLER_TASKS[caller]
            or task == "Mosdepth"
            or (task in ("NormalizeVcf", "VariantQC") and label == caller)
        ):
            keep.append(row)
    return keep


def scale_tasks(rows: list[dict[str, str]], bp: int, depth: float) -> list[TaskEstimate]:
    out = []
    size_factor = GENOME_BP / bp
    depth_factor = TARGET_DEPTH / depth if depth > 0 else 1.0
    for row in rows:
        factor = size_factor * (depth_factor if row["task"] in READ_DRIVEN else 1.0)
        out.append(
            TaskEstimate(
                row["task"],
                int(float(row["requested_cpu"])),
                float(row["requested_memory_gb"]),
                float(row["wall_seconds"]) * factor / 3600,
                max(float(row["cpu_seconds"]), 0) * factor / 3600,
            )
        )
    return out


def price(tasks: list[TaskEstimate], machines: list[Machine], cloud: str, region: str, spot: bool) -> float:
    total = 0.0
    for t in tasks:
        m = cheapest(machines, cloud, region, t.cpu, t.mem_gb, spot)
        total += t.wall_hours * (m.spot if spot and m.spot is not None else m.on_demand)
    return total


def healthomics_storage(prices: dict[str, Any], hours: float) -> float:
    ho = prices["aws_healthomics"]
    return float(ho["run_storage_gb_hour"]) * float(ho["run_storage_gib_assumed"]) * hours


def build(results: Path, prices: dict[str, Any], labels: list[str] | None = None) -> dict[str, Any]:
    machines = load_machines(prices)
    per_caller: dict[str, list[tuple[str, list[TaskEstimate]]]] = defaultdict(list)
    run_dirs = sorted(p for p in results.iterdir() if (p / "resources.tsv").exists() and (p / "metrics.json").exists())
    for run_dir in run_dirs:
        if labels and run_dir.name not in labels:
            continue
        metrics, resources = read_run(run_dir)
        bp = region_bp(metrics["region"])
        depth = float(metrics["coverage"]["mean_depth"])
        for caller in metrics["callers"]:
            kept = production_tasks(resources, caller)
            if any(r["task"] == CALLER_TASKS[caller] for r in kept):
                per_caller[caller].append((run_dir.name, scale_tasks(kept, bp, depth)))

    options = [
        ("AWS EC2", "aws_ec2", "ca-central-1"),
        ("AWS EC2", "aws_ec2", "us-east-1"),
        ("AWS HealthOmics", "aws_healthomics", "us-east-1"),
        ("GCP (Batch)", "gcp_compute", "northamerica-northeast1"),
        ("GCP (Batch)", "gcp_compute", "us-central1"),
    ]
    report: dict[str, Any] = {"callers": {}, "retrieved": prices["retrieved"]}
    for caller, runs in sorted(per_caller.items()):
        by_label = {label: tasks for label, tasks in runs}
        mid_label = "full" if "full" in by_label else sorted(by_label)[-1]
        mid_tasks = by_label[mid_label]
        rows: list[dict[str, Any]] = []
        for title, cloud, region in options:
            for spot in (False, True):
                if cloud == "aws_healthomics" and spot:
                    continue
                costs = [price(tasks, machines, cloud, region, spot) for tasks in by_label.values()]
                mid = price(mid_tasks, machines, cloud, region, spot)
                hours = sum(t.wall_hours for t in mid_tasks)
                extra = healthomics_storage(prices, hours) if cloud == "aws_healthomics" else 0.0
                spread = (min(costs), max(costs)) if len(costs) > 1 else (mid * 0.75, mid * 1.2)
                rows.append(
                    {
                        "option": title,
                        "region": region,
                        "pricing": "spot" if spot else "on-demand",
                        "low": spread[0] + extra,
                        "mid": mid + extra,
                        "high": spread[1] * HIGH_OVERHEAD + extra,
                        "storage": extra,
                    }
                )
        report["callers"][caller] = {
            "profiles": sorted(by_label),
            "mid_profile": mid_label,
            "tasks": [t.__dict__ for t in mid_tasks],
            "wall_hours": sum(t.wall_hours for t in mid_tasks),
            "cpu_hours": sum(t.cpu_hours for t in mid_tasks),
            "rows": rows,
        }
    return report


def money(x: float) -> str:
    return f"${x:,.2f}"


def render(report: dict[str, Any]) -> str:
    lines = [
        "# Estimated compute cost per 30x whole genome",
        "",
        f"Generated by `scripts/estimate_cost.py` from measured task runtimes. Prices retrieved {report['retrieved']} "
        "(`config/prices.yaml`, which records the source and confidence of every price).",
        "",
        "**These are estimates, extrapolated from small regions, not measured whole-genome runs.** "
        "They are for comparing options and spotting surprises, not for quoting a customer.",
        "",
    ]
    for caller, data in report["callers"].items():
        lines += [
            f"## {caller}",
            "",
            f"Based on profiles: {', '.join(data['profiles'])} (central estimate from `{data['mid_profile']}`). "
            f"Estimated serial runtime on the requested machine sizes: **{data['wall_hours']:.1f} h**; "
            f"CPU time used: {data['cpu_hours']:.1f} CPU-hours.",
            "",
            "| Option | Region | Pricing | Low | Central | High |",
            "|---|---|---|---:|---:|---:|",
        ]
        for r in data["rows"]:
            lines.append(
                f"| {r['option']} | {r['region']} | {r['pricing']} | {money(r['low'])} | "
                f"**{money(r['mid'])}** | {money(r['high'])} |"
            )
        lines += [
            "",
            "Per task (central estimate, whole genome):",
            "",
            "| Task | Requested CPU | Requested memory (GiB) | Wall hours | CPU-hours |",
            "|---|---:|---:|---:|---:|",
        ]
        for t in data["tasks"]:
            lines.append(
                f"| {t['task']} | {t['cpu']} | {t['mem_gb']:g} | {t['wall_hours']:.2f} | {t['cpu_hours']:.2f} |"
            )
        if caller == "deepvariant":
            ratio = data["cpu_hours"] / PUBLISHED_DV_VCPU_HOURS
            lines += [
                "",
                f"Sanity check: Google reports DeepVariant 1.10.0 on a 35x genome at {PUBLISHED_DV_VCPU_HOURS:.0f} "
                f"vCPU-hours allocated (n2-standard-96, 69 min). This estimate uses {data['cpu_hours']:.0f} CPU-hours "
                f"of actual CPU time, {ratio:.2f}x the published allocation.",
            ]
        lines.append("")

    cheapest_rows = []
    for caller, data in report["callers"].items():
        best = min(data["rows"], key=lambda r: r["mid"])
        best_od = min((r for r in data["rows"] if r["pricing"] == "on-demand"), key=lambda r: r["mid"])
        cheapest_rows.append((caller, best, best_od))
    lines += ["## Reading the numbers", ""]
    for caller, best, best_od in cheapest_rows:
        saving = 100 * (1 - best["mid"] / best_od["mid"]) if best is not best_od and best_od["mid"] else 0.0
        lines.append(
            f"- **{caller}**: cheapest listed option is {best['option']} {best['region']} ({best['pricing']}) at about "
            f"{money(best['mid'])} per genome; the cheapest on-demand option is {best_od['option']} "
            f"{best_od['region']} at {money(best_od['mid'])}"
            + (f", so spot saves about {saving:.0f}% if the workflow tolerates preemption." if saving else ".")
        )
    lines += [
        "- Compute is rarely the deciding factor at these prices. Where the customer's data already sits matters "
        "more: moving a 30x BAM (~60-100 GB) out of a cloud costs roughly $5-12 in internet egress alone "
        "(see `egress_gb` in `config/prices.yaml`), and data-residency rules can rule a region out entirely "
        "(the Canadian regions are listed for that reason).",
        "- HealthOmics costs more per hour than EC2 but removes the cluster to run and maintain; its run storage "
        "is included above under an assumed 1,200 GiB static allocation.",
        "",
        "## Method",
        "",
        (__doc__ or "").split("Method (also printed in the report):", 1)[1].strip(),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--prices", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--json", type=Path, help="also write the numbers as JSON")
    parser.add_argument("--labels", default="ci,full", help="comma-separated run labels to use (default: ci,full)")
    args = parser.parse_args(argv)
    prices = yaml.safe_load(args.prices.read_text(encoding="utf-8"))
    report = build(args.results, prices, [x for x in args.labels.split(",") if x])
    if not report["callers"]:
        print(f"no runs with resources.tsv and metrics.json under {args.results}", file=sys.stderr)
        return 1
    args.out.write_text(render(report), encoding="utf-8")
    if args.json:
        args.json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
