# Working notes for AI assistants (and humans)

Release validation for a germline short-read WGS workflow: WDL 1.0 run with miniwdl, benchmarked
against GIAB HG002 with hap.py, gated against committed baselines.

## Layout

- `wdl/main.wdl` + `wdl/tasks/*.wdl`: the workflow. `wdl/optional/`: long-read and deliverables modules.
- `scripts/`: standard-library Python (plus PyYAML/matplotlib where noted). `fetch_data.py` prepares
  data, `summarize_happy.py` makes `metrics.json`, `compare_metrics.py` is the regression gate.
- `config/`: data manifest (URLs + MD5), profiles (regions), thresholds, prices, miniwdl config.
- `baselines/`: gated reference metrics. Change only per `docs/runbooks/updating-baselines.md`.
- `docs/results/<label>/`: small generated outputs that are committed; large outputs go to `results/`.

## Commands

    make test lint                 # pytest, ruff, mypy --strict, miniwdl check, womtool validate
    make run PROFILE=fixture       # offline run on committed test data (minutes)
    make ci                        # ci profile + regression gate
    make run PROFILE=full          # 5 Mb, GATK and DeepVariant

## Rules

- Pin every container as `tag@sha256:digest`. Record any new image in the README tools table.
- Every task writes `resources.json` with the shared snippet (wall, CPU, peak memory). Keep it.
- Never drop `@SQ` lines with `samtools reheader`: BAM records refer to contigs by index. Re-encode
  through SAM text instead (see `FetchReadsSlice`).
- Do not loosen `config/thresholds.yaml` to make a run pass; investigate and write it up.
- No credentials, account IDs or bucket names in the repo. Cloud configs with them are gitignored.
- Python: ruff (line length 120), mypy strict on `scripts/`, tests in `tests/` run offline.
- Every result number in the docs comes from a generated file (`metrics.json`, `metrics.md`,
  `gate.md`, `resources.tsv`, a script's output). Never type a number in by hand; quote or embed
  the generated file, and regenerate it when the inputs change.
- Changes written by an assistant are reviewed as a diff, and `make test lint` (plus the run they
  affect) passes before they are committed.
