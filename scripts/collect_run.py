#!/usr/bin/env python3
"""Copy the outputs of a finished miniwdl run into results/ (large files) and docs/results/ (small).

    collect_run.py _runs/ci/_LAST --label ci

results/<label>/        VCFs, hap.py output, read slice: ignored by git
docs/results/<label>/   metrics.json, metrics.md, coverage, bcftools stats, resources.tsv: committed
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PREFIX = "ReleaseValidation."
SMALL = {
    "metrics_json",
    "metrics_md",
    "coverage_summary",
    "bcftools_stats",
    "happy_summary",
    "happy_extended",
    "preflight_report",
}
RESOURCE_FIELDS = [
    "task",
    "label",
    "wall_seconds",
    "cpu_seconds",
    "peak_memory_bytes",
    "requested_cpu",
    "requested_memory_gb",
    "image",
]


def as_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def collect(run_dir: Path, label: str, results: Path, docs: Path) -> dict[str, object]:
    data = json.loads((run_dir / "outputs.json").read_text(encoding="utf-8"))
    outputs = data.get("outputs", data)  # miniwdl writes the outputs flat; its stdout wraps them
    big, small = results / label, docs / label
    for d in (big, small):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)

    for key, value in outputs.items():
        name = key.removeprefix(PREFIX)
        if name in ("resources", "slice_read_count") or value is None:
            continue  # optional outputs (e.g. preflight_report) are null when the step was skipped
        dest = small if name in SMALL else big
        for src in as_list(value):
            path = Path(src)
            # Per-caller files share basenames across scatter shards; hap.py and QC names carry the caller.
            shutil.copy2(path, dest / path.name)

    rows = [json.loads(Path(p).read_text(encoding="utf-8")) for p in as_list(outputs[PREFIX + "resources"])]
    with (small / "resources.tsv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=RESOURCE_FIELDS, delimiter="\t", extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    info = {
        "label": label,
        "run_dir": run_dir.resolve().name,
        "slice_read_count": outputs.get(PREFIX + "slice_read_count"),
        "tasks": len(rows),
        "total_wall_seconds": round(sum(float(r["wall_seconds"]) for r in rows), 1),
    }
    (small / "run_info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    return info


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path, help="miniwdl run directory (contains outputs.json)")
    parser.add_argument("--label", required=True)
    parser.add_argument("--results", type=Path, default=REPO / "results")
    parser.add_argument("--docs", type=Path, default=REPO / "docs" / "results")
    args = parser.parse_args(argv)
    info = collect(args.run_dir, args.label, args.results, args.docs)
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
