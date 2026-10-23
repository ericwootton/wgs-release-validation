#!/usr/bin/env python3
"""QC the long-read outputs and assemble a partner handoff folder (standard library only).

    longread_handoff.py --label longread --region chr20:1000001-6000000 --read-count N \\
        --sv-vcf pbsv.vcf.gz --sv-vcf sniffles.vcf.gz --truvari pbsv.truvari.json ... \\
        --trgt-vcf trgt.vcf.gz --cpg-bed cpg.combined.bed.gz --index <each .tbi> \\
        [--cpg-haplotype-bed cpg.hap1.bed.gz --cpg-haplotype-bed cpg.hap2.bed.gz] \\
        --resources <each resources.json> [--cpg-islands islands.bed] --out handoff

Writes into --out:
  the data files (bgzipped, with their .tbi), prefixed with the run label
  MANIFEST.tsv        file, bytes, MD5, description
  DATA_DICTIONARY.md  every column and VCF field a recipient needs
  QC_SUMMARY.md       one page, plain language
  VERSIONS.md         container images and the commands each step ran
  qc.json             the QC numbers, machine-readable
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import shutil
import statistics
import sys
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import IO, Any

SIZE_BINS = [(50, 99, "50-99 bp"), (100, 499, "100-499 bp"), (500, 999, "500-999 bp"),
             (1000, 9999, "1-10 kb"), (10000, 10**12, ">= 10 kb")]  # fmt: skip
COMMANDS = {
    "Pbsv": "pbsv discover --hifi --region REGION --tandem-repeats trf.bed in.bam in.svsig.gz; "
    "pbsv call --hifi -j N ref.fa in.svsig.gz pbsv.vcf",
    "Sniffles": "sniffles --input in.bam --vcf sniffles.vcf --reference ref.fa --tandem-repeats trf.bed --threads N",
    "Truvari": "truvari bench -b truth.vcf.gz -c query.vcf.gz -f ref.fa --includebed bench.bed "
    "--pick ac --passonly -r 2000 -C 5000; truvari refine -f ref.fa --align mafft --threads N",
    "Trgt": "trgt genotype --genome ref.fa --reads in.bam --repeats repeats.bed --karyotype XY --output-prefix trgt",
    "CpgScores": "aligned_bam_to_cpg_scores --bam in.bam --ref ref.fa --output-prefix cpg --threads N",
    "FetchReadsSlice": "samtools view -b -X URL URL.bai REGION(+/-20 kb); header reduced to the analysed contig",
    "FetchReference": "samtools faidx GRCh38_no_alt_analysis_set.fa chr20",
}


def open_text(path: Path) -> IO[str]:
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_info(text: str) -> dict[str, str]:
    out = {}
    for item in text.split(";"):
        key, _, value = item.partition("=")
        out[key] = value
    return out


def vcf_records(path: Path) -> Iterator[tuple[list[str], dict[str, str], list[dict[str, str]]]]:
    with open_text(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            keys = f[8].split(":") if len(f) > 8 else []
            samples = [dict(zip(keys, s.split(":"), strict=False)) for s in f[9:]]
            yield f, parse_info(f[7]), samples


# --------------------------------------------------------------------------- SVs


def sv_length(fields: list[str], info: dict[str, str]) -> int:
    if info.get("SVLEN", "") not in ("", "."):
        return abs(int(info["SVLEN"].split(",")[0]))
    if "END" in info:
        return abs(int(info["END"]) - int(fields[1]))
    return abs(len(fields[4]) - len(fields[3]))


def sv_qc(path: Path) -> dict[str, Any]:
    total = passing = 0
    by_type: Counter[str] = Counter()
    by_size: Counter[str] = Counter()
    for fields, info, _ in vcf_records(path):
        total += 1
        if fields[6] not in ("PASS", "."):
            continue
        passing += 1
        svtype = info.get("SVTYPE", "?")
        by_type[svtype] += 1
        if svtype != "BND":
            length = sv_length(fields, info)
            by_size[next((name for lo, hi, name in SIZE_BINS if lo <= length <= hi), "< 50 bp")] += 1
    return {
        "records": total,
        "pass": passing,
        "pass_fraction": passing / total if total else 0.0,
        "by_type": dict(sorted(by_type.items())),
        "by_size": {name: by_size.get(name, 0) for name in ["< 50 bp", *(n for _, _, n in SIZE_BINS)]},
    }


def truvari_qc(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    keys = ["TP-base", "TP-comp", "FP", "FN", "precision", "recall", "f1", "base cnt", "comp cnt", "gt_concordance"]
    return {k: data.get(k) for k in keys}


# --------------------------------------------------------------------------- tandem repeats


def trgt_qc(path: Path) -> dict[str, Any]:
    loci: list[dict[str, Any]] = []
    for fields, info, samples in vcf_records(path):
        s = samples[0] if samples else {}
        gt = s.get("GT", ".")
        allele_lengths = [int(x) for x in s.get("AL", ".").split(",") if x not in (".", "")]
        spanning = [int(x) for x in s.get("SD", ".").split(",") if x not in (".", "")]
        loci.append({
            "id": info.get("TRID", fields[2]),
            "chrom": fields[0],
            "pos": int(fields[1]),
            "motifs": info.get("MOTIFS", ""),
            "genotyped": gt.replace("|", "/") not in (".", "./.", ""),
            "allele_lengths_bp": allele_lengths,
            "motif_counts": s.get("MC", "."),
            "spanning_reads": sum(spanning),
        })  # fmt: skip
    genotyped = [locus for locus in loci if locus["genotyped"]]
    reads: list[int] = [locus["spanning_reads"] for locus in genotyped]
    lengths: list[int] = [n for locus in genotyped for n in locus["allele_lengths_bp"]]
    return {
        "loci": len(loci),
        "genotyped": len(genotyped),
        "no_call_rate": 1 - len(genotyped) / len(loci) if loci else 0.0,
        "median_spanning_reads": statistics.median(reads) if reads else 0,
        "allele_length_bp": {
            "min": min(lengths, default=0),
            "median": statistics.median(lengths) if lengths else 0,
            "max": max(lengths, default=0),
        },
        "per_locus": loci,
    }


# --------------------------------------------------------------------------- methylation


def read_islands(path: Path | None) -> list[tuple[int, int]]:
    if path is None:
        return []
    out = []
    with open_text(path) as fh:
        for line in fh:
            f = line.split("\t")
            out.append((int(f[1]), int(f[2])))
    return sorted(out)


def in_any(intervals: list[tuple[int, int]], pos: int) -> bool:
    lo, hi = 0, len(intervals)
    while lo < hi:
        mid = (lo + hi) // 2
        if intervals[mid][1] <= pos:
            lo = mid + 1
        else:
            hi = mid
    return lo < len(intervals) and intervals[lo][0] <= pos


def cpg_qc(path: Path, islands: list[tuple[int, int]], start0: int = 0, end0: int = 1 << 62) -> dict[str, Any]:
    """pb-CpG-tools bed: chrom, begin, end, mod_score (0-100), type, cov, est_mod, est_unmod, discretized."""
    covs: list[int] = []
    scores: list[float] = []
    island_scores: list[float] = []
    sea_scores: list[float] = []
    with open_text(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.split("\t")
            begin, score, cov = int(f[1]), float(f[3]), int(f[5])
            if not start0 <= begin < end0:
                continue  # reads were fetched with padding; QC covers the requested region only
            covs.append(cov)
            if cov < 10:
                continue
            scores.append(score)
            (island_scores if in_any(islands, begin) else sea_scores).append(score)
    n = len(covs)
    return {
        "cpg_sites": n,
        "median_coverage": statistics.median(covs) if covs else 0,
        "fraction_ge_10x": sum(c >= 10 for c in covs) / n if n else 0.0,
        "sites_ge_10x": len(scores),
        "mean_methylation_pct": statistics.fmean(scores) if scores else 0.0,
        # Bimodality: in most human DNA, CpGs are either mostly methylated or mostly unmethylated.
        "fraction_below_20pct": sum(s < 20 for s in scores) / len(scores) if scores else 0.0,
        "fraction_above_80pct": sum(s > 80 for s in scores) / len(scores) if scores else 0.0,
        "islands_available": bool(islands),
        "mean_in_islands_pct": statistics.fmean(island_scores) if island_scores else None,
        "mean_outside_islands_pct": statistics.fmean(sea_scores) if sea_scores else None,
        "sites_in_islands": len(island_scores),
    }


def cpg_scores(path: Path, start0: int, end0: int, min_cov: int = 10) -> dict[int, float]:
    out = {}
    with open_text(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.split("\t")
            begin = int(f[1])
            if start0 <= begin < end0 and int(f[5]) >= min_cov:
                out[begin] = float(f[3])
    return out


def haplotype_qc(beds: list[Path], start0: int, end0: int) -> dict[str, Any]:
    """Per-haplotype summaries, and how many CpGs differ strongly between the two haplotypes."""
    per_hap = {bed.name.split(".")[1]: cpg_qc(bed, [], start0, end0) for bed in sorted(beds, key=lambda b: b.name)}
    out: dict[str, Any] = {"haplotypes": per_hap}
    if len(beds) == 2:
        a, b = (cpg_scores(bed, start0, end0) for bed in sorted(beds, key=lambda b: b.name))
        shared = a.keys() & b.keys()
        out["sites_ge_10x_both"] = len(shared)
        out["sites_differ_ge_50"] = sum(abs(a[s] - b[s]) >= 50 for s in shared)
    return out


# --------------------------------------------------------------------------- writing


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def fmt(x: Any, digits: int = 3) -> str:
    return f"{x:.{digits}f}" if isinstance(x, float) else str(x)


def qc_summary(qc: dict[str, Any]) -> str:
    lines = [
        f"# QC summary: {qc['label']}",
        "",
        f"HG002 PacBio HiFi reads over {qc['region']} (GRCh38), {qc['read_count']:,} reads analysed. "
        "Research use only: these results are not for clinical decisions.",
        "",
        "## Structural variants",
        "",
        "Compared with the GIAB HG002 v5.0q structural-variant benchmark, which is a **draft** release. "
        "The benchmark scores events of 50 bp and larger inside its benchmark regions. "
        "Recall is the share of benchmark SVs that were found; precision is the share of calls that are in "
        "the benchmark.",
        "",
        "| Caller | Calls (PASS) | Recall | Precision | F1 | Found | Missed | False calls |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for caller, data in qc["sv"].items():
        t = data.get("truvari_refined") or data["truvari"]
        lines.append(
            f"| {caller} | {data['pass']} of {data['records']} | {fmt(t['recall'])} | {fmt(t['precision'])} | "
            f"{fmt(t['f1'])} | {t['TP-base']} | {t['FN']} | {t['FP']} |"
        )
    if any("truvari_refined" in d for d in qc["sv"].values()):
        before = "; ".join(
            f"{c} recall {fmt(d['truvari']['recall'])}, precision {fmt(d['truvari']['precision'])}"
            for c, d in qc["sv"].items()
        )
        lines += [
            "",
            "These numbers are after truvari refinement, which re-aligns the calls in each disagreeing region "
            "so that the same event described differently is still matched, as the benchmark's README "
            f"recommends. Before refinement: {before}.",
        ]
    columns = [*qc["sv_types"], *qc["sv_sizes"]]
    lines += ["", "PASS calls by type and size:", "", "| Caller | " + " | ".join(columns) + " |"]
    lines.append("|---|" + "---:|" * len(columns))
    for caller, data in qc["sv"].items():
        cells = [str(data["by_type"].get(t, 0)) for t in qc["sv_types"]]
        cells += [str(data["by_size"].get(s, 0)) for s in qc["sv_sizes"]]
        lines.append(f"| {caller} | " + " | ".join(cells) + " |")
    small = {c: d["by_size"].get("< 50 bp", 0) for c, d in qc["sv"].items()}
    if any(small.values()):
        counts = " and ".join(f"{n} from {c}" for c, n in small.items() if n)
        lines += ["", f"Calls under 50 bp ({counts}) are in the files and in the table above, but the benchmark "
                  "only contains events of 50 bp and larger. Truvari still compares calls from 30 bp, so a call "
                  "just under 50 bp can match a benchmark event; smaller calls are not scored."]  # fmt: skip

    tr = qc["trgt"]
    lines += [
        "",
        "## Tandem repeats (TRGT)",
        "",
        f"{tr['genotyped']} of {tr['loci']} catalogue loci in the region were genotyped "
        f"(no-call rate {pct(tr['no_call_rate'])}), with a median of {fmt(tr['median_spanning_reads'], 0)} reads "
        f"fully spanning each locus. Allele lengths ranged from {tr['allele_length_bp']['min']} to "
        f"{tr['allele_length_bp']['max']} bp (median {fmt(tr['allele_length_bp']['median'], 0)}).",
    ]
    if qc["highlight"]:
        lines += ["", "Disease-associated loci in the region:", "",
                  "| Locus | Position | Allele lengths (bp) | Motif counts | Spanning reads |",
                  "|---|---|---|---|---:|"]  # fmt: skip
        for locus in qc["highlight"]:
            lengths = ", ".join(map(str, locus["allele_lengths_bp"])) or "no call"
            lines.append(f"| {locus['id']} | {locus['chrom']}:{locus['pos']:,} | {lengths} | "
                         f"{locus['motif_counts']} | {locus['spanning_reads']} |")  # fmt: skip
        lines += ["", "These are measurements, not interpretations: whether an allele length is in a normal "
                  "range depends on the locus and needs clinical-grade review."]  # fmt: skip
        if qc.get("plots"):
            lines += ["", "Read-level plots of these loci (TRGT `plot`, one row per spanning read, coloured by "
                      "motif): " + ", ".join(f"`{name}`" for name in qc["plots"]) + "."]  # fmt: skip

    cpg = qc["cpg"]
    lines += [
        "",
        "## CpG methylation (pb-CpG-tools)",
        "",
        f"{cpg['cpg_sites']:,} CpG sites scored; median coverage {fmt(cpg['median_coverage'], 0)}x, "
        f"{pct(cpg['fraction_ge_10x'])} with at least 10 reads. At sites with 10 or more reads, mean "
        f"methylation is {cpg['mean_methylation_pct']:.1f}%; {pct(cpg['fraction_below_20pct'])} are below 20% and "
        f"{pct(cpg['fraction_above_80pct'])} above 80%, the two-peaked pattern typical of human DNA. "
        "HG002 DNA comes from a lymphoblastoid cell line, so methylation at some loci can differ from "
        "blood or tissue.",
    ]
    if cpg["islands_available"] and cpg["mean_in_islands_pct"] is not None:
        lines.append(
            f"CpG islands are mostly unmethylated, as expected: {cpg['mean_in_islands_pct']:.1f}% mean inside "
            f"islands ({cpg['sites_in_islands']:,} sites) against {cpg['mean_outside_islands_pct']:.1f}% outside."
        )
    haps = qc.get("cpg_haplotypes", {}).get("haplotypes", {})
    if haps:
        per = "; ".join(
            f"{name}: {h['cpg_sites']:,} sites, mean {h['mean_methylation_pct']:.1f}% at sites with 10 or more reads"
            for name, h in haps.items()
        )
        lines += ["", f"Scores are also given per haplotype, from the reads' HP tags ({per})."]
        if "sites_ge_10x_both" in qc["cpg_haplotypes"]:
            both, differ = qc["cpg_haplotypes"]["sites_ge_10x_both"], qc["cpg_haplotypes"]["sites_differ_ge_50"]
            lines.append(
                f"Of {both:,} CpGs with 10 or more reads on both haplotypes, {differ:,} "
                f"({pct(differ / both if both else 0.0)}) differ by 50 percentage points or more between them."
            )
        lines.append(
            "The haplotype numbers come from the phasing behind the HP tags. Unless that phasing used parental "
            "data, hap1 in one phase block need not be the same parent as hap1 in the next."
        )
    lines += [
        "",
        "## What was checked before release",
        "",
        "- Every data file opens, is bgzip-compressed and has a matching .tbi index; MD5s are in MANIFEST.tsv.",
        "- SV calls were compared with the benchmark only inside its benchmark regions.",
        "- Tool versions and commands are in VERSIONS.md; field definitions are in DATA_DICTIONARY.md.",
        "",
    ]
    return "\n".join(lines)


DATA_DICTIONARY = """# Data dictionary

All coordinates are GRCh38. VCF positions are 1-based; BED-style files are 0-based, half-open.

## `*.pbsv.vcf.gz` and `*.sniffles.vcf.gz`: structural variants

| Field | Meaning |
|---|---|
| FILTER | `PASS`, or why the caller did not trust the call |
| INFO/SVTYPE | DEL (deletion), INS (insertion), DUP (duplication), INV (inversion), BND (breakend) |
| INFO/SVLEN | Length of the event in bp (negative for deletions) |
| INFO/END | Last reference base affected |
| FORMAT/GT | Genotype: 0/1 one copy, 1/1 both copies |
| FORMAT/AD | Reads supporting reference and alternate allele (pbsv) |
| FORMAT/DR, FORMAT/DV | Reads supporting reference and variant (Sniffles) |

## `*.trgt.vcf.gz`: tandem-repeat genotypes

| Field | Meaning |
|---|---|
| INFO/TRID | Locus identifier from the repeat catalogue |
| INFO/MOTIFS | Repeat unit(s) at the locus |
| INFO/STRUC | Repeat structure from the catalogue |
| FORMAT/AL | Length of each allele in bp |
| FORMAT/MC | Number of motif copies per allele (per motif, separated by `_`) |
| FORMAT/SD | Number of reads fully spanning the locus per allele |
| FORMAT/AP | Allele purity (share of the allele matching the expected motif) |
| FORMAT/AM | Mean methylation of the allele, where reads carry methylation tags |

## `*.cpg.combined.bed.gz`, `*.cpg.hap1.bed.gz`, `*.cpg.hap2.bed.gz`: CpG methylation

`combined` uses all reads; `hap1` and `hap2` use only the reads tagged with that haplotype (BAM tag
`HP`). Haplotype numbers are only consistent within a phase block.

| Column | Meaning |
|---|---|
| 1-3 | chrom, begin, end of the CpG (0-based) |
| 4 | Modification score: estimated percent of reads methylated at this CpG (0-100) |
| 5 | Which reads were used (`Total` = all, `hap1` or `hap2`) |
| 6 | Coverage: reads covering the CpG |
| 7, 8 | Estimated methylated and unmethylated read counts |
| 9 | Discretised modification score |

## `*.trgt.<locus>.svg`: repeat plots

One plot per highlighted locus, from `trgt plot`. Each row is one read spanning the repeat, grouped
by allele and labelled with the allele length; colours mark the repeat motifs (legend at the foot).

## `qc.json`

The numbers in QC_SUMMARY.md, machine-readable. `sv.<caller>.truvari` holds the truvari bench summary
(`TP-base`, `FN`, `FP`, `precision`, `recall`, `f1`); `sv.<caller>.truvari_refined` holds the same
fields after `truvari refine`, which are the ones reported in QC_SUMMARY.md.
"""


def copy_with_index(src: Path, out: Path, label: str, indexes: dict[str, Path]) -> list[Path]:
    dest = out / f"{label}.{src.name}"
    shutil.copyfile(src, dest)
    copied = [dest]
    tbi = indexes.get(src.name + ".tbi")
    if tbi is None:
        raise SystemExit(f"no .tbi supplied for {src.name}")
    shutil.copyfile(tbi, out / f"{dest.name}.tbi")
    copied.append(out / f"{dest.name}.tbi")
    with src.open("rb") as fh:  # bgzip files are gzip files starting with the BGZF extra field
        if fh.read(4) != b"\x1f\x8b\x08\x04":
            raise SystemExit(f"{src.name} is not bgzip-compressed")
    return copied


def describe(name: str) -> str:
    for key, text in [
        (".pbsv.vcf.gz.tbi", "tabix index"), (".sniffles.vcf.gz.tbi", "tabix index"),
        (".trgt.vcf.gz.tbi", "tabix index"), (".bed.gz.tbi", "tabix index"),
        (".pbsv.vcf.gz", "Structural variants called by pbsv"),
        (".sniffles.vcf.gz", "Structural variants called by Sniffles2"),
        (".trgt.vcf.gz", "Tandem-repeat genotypes from TRGT"),
        (".combined.bed.gz", "CpG methylation scores from pb-CpG-tools (all reads)"),
        (".hap1.bed.gz", "CpG methylation scores from pb-CpG-tools (haplotype 1 reads)"),
        (".hap2.bed.gz", "CpG methylation scores from pb-CpG-tools (haplotype 2 reads)"),
        (".svg", "TRGT read-level plot of one repeat locus (reads spanning it, coloured by motif)"),
        ("QC_SUMMARY.md", "One-page plain-language QC summary"),
        ("DATA_DICTIONARY.md", "Definitions of every column and field"),
        ("VERSIONS.md", "Tool versions, container images and commands"),
        ("qc.json", "QC numbers, machine-readable"),
    ]:  # fmt: skip
        if name.endswith(key):
            return text
    return ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--label", required=True)
    p.add_argument("--region", required=True)
    p.add_argument("--read-count", type=int, required=True)
    p.add_argument("--sv-vcf", type=Path, action="append", required=True, help="<caller>.vcf.gz (repeatable)")
    p.add_argument("--truvari", type=Path, action="append", required=True, help="<caller>.truvari.json")
    p.add_argument(
        "--truvari-refine",
        type=Path,
        action="append",
        default=[],
        help="<caller>.truvari.refine.json (after truvari refine)",
    )
    p.add_argument("--trgt-vcf", type=Path, required=True)
    p.add_argument("--cpg-bed", type=Path, required=True)
    p.add_argument("--cpg-haplotype-bed", type=Path, action="append", default=[], help="cpg.hap<N>.bed.gz")
    p.add_argument("--cpg-islands", type=Path)
    p.add_argument("--index", type=Path, action="append", default=[], help=".tbi for each data file")
    p.add_argument("--resources", type=Path, action="append", default=[])
    p.add_argument("--highlight", action="append", help="TRGT locus IDs (default: SCA36_NOP56, CJD_PRNP)")
    p.add_argument("--plot", type=Path, action="append", default=[], help="<locus>.svg from trgt plot")
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    highlight = args.highlight or ["SCA36_NOP56", "CJD_PRNP"]

    args.out.mkdir(parents=True, exist_ok=True)
    indexes = {i.name: i for i in args.index}
    truvari = {t.name.split(".")[0]: t for t in args.truvari}
    refined = {t.name.split(".")[0]: t for t in args.truvari_refine}
    qc: dict[str, Any] = {"label": args.label, "region": args.region, "read_count": args.read_count, "sv": {}}
    files: list[Path] = []
    for vcf in args.sv_vcf:
        caller = vcf.name.split(".")[0]
        qc["sv"][caller] = {**sv_qc(vcf), "truvari": truvari_qc(truvari[caller])}
        if caller in refined:
            qc["sv"][caller]["truvari_refined"] = truvari_qc(refined[caller])
        files += copy_with_index(vcf, args.out, args.label, indexes)
    qc["sv_types"] = sorted({t for d in qc["sv"].values() for t in d["by_type"]})
    qc["sv_sizes"] = ["< 50 bp", *(n for _, _, n in SIZE_BINS)]
    qc["trgt"] = trgt_qc(args.trgt_vcf)
    qc["highlight"] = [locus for locus in qc["trgt"]["per_locus"] if locus["id"] in highlight]
    files += copy_with_index(args.trgt_vcf, args.out, args.label, indexes)
    qc["plots"] = []
    for plot in args.plot:
        dest = args.out / f"{args.label}.trgt.{plot.name}"
        shutil.copyfile(plot, dest)
        qc["plots"].append(dest.name)
        files.append(dest)
    span = args.region.split(":", 1)[1].replace(",", "").split("-")
    qc["cpg"] = cpg_qc(args.cpg_bed, read_islands(args.cpg_islands), int(span[0]) - 1, int(span[1]))
    files += copy_with_index(args.cpg_bed, args.out, args.label, indexes)
    if args.cpg_haplotype_bed:
        qc["cpg_haplotypes"] = haplotype_qc(args.cpg_haplotype_bed, int(span[0]) - 1, int(span[1]))
        for bed in args.cpg_haplotype_bed:
            files += copy_with_index(bed, args.out, args.label, indexes)

    resources = [json.loads(r.read_text(encoding="utf-8")) for r in args.resources]
    qc["resources"] = resources
    versions = ["# Versions and commands", "", "| Step | Container image | Command |", "|---|---|---|"]
    for r in resources:
        # Truvari runs once per SV caller; the label tells the rows apart.
        step = f"{r['task']} ({r['label']})" if r["task"] == "Truvari" and r.get("label") else r["task"]
        versions.append(f"| {step} | `{r['image']}` | `{COMMANDS.get(r['task'], '')}` |")

    for name, text in [
        ("QC_SUMMARY.md", qc_summary(qc)),
        ("DATA_DICTIONARY.md", DATA_DICTIONARY),
        ("VERSIONS.md", "\n".join(versions) + "\n"),
        ("qc.json", json.dumps(qc, indent=2) + "\n"),
    ]:
        (args.out / name).write_text(text, encoding="utf-8")
        files.append(args.out / name)

    with (args.out / "MANIFEST.tsv").open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("file\tbytes\tmd5\tdescription\n")
        for f in sorted(files):
            fh.write(f"{f.name}\t{f.stat().st_size}\t{md5sum(f)}\t{describe(f.name)}\n")
    print(f"handoff written to {args.out} ({len(files)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
