#!/usr/bin/env python3
"""Rewrite a miniwdl inputs JSON for a cloud run, and list the files to upload first.

    cloud_inputs.py inputs/full.json --target healthomics --prefix s3://BUCKET/wrv \
        --drop ref_url --drop reads_url \
        --set ref_fasta=data/chr20.fa --set reads_bam=results/full/slice.bam \
        --set reads_bai=results/full/slice.bam.bai \
        --set happy_docker=ACCOUNT.dkr.ecr.REGION.amazonaws.com/happy-vcfeval@sha256:... \
        --out _cloud/full.healthomics.json --uploads _cloud/uploads.tsv

Every value that names a local file is replaced by <prefix>/<same relative path> and listed
in the uploads TSV (local path, remote URI). Nothing is uploaded here.

Targets differ in two ways (docs/results/cloud-run.md):
- healthomics: parameter names drop the "ReleaseValidation." prefix, and https:// inputs are
  refused, because runs have no internet access unless VPC networking is set up.
- cromwell: names keep the prefix, and https:// inputs are kept (Batch VMs can stream them).
- wes: as cromwell, for a GA4GH WES server; the prefix can be any URL the server can read
  (gs://, s3://, http(s)://), e.g. a web server over this directory (docs/ga4gh.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

WORKFLOW = "ReleaseValidation"
# A string value with one of these endings is taken to be a file even if it is missing, so a
# typo or an unfetched input fails here rather than being passed through as a plain string.
FILE_SUFFIXES = (
    ".vcf",
    ".gz",
    ".bed",
    ".bam",
    ".bai",
    ".cram",
    ".crai",
    ".fa",
    ".fasta",
    ".fai",
    ".tbi",
    ".csi",
    ".tsv",
    ".json",
    ".py",
    ".txt",
)


def bare_name(name: str) -> str:
    return name.removeprefix(f"{WORKFLOW}.")


def parse_assignments(items: list[str]) -> dict[str, Any]:
    """name=value pairs. A value that parses as JSON (4, true, ["a"]) keeps its type."""
    out: dict[str, Any] = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise SystemExit(f"error: --set expects name=value, got {item!r}")
        try:
            out[bare_name(key)] = json.loads(value)
        except json.JSONDecodeError:
            out[bare_name(key)] = value
    return out


def rewrite(
    inputs: dict[str, Any],
    target: str,
    prefix: str,
    sets: dict[str, Any],
    drops: list[str],
    base: Path,
) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """Return (rewritten inputs, [(local path, remote uri)])."""
    bare = {bare_name(k): v for k, v in inputs.items()}
    for name in drops:
        if bare_name(name) not in bare:
            raise SystemExit(f"error: --drop {name}: no such input")
        del bare[bare_name(name)]
    bare.update(sets)

    uploads: dict[str, str] = {}
    owners: dict[str, str] = {}  # remote uri -> local path, to catch two files with one key
    prefix = prefix.rstrip("/")

    def convert(name: str, value: Any) -> Any:
        if isinstance(value, list):
            return [convert(name, v) for v in value]
        if not isinstance(value, str):
            return value
        if value.startswith(("http://", "https://")) and target == "healthomics":
            raise SystemExit(
                f"error: {name} is a URL ({value}). HealthOmics runs cannot reach the internet "
                "by default: stage the file to S3, pass it with --set, and --drop this input."
            )
        if "://" in value:
            return value
        path = base / value
        if ".." in Path(value).parts:
            raise SystemExit(f"error: {name}: {value} leaves the base directory; give a path under it")
        if not path.is_file():
            if value.endswith(FILE_SUFFIXES) or value.startswith(("./", "/", "data/")):
                raise SystemExit(f"error: {name}: {value} looks like a local file but does not exist; fetch it first")
            return value
        rel = Path(value).name if Path(value).is_absolute() else Path(value).as_posix().removeprefix("./")
        remote = f"{prefix}/{rel}"
        other = owners.setdefault(remote, str(path))
        if other != str(path):
            raise SystemExit(f"error: {other} and {path} would both upload to {remote}; rename one")
        uploads[str(path)] = remote
        return remote

    converted = {name: convert(name, value) for name, value in bare.items()}
    if target in ("cromwell", "wes"):
        converted = {f"{WORKFLOW}.{k}": v for k, v in converted.items()}
    return converted, sorted(uploads.items())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", type=Path)
    ap.add_argument("--target", choices=("healthomics", "cromwell", "wes"), required=True)
    ap.add_argument("--prefix", required=True, help="s3://bucket/path, gs://bucket/path, or a URL for wes")
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE", dest="sets")
    ap.add_argument("--drop", action="append", default=[], metavar="NAME")
    ap.add_argument("--base", type=Path, default=Path("."), help="directory local paths are relative to")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--uploads", type=Path, required=True)
    args = ap.parse_args(argv)

    schemes = {"healthomics": ("s3://",), "cromwell": ("gs://",), "wes": ("gs://", "s3://", "http://", "https://")}
    if not args.prefix.startswith(schemes[args.target]):
        raise SystemExit(f"error: --prefix for {args.target} must start with {' or '.join(schemes[args.target])}")

    inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
    rewritten, uploads = rewrite(inputs, args.target, args.prefix, parse_assignments(args.sets), args.drop, args.base)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rewritten, indent=2) + "\n", encoding="utf-8", newline="\n")
    args.uploads.parent.mkdir(parents=True, exist_ok=True)
    args.uploads.write_text(
        "".join(f"{local}\t{remote}\n" for local, remote in uploads), encoding="utf-8", newline="\n"
    )
    print(f"{args.out}: {len(rewritten)} inputs; {len(uploads)} files to upload, listed in {args.uploads}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
