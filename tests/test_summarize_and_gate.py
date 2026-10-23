import copy
import csv
import json
from pathlib import Path

import pytest
import yaml

import compare_metrics as cm
import summarize_happy as sh

REPO = Path(__file__).resolve().parent.parent
COLUMNS = [
    "Type",
    "Subtype",
    "Subset",
    "Filter",
    "Genotype",
    "TRUTH.TOTAL",
    "TRUTH.TP",
    "TRUTH.FN",
    "QUERY.TOTAL",
    "QUERY.TP",
    "QUERY.FP",
    "QUERY.UNK",
    "FP.gt",
]


def happy_row(kind, subset, tp, fn, fp, filt="PASS", subtype="*", genotype="*"):
    return {
        "Type": kind,
        "Subtype": subtype,
        "Subset": subset,
        "Filter": filt,
        "Genotype": genotype,
        "TRUTH.TOTAL": tp + fn,
        "TRUTH.TP": tp,
        "TRUTH.FN": fn,
        "QUERY.TOTAL": tp + fp + 3,
        "QUERY.TP": tp,
        "QUERY.FP": fp,
        "QUERY.UNK": 3,
        "FP.gt": 0,
    }


def write_extended(path: Path, rows):
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


@pytest.fixture
def extended(tmp_path):
    return write_extended(
        tmp_path / "gatk.extended.csv",
        [
            happy_row("SNP", "*", 990, 10, 5),
            happy_row("SNP", "*", 500, 500, 500, filt="ALL"),  # ignored: not PASS
            happy_row("SNP", "*", 1, 1, 1, subtype="ti"),  # ignored: subtype
            happy_row("SNP", "all_difficult", 180, 20, 4),
            happy_row("SNP", "coding", 20, 0, 0),
            happy_row("INDEL", "*", 95, 5, 2),
            happy_row("INDEL", "all_difficult", 18, 2, 1),
        ],
    )


def test_wilson_interval():
    lo, hi = sh.wilson(990, 1000)
    assert lo < 0.99 < hi
    assert lo > 0.98 and hi < 0.995
    assert sh.wilson(0, 0) is None
    assert sh.wilson(10, 10)[1] == pytest.approx(1.0)


def test_read_extended_selects_pass_rows(extended):
    data = sh.read_extended(extended)
    snp = data["SNP"]["*"]
    assert snp["truth_tp"] == 990 and snp["truth_fn"] == 10 and snp["query_fp"] == 5
    assert snp["recall"] == pytest.approx(0.99)
    assert snp["precision"] == pytest.approx(990 / 995)
    assert snp["f1"] == pytest.approx(2 * 0.99 * (990 / 995) / (0.99 + 990 / 995))
    assert set(data["INDEL"]) == {"*", "all_difficult"}


def test_read_extended_rejects_other_csv(tmp_path):
    bad = write_extended(tmp_path / "bad.csv", [happy_row("SNP", "coding", 1, 1, 1)])
    with pytest.raises(ValueError, match="no PASS row"):
        sh.read_extended(bad)


def test_main_fails_when_no_truth_variants(tmp_path, capsys):
    # What a BED named "20" against a "chr20" truth set produces: hap.py succeeds with zero truth.
    rows = [happy_row(kind, "*", 0, 0, 0) for kind in ("SNP", "INDEL")]
    empty = write_extended(tmp_path / "gatk.extended.csv", rows)
    out_json, out_md = tmp_path / "metrics.json", tmp_path / "metrics.md"
    args = ["--extended", f"gatk={empty}", "--run-label", "t", "--region", "chr20:1-10"]
    assert sh.main([*args, "--out-json", str(out_json), "--out-md", str(out_md)]) == 1
    assert out_json.exists()  # still written, for inspection
    assert "same chromosome names" in capsys.readouterr().err


def test_main_writes_json_and_markdown(extended, tmp_path):
    mosdepth = tmp_path / "m.txt"
    mosdepth.write_text(
        "chrom\tlength\tbases\tmean\tmin\tmax\nchr20_region\t10\t300\t30.0\t0\t60\ntotal_region\t10\t300\t30.0\t0\t60\n"
    )
    out_json, out_md = tmp_path / "metrics.json", tmp_path / "metrics.md"
    assert (
        sh.main(
            [
                "--extended",
                f"gatk={extended}",
                "--tool-version",
                "gatk=broadinstitute/gatk:4.7.0.0",
                "--run-label",
                "t",
                "--region",
                "chr20:1-10",
                "--mosdepth",
                str(mosdepth),
                "--out-json",
                str(out_json),
                "--out-md",
                str(out_md),
            ]
        )
        == 0
    )
    data = json.loads(out_json.read_text())
    assert data["schema_version"] == 1
    assert data["tool_versions"] == {"gatk": "broadinstitute/gatk:4.7.0.0"}
    assert data["coverage"]["mean_depth"] == 30.0
    md = out_md.read_text()
    assert "| gatk | SNP | all benchmark regions | 1,000 | 10 | 5 |" in md
    assert "all_difficult" in md


@pytest.fixture
def thresholds():
    return yaml.safe_load((REPO / "config" / "thresholds.yaml").read_text())


@pytest.fixture
def baseline(extended):
    return {
        "schema_version": 1,
        "region": "chr20:1-10",
        "tool_versions": {"gatk": "a"},
        "callers": {"gatk": sh.read_extended(extended)},
    }


def statuses(rows):
    return {(r.kind, r.stratum): r.status for r in rows}


def test_identical_metrics_pass(baseline, thresholds):
    rows = cm.compare(baseline, copy.deepcopy(baseline), thresholds)
    assert all(r.status in ("PASS", "INFO") for r in rows)
    # strata below min_truth_variants are reported, not gated
    assert statuses(rows)[("SNP", "coding")] == "INFO"
    assert statuses(rows)[("INDEL", "all_difficult")] == "INFO"


def test_overall_drop_beyond_limit_fails(baseline, thresholds):
    cand = copy.deepcopy(baseline)
    cand["tool_versions"] = {"gatk": "b"}
    snp = cand["callers"]["gatk"]["SNP"]["*"]
    snp["f1"] -= 0.003  # limit for SNP overall is 0.002
    rows = cm.compare(baseline, cand, thresholds)
    assert statuses(rows)[("SNP", "*")] == "FAIL"


def test_small_drop_within_limit_passes(baseline, thresholds):
    cand = copy.deepcopy(baseline)
    cand["tool_versions"] = {"gatk": "b"}
    cand["callers"]["gatk"]["SNP"]["*"]["f1"] -= 0.001
    cand["callers"]["gatk"]["SNP"]["all_difficult"]["f1"] -= 0.009
    assert statuses(cm.compare(baseline, cand, thresholds))[("SNP", "*")] == "PASS"
    assert statuses(cm.compare(baseline, cand, thresholds))[("SNP", "all_difficult")] == "PASS"


def test_improvement_never_fails(baseline, thresholds):
    cand = copy.deepcopy(baseline)
    cand["tool_versions"] = {"gatk": "b"}
    cand["callers"]["gatk"]["SNP"]["*"]["f1"] += 0.05
    assert statuses(cm.compare(baseline, cand, thresholds))[("SNP", "*")] == "PASS"


def test_same_tools_with_changed_counts_fails_as_nondeterminism(baseline, thresholds):
    cand = copy.deepcopy(baseline)
    cand["callers"]["gatk"]["SNP"]["*"]["truth_tp"] -= 1
    rows = cm.compare(baseline, cand, thresholds)
    row = next(r for r in rows if (r.kind, r.stratum) == ("SNP", "*"))
    assert row.status == "FAIL" and "identical tool images" in row.note


def test_missing_caller_or_stratum_fails(baseline, thresholds):
    cand = copy.deepcopy(baseline)
    del cand["callers"]["gatk"]["INDEL"]["*"]
    assert statuses(cm.compare(baseline, cand, thresholds))[("INDEL", "*")] == "FAIL"
    cand["callers"] = {}
    assert any(r.note == "caller missing from candidate" for r in cm.compare(baseline, cand, thresholds))


def test_region_mismatch_is_an_error(baseline, thresholds):
    cand = copy.deepcopy(baseline)
    cand["region"] = "chr20:1-11"
    with pytest.raises(ValueError, match="regions differ"):
        cm.compare(baseline, cand, thresholds)


def test_cli_exit_codes(baseline, tmp_path):
    base_path, cand_path = tmp_path / "b.json", tmp_path / "c.json"
    base_path.write_text(json.dumps(baseline))
    cand = copy.deepcopy(baseline)
    cand["tool_versions"] = {"gatk": "b"}
    cand["callers"]["gatk"]["INDEL"]["*"]["f1"] -= 0.02
    cand_path.write_text(json.dumps(cand))
    summary = tmp_path / "summary.md"
    assert cm.main([str(base_path), str(base_path)]) == 0
    assert cm.main([str(base_path), str(cand_path), "--summary-file", str(summary)]) == 1
    assert "FAIL" in summary.read_text()
    (tmp_path / "junk.json").write_text("{}")
    assert cm.main([str(base_path), str(tmp_path / "junk.json")]) == 2
