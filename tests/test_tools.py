import csv
import gzip
import json
from pathlib import Path

import pytest
import yaml

import cloud_inputs as ci
import diff_decisions as dd
import estimate_cost as ec
import fetch_data as fd
import longread_handoff as lh
import pick_fn_examples as pf
import plot_metrics as pm
import site_evidence as se
import sv_merge_report as sm
import wes_run as wr

REPO = Path(__file__).resolve().parent.parent


# --------------------------------------------------------------------------- site_evidence


def sam(pos, cigar, seq, mapq=60, flag=0):
    return "\t".join(["r", str(flag), "chr20", str(pos), str(mapq), cigar, "=", "0", "0", seq, "*"]) + "\n"


def test_snp_alleles_and_mapq_bands():
    lines = [
        sam(100, "10M", "AAAAAGAAAA"),  # alt at 105
        sam(100, "10M", "AAAAAAAAAA"),  # ref
        sam(101, "10M", "AAAAGAAAAA", mapq=0),  # alt, unusable MAPQ
        sam(100, "10M", "AAAAATAAAA"),  # other base
        sam(100, "10M", "AAAAAGAAAA", flag=0x400),  # duplicate: skipped
        sam(200, "10M", "AAAAAAAAAA"),  # does not cover the site
    ]
    counts = se.tally(lines, 105, "A", "G")
    assert counts[("60", "alt")] == 1
    assert counts[("60", "ref")] == 1
    assert counts[("0", "alt")] == 1
    assert counts[("60", "other")] == 2  # the T read, and the read not covering the site
    report = se.render(counts, "chr20:105 A>G")
    assert "Alternate-allele reads with MAPQ >= 20: 1 of 2." in report


def test_deletion_and_insertion_support():
    # Deletion ACG>A at 105: anchor base at 105, then 2D.
    assert se.allele_at(100, "6M2D4M", "AAAAAAAAAA", 105, "ACG", "A") == "alt"
    assert se.allele_at(100, "10M", "AAAAAAAAAA", 105, "ACG", "A") == "ref"
    # Insertion A>ATT at 105.
    assert se.allele_at(100, "6M2I4M", "AAAAAATTAAAA", 105, "A", "ATT") == "alt"
    assert se.allele_at(100, "6M2I4M", "AAAAAAGGAAAA", 105, "A", "ATT") == "other"
    # Soft clip shifts the read position but not the reference position.
    assert se.allele_at(100, "3S10M", "TTTAAAAAGAAAA", 105, "A", "G") == "alt"


# --------------------------------------------------------------------------- pick_fn_examples


HAPPY_VCF = """##fileformat=VCFv4.2
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tTRUTH\tQUERY
chr20\t300\t.\tA\tG\t.\t.\tRegions=lowmap_or_segdup,all_difficult\tGT:BD:BVT\t0/1:FN:SNP\t.:.:NOCALL
chr20\t200\t.\tC\tT\t.\t.\tRegions=not_difficult\tGT:BD:BVT\t0/1:FN:SNP\t.:.:NOCALL
chr20\t250\t.\tCA\tC\t.\t.\tRegions=lowmap_or_segdup\tGT:BD:BVT\t.:.:NOCALL\t0/1:FP:INDEL
chr20\t260\t.\tG\tA\t.\t.\t.\tGT:BD:BVT\t0/1:TP:SNP\t0/1:TP:SNP
chr20\t270\t.\tG\tA\t.\t.\tRegions=lowmap_or_segdup\tGT:BD:BVT\t1/1:FN:SNP\t0/1:FP:SNP
"""


def test_pick_fn_examples(tmp_path):
    path = tmp_path / "happy.vcf.gz"
    with gzip.open(path, "wt") as fh:
        fh.write(HAPPY_VCF)
    fns = pf.select(pf.iter_sites(path), "FN", None, None)
    assert [s.pos for s in fns] == [200, 270, 300]  # sorted by position
    lowmap = pf.select(pf.iter_sites(path), "FN", "lowmap_or_segdup", "SNP")
    assert [s.pos for s in lowmap] == [270, 300]
    fps = pf.select(pf.iter_sites(path), "FP", "lowmap_or_segdup", None)
    # The genotype mismatch at 270 is both a missed variant and a false call, as hap.py counts it.
    assert [(s.pos, s.variant_type, s.query_gt) for s in fps] == [(250, "INDEL", "0/1"), (270, "SNP", "0/1")]


def test_diff_decisions_reports_changed_sites_only(tmp_path):
    old, new = tmp_path / "old.vcf.gz", tmp_path / "new.vcf.gz"
    with gzip.open(old, "wt") as fh:
        fh.write(HAPPY_VCF)
    # new: 300 is now found, the false call at 250 is gone, a new false call at 400; rest unchanged
    lines = HAPPY_VCF.splitlines(keepends=True)
    lines[2] = lines[2].replace("0/1:FN:SNP\t.:.:NOCALL", "0/1:TP:SNP\t0/1:TP:SNP")
    del lines[4]
    lines.append("chr20\t400\t.\tT\tC\t.\t.\t.\tGT:BD:BVT\t.:.:NOCALL\t0/1:FP:SNP\n")
    changed_vcf = "".join(lines)
    with gzip.open(new, "wt") as fh:
        fh.write(changed_vcf)
    rows = dd.changed(dd.load(old), dd.load(new))
    assert [(k[1], dd.label(a), dd.label(b)) for k, a, b in rows] == [
        (250, "FP", "absent"),
        (300, "FN", "TP"),
        (400, "absent", "FP"),
    ]
    text = dd.render(rows, 2, ["lowmap_or_segdup"])
    assert text.startswith("3 site(s) changed decision: 1 FN → TP, 1 FP → absent, 1 absent → FP.")
    assert "| chr20:300 A>G | SNP | FN | TP | 0/1 | . | 0/1 | lowmap_or_segdup |" in text
    assert "First 2 of 3 shown." in text
    assert dd.render([], 10, []) == "No site changed decision.\n"


# --------------------------------------------------------------------------- fetch_data subset


def test_clip_bed_lines_clips_plain_and_keeps_whole_annotated(tmp_path):
    src = tmp_path / "in.bed"
    src.write_text(
        "chr20\t50\t150\n"  # plain, crosses start: clipped
        "chr20\t120\t130\tID=A;MOTIFS=CAG;STRUC=<TR>\n"  # annotated, inside: kept
        "chr20\t190\t210\tID=B;MOTIFS=CAG;STRUC=<TR>\n"  # annotated, crosses end: dropped
        "chr21\t100\t200\n"
    )
    out = tmp_path / "out.bed"
    n = fd.clip_bed_lines(src, fd.Region.parse("chr20:101-200"), out)
    assert n == 2
    assert out.read_text().splitlines() == ["chr20\t100\t150", "chr20\t120\t130\tID=A;MOTIFS=CAG;STRUC=<TR>"]


# --------------------------------------------------------------------------- plot_metrics


def metrics_file(path: Path, callers: dict[str, float]) -> Path:
    def row(f1: float, n: int) -> dict[str, object]:
        return {
            "truth_total": n,
            "recall": f1,
            "precision": f1,
            "f1": f1,
            "recall_ci95": [f1 - 0.01, min(1.0, f1 + 0.01)],
            "precision_ci95": [f1 - 0.01, min(1.0, f1 + 0.01)],
        }

    data = {
        "callers": {
            name: {
                kind: {"*": row(f1, 500), "all_difficult": row(f1 - 0.05, 80), "coding": row(1.0, 3)}
                for kind in ("SNP", "INDEL")
            }
            for name, f1 in callers.items()
        }
    }
    path.write_text(json.dumps(data))
    return path


def test_plot_metrics_writes_figures_and_tables(tmp_path):
    m = metrics_file(tmp_path / "metrics.json", {"gatk": 0.99, "deepvariant": 0.995})
    assert pm.main(["--metrics", f"full={m}", "--out", str(tmp_path / "fig")]) == 0
    assert (tmp_path / "fig" / "f1_by_stratum.png").stat().st_size > 10_000
    table = (tmp_path / "fig" / "recall_precision_by_stratum.md").read_text(encoding="utf-8")
    assert "All difficult regions" in table and "deepvariant" in table
    assert "Coding sequence" not in table  # 3 truth variants: below the plotting minimum


def test_plot_metrics_names_series_by_label_when_comparing(tmp_path):
    old = metrics_file(tmp_path / "old.json", {"gatk": 0.99})
    new = metrics_file(tmp_path / "new.json", {"gatk": 0.991})
    series = pm.load_series([f"4.6={old}", f"4.7={new}"])
    assert [name for name, _ in series] == ["4.6: gatk", "4.7: gatk"]


# --------------------------------------------------------------------------- estimate_cost


def write_run(results: Path, label: str, region: str, depth: float, rows: list[dict[str, object]]) -> None:
    d = results / label
    d.mkdir(parents=True)
    (d / "metrics.json").write_text(
        json.dumps({"region": region, "coverage": {"mean_depth": depth}, "callers": {"gatk": {}}})
    )
    with (d / "resources.tsv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter="\t")
        w.writeheader()
        w.writerows(rows)


def resource(task: str, wall: float, label: str = "", cpu: int = 4, mem: float = 6) -> dict[str, object]:
    return {
        "task": task,
        "label": label,
        "wall_seconds": wall,
        "cpu_seconds": wall * cpu * 0.8,
        "peak_memory_bytes": 1e9,
        "requested_cpu": cpu,
        "requested_memory_gb": mem,
        "image": "x",
    }


def test_estimate_cost_scales_and_prices(tmp_path):
    prices = yaml.safe_load((REPO / "config" / "prices.yaml").read_text(encoding="utf-8"))
    results = tmp_path / "results"
    tasks = [
        resource("FetchReadsSlice", 30),  # validation only: excluded
        resource("HaplotypeCaller", 100),
        resource("Mosdepth", 2, cpu=1, mem=2),
        resource("NormalizeVcf", 1, label="gatk", cpu=1, mem=2),
        resource("HappyBenchmark", 50, label="gatk"),  # validation only: excluded
    ]
    write_run(results, "full", "chr20:1-5000000", 30.0, tasks)
    write_run(results, "ignored-upgrade-run", "chr20:1-5000000", 30.0, tasks)
    report = ec.build(results, prices, ["ci", "full"])
    gatk = report["callers"]["gatk"]
    assert gatk["profiles"] == ["full"]
    assert [t["task"] for t in gatk["tasks"]] == ["HaplotypeCaller", "Mosdepth", "NormalizeVcf"]
    factor = ec.GENOME_BP / 5_000_000
    assert gatk["wall_hours"] == pytest.approx((100 + 2 + 1) * factor / 3600)
    for r in gatk["rows"]:
        assert r["low"] <= r["mid"] <= r["high"]
    spot = [r for r in gatk["rows"] if r["pricing"] == "spot" and r["option"] == "AWS EC2"]
    on_demand = [r for r in gatk["rows"] if r["pricing"] == "on-demand" and r["option"] == "AWS EC2"]
    assert all(s["mid"] < o["mid"] for s, o in zip(spot, on_demand, strict=True))
    text = ec.render(report)
    assert "## gatk" in text and "Reading the numbers" in text and "## Method" in text


def test_cheapest_machine_respects_memory():
    machines = [
        ec.Machine("aws_ec2", "r", "small", 4, 8, 0.10, 0.04),
        ec.Machine("aws_ec2", "r", "big", 4, 32, 0.20, 0.03),
    ]
    assert ec.cheapest(machines, "aws_ec2", "r", 4, 6, spot=False).name == "small"
    assert ec.cheapest(machines, "aws_ec2", "r", 4, 6, spot=True).name == "big"
    with pytest.raises(ValueError):
        ec.cheapest(machines, "aws_ec2", "r", 8, 6, spot=False)


# --------------------------------------------------------------------------- cloud_inputs


def _cloud_fixture(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "truth.vcf").write_text("x")
    (tmp_path / "data" / "a.bed").write_text("x")
    return {
        "ReleaseValidation.region": "chr20:1-100",
        "ReleaseValidation.truth_vcf": "data/truth.vcf",
        "ReleaseValidation.strat_beds": ["data/a.bed"],
        "ReleaseValidation.reads_url": "https://example.org/reads.bam",
        "ReleaseValidation.run_preflight": True,
    }


def test_cloud_inputs_healthomics_strips_prefix_and_maps_files(tmp_path):
    inputs = _cloud_fixture(tmp_path)
    sets = {"reads_bam": "data/truth.vcf"}
    out, uploads = ci.rewrite(inputs, "healthomics", "s3://b/wrv/", sets, ["reads_url"], tmp_path)
    assert out["truth_vcf"] == "s3://b/wrv/data/truth.vcf"
    assert out["strat_beds"] == ["s3://b/wrv/data/a.bed"]
    assert out["region"] == "chr20:1-100" and out["run_preflight"] is True
    assert "reads_url" not in out and not any(k.startswith("ReleaseValidation.") for k in out)
    assert [remote for _, remote in uploads] == ["s3://b/wrv/data/a.bed", "s3://b/wrv/data/truth.vcf"]


def test_cloud_inputs_healthomics_refuses_urls(tmp_path):
    with pytest.raises(SystemExit, match="cannot reach the internet"):
        ci.rewrite(_cloud_fixture(tmp_path), "healthomics", "s3://b/wrv", {}, [], tmp_path)


def test_cloud_inputs_cromwell_keeps_prefix_and_urls(tmp_path):
    out, uploads = ci.rewrite(_cloud_fixture(tmp_path), "cromwell", "gs://b/wrv", {}, [], tmp_path)
    assert out["ReleaseValidation.reads_url"] == "https://example.org/reads.bam"
    assert out["ReleaseValidation.truth_vcf"] == "gs://b/wrv/data/truth.vcf"
    assert len(uploads) == 2


def test_cloud_inputs_set_keeps_json_types_and_accepts_prefixed_names():
    sets = ci.parse_assignments(["ReleaseValidation.deepvariant_shards=4", "run_preflight=false", "region=chr20:1-2"])
    assert sets == {"deepvariant_shards": 4, "run_preflight": False, "region": "chr20:1-2"}


def test_cloud_inputs_refuses_unknown_drop_and_colliding_files(tmp_path):
    inputs = _cloud_fixture(tmp_path)
    with pytest.raises(SystemExit, match="no such input"):
        ci.rewrite(inputs, "cromwell", "gs://b/wrv", {}, ["reads_ulr"], tmp_path)
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "a.bed").write_text("y")
    sets = {"strat_beds": [str(tmp_path / "data" / "a.bed"), str(tmp_path / "other" / "a.bed")]}
    with pytest.raises(SystemExit, match=r"would both upload to gs://b/wrv/a\.bed"):
        ci.rewrite(inputs, "cromwell", "gs://b/wrv", sets, ["ReleaseValidation.reads_url"], tmp_path)


def test_cloud_inputs_refuses_missing_files_and_parent_paths(tmp_path):
    inputs = _cloud_fixture(tmp_path)
    with pytest.raises(SystemExit, match="does not exist; fetch it first"):
        ci.rewrite(inputs, "cromwell", "gs://b/wrv", {"truth_bed": "data/missing.bed"}, [], tmp_path)
    with pytest.raises(SystemExit, match="leaves the base directory"):
        ci.rewrite(inputs, "cromwell", "gs://b/wrv", {"truth_vcf": "../evil.vcf"}, [], tmp_path)


def test_cloud_inputs_wes_keeps_prefix_and_takes_http_prefix(tmp_path):
    out, uploads = ci.rewrite(_cloud_fixture(tmp_path), "wes", "http://172.17.0.1:8081", {}, [], tmp_path)
    assert out["ReleaseValidation.truth_vcf"] == "http://172.17.0.1:8081/data/truth.vcf"
    assert out["ReleaseValidation.reads_url"] == "https://example.org/reads.bam"
    assert len(uploads) == 2


# --------------------------------------------------------------------------- wes_run


def test_wes_multipart_body_has_every_field():
    body, ctype = wr.multipart({"workflow_type": "WDL", "workflow_params": '{"a": 1}'})
    boundary = ctype.split("boundary=")[1]
    text = body.decode("utf-8")
    assert text.count(f"--{boundary}\r\n") == 2 and text.endswith(f"--{boundary}--\r\n")
    assert 'name="workflow_params"\r\n\r\n{"a": 1}\r\n' in text


def test_wes_summary_holds_no_server_paths():
    run_log = {
        "run_id": "r1",
        "state": "COMPLETE",
        "run_log": {"start_time": "t0", "end_time": "t1", "stdout": "/srv/cromwell/stdout"},
        "task_logs": [{"name": "A", "exit_code": 0, "stderr": "/srv/cromwell/call-A/stderr"}],
        "outputs": {"ReleaseValidation.metrics_json": "/srv/cromwell/call-S/metrics.json"},
        "request": {"workflow_params": {"x": "/home/someone/data.vcf"}},
    }
    summary = wr.summarise(run_log, {"supported_wes_versions": ["1.0"], "workflow_engine_versions": {"Cromwell": "91"}})
    assert "/" not in json.dumps(summary).replace('"1.0"', "")
    assert summary["outputs"] == ["ReleaseValidation.metrics_json"] and summary["task_exit_codes"] == [0]


def test_wes_save_outputs_removes_stale_copies(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "metrics.json").write_text("old run")
    new = tmp_path / "metrics.md"
    new.write_text("new")
    outputs = {"ReleaseValidation.metrics_json": "/not/readable/here.json", "ReleaseValidation.metrics_md": str(new)}
    assert wr.save_outputs({"outputs": outputs}, out) == ["metrics.md"]
    assert not (out / "metrics.json").exists() and (out / "metrics.md").read_text() == "new"


# --------------------------------------------------------------------------- longread_handoff


def _cpg_bed(path, rows):
    with gzip.open(path, "wt") as fh:
        fh.write("##pb-cpg-tools-version=3.0.0\n")
        for pos, score, cov in rows:
            fh.write(f"chr20\t{pos}\t{pos + 1}\t{score}\thap\t{cov}\t0\t0\t0.0\n")
    return path


def test_longread_haplotype_qc_counts_sites_that_differ(tmp_path):
    # 300 is under 10x on hap1, 5000 is outside the region: neither is compared.
    hap1 = _cpg_bed(tmp_path / "cpg.hap1.bed.gz", [(100, 10.0, 12), (200, 90.0, 12), (300, 50.0, 5), (5000, 0.0, 30)])
    hap2 = _cpg_bed(tmp_path / "cpg.hap2.bed.gz", [(100, 80.0, 12), (200, 85.0, 12), (300, 50.0, 20)])
    out = lh.haplotype_qc([hap2, hap1], 0, 1000)
    assert list(out["haplotypes"]) == ["hap1", "hap2"]
    assert out["haplotypes"]["hap1"]["cpg_sites"] == 3
    assert out["haplotypes"]["hap1"]["mean_methylation_pct"] == 50.0
    assert (out["sites_ge_10x_both"], out["sites_differ_ge_50"]) == (2, 1)


def test_longread_summary_notes_unscored_small_calls(tmp_path):
    vcf = tmp_path / "pbsv.vcf"
    vcf.write_text(
        "##fileformat=VCFv4.2\n"
        "chr20\t100\t.\tN\t<DEL>\t.\tPASS\tSVTYPE=DEL;SVLEN=-30;END=130\n"
        "chr20\t500\t.\tN\t<INS>\t.\tPASS\tSVTYPE=INS;SVLEN=200\n"
    )
    sv = lh.sv_qc(vcf)
    assert sv["by_size"]["< 50 bp"] == 1 and sv["by_size"]["100-499 bp"] == 1
    score = {"TP-base": 1, "FN": 0, "FP": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0}
    cpg = lh.cpg_qc(_cpg_bed(tmp_path / "cpg.combined.bed.gz", [(100, 10.0, 12)]), [])
    qc = {
        "label": "t", "region": "chr20:1-1000", "read_count": 1,
        "sv": {"pbsv": {**sv, "truvari": score}}, "sv_types": ["DEL", "INS"], "sv_sizes": list(sv["by_size"]),
        "trgt": {"genotyped": 0, "loci": 0, "no_call_rate": 0.0, "median_spanning_reads": 0,
                 "allele_length_bp": {"min": 0, "median": 0, "max": 0}},
        "highlight": [], "cpg": cpg,
    }  # fmt: skip
    text = lh.qc_summary(qc)
    assert "Calls under 50 bp (1 from pbsv) are in the files and in the table above" in text
    assert "per haplotype" not in text


# --------------------------------------------------------------------------- sv_merge_report


def test_sv_merge_report_reads_run_outputs(tmp_path):
    def score(tp, fp):
        return {"TP-base": tp, "FN": 10 - tp, "FP": fp, "precision": tp / (tp + fp), "recall": tp / 10, "f1": 0.5}

    outputs = {"summaries": [], "refine_summaries": [], "resources": []}
    counts = ["label\trecords\trecords_ge50"]
    for i, label in enumerate(sm.ORDER):
        for key, suffix, tp in (("summaries", "truvari.json", 7), ("refine_summaries", "truvari.refine.json", 8)):
            p = tmp_path / f"{label}.{suffix}"
            p.write_text(json.dumps(score(tp, i)))
            outputs[key].append(str(p))
        r = tmp_path / f"{label}.resources.json"
        r.write_text(json.dumps({"task": "Truvari", "label": label, "wall_seconds": 1.5}))
        outputs["resources"].append(str(r))
        counts.append(f"{label}\t{20 + i}\t{10 + i}")
    (tmp_path / "counts.tsv").write_text("\n".join(counts) + "\n")
    named = {f"SvMerge.{k}": v for k, v in outputs.items()} | {"SvMerge.counts": str(tmp_path / "counts.tsv")}
    (tmp_path / "outputs.json").write_text(json.dumps(named))

    (tmp_path / "inputs.json").write_text(json.dumps({"SvMerge.region": "chr20:1-50"}))
    result = sm.collect(tmp_path)
    assert result["region"] == "chr20:1-50" and result["sample"] == "HG002"
    assert list(result["strategies"]) == sm.ORDER
    assert result["strategies"]["union"]["refine"]["fp"] == 2
    assert result["strategies"]["union"]["records_ge50"] == 12
    text = sm.render(result)
    assert "| intersect | 8 | 2 | 5 | 0.615 | 0.800 | 0.500 |" in text
    assert "HG002 PacBio HiFi over" in text and "`chr20:1-50`" in text


def test_sv_merge_report_refuses_missing_strategy(tmp_path):
    (tmp_path / "counts.tsv").write_text("label\trecords\trecords_ge50\n")
    outputs = {"summaries": [], "refine_summaries": [], "resources": [], "counts": str(tmp_path / "counts.tsv")}
    (tmp_path / "outputs.json").write_text(json.dumps(outputs))
    with pytest.raises(SystemExit, match="no results for pbsv"):
        sm.collect(tmp_path)


def test_sv_merge_report_refuses_missing_counts_row(tmp_path):
    test_sv_merge_report_reads_run_outputs(tmp_path)
    rows = (tmp_path / "counts.tsv").read_text().splitlines()
    (tmp_path / "counts.tsv").write_text("\n".join(r for r in rows if not r.startswith("union")) + "\n")
    with pytest.raises(SystemExit, match="no results for union"):
        sm.collect(tmp_path)
